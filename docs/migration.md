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
docker compose exec cos uv run cos docs
```

Note the total document count. You will compare this count again after the
migration completes.

## Run The Migration

```bash
docker compose exec cos uv run cos migrate
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
docker compose exec cos uv run cos docs
```

Verify all of the following:

- The total document count matches the pre-migration baseline.
- Every row shows a readable `SOURCE ALIAS` — no row should be blank or show a raw UUID.
- Previously ingested documents are still visible through `cos docs`.

For a machine-readable check, confirm the JSON fields match the Epic 6 contract:

```bash
docker compose exec cos uv run cos docs --json
```

Each object must include `id`, `source_alias`, `source_locator`, `ingested_at`,
`current_version`, and `chunk_count`. No `source_path` field should appear as a
primary provenance field — legacy records that were not backfilled will fall back
to using the stored file path as their locator, which is the expected pre-migration
compatibility behaviour and not an error.

## Recovery

### If The Migration Fails Mid-Run

Rerun the same command:

```bash
docker compose exec cos uv run cos migrate
```

The migration is safe to rerun. Inserts use conflict-safe behavior, so already
backfilled records are reused and only unfinished legacy documents are migrated.

### If Counts Differ Or A Document Still Looks Legacy

Run these diagnostic queries inside Postgres to pinpoint what is uncanonical:

```sql
-- document versions with no canonical blob link
SELECT COUNT(*)
FROM document_versions
WHERE content_blob_id IS NULL;

-- chunks not linked to a document version
SELECT COUNT(*)
FROM chunks
WHERE document_version_id IS NULL;

-- documents with at least one version not linked to a source record
SELECT COUNT(*)
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

If any of these queries return non-zero counts, rerun `cos migrate` first. The
migration is safe to rerun — it only touches records that still need backfill.

If the same rows remain after a second migration run, capture the logs and
inspect before making manual changes:

```bash
docker compose logs cos --tail=100
```

Identify any error messages referencing specific documents, then decide whether
to rerun migration or proceed to the full rollback procedure below. Do not
attempt manual SQL repair unless rerunning the migration cannot resolve the
issue.

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
docker compose exec cos uv run cos migrate
```

Because the canonical tables are derived from `documents`, `document_versions`,
and `chunks`, rerunning the backfill rebuilds the canonical identity layer from
the preserved Phase 1 records.
