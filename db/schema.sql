-- Agent platform state store, schema v1.
-- Postgres. CHECK constraints instead of enums for cheap evolution;
-- promote to types if churn settles. Applied by emctl migrate (task 1).

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
    token_cost  BIGINT,
    cost_usd    NUMERIC(10,4),   -- compute/API spend beyond tokens (ML lanes)
    log_ref     TEXT
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
    id          SERIAL PRIMARY KEY,
    project_id  INT REFERENCES projects(id),
    title       TEXT NOT NULL,
    context     TEXT,
    decision    TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
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

CREATE INDEX idx_tasks_status   ON tasks(status) WHERE status != 'done';
CREATE INDEX idx_runs_task      ON runs(task_id);
CREATE INDEX idx_reviews_pr     ON reviews(pr_id);
CREATE INDEX idx_debt_open      ON debt(status) WHERE status = 'open';
CREATE INDEX idx_learnings_open ON learnings(status) WHERE status = 'open';
