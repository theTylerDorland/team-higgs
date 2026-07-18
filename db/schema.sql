-- Agent platform state store, schema v2.1 (through migration 0004).
--
-- REFERENCE ONLY. As of emctl task 1, the operative schema truth is the
-- Alembic migration set under emctl/migrations/ (0001 reproduces the v1
-- baseline; 0003 adds the observability v2 surface; 0004 adds the typed
-- token columns on `runs`, all reflected here).
-- `emctl migrate` applies those migrations; this file is no longer applied
-- to any database (the docker-compose init mount was removed to avoid
-- colliding with Alembic). Change the schema by adding a migration, then
-- update this reference to match.
--
-- Postgres. CHECK constraints instead of enums for cheap evolution;
-- promote to types if churn settles.

CREATE TABLE projects (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    repo        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active','paused','done','archived')),
    brief       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE tasks (
    id             SERIAL PRIMARY KEY,
    project_id     INT NOT NULL REFERENCES projects(id),
    title          TEXT NOT NULL,
    spec           TEXT,
    status         TEXT NOT NULL DEFAULT 'backlog'
                   CHECK (status IN ('backlog','planned','in_progress',
                                     'in_review','awaiting_tyler','done')),
    blocked        BOOLEAN NOT NULL DEFAULT FALSE,
    blocked_reason TEXT,
    role           TEXT,          -- implementer-backend, reviewer-security, ...
    model_tier     TEXT NOT NULL DEFAULT 'execute'
                   CHECK (model_tier IN ('plan','execute','local')),
    prd_ref        TEXT,          -- docs/prd/<file>#<section>
    branch         TEXT,
    depends_on     INT[] NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE runs (
    id          SERIAL PRIMARY KEY,
    task_id     INT REFERENCES tasks(id),
    role        TEXT NOT NULL,
    model       TEXT NOT NULL,
    mode        TEXT NOT NULL CHECK (mode IN ('team','subagent','headless',
                                              'interactive')),
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at    TIMESTAMPTZ,
    outcome     TEXT CHECK (outcome IN ('done','negative-result','blocked',
                                        'failed')),
    token_cost  BIGINT,           -- legacy lump (~output only); superseded for
                                   -- cost by the typed columns below
    cost_usd    NUMERIC(10,4),   -- compute/API spend beyond tokens (ML lanes)
    log_ref     TEXT,
    -- schema v2.1 (migration 0004): per-run token usage by type, for accurate
    -- (cache-dominated) API cost projection. All nullable; NULL when no
    -- transcript was aggregated. cache_read/write map to the API's
    -- cache_read_input_tokens / cache_creation_input_tokens.
    input_tokens        BIGINT,
    output_tokens       BIGINT,
    cache_read_tokens   BIGINT,
    cache_write_tokens  BIGINT
);

CREATE TABLE prs (
    id             SERIAL PRIMARY KEY,
    project_id     INT NOT NULL REFERENCES projects(id),
    github_pr      INT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'open'
                   CHECK (status IN ('open','merged','rejected','closed')),
    risk_level     TEXT CHECK (risk_level IN ('low','medium','high')),
    em_summary     TEXT,          -- the full synthesized report
    tyler_decision TEXT,
    decided_at     TIMESTAMPTZ,
    task_id        INT REFERENCES tasks(id),  -- schema v2 (0003): task this PR implements
    UNIQUE (project_id, github_pr)
);

CREATE TABLE reviews (
    id                  SERIAL PRIMARY KEY,
    pr_id               INT NOT NULL REFERENCES prs(id),
    role                TEXT NOT NULL,
    model               TEXT,     -- for the cross-model panel analytics
    verdict             TEXT NOT NULL
                        CHECK (verdict IN ('approve','concerns','block')),
    findings            JSONB NOT NULL DEFAULT '[]',
                        -- [{severity, where, claim, evidence, why, fix}]
    strongest_objection TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE questions (
    id          SERIAL PRIMARY KEY,
    project_id  INT REFERENCES projects(id),
    body        TEXT NOT NULL,
    blocking    BOOLEAN NOT NULL DEFAULT FALSE,
    answer      TEXT,
    answered_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE decisions (
    id            SERIAL PRIMARY KEY,
    project_id    INT REFERENCES projects(id),
    title         TEXT NOT NULL,
    context       TEXT,
    decision      TEXT NOT NULL,
    -- schema v2 (migration 0003): status/significance/supersession link.
    status        TEXT NOT NULL DEFAULT 'accepted'
                  CHECK (status IN ('proposed','accepted','superseded','reversed')),
    significance  TEXT NOT NULL DEFAULT 'major'
                  CHECK (significance IN ('major','minor')),
    superseded_by INT REFERENCES decisions(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE artifacts (
    id          SERIAL PRIMARY KEY,
    project_id  INT NOT NULL REFERENCES projects(id),
    task_id     INT REFERENCES tasks(id),
    type        TEXT NOT NULL
                CHECK (type IN ('mockup','diagram','spec','schema',
                                'model','eval-set','prompt')),
    path        TEXT NOT NULL,   -- repo path, or GCS ref for large binaries
    status      TEXT NOT NULL DEFAULT 'proposed'
                CHECK (status IN ('proposed','approved','rejected',
                                  'superseded')),
    decided_at  TIMESTAMPTZ,
    notes       TEXT
);

CREATE TABLE learnings (
    id          SERIAL PRIMARY KEY,
    category    TEXT NOT NULL CHECK (category IN ('start','stop','keep',
                                                  'question')),
    observation TEXT NOT NULL,
    evidence    TEXT,            -- run/PR/task refs
    filed_by    TEXT,            -- role that filed it
    status      TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ('open','resolved','escalated')),
    retro_id    INT,             -- set when a retro consumes it
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE debt (
    id           SERIAL PRIMARY KEY,
    project_id   INT REFERENCES projects(id),
    location     TEXT NOT NULL,  -- file/module refs; required, no vibes-debt
    kind         TEXT NOT NULL CHECK (kind IN ('duplication','coupling',
                                     'missing-tests','pattern-drift',
                                     'dead-code','docs','other')),
    severity     TEXT NOT NULL CHECK (severity IN ('high','medium','low')),
    evidence     TEXT NOT NULL,
    filed_by     TEXT,
    recurrence   INT NOT NULL DEFAULT 1,   -- bumped on merge of duplicates
    passes_survived INT NOT NULL DEFAULT 0, -- health passes seen unaddressed
    status       TEXT NOT NULL DEFAULT 'open'
                 CHECK (status IN ('open','proposed','resolved','stale',
                                   'escalated')),
    resolved_ref TEXT,           -- resolving PR, when closed
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE metrics (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    definition  TEXT NOT NULL,   -- the query or computation, as text
    rationale   TEXT NOT NULL,   -- the decision this metric informs
    status      TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('proposed','active','retired')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE retros (
    id          SERIAL PRIMARY KEY,
    trigger     TEXT NOT NULL,   -- metric trend | ledger cluster | cadence
    doc_path    TEXT,            -- docs/retros/<file>
    opened_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at   TIMESTAMPTZ
);

-- schema v2 (migration 0003): EM-curated risk register.
CREATE TABLE risks (
    id              SERIAL PRIMARY KEY,
    project_id      INT NOT NULL REFERENCES projects(id),
    title           TEXT NOT NULL,
    body            TEXT,
    category        TEXT NOT NULL CHECK (category IN ('security','architecture',
                                    'operational','cost','dependency','product')),
    severity        TEXT NOT NULL CHECK (severity IN ('high','medium','low')),
    status          TEXT NOT NULL DEFAULT 'acknowledged'
                    CHECK (status IN ('acknowledged','mitigated','accepted',
                                      'realized','closed')),
    mitigation      TEXT,
    decision_id     INT REFERENCES decisions(id),
    pr_id           INT REFERENCES prs(id),
    acknowledged_by TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ      -- set when status leaves 'acknowledged'
);

-- schema v2 (migration 0003): task status history for cycle-time / rework.
CREATE TABLE task_events (
    id          SERIAL PRIMARY KEY,
    task_id     INT NOT NULL REFERENCES tasks(id),
    from_status TEXT,                -- null on creation
    to_status   TEXT NOT NULL,
    actor       TEXT,                -- role that made the change
    at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tasks_status   ON tasks(status) WHERE status != 'done';
CREATE INDEX idx_runs_task      ON runs(task_id);
CREATE INDEX idx_reviews_pr     ON reviews(pr_id);
CREATE INDEX idx_debt_open      ON debt(status) WHERE status = 'open';
CREATE INDEX idx_learnings_open ON learnings(status) WHERE status = 'open';
CREATE INDEX idx_risks_open       ON risks(status) WHERE status = 'acknowledged';
CREATE INDEX idx_task_events_task ON task_events(task_id);
