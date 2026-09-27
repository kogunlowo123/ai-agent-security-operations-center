-- =============================================================================
-- AI Agent SOC – Session Ledger Schema
-- PostgreSQL 15+
-- =============================================================================

-- Extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- agent_sessions
-- =============================================================================
CREATE TABLE IF NOT EXISTS agent_sessions (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id         UUID        NOT NULL,
    tenant_id        UUID        NOT NULL,
    tier             CHAR(2)     NOT NULL CHECK (tier IN ('T1', 'T2', 'T3')),
    scopes           TEXT[]      NOT NULL DEFAULT '{}',
    token_hash       TEXT        NOT NULL,          -- SHA-256 hex of the raw JWT
    issued_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at       TIMESTAMPTZ NOT NULL,
    revoked_at       TIMESTAMPTZ,
    revocation_reason TEXT,
    metadata         JSONB       NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT expires_after_issued CHECK (expires_at > issued_at)
);

CREATE INDEX IF NOT EXISTS idx_sessions_agent_id   ON agent_sessions (agent_id);
CREATE INDEX IF NOT EXISTS idx_sessions_tenant_id  ON agent_sessions (tenant_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON agent_sessions (expires_at);
CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON agent_sessions (token_hash);

-- =============================================================================
-- session_events  (audit trail for every meaningful action in a session)
-- =============================================================================
CREATE TABLE IF NOT EXISTS session_events (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID        NOT NULL REFERENCES agent_sessions (id) ON DELETE CASCADE,
    event_type  TEXT        NOT NULL,   -- e.g. ISSUED, VERIFIED, REVOKED, SCOPE_DENIED
    actor       TEXT        NOT NULL,   -- who triggered the event (agent_id or system)
    payload     JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_session_events_session_id ON session_events (session_id);
CREATE INDEX IF NOT EXISTS idx_session_events_event_type ON session_events (event_type);
CREATE INDEX IF NOT EXISTS idx_session_events_created_at ON session_events (created_at);

-- =============================================================================
-- token_revocations  (fast JTI lookup for revocation checks)
-- =============================================================================
CREATE TABLE IF NOT EXISTS token_revocations (
    jti         TEXT        PRIMARY KEY,            -- JWT ID (uuid)
    revoked_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reason      TEXT        NOT NULL DEFAULT 'unspecified',
    revoked_by  TEXT        NOT NULL                -- agent_id or operator e-mail
);

CREATE INDEX IF NOT EXISTS idx_token_revocations_revoked_at ON token_revocations (revoked_at);

-- =============================================================================
-- Row-level security
-- =============================================================================
ALTER TABLE agent_sessions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_events    ENABLE ROW LEVEL SECURITY;
ALTER TABLE token_revocations ENABLE ROW LEVEL SECURITY;

-- Policy: each tenant may only read/modify its own sessions
CREATE POLICY tenant_isolation_sessions
    ON agent_sessions
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- Policy: session events are visible only within the owning session's tenant
CREATE POLICY tenant_isolation_session_events
    ON session_events
    USING (
        session_id IN (
            SELECT id FROM agent_sessions
            WHERE tenant_id = current_setting('app.current_tenant_id')::uuid
        )
    );

-- Policy: revocations are globally readable by the broker service (no tenant filter)
--         Application role 'soc_broker' bypasses RLS; all others are denied.
CREATE POLICY broker_only_revocations
    ON token_revocations
    USING (current_user = 'soc_broker');

-- =============================================================================
-- Helper function: expire old sessions (run periodically)
-- =============================================================================
CREATE OR REPLACE FUNCTION purge_expired_sessions(older_than INTERVAL DEFAULT '30 days')
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM agent_sessions
    WHERE expires_at < NOW() - older_than
      AND revoked_at IS NOT NULL;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
