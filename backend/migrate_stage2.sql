-- PrivView Stage 2 migration (run ONCE on your existing Stage 1 database).
-- It only ADDS columns. Your users, login attempts and logs are kept.
--
--   psql -U privview_user -d privview -f backend/migrate_stage2.sql
--
-- Safe to run twice (IF NOT EXISTS).

-- 1. datasets: store file info, processing result and the ENCRYPTED data
ALTER TABLE datasets
    ADD COLUMN IF NOT EXISTS filename       VARCHAR(255) NOT NULL DEFAULT '',   -- sanitised filename
    ADD COLUMN IF NOT EXISTS file_type      VARCHAR(10)  NOT NULL DEFAULT '',   -- csv / xlsx
    ADD COLUMN IF NOT EXISTS record_count   INTEGER      NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS column_count   INTEGER      NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS status         VARCHAR(20)  NOT NULL DEFAULT 'processing'
                            CHECK (status IN ('processing', 'protected', 'failed')),
    ADD COLUMN IF NOT EXISTS summary        JSONB,                              -- processing results shown to admin
    ADD COLUMN IF NOT EXISTS encrypted_data BYTEA,                              -- AES-256-GCM ciphertext
    ADD COLUMN IF NOT EXISTS nonce          BYTEA;                              -- AES-GCM nonce (not secret)

-- 2. activity_logs: the admin log page needs role, dataset name and success/failure
ALTER TABLE activity_logs
    ADD COLUMN IF NOT EXISTS role         VARCHAR(20),
    ADD COLUMN IF NOT EXISTS dataset_name VARCHAR(100),
    ADD COLUMN IF NOT EXISTS success      BOOLEAN NOT NULL DEFAULT TRUE;

-- 3. tidy up the old Stage 1 log rows
UPDATE activity_logs SET success = FALSE
 WHERE action IN ('LOGIN_FAILED', 'OTP_WRONG', 'ACCESS_DENIED');

UPDATE activity_logs a SET role = u.role
  FROM users u WHERE a.user_id = u.id AND a.role IS NULL;
