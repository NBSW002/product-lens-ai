CREATE DATABASE IF NOT EXISTS product_lens
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE product_lens;

CREATE TABLE IF NOT EXISTS users (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  email VARCHAR(255) NOT NULL,
  username VARCHAR(64) NULL,
  password_hash VARCHAR(255) NOT NULL,
  password_alg VARCHAR(32) NOT NULL DEFAULT 'pbkdf2_sha256',
  status ENUM('active', 'disabled') NOT NULL DEFAULT 'active',
  role ENUM('user', 'admin') NOT NULL DEFAULT 'user',
  points_balance INT UNSIGNED NOT NULL DEFAULT 0,
  last_login_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),

  UNIQUE KEY uk_users_email (email),
  INDEX idx_users_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS user_sessions (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  access_token_hash CHAR(64) NOT NULL,
  user_agent VARCHAR(255) NULL,
  ip_address VARCHAR(64) NULL,
  expires_at DATETIME(6) NOT NULL,
  revoked_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

  UNIQUE KEY uk_user_sessions_token (access_token_hash),
  INDEX idx_user_sessions_user (user_id),
  INDEX idx_user_sessions_expires (expires_at),
  CONSTRAINT fk_user_sessions_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS analysis_jobs (
  id CHAR(36) PRIMARY KEY,
  user_id BIGINT UNSIGNED NULL,
  point_ledger_id BIGINT UNSIGNED NULL,
  point_cost INT UNSIGNED NOT NULL DEFAULT 1,
  request_url_hash CHAR(64) NOT NULL,
  request_url_encryption_alg VARCHAR(32) NOT NULL DEFAULT 'AES-256-GCM',
  request_url_key_id VARCHAR(64) NOT NULL,
  request_url_nonce VARBINARY(32) NOT NULL,
  request_url_auth_tag VARBINARY(32) NOT NULL,
  request_url_ciphertext LONGBLOB NOT NULL,
  status ENUM('queued', 'running', 'completed', 'failed') NOT NULL DEFAULT 'queued',
  stage VARCHAR(64) NOT NULL DEFAULT 'QUEUED',
  progress TINYINT UNSIGNED NOT NULL DEFAULT 0,
  error_message TEXT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  finished_at DATETIME(6) NULL,

  INDEX idx_jobs_user_created_at (user_id, created_at),
  INDEX idx_jobs_status_created_at (status, created_at),
  INDEX idx_jobs_created_at (created_at),
  INDEX idx_jobs_request_url_hash (request_url_hash),
  CONSTRAINT fk_jobs_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS point_ledger (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  job_id CHAR(36) NULL,
  change_amount INT NOT NULL,
  balance_after INT UNSIGNED NOT NULL,
  reason ENUM('register_bonus', 'analysis_reserve', 'analysis_refund', 'admin_adjust') NOT NULL,
  status ENUM('confirmed', 'refunded') NOT NULL DEFAULT 'confirmed',
  related_ledger_id BIGINT UNSIGNED NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

  INDEX idx_point_ledger_user_created_at (user_id, created_at),
  INDEX idx_point_ledger_job (job_id),
  CONSTRAINT fk_point_ledger_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE,
  CONSTRAINT fk_point_ledger_related
    FOREIGN KEY (related_ledger_id) REFERENCES point_ledger(id)
    ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS encrypted_product_facts (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  job_id CHAR(36) NOT NULL,
  asin_hash CHAR(64) NOT NULL,
  source_url_hash CHAR(64) NOT NULL,
  encryption_alg VARCHAR(32) NOT NULL DEFAULT 'AES-256-GCM',
  key_id VARCHAR(64) NOT NULL,
  nonce VARBINARY(32) NOT NULL,
  auth_tag VARBINARY(32) NOT NULL,
  ciphertext LONGBLOB NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

  UNIQUE KEY uk_product_facts_job (job_id),
  INDEX idx_product_asin_hash (asin_hash),
  CONSTRAINT fk_product_facts_job
    FOREIGN KEY (job_id) REFERENCES analysis_jobs(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS product_analysis_results (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  job_id CHAR(36) NOT NULL,
  target_users JSON NOT NULL,
  scenarios JSON NOT NULL,
  pain_points JSON NOT NULL,
  selling_points JSON NOT NULL,
  visual_findings JSON NOT NULL,
  voiceover TEXT NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

  UNIQUE KEY uk_analysis_job (job_id),
  CONSTRAINT fk_analysis_job
    FOREIGN KEY (job_id) REFERENCES analysis_jobs(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS quality_reports (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  job_id CHAR(36) NOT NULL,
  score TINYINT UNSIGNED NOT NULL,
  passed BOOLEAN NOT NULL,
  evidence_coverage TINYINT UNSIGNED NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

  UNIQUE KEY uk_quality_job (job_id),
  CONSTRAINT fk_quality_job
    FOREIGN KEY (job_id) REFERENCES analysis_jobs(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS quality_issues (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  quality_report_id BIGINT UNSIGNED NOT NULL,
  code VARCHAR(64) NOT NULL,
  severity ENUM('low', 'medium', 'high') NOT NULL,
  message TEXT NOT NULL,
  suggestion TEXT NOT NULL,

  INDEX idx_quality_issues_report (quality_report_id),
  CONSTRAINT fk_quality_issues_report
    FOREIGN KEY (quality_report_id) REFERENCES quality_reports(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS trace_events (
  id CHAR(64) NOT NULL,
  job_id CHAR(36) NOT NULL,
  stage ENUM(
    'PRODUCT_FETCH',
    'VISION_ANALYSIS',
    'TEXT_DRAFT',
    'QUALITY_CHECK',
    'TEXT_REVISION',
    'FINALIZE'
  ) NOT NULL,
  title VARCHAR(128) NOT NULL,
  status ENUM('pending', 'running', 'completed', 'failed', 'skipped') NOT NULL DEFAULT 'pending',
  provider VARCHAR(64) NOT NULL,
  model VARCHAR(128) NULL,
  started_at DATETIME(6) NULL,
  finished_at DATETIME(6) NULL,
  duration_ms INT UNSIGNED NULL,
  input_json JSON NULL,
  output_json JSON NULL,
  field_sources JSON NULL,
  error_message TEXT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

  PRIMARY KEY (job_id, id),
  INDEX idx_trace_job_stage (job_id, stage),
  INDEX idx_trace_job_status (job_id, status),
  CONSTRAINT fk_trace_job
    FOREIGN KEY (job_id) REFERENCES analysis_jobs(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP PROCEDURE IF EXISTS add_column_if_missing;

DELIMITER //
CREATE PROCEDURE add_column_if_missing(
  IN table_name_value VARCHAR(64),
  IN column_name_value VARCHAR(64),
  IN alter_sql_value TEXT
)
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = table_name_value
      AND COLUMN_NAME = column_name_value
  ) THEN
    SET @alter_sql = alter_sql_value;
    PREPARE stmt FROM @alter_sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
  END IF;
END //
DELIMITER ;

CALL add_column_if_missing(
  'analysis_jobs',
  'user_id',
  'ALTER TABLE analysis_jobs ADD COLUMN user_id BIGINT UNSIGNED NULL AFTER id'
);

CALL add_column_if_missing(
  'analysis_jobs',
  'point_ledger_id',
  'ALTER TABLE analysis_jobs ADD COLUMN point_ledger_id BIGINT UNSIGNED NULL AFTER user_id'
);

CALL add_column_if_missing(
  'analysis_jobs',
  'point_cost',
  'ALTER TABLE analysis_jobs ADD COLUMN point_cost INT UNSIGNED NOT NULL DEFAULT 1 AFTER point_ledger_id'
);

DROP PROCEDURE IF EXISTS add_column_if_missing;
