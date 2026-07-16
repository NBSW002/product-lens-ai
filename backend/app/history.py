import json
import os
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from app.crypto import ProductCipher, decode_base64_secret, hash_lookup
from app.models import Job


class Cursor(Protocol):
    lastrowid: int

    def execute(self, query: str, args: tuple[Any, ...] | None = None) -> int: ...
    def executemany(self, query: str, args: list[tuple[Any, ...]]) -> int: ...
    def close(self) -> None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


ConnectFactory = Callable[[], Connection]


class MySqlHistoryStore:
    def __init__(self, connect: ConnectFactory, cipher: ProductCipher, hash_secret: bytes) -> None:
        self._connect = connect
        self._cipher = cipher
        self._hash_secret = hash_secret

    def save_job(self, job: Job) -> None:
        connection = self._connect()
        cursor = connection.cursor()
        try:
            self._upsert_job(cursor, job)
            if job.result is not None:
                self._upsert_product_facts(cursor, job)
                self._upsert_analysis(cursor, job)
                quality_report_id = self._upsert_quality_report(cursor, job)
                self._replace_quality_issues(cursor, quality_report_id, job)
            self._upsert_trace_events(cursor, job)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def _upsert_job(self, cursor: Cursor, job: Job) -> None:
        encrypted_url = self._cipher.encrypt_json({"url": job.url})
        cursor.execute(
            """
            INSERT INTO analysis_jobs (
              id, request_url_hash, request_url_encryption_alg, request_url_key_id,
              request_url_nonce, request_url_auth_tag, request_url_ciphertext,
              status, stage, progress, error_message, created_at, updated_at, finished_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
              request_url_hash = VALUES(request_url_hash),
              request_url_encryption_alg = VALUES(request_url_encryption_alg),
              request_url_key_id = VALUES(request_url_key_id),
              request_url_nonce = VALUES(request_url_nonce),
              request_url_auth_tag = VALUES(request_url_auth_tag),
              request_url_ciphertext = VALUES(request_url_ciphertext),
              status = VALUES(status),
              stage = VALUES(stage),
              progress = VALUES(progress),
              error_message = VALUES(error_message),
              updated_at = VALUES(updated_at),
              finished_at = VALUES(finished_at)
            """,
            (
                job.id,
                hash_lookup(job.url, self._hash_secret),
                encrypted_url.algorithm,
                encrypted_url.key_id,
                encrypted_url.nonce,
                encrypted_url.auth_tag,
                encrypted_url.ciphertext,
                job.status,
                job.stage,
                job.progress,
                job.error,
                _mysql_datetime(job.created_at),
                _mysql_datetime(job.updated_at),
                _finished_at(job),
            ),
        )

    def _upsert_product_facts(self, cursor: Cursor, job: Job) -> None:
        if job.result is None:
            return
        facts = job.result.facts.model_dump(mode="json")
        encrypted = self._cipher.encrypt_json(facts)
        cursor.execute(
            """
            INSERT INTO encrypted_product_facts (
              job_id, asin_hash, source_url_hash, encryption_alg, key_id,
              nonce, auth_tag, ciphertext
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
              asin_hash = VALUES(asin_hash),
              source_url_hash = VALUES(source_url_hash),
              encryption_alg = VALUES(encryption_alg),
              key_id = VALUES(key_id),
              nonce = VALUES(nonce),
              auth_tag = VALUES(auth_tag),
              ciphertext = VALUES(ciphertext)
            """,
            (
                job.id,
                hash_lookup(job.result.facts.asin, self._hash_secret),
                hash_lookup(job.result.facts.source_url, self._hash_secret),
                encrypted.algorithm,
                encrypted.key_id,
                encrypted.nonce,
                encrypted.auth_tag,
                encrypted.ciphertext,
            ),
        )

    def _upsert_analysis(self, cursor: Cursor, job: Job) -> None:
        if job.result is None:
            return
        analysis = job.result.analysis
        cursor.execute(
            """
            INSERT INTO product_analysis_results (
              job_id, target_users, scenarios, pain_points, selling_points,
              visual_findings, voiceover
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
              target_users = VALUES(target_users),
              scenarios = VALUES(scenarios),
              pain_points = VALUES(pain_points),
              selling_points = VALUES(selling_points),
              visual_findings = VALUES(visual_findings),
              voiceover = VALUES(voiceover)
            """,
            (
                job.id,
                _json(analysis.target_users),
                _json(analysis.scenarios),
                _json(analysis.pain_points),
                _json(analysis.selling_points),
                _json(analysis.visual_findings),
                analysis.voiceover,
            ),
        )

    def _upsert_quality_report(self, cursor: Cursor, job: Job) -> int:
        if job.result is None:
            raise ValueError("Cannot save quality report without an analysis result")
        quality = job.result.quality
        cursor.execute(
            """
            INSERT INTO quality_reports (job_id, score, passed, evidence_coverage)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
              id = LAST_INSERT_ID(id),
              score = VALUES(score),
              passed = VALUES(passed),
              evidence_coverage = VALUES(evidence_coverage)
            """,
            (job.id, quality.score, quality.passed, quality.evidence_coverage),
        )
        return cursor.lastrowid

    def _replace_quality_issues(self, cursor: Cursor, quality_report_id: int, job: Job) -> None:
        cursor.execute("DELETE FROM quality_issues WHERE quality_report_id = %s", (quality_report_id,))
        if job.result is None or not job.result.quality.issues:
            return
        cursor.executemany(
            """
            INSERT INTO quality_issues (
              quality_report_id, code, severity, message, suggestion
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            [
                (quality_report_id, issue.code, issue.severity, issue.message, issue.suggestion)
                for issue in job.result.quality.issues
            ],
        )

    def _upsert_trace_events(self, cursor: Cursor, job: Job) -> None:
        if not job.trace_events:
            return
        cursor.executemany(
            """
            INSERT INTO trace_events (
              id, job_id, stage, title, status, provider, model, started_at,
              finished_at, duration_ms, input_json, output_json, field_sources,
              error_message
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
              status = VALUES(status),
              provider = VALUES(provider),
              model = VALUES(model),
              started_at = VALUES(started_at),
              finished_at = VALUES(finished_at),
              duration_ms = VALUES(duration_ms),
              input_json = VALUES(input_json),
              output_json = VALUES(output_json),
              field_sources = VALUES(field_sources),
              error_message = VALUES(error_message)
            """,
            [
                (
                    event.id,
                    job.id,
                    event.stage,
                    event.title,
                    event.status,
                    event.provider,
                    event.model,
                    _mysql_datetime(event.started_at),
                    _mysql_datetime(event.finished_at),
                    event.duration_ms,
                    _json(event.input),
                    _json(event.output),
                    _json(event.field_sources),
                    event.error,
                )
                for event in job.trace_events
            ],
        )


def build_history_store_from_env() -> MySqlHistoryStore | None:
    load_backend_env()
    required = [
        "MYSQL_HOST",
        "MYSQL_DATABASE",
        "MYSQL_USER",
        "MYSQL_PASSWORD",
        "PRODUCT_ENCRYPTION_KEY",
        "PRODUCT_ENCRYPTION_KEY_ID",
        "PRODUCT_HASH_SECRET",
    ]
    if not all(os.getenv(name) for name in required):
        return None

    cipher = ProductCipher.from_base64(
        os.environ["PRODUCT_ENCRYPTION_KEY"],
        os.environ["PRODUCT_ENCRYPTION_KEY_ID"],
    )
    hash_secret = decode_base64_secret(os.environ["PRODUCT_HASH_SECRET"], "PRODUCT_HASH_SECRET")

    def connect() -> Connection:
        try:
            import pymysql
        except ImportError as exc:
            raise RuntimeError("Install pymysql to enable MySQL history storage") from exc
        return pymysql.connect(
            host=os.environ["MYSQL_HOST"],
            port=int(os.getenv("MYSQL_PORT", "3306")),
            database=os.environ["MYSQL_DATABASE"],
            user=os.environ["MYSQL_USER"],
            password=os.environ["MYSQL_PASSWORD"],
            charset="utf8mb4",
            autocommit=False,
        )

    return MySqlHistoryStore(connect=connect, cipher=cipher, hash_secret=hash_secret)


def load_backend_env() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _mysql_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _finished_at(job: Job) -> datetime | None:
    if job.status in {"completed", "failed"}:
        return _mysql_datetime(job.updated_at)
    return None
