-- PrivView database schema (PostgreSQL)
-- Run with:  psql -U privview_user -d privview -f schema.sql

DROP TABLE IF EXISTS activity_logs, dataset_access, datasets, login_attempts, users CASCADE;

-- 1. Users (no signup page: rows are created by seed.py)
CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    email         VARCHAR(120) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20)  NOT NULL CHECK (role IN ('admin', 'analyst')),
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- 2. One row per login try (holds the OTP state for MFA)
CREATE TABLE login_attempts (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    otp_hash     VARCHAR(255) NOT NULL,          -- OTP is stored hashed, never plain
    expires_at   TIMESTAMPTZ  NOT NULL,
    resend_count INTEGER      NOT NULL DEFAULT 0, -- max 1
    wrong_count  INTEGER      NOT NULL DEFAULT 0, -- max 2 wrong entries
    status       VARCHAR(20)  NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'verified', 'failed', 'replaced')),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- 3. Datasets (Stage 2: file info + processing result + ENCRYPTED protected data)
CREATE TABLE datasets (
    id             SERIAL PRIMARY KEY,
    name           VARCHAR(100) NOT NULL,
    description    TEXT,
    uploaded_by    INTEGER      NOT NULL REFERENCES users(id),
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    filename       VARCHAR(255) NOT NULL DEFAULT '',
    file_type      VARCHAR(10)  NOT NULL DEFAULT '',
    record_count   INTEGER      NOT NULL DEFAULT 0,
    column_count   INTEGER      NOT NULL DEFAULT 0,
    status         VARCHAR(20)  NOT NULL DEFAULT 'processing'
                   CHECK (status IN ('processing', 'protected', 'failed')),
    summary        JSONB,
    encrypted_data BYTEA,
    nonce          BYTEA
);

-- 4. Which analyst may use which dataset (many-to-many link table)
CREATE TABLE dataset_access (
    id          SERIAL PRIMARY KEY,
    dataset_id  INTEGER     NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    user_id     INTEGER     NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
    granted_by  INTEGER     NOT NULL REFERENCES users(id),
    granted_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (dataset_id, user_id)
);

-- 5. Audit trail of important actions
CREATE TABLE activity_logs (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,  -- NULL if user unknown
    action     VARCHAR(50) NOT NULL,
    details    TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    role         VARCHAR(20),
    dataset_name VARCHAR(100),
    success      BOOLEAN NOT NULL DEFAULT TRUE
);
