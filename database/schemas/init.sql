-- =============================================================
-- ResQAI - PostgreSQL Database Initialization
-- Extensions and initial setup
-- =============================================================

-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- UUID generation
CREATE EXTENSION IF NOT EXISTS "postgis";         -- Geospatial support
CREATE EXTENSION IF NOT EXISTS "pg_trgm";         -- Trigram text search
CREATE EXTENSION IF NOT EXISTS "btree_gin";       -- GIN index support
CREATE EXTENSION IF NOT EXISTS "unaccent";        -- Accent-insensitive search
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements"; -- Query performance monitoring

-- Create application schema
CREATE SCHEMA IF NOT EXISTS resqai;

-- Set default search path
ALTER DATABASE resqai_db SET search_path TO resqai, public;

-- Create updated_at trigger function (reusable across all tables)
CREATE OR REPLACE FUNCTION resqai.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create audit log trigger function
CREATE OR REPLACE FUNCTION resqai.audit_trigger()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO resqai.audit_logs (
        table_name,
        operation,
        old_values,
        new_values,
        changed_at
    ) VALUES (
        TG_TABLE_NAME,
        TG_OP,
        CASE WHEN TG_OP != 'INSERT' THEN row_to_json(OLD) ELSE NULL END,
        CASE WHEN TG_OP != 'DELETE' THEN row_to_json(NEW) ELSE NULL END,
        CURRENT_TIMESTAMP
    );
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT USAGE ON SCHEMA resqai TO resqai_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA resqai TO resqai_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA resqai TO resqai_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA resqai GRANT ALL ON TABLES TO resqai_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA resqai GRANT ALL ON SEQUENCES TO resqai_user;
