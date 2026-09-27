package soc.access

import future.keywords.in

default allow = false

# ---------------------------------------------------------------------------
# Events – ingest (POST /api/v1/events)
# ---------------------------------------------------------------------------
allow {
    input.method == "POST"
    input.path[0] == "api"
    input.path[2] == "events"
    has_scope(input.token.scopes, "events:ingest")
    same_tenant
}

# ---------------------------------------------------------------------------
# Events – read (GET /api/v1/events)
# ---------------------------------------------------------------------------
allow {
    input.method == "GET"
    input.path[0] == "api"
    input.path[2] == "events"
    has_scope(input.token.scopes, "events:read")
    same_tenant
}

# ---------------------------------------------------------------------------
# Incidents – read (GET /api/v1/incidents[/*])
# ---------------------------------------------------------------------------
allow {
    input.method == "GET"
    input.path[0] == "api"
    input.path[2] == "incidents"
    has_scope(input.token.scopes, "incidents:read")
    same_tenant
}

# ---------------------------------------------------------------------------
# Incidents – write (POST/PATCH/PUT /api/v1/incidents)
# ---------------------------------------------------------------------------
allow {
    input.method in ["POST", "PATCH", "PUT"]
    input.path[0] == "api"
    input.path[2] == "incidents"
    has_scope(input.token.scopes, "incidents:write")
    same_tenant
    require_t2_or_above
}

# ---------------------------------------------------------------------------
# Posture – read (GET /api/v1/posture)
# ---------------------------------------------------------------------------
allow {
    input.method == "GET"
    input.path[2] == "posture"
    has_scope(input.token.scopes, "posture:read")
    same_tenant
}

# ---------------------------------------------------------------------------
# Posture – write (POST/PATCH /api/v1/posture)
# ---------------------------------------------------------------------------
allow {
    input.method in ["POST", "PATCH"]
    input.path[2] == "posture"
    has_scope(input.token.scopes, "posture:write")
    same_tenant
    require_t2_or_above
}

# ---------------------------------------------------------------------------
# Hunt – launch (POST /api/v1/hunt)
# ---------------------------------------------------------------------------
allow {
    input.method == "POST"
    input.path[2] == "hunt"
    has_scope(input.token.scopes, "hunt:launch")
    same_tenant
    require_t2_or_above
}

# ---------------------------------------------------------------------------
# Hunt – read (GET /api/v1/hunt)
# ---------------------------------------------------------------------------
allow {
    input.method == "GET"
    input.path[2] == "hunt"
    has_scope(input.token.scopes, "hunt:read")
    same_tenant
}

# ---------------------------------------------------------------------------
# Agents – manage (any method /api/v1/agents)
# ---------------------------------------------------------------------------
allow {
    input.path[2] == "agents"
    has_scope(input.token.scopes, "agents:manage")
    same_tenant
    require_t2_or_above
}

# ---------------------------------------------------------------------------
# Sessions – revoke (DELETE /api/v1/sessions/*)
# ---------------------------------------------------------------------------
allow {
    input.method == "DELETE"
    input.path[2] == "sessions"
    has_scope(input.token.scopes, "sessions:revoke")
    same_tenant
    require_t2_or_above
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

same_tenant {
    input.token.tenant_id == input.resource_tenant_id
}

has_scope(scopes, required) {
    scopes[_] == required
}

require_t2_or_above {
    input.token.tier in ["T2", "T3"]
}

# Deny explicitly if token is expired (belt-and-suspenders)
deny_expired {
    now := time.now_ns() / 1000000000
    input.token.exp < now
}
