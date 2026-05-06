# Migration Backfill Guide

## Purpose

`cos migrate` backfills legacy Phase 1 path-centric documents into the canonical
identity tables introduced in Epic 6. It creates any missing `content_blobs`,
`sources`, and `source_versions` rows for pre-canonical documents, fills
`document_versions.content_blob_id`, and links surviving chunks to their current
document version.

## When To Run

Run this before enabling Epic 6 connected-source stories such as Gmail,
Calendar, or MCP ingest. It is also safe to rerun at any time because the
backfill is idempotent and uses conflict-safe inserts.

## Pre-Migration Baseline

Record the current document inventory before you migrate:

```bash
docker compose run cos cos docs
```

Note the total document count. You will compare this count again after the
migration completes.

## Run The Migration

```bash
docker compose run cos cos migrate
```

Expected success output:

```text
Migration complete: X document(s) backfilled, Y already canonical.
```

`X` counts documents that needed canonical backfill during this run. `Y` counts
documents that were already canonical before the run started.

## Verify After Migration

Run the document listing again:

```bash
docker compose run cos cos docs
```

Verify all of the following:

- The total document count matches the pre-migration baseline.
- Every row shows a readable `SOURCE ALIAS`.
- Previously ingested documents are still visible through `cos docs`.

## Recovery

### If The Migration Fails Mid-Run

Rerun the same command:

```bash
docker compose run cos cos migrate
```

The migration is safe to rerun. Inserts use conflict-safe behavior, so already
backfilled records are reused and only unfinished legacy documents are migrated.

### If Counts Differ Or A Document Still Looks Legacy

Run these diagnostic queries inside Postgres:

```sql
SELECT COUNT(*)
FROM document_versions
WHERE content_blob_id IS NULL;

SELECT COUNT(*)
FROM chunks
WHERE document_version_id IS NULL;

SELECT d.source_path
FROM documents d
WHERE EXISTS (
    SELECT 1
    FROM document_versions dv
    WHERE dv.document_id = d.id
      AND NOT EXISTS (
          SELECT 1
          FROM source_versions sv
          WHERE sv.document_version_id = dv.id
      )
);
```

If any of these queries return unexpected rows, rerun `cos migrate` first. If
the same rows remain, capture `cos logs cos` and inspect the affected document
paths before making manual changes.

### Full Rollback

Only use rollback if the canonical tables are clearly corrupted and rerunning
the migration does not recover the store.

1. Stop any ingest jobs that might write to the database.
2. Connect to Postgres.
3. Remove derivative canonical rows and reset the nullable foreign keys:

```sql
-- Remove canonical linkages first (source_versions references all three canonical tables)
DELETE FROM source_versions;
-- Null out FK columns so the canonical tables can be cleared safely
UPDATE document_versions SET content_blob_id = NULL;
UPDATE chunks SET document_version_id = NULL;
-- Clear the canonical tables (no remaining FK references)
TRUNCATE content_blobs;
TRUNCATE sources;
```

4. Rerun the migration:

```bash
docker compose run cos cos migrate
```

Because the canonical tables are derived from `documents`, `document_versions`,
and `chunks`, rerunning the backfill rebuilds the canonical identity layer from
the preserved Phase 1 records.
