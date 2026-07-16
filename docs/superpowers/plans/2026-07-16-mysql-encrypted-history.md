# MySQL Encrypted History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store completed analysis history in MySQL while encrypting product facts before they are written.

**Architecture:** Keep the current in-memory `JobRepository` for active task state, and add an optional MySQL history store used when database and encryption environment variables are configured. Product facts are serialized to JSON, encrypted with AES-256-GCM in the backend, and written as ciphertext plus nonce/tag/key metadata.

**Tech Stack:** FastAPI, Pydantic, PyMySQL, cryptography AESGCM, MySQL 8.4, Docker Compose.

## Global Constraints

- Default local demo behavior must continue without MySQL.
- Product facts must not be stored in plaintext in MySQL.
- Hashes for lookup must use a configured secret so ASIN and URL are not directly reversible.
- Deployment must include SQL schema and Docker commands/files.

---

### Task 1: Encryption Helpers

**Files:**
- Create: `backend/app/crypto.py`
- Test: `backend/tests/test_crypto.py`

**Interfaces:**
- Produces: `ProductCipher.encrypt_json(payload: dict[str, object]) -> EncryptedPayload`
- Produces: `ProductCipher.decrypt_json(payload: EncryptedPayload) -> dict[str, object]`
- Produces: `hash_lookup(value: str, secret: bytes) -> str`

- [ ] Write failing tests proving plaintext is absent from ciphertext and decrypt round-trips.
- [ ] Implement AES-256-GCM encryption/decryption and keyed lookup hash.
- [ ] Run `python -m pytest backend/tests/test_crypto.py -q`.

### Task 2: MySQL History Store

**Files:**
- Create: `backend/app/history.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_history.py`

**Interfaces:**
- Consumes: `ProductCipher`
- Produces: `MySqlHistoryStore.save_job(job: Job) -> None`
- Produces: `build_history_store_from_env() -> MySqlHistoryStore | None`

- [ ] Write failing tests using a fake DB connection to assert encrypted product facts and result rows are persisted.
- [ ] Implement SQL inserts in one transaction.
- [ ] Wire optional history persistence into `run_job` after terminal job state.
- [ ] Run `python -m pytest backend/tests/test_history.py backend/tests/test_api.py -q`.

### Task 3: Deployment Artifacts

**Files:**
- Create: `backend/sql/schema.sql`
- Create: `docker-compose.mysql.yml`
- Create: `backend/.env.mysql.example`

**Interfaces:**
- Consumes: table names used by `MySqlHistoryStore`.
- Produces: reproducible MySQL startup and schema initialization.

- [ ] Add MySQL schema matching the store writes.
- [ ] Add Docker Compose service for MySQL 8.4 with volume and init SQL.
- [ ] Add env example showing DB and encryption settings.
- [ ] Run backend tests and a local import/health check.
