-- Jobs queue (Phase 2) — background ingest worker substrate
CREATE TABLE IF NOT EXISTS jobs (
    id            uuid        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    job_type      text        NOT NULL,
    status        text        NOT NULL DEFAULT 'queued'
                              CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
    payload       jsonb       NOT NULL,
    attempt_count integer     NOT NULL DEFAULT 0,
    max_attempts  integer     NOT NULL DEFAULT 3,
    available_at  timestamptz NOT NULL DEFAULT now(),
    started_at    timestamptz,
    completed_at  timestamptz,
    last_error    text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

-- Supports dequeue: WHERE job_type = X AND status = 'queued' AND available_at <= now() ORDER BY created_at ASC
CREATE INDEX IF NOT EXISTS idx_jobs_dequeue
    ON jobs (job_type, available_at, created_at)
    WHERE status = 'queued';

-- Supports stale-job requeue: WHERE status = 'running' AND started_at < threshold
CREATE INDEX IF NOT EXISTS idx_jobs_running_started_at
    ON jobs (status, started_at)
    WHERE status = 'running';
