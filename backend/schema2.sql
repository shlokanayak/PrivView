ALTER TABLE datasets
    ADD COLUMN IF NOT EXISTS filename       VARCHAR(255) NOT NULL DEFAULT '',   
    ADD COLUMN IF NOT EXISTS file_type      VARCHAR(10)  NOT NULL DEFAULT '',   
    ADD COLUMN IF NOT EXISTS record_count   INTEGER      NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS column_count   INTEGER      NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS status         VARCHAR(20)  NOT NULL DEFAULT 'processing'
                            CHECK (status IN ('processing', 'protected', 'failed')),
    ADD COLUMN IF NOT EXISTS summary        JSONB,                              
    ADD COLUMN IF NOT EXISTS encrypted_data BYTEA,                              
    ADD COLUMN IF NOT EXISTS nonce          BYTEA;                              

ALTER TABLE activity_logs
    ADD COLUMN IF NOT EXISTS role         VARCHAR(20),
    ADD COLUMN IF NOT EXISTS dataset_name VARCHAR(100),
    ADD COLUMN IF NOT EXISTS success      BOOLEAN NOT NULL DEFAULT TRUE;

UPDATE activity_logs SET success = FALSE
 WHERE action IN ('LOGIN_FAILED', 'OTP_WRONG', 'ACCESS_DENIED');

UPDATE activity_logs a SET role = u.role
  FROM users u WHERE a.user_id = u.id AND a.role IS NULL;
