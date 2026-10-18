DROP TABLE IF EXISTS activity_logs, dataset_access, datasets, login_attempts, users CASCADE;
CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    email         VARCHAR(120) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20)  NOT NULL CHECK (role IN ('admin', 'analyst')),
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE login_attempts (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    otp_hash     VARCHAR(255) NOT NULL,         
    expires_at   TIMESTAMPTZ  NOT NULL,
    resend_count INTEGER      NOT NULL DEFAULT 0, 
    wrong_count  INTEGER      NOT NULL DEFAULT 0, 
    status       VARCHAR(20)  NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'verified', 'failed', 'replaced')),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

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

CREATE TABLE dataset_access (
    id          SERIAL PRIMARY KEY,
    dataset_id  INTEGER     NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    user_id     INTEGER     NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
    granted_by  INTEGER     NOT NULL REFERENCES users(id),
    granted_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (dataset_id, user_id)
);

CREATE TABLE activity_logs (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,  
    action     VARCHAR(50) NOT NULL,
    details    TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    role         VARCHAR(20),
    dataset_name VARCHAR(100),
    success      BOOLEAN NOT NULL DEFAULT TRUE
);
