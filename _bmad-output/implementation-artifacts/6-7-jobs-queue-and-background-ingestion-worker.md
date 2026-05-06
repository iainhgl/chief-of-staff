# Story 6.7: Jobs Queue and Background Ingestion Worker

Status: done

## Story

As an operator,
I want connector-triggered ingestion to run through a background job mechanism,
So that live-source ingest does not block MCP retrieval or destabilise the core path.

## Acceptance Criteria

1. **Given** the Phase 2 jobs migration is applied,
   **When** the jobs table is inspected,
   **Then** it supports queued ingestion work with status tracking, retry metadata, and completion/error timestamps.

2. **Given** a connector discovers new content to ingest,
   **When** it submits work,
   **Then** it creates a background job carrying the connector payload and does not invoke the ingest pipeline inline on the connector poll loop.

3. **Given** the worker processes queued jobs,
   **When** it handles an ingest request,
   **Then** it executes through the same canonical identity decision path used by CLI ingest and records whether the outcome was new content, changed content, known-content/new-source, or no-op.

4. **Given** the worker crashes or the container restarts mid-job,
   **When** processing resumes,
   **Then** unfinished work is retried safely and does not leave partial canonical identity records visible to users.

## Tasks / Subtasks

- [x] Task 1: Replace the stub-only `002_jobs.sql` with the real Phase 2 queue schema (AC: #1, #4)
  - [x] Update [src/cos/store/migrations/002_jobs.sql](/Users/iain.livingstone/Development/CoS/cos/src/cos/store/migrations/002_jobs.sql) so it creates an idempotent `jobs` table instead of comments only
  - [x] Include at minimum: `id`, `job_type`, `status`, `payload`, `attempt_count`, `max_attempts`, `available_at`, `started_at`, `completed_at`, `last_error`, `created_at`, `updated_at`
  - [x] Use a status `CHECK` constraint rather than inventing a Postgres enum type; keep the migration simple and safely re-runnable
  - [x] Add dequeue/retry indexes, especially one that supports `WHERE job_type = ‘ingest’ AND status = ‘queued’ AND available_at <= now() ORDER BY created_at ASC`
  - [x] Preserve idempotency with `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, and guarded `ALTER TABLE` only where required
  - [x] Replace the obsolete expectation in [tests/store/test_migrations.py](/Users/iain.livingstone/Development/CoS/cos/tests/store/test_migrations.py) that `002_jobs.sql` contains no executable SQL

- [x] Task 2: Add job queue records and store helpers without creating a second ingest path (AC: #1, #2, #4)
  - [x] Extend [src/cos/store/models.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/store/models.py) with queue-facing dataclasses such as `JobRecord` and, if helpful, a typed ingest payload wrapper
  - [x] Add enqueue/claim/update helpers in [src/cos/store/db.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/store/db.py): `enqueue_job(...)`, `claim_next_job(...)`, `mark_job_succeeded(...)`, `mark_job_retryable_failure(...)`, `mark_job_terminal_failure(...)`, `requeue_stale_jobs(...)`
  - [x] Implement job claiming with a single transactional claim query using `FOR UPDATE SKIP LOCKED`; do not use an in-memory queue or a separate broker
  - [x] Keep payload storage in `jsonb`, but store metadata only; do not put raw attachment bytes or large base64 blobs into the `jobs` table
  - [x] Define the payload contract around a shared staged file path plus canonical provenance fields:
    - [x] `staged_path`
    - [x] `source_type`
    - [x] `source_locator`
    - [x] `source_alias`
    - [x] optional `metadata`

- [x] Task 3: Refactor the ingest service boundary so worker jobs reuse the existing canonical identity decision engine (AC: #2, #3, #4)
  - [x] Update [src/cos/ingestion/pipeline.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/ingestion/pipeline.py) so the current file-based `run_pipeline(...)` becomes a thin wrapper over a more general source-aware ingest function
  - [x] The shared ingest core must accept `staged_path`, `source_type`, `source_locator`, and `source_alias` explicitly instead of hardcoding `source_type = "file"` and `source_locator = str(source_path)`
  - [x] Keep [src/cos/services/ingestion.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/ingestion.py) working for CLI ingest with no user-visible behaviour change
  - [x] Reuse, not duplicate, the existing canonical identity pieces:
    - [x] `check_canonical_identity()` in [src/cos/ingestion/identity.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/ingestion/identity.py)
    - [x] `store_document_canonical()` and `link_new_source_to_existing_blob()` in [src/cos/store/db.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/store/db.py)
    - [x] existing `IngestOutcome` values and operator-facing result messages
  - [x] Ensure the worker path reports the same four ingest outcomes already locked in Story 6.3

- [x] Task 4: Add a thin jobs service and a dedicated worker process (AC: #2, #3, #4)
  - [x] Create [src/cos/services/jobs.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/jobs.py) as the public orchestration layer for queue operations
  - [x] Create [src/cos/worker.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/worker.py) as the long-running worker entry point
  - [x] Add a project script in [pyproject.toml](/Users/iain.livingstone/Development/CoS/cos/pyproject.toml): `cos-worker = "cos.worker:run"`
  - [x] Implement a simple sequential worker loop first: claim one ingest job, process it, update status, sleep briefly when the queue is empty
  - [x] Add a test-friendly `run_once` or equivalent single-iteration mode so worker behaviour can be exercised without infinite loops or real sleeps
  - [x] On startup, call `requeue_stale_jobs(...)` before normal processing so interrupted `running` jobs become available again
  - [x] Use structured JSON logs with valid existing components only:
    - [x] queue lifecycle / worker processing: `component: "ingestion"`
    - [x] connector enqueue/degraded source behaviour in later stories: `component: "connector"`
  - [x] Do not invent a new log component such as `"worker"` because it is not in the project’s allowed component list

- [x] Task 5: Wire the worker into runtime without destabilising the MCP server path (AC: #4)
  - [x] Update [docker-compose.yml](/Users/iain.livingstone/Development/CoS/cos/docker-compose.yml) to add a separate `worker` service based on the same image as `cos`
  - [x] Mount the same shared volumes the worker needs to see staged files and future connector auth state, including `./data:/data`, `./config.yaml:/app/config.yaml:ro`, `./role_packs:/app/role_packs:ro`, `./local/certs:/certs:ro`, and `./tokens:/app/tokens`
  - [x] Run the worker service with `uv run cos-worker`
  - [x] Keep MCP retrieval isolated: a worker failure must not take down the `cos` service or change the existing MCP server health path
  - [x] Do not expand `cos status`, `get_status`, or manual-testing scope in this story beyond what is necessary to keep the platform bootable; fuller operator validation belongs to Stories 6.11 and 6.12

- [x] Task 6: Add automated coverage for schema, queue semantics, worker retry, and ingest-path reuse (AC: #1, #2, #3, #4)
  - [x] Extend [tests/store/test_migrations.py](/Users/iain.livingstone/Development/CoS/cos/tests/store/test_migrations.py) to assert the `jobs` table and required columns exist after migrations run
  - [x] Add [tests/store/test_jobs.py](/Users/iain.livingstone/Development/CoS/cos/tests/store/test_jobs.py) for enqueue, claim order, retry transition, stale-job requeue, and terminal-failure behaviour
  - [x] Add [tests/services/test_jobs_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_jobs_service.py) for service-layer enqueue and process orchestration
  - [x] Add [tests/worker/test_worker.py](/Users/iain.livingstone/Development/CoS/cos/tests/worker/test_worker.py) for `run_once`, success, retryable failure, terminal failure, and stale job recovery on startup
  - [x] Extend [tests/ingestion/test_pipeline.py](/Users/iain.livingstone/Development/CoS/cos/tests/ingestion/test_pipeline.py) and [tests/services/test_ingestion_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_ingestion_service.py) to cover the new shared source-aware ingest path while keeping existing CLI ingest behaviour unchanged
  - [x] Keep all tests offline: no Gmail API, Calendar API, browser auth, or external queue service

### Review Findings

- [x] [Review][Patch] Claimed jobs are not durably visible as `running` because claim, ingest, and terminal update share one uncommitted connection, so status tracking and startup stale-job recovery do not work as designed [src/cos/services/jobs.py:41]
- [x] [Review][Patch] Retry backoff is calculated from the claim transaction start time rather than the failure time, so long-running failures can be re-queued immediately instead of waiting for the intended delay [src/cos/store/db.py:715]
- [x] [Review][Patch] Malformed `jobs.payload` rows can raise before the retry/terminal handling block and crash the worker loop instead of being recorded as a failed job [src/cos/services/jobs.py:50]
- [x] [Review][Defer] `gen_random_uuid()` remains an implicit migration dependency in the new jobs table, but that pattern is pre-existing across earlier migrations in this repo [src/cos/store/migrations/002_jobs.sql:3] — deferred, pre-existing

## Dev Notes

### Story Positioning

Story 6.7 is the **async boundary story** for Epic 6.

- Stories 6.1 through 6.5 hardened canonical identity, deduplication, provenance, citations, and migration/backfill
- Story 6.6 added the Google OAuth foundation and auth-capable connector helpers:
  - [src/cos/connectors/google_auth.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/google_auth.py)
  - [src/cos/connectors/gmail.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/gmail.py)
  - [src/cos/connectors/calendar.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/calendar.py)
- Story 6.7 must now separate **content discovery** from **content ingestion**
- Stories 6.8 and 6.9 should enqueue work into this queue instead of calling the ingest pipeline inline

This story is not the Gmail connector, not the Calendar connector, and not the scheduler. It creates the background ingest substrate those later stories will rely on.

### Critical Guardrail: Do Not Create a Second Ingest Pipeline

The current implementation already contains the canonical ingest path:

- [src/cos/ingestion/identity.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/ingestion/identity.py) determines the four locked outcomes
- [src/cos/ingestion/pipeline.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/ingestion/pipeline.py) performs extract -> chunk -> embed -> canonical store
- [src/cos/store/db.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/store/db.py) persists canonical rows and provenance links

The worker must call into that same decision path. Do not create a connector-only ingest function with separate dedupe, separate provenance rules, or separate store writes. The right move here is a small refactor that makes the existing pipeline accept source metadata overrides while preserving current CLI behaviour.

### Critical Guardrail: Queue Payloads Must Reference Shared Staged Files, Not Inline Bytes

Future connectors may run in a different process or service than the queue worker. Because of that:

- payloads should carry a `staged_path` plus metadata, not raw file bytes in `jsonb`
- staged files must live on a volume shared between producer and worker, which in this repo is `./data:/data`
- do not stage to container-local `/tmp` if another service will need to read the file later

A safe forward-compatible payload shape is:

```json
{
  "staged_path": "/data/connector-staging/2026-05-06/<uuid>.pdf",
  "source_type": "gmail_attachment",
  "source_locator": "gmail://message/<message-id>/attachment/<attachment-id>",
  "source_alias": "board-pack.pdf",
  "metadata": {
    "connector": "gmail"
  }
}
```

Story 6.7 does not need to implement Gmail staging itself, but it must lock the worker contract so 6.8 and 6.9 can build on it cleanly.

### Current Code Seams To Reuse

#### CLI ingest path today

[src/cos/services/ingestion.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/ingestion.py) currently opens a DB connection and calls `run_pipeline(source_path, config, conn)`. That is the seam to preserve.

#### Canonical identity engine today

[src/cos/ingestion/identity.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/ingestion/identity.py) already exposes the exact four outcomes this story must preserve:

- `new_content`
- `changed_content`
- `new_source_known_content`
- `unchanged`

The worker must surface one of those outcomes for every successfully processed ingest job.

#### Migration runner behaviour today

[src/cos/store/db.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/store/db.py) reruns every SQL file in sorted order on every startup and skips only files with no executable SQL. That means the new `002_jobs.sql` must be idempotent for:

- fresh databases
- already-migrated databases
- repeated startup runs

Do not write one-shot SQL that assumes `002_jobs.sql` runs only once.

### Suggested Jobs Table Contract

Keep the queue deliberately small and explicit. A good table contract for this story is:

- `job_type text not null`
- `status text not null`
- `payload jsonb not null`
- `attempt_count integer not null default 0`
- `max_attempts integer not null default 3`
- `available_at timestamptz not null default now()`
- `started_at timestamptz null`
- `completed_at timestamptz null`
- `last_error text null`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Recommended status set:

- `queued`
- `running`
- `succeeded`
- `failed`

Recommended retry semantics:

- claim increments `attempt_count` and sets `status = 'running'`
- retryable failure moves the job back to `queued`, updates `available_at`, and stores `last_error`
- final failure sets `status = 'failed'` and `completed_at = now()`
- success sets `status = 'succeeded'` and `completed_at = now()`

### Safe Claim Pattern

Use Postgres row locking for queue claims. The worker should not:

- select a candidate row and then update it in a separate non-locking step
- depend on in-memory mutexes
- depend on APScheduler job stores for queue semantics

Prefer a single transactional claim pattern built around `FOR UPDATE SKIP LOCKED`, for example:

```sql
WITH candidate AS (
    SELECT id
    FROM jobs
    WHERE job_type = 'ingest'
      AND status = 'queued'
      AND available_at <= now()
    ORDER BY created_at ASC
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
UPDATE jobs j
SET status = 'running',
    attempt_count = j.attempt_count + 1,
    started_at = now(),
    updated_at = now()
FROM candidate
WHERE j.id = candidate.id
RETURNING j.id, j.payload, j.attempt_count, j.max_attempts;
```

This is the correct queue-like use of `SKIP LOCKED`; it is not appropriate for general-purpose result consistency, but it is appropriate for multi-consumer queue claims. [Source: PostgreSQL `SELECT` locking clause docs](https://www.postgresql.org/docs/current/sql-select.html)

### Worker Runtime Guidance

Start with the simplest reliable worker:

- one process
- one claimed job at a time
- separate DB connection per processing attempt
- brief sleep when no job is available
- `run_once` hook for tests

Do not introduce parallel fan-out in this story. The current codebase and acceptance criteria do not require it, and Psycopg notes that operations on one shared `AsyncConnection` are serialized anyway. If concurrency is added later, use multiple connections rather than multiple tasks sharing one connection for heavy queue work. [Source: Psycopg async/concurrency docs](https://www.psycopg.org/psycopg3/docs/advanced/async.html)

### Crash Recovery Guidance

Acceptance criterion #4 is about **job recovery**, not only DB atomicity.

Required behaviour:

- if the worker dies after marking a job `running` but before terminal update, the next worker startup must return that work to the queue
- requeued work must not expose partial canonical rows to users

Why partial canonical rows are manageable here:

- unchanged and known-content/new-source outcomes are already small, explicit DB operations
- new/changed-content writes funnel through canonical store helpers that already use transactions

The missing piece is job-state recovery. Implement `requeue_stale_jobs(...)` using a conservative timeout and run it at worker startup before normal claiming.

### Architecture Compliance

- Keep module boundaries intact: connector code in later stories should call [src/cos/services/jobs.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/jobs.py), not `cos.store.db` or `cos.ingestion.pipeline` directly
- Keep config loading through [src/cos/config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py) only
- Keep all DB and external I/O async
- Keep MCP retrieval independent from queue/worker failure
- Keep JSON logging to stdout; no `print()` inside worker internals
- Do not add Redis, Celery, RQ, RabbitMQ, or any other new queue infrastructure; the architecture explicitly chose Postgres for this phase

### Library / Framework Notes

- Use the already-installed `psycopg` / `psycopg-pool` stack for queue persistence; do not add another DB client
- Do not use APScheduler as the ingest queue. APScheduler remains appropriate for later scheduled jobs, but its docs describe job stores/executors for scheduler workloads, not as a replacement for this Postgres-backed ingest queue. Job stores also should not be shared between schedulers. [Source: APScheduler 3 user guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html)
- No new dependency should be needed for Story 6.7

### Project Structure Notes

There are a few important repo realities that differ from the older architecture text and are easy for a dev agent to miss:

- [src/cos/connectors/](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors) is no longer stub-only; Story 6.6 already added auth-capable Gmail/Calendar modules
- [src/cos/store/migrations/](/Users/iain.livingstone/Development/CoS/cos/src/cos/store/migrations) now contains `001_initial.sql`, `002_jobs.sql`, `003_search_indexes.sql`, and `004_canonical_identity.sql`
- [src/cos/ingestion/identity.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/ingestion/identity.py) exists and is the canonical outcome engine; older architecture snapshots do not mention it
- there is no `project-context.md` file in this repo today

Design the story implementation around the real codebase, not around stale assumptions from earlier planning drafts.

### Suggested File Touchpoints

- [src/cos/store/migrations/002_jobs.sql](/Users/iain.livingstone/Development/CoS/cos/src/cos/store/migrations/002_jobs.sql)
- [src/cos/store/db.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/store/db.py)
- [src/cos/store/models.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/store/models.py)
- [src/cos/ingestion/pipeline.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/ingestion/pipeline.py)
- [src/cos/services/ingestion.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/ingestion.py)
- [src/cos/services/jobs.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/jobs.py)
- [src/cos/worker.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/worker.py)
- [pyproject.toml](/Users/iain.livingstone/Development/CoS/cos/pyproject.toml)
- [docker-compose.yml](/Users/iain.livingstone/Development/CoS/cos/docker-compose.yml)
- [tests/store/test_migrations.py](/Users/iain.livingstone/Development/CoS/cos/tests/store/test_migrations.py)
- [tests/store/test_jobs.py](/Users/iain.livingstone/Development/CoS/cos/tests/store/test_jobs.py)
- [tests/services/test_jobs_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_jobs_service.py)
- [tests/worker/test_worker.py](/Users/iain.livingstone/Development/CoS/cos/tests/worker/test_worker.py)
- [tests/ingestion/test_pipeline.py](/Users/iain.livingstone/Development/CoS/cos/tests/ingestion/test_pipeline.py)
- [tests/services/test_ingestion_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_ingestion_service.py)

### Previous Story Intelligence (Story 6.6)

Story 6.6 is currently `review`, and its implementation already landed the core Google auth scaffolding:

- `google_oauth` config is optional and backward-compatible
- `tokens/` is mounted into the `cos` container
- Gmail and Calendar connector helper modules now load refreshable credentials

Implications for 6.7:

- do not revisit OAuth or token storage here
- do not move token logic into the queue worker
- future connected-source stories should discover content with those auth helpers, stage artifacts to shared storage, and enqueue ingest jobs into the queue built here

### Git / Recent Work Intelligence

Recent Epic 6 work is sequential and should be extended, not rewritten:

- `46f9e70` — Implement story 6.6 OAuth authentication setup
- `de4684f` — Implement story 6.5 migration backfill and operator recovery
- `9aea810` — Implement story 6.4 citation and listing updates using source alias

Follow the patterns those stories established:

- additive migrations
- structured operator-facing CLI output
- explicit tests for each acceptance criterion
- narrow scope per story

### Non-Goals

- No Gmail polling loop yet
- No Calendar fetch loop yet
- No MCP `ingest_document` tool yet
- No new retrieval or citation changes
- No role-pack changes
- No scheduler / daily brief work
- No Redis/Celery/external message bus
- No attempt at multi-worker horizontal scaling beyond safe `SKIP LOCKED` semantics

### References

- [Epic 6 stories and ACs in epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)
- [Architecture: ingestion trigger, service boundaries, logging, and queue design](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
- [Architecture diagrams: jobs table and phase evolution](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture-diagrams.md)
- [PRD: component isolation and ingestion-worker expectations](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)
- [Previous story: 6.6 OAuth authentication setup](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-6-oauth-authentication-setup-for-gmail-and-calendar.md)
- [PostgreSQL `SKIP LOCKED` documentation](https://www.postgresql.org/docs/current/sql-select.html)
- [Psycopg async/concurrency documentation](https://www.psycopg.org/psycopg3/docs/advanced/async.html)
- [APScheduler 3 user guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- `enqueue_job` initially passed Python `datetime.now(timezone.utc)` as `available_at`, causing the condition `available_at <= now()` in the claim query to evaluate False due to clock skew between Python host and Postgres container. Fixed by letting the database supply `available_at` via `DEFAULT now()` when no explicit value is given.
- CTE claim query (`WITH candidate AS (... FOR UPDATE SKIP LOCKED) UPDATE jobs FROM candidate`) required explicit table-qualifier `j.` on all RETURNING columns to avoid ambiguous column error.

### Completion Notes List

- Implemented real `002_jobs.sql` schema: `jobs` table with status CHECK constraint, `idx_jobs_dequeue` partial index, `idx_jobs_running_started_at` partial index. All idempotent.
- Added `JobRecord` and `IngestJobPayload` dataclasses to `models.py`.
- Added six queue helpers to `db.py`: `enqueue_job`, `claim_next_job` (CTE with FOR UPDATE SKIP LOCKED), `mark_job_succeeded`, `mark_job_retryable_failure`, `mark_job_terminal_failure`, `requeue_stale_jobs`.
- Refactored `pipeline.py`: `run_pipeline_from_source` is the new shared ingest core accepting explicit source metadata; `run_pipeline` is a thin wrapper that derives `source_type="file"` — no CLI behaviour change.
- Created `services/jobs.py`: `submit_ingest_job` (enqueue) and `process_next_ingest_job` (claim + call pipeline + update status).
- Created `worker.py`: `run_once` (single iteration, test-friendly), `recover_stale_jobs`, `_run_loop` (startup recovery + sequential claim loop), `run` (entry point).
- Added `cos-worker` script to `pyproject.toml`.
- Added `worker` service to `docker-compose.yml` with same volumes as `cos`; isolated from MCP server.
- All 262 tests pass (13 new in `test_jobs.py`, 7 new in `test_jobs_service.py`, 7 new in `test_worker.py`, 3 new pipeline tests, migration tests updated).

### File List

- `_bmad-output/implementation-artifacts/6-7-jobs-queue-and-background-ingestion-worker.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `src/cos/store/migrations/002_jobs.sql`
- `src/cos/store/models.py`
- `src/cos/store/db.py`
- `src/cos/ingestion/pipeline.py`
- `src/cos/services/jobs.py`
- `src/cos/worker.py`
- `pyproject.toml`
- `docker-compose.yml`
- `tests/store/conftest.py`
- `tests/store/test_migrations.py`
- `tests/store/test_jobs.py`
- `tests/services/conftest.py`
- `tests/services/test_jobs_service.py`
- `tests/ingestion/conftest.py`
- `tests/ingestion/test_pipeline.py`
- `tests/worker/__init__.py`
- `tests/worker/conftest.py`
- `tests/worker/test_worker.py`
