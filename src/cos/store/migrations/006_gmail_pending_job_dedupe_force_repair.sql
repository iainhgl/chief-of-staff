-- 006_gmail_pending_job_dedupe_force_repair.sql

-- Existing environments may already have the first version of this index,
-- which blocked intentional --force requeues. Rebuild it with the corrected
-- predicate so force-triggered jobs stay out of the dedupe guard.
DROP INDEX IF EXISTS idx_jobs_ingest_gmail_pending_unique;

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
