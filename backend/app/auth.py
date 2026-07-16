import base64
import hashlib
import hmac
import os
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.crypto import hash_lookup
from app.history import load_backend_env
from app.models import Job


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    username: str | None = Field(default=None, max_length=64)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class UserPublic(BaseModel):
    id: int
    email: str
    username: str | None
    role: str
    status: str
    points_balance: int
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserPublic
    access_token: str
    token_type: str = "bearer"


class PointsResponse(BaseModel):
    balance: int


class LedgerEntry(BaseModel):
    id: int
    job_id: str | None
    change_amount: int
    balance_after: int
    reason: str
    status: str
    created_at: datetime


class Cursor(Protocol):
    lastrowid: int

    def execute(self, query: str, args: tuple[Any, ...] | None = None) -> int: ...
    def fetchone(self) -> dict[str, Any] | None: ...
    def fetchall(self) -> list[dict[str, Any]]: ...
    def close(self) -> None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


ConnectFactory = Callable[[], Connection]


@dataclass(frozen=True)
class ReservedPoint:
    ledger_id: int
    balance_after: int


class AuthError(Exception):
    pass


class DuplicateUserError(AuthError):
    pass


class InvalidCredentialsError(AuthError):
    pass


class InsufficientPointsError(AuthError):
    pass


class AuthStore:
    def __init__(self, connect: ConnectFactory, token_secret: bytes, session_days: int = 7) -> None:
        self._connect = connect
        self._token_secret = token_secret
        self._session_days = session_days

    def register(self, payload: RegisterRequest, user_agent: str | None, ip_address: str | None) -> AuthResponse:
        connection = self._connect()
        cursor = connection.cursor()
        try:
            existing = self._find_user_by_email(cursor, payload.email)
            if existing is not None:
                raise DuplicateUserError("email already registered")

            password_hash = hash_password(payload.password)
            cursor.execute(
                """
                INSERT INTO users (
                  email, username, password_hash, password_alg, status, role, points_balance
                )
                VALUES (%s, %s, %s, %s, 'active', 'user', 10)
                """,
                (payload.email.lower(), payload.username, password_hash, "pbkdf2_sha256"),
            )
            user_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT INTO point_ledger (
                  user_id, change_amount, balance_after, reason, status
                )
                VALUES (%s, 10, 10, 'register_bonus', 'confirmed')
                """,
                (user_id,),
            )
            token = self._create_session(cursor, user_id, user_agent, ip_address)
            user = self._get_user_by_id(cursor, user_id)
            connection.commit()
            return AuthResponse(user=to_user_public(user), access_token=token)
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def login(self, payload: LoginRequest, user_agent: str | None, ip_address: str | None) -> AuthResponse:
        connection = self._connect()
        cursor = connection.cursor()
        try:
            user = self._find_user_by_email(cursor, payload.email)
            if user is None or user["status"] != "active" or not verify_password(payload.password, user["password_hash"]):
                raise InvalidCredentialsError("invalid email or password")
            cursor.execute("UPDATE users SET last_login_at = UTC_TIMESTAMP(6) WHERE id = %s", (user["id"],))
            token = self._create_session(cursor, int(user["id"]), user_agent, ip_address)
            user = self._get_user_by_id(cursor, int(user["id"]))
            connection.commit()
            return AuthResponse(user=to_user_public(user), access_token=token)
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def authenticate(self, token: str) -> UserPublic | None:
        token_hash = hash_lookup(token, self._token_secret)
        connection = self._connect()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT u.*
                FROM user_sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.access_token_hash = %s
                  AND s.revoked_at IS NULL
                  AND s.expires_at > UTC_TIMESTAMP(6)
                  AND u.status = 'active'
                """,
                (token_hash,),
            )
            user = cursor.fetchone()
            return to_user_public(user) if user else None
        finally:
            cursor.close()
            connection.close()

    def logout(self, token: str) -> None:
        token_hash = hash_lookup(token, self._token_secret)
        connection = self._connect()
        cursor = connection.cursor()
        try:
            cursor.execute(
                "UPDATE user_sessions SET revoked_at = UTC_TIMESTAMP(6) WHERE access_token_hash = %s",
                (token_hash,),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def get_points(self, user_id: int) -> PointsResponse:
        connection = self._connect()
        cursor = connection.cursor()
        try:
            user = self._get_user_by_id(cursor, user_id)
            return PointsResponse(balance=int(user["points_balance"]))
        finally:
            cursor.close()
            connection.close()

    def get_ledger(self, user_id: int, limit: int = 50) -> list[LedgerEntry]:
        connection = self._connect()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT id, job_id, change_amount, balance_after, reason, status, created_at
                FROM point_ledger
                WHERE user_id = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return [LedgerEntry(**row) for row in cursor.fetchall()]
        finally:
            cursor.close()
            connection.close()

    def reserve_analysis_point(self, user_id: int, job: Job) -> ReservedPoint:
        connection = self._connect()
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT points_balance FROM users WHERE id = %s FOR UPDATE", (user_id,))
            row = cursor.fetchone()
            if row is None:
                raise InvalidCredentialsError("user not found")
            balance = int(row["points_balance"])
            if balance < 1:
                raise InsufficientPointsError("insufficient points")
            balance_after = balance - 1
            cursor.execute("UPDATE users SET points_balance = %s WHERE id = %s", (balance_after, user_id))
            cursor.execute(
                """
                INSERT INTO point_ledger (
                  user_id, job_id, change_amount, balance_after, reason, status
                )
                VALUES (%s, %s, -1, %s, 'analysis_reserve', 'confirmed')
                """,
                (user_id, job.id, balance_after),
            )
            ledger_id = cursor.lastrowid
            self._insert_job_owner(cursor, user_id, job, ledger_id)
            connection.commit()
            return ReservedPoint(ledger_id=ledger_id, balance_after=balance_after)
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def refund_analysis_point(self, job_id: str) -> None:
        connection = self._connect()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT id, user_id, status
                FROM point_ledger
                WHERE job_id = %s AND reason = 'analysis_reserve'
                ORDER BY id DESC
                LIMIT 1
                FOR UPDATE
                """,
                (job_id,),
            )
            reserved = cursor.fetchone()
            if reserved is None or reserved["status"] == "refunded":
                connection.commit()
                return
            user_id = int(reserved["user_id"])
            cursor.execute("SELECT points_balance FROM users WHERE id = %s FOR UPDATE", (user_id,))
            user = cursor.fetchone()
            if user is None:
                connection.commit()
                return
            balance_after = int(user["points_balance"]) + 1
            cursor.execute("UPDATE users SET points_balance = %s WHERE id = %s", (balance_after, user_id))
            cursor.execute(
                """
                INSERT INTO point_ledger (
                  user_id, job_id, change_amount, balance_after, reason, status, related_ledger_id
                )
                VALUES (%s, %s, 1, %s, 'analysis_refund', 'confirmed', %s)
                """,
                (user_id, job_id, balance_after, reserved["id"]),
            )
            cursor.execute("UPDATE point_ledger SET status = 'refunded' WHERE id = %s", (reserved["id"],))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def user_owns_job(self, user: UserPublic, job_id: str) -> bool:
        if user.role == "admin":
            return True
        connection = self._connect()
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT user_id FROM analysis_jobs WHERE id = %s", (job_id,))
            row = cursor.fetchone()
            return row is not None and int(row["user_id"]) == user.id
        finally:
            cursor.close()
            connection.close()

    def _find_user_by_email(self, cursor: Cursor, email: str) -> dict[str, Any] | None:
        cursor.execute("SELECT * FROM users WHERE email = %s", (email.lower(),))
        return cursor.fetchone()

    def _get_user_by_id(self, cursor: Cursor, user_id: int) -> dict[str, Any]:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        if row is None:
            raise InvalidCredentialsError("user not found")
        return row

    def _create_session(self, cursor: Cursor, user_id: int, user_agent: str | None, ip_address: str | None) -> str:
        token = secrets.token_urlsafe(48)
        token_hash = hash_lookup(token, self._token_secret)
        expires_at = datetime.now(timezone.utc) + timedelta(days=self._session_days)
        cursor.execute(
            """
            INSERT INTO user_sessions (
              user_id, access_token_hash, user_agent, ip_address, expires_at
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, token_hash, (user_agent or "")[:255], (ip_address or "")[:64], _mysql_datetime(expires_at)),
        )
        return token

    def _insert_job_owner(self, cursor: Cursor, user_id: int, job: Job, ledger_id: int) -> None:
        cursor.execute(
            """
            INSERT INTO analysis_jobs (
              id, user_id, point_ledger_id, point_cost, request_url_hash,
              request_url_encryption_alg, request_url_key_id, request_url_nonce,
              request_url_auth_tag, request_url_ciphertext, status, stage,
              progress, created_at, updated_at
            )
            VALUES (
              %s, %s, %s, 1, %s,
              'pending', 'pending', X'', X'', X'', %s, %s,
              %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
              user_id = VALUES(user_id),
              point_ledger_id = VALUES(point_ledger_id),
              point_cost = VALUES(point_cost)
            """,
            (
                job.id,
                user_id,
                ledger_id,
                hash_lookup(job.url, self._token_secret),
                job.status,
                job.stage,
                job.progress,
                _mysql_datetime(job.created_at),
                _mysql_datetime(job.updated_at),
            ),
        )


def build_auth_store_from_env() -> AuthStore | None:
    load_backend_env()
    required = ["MYSQL_HOST", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD", "PRODUCT_HASH_SECRET"]
    if not all(os.getenv(name) for name in required):
        return None
    token_secret = base64.b64decode(os.environ["PRODUCT_HASH_SECRET"], validate=True)

    def connect() -> Connection:
        try:
            import pymysql
            from pymysql.cursors import DictCursor
        except ImportError as exc:
            raise RuntimeError("Install pymysql to enable user and points storage") from exc
        return pymysql.connect(
            host=os.environ["MYSQL_HOST"],
            port=int(os.getenv("MYSQL_PORT", "3306")),
            database=os.environ["MYSQL_DATABASE"],
            user=os.environ["MYSQL_USER"],
            password=os.environ["MYSQL_PASSWORD"],
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
        )

    return AuthStore(connect=connect, token_secret=token_secret)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return "pbkdf2_sha256$210000$" + base64.b64encode(salt).decode("ascii") + "$" + base64.b64encode(digest).decode("ascii")


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def to_user_public(row: dict[str, Any]) -> UserPublic:
    return UserPublic(
        id=int(row["id"]),
        email=str(row["email"]),
        username=row.get("username"),
        role=str(row["role"]),
        status=str(row["status"]),
        points_balance=int(row["points_balance"]),
        created_at=row["created_at"],
    )


def _mysql_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)
