-- 005_gmail_pending_job_dedupe.sql

-- Prevent concurrent Gmail polls from queueing the same artifact fingerprint
-- more than once while a prior ingest job is still queued or running.
CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_ingest_gmail_pending_unique
    ON jobs (
        (payload->>'source_locator'),
        (payload->'metadata'->>'content_fingerprint')
    )
    WHERE job_type = 'ingest'
      AND status IN ('queued', 'running')
      AND payload->>'source_type' IN ('gmail_message_body', 'gmail_attachment')
      AND payload->'metadata' ? 'content_fingerprint'
      AND NOT (payload->'metadata' ? 'force_reenqueue');
