-- 004_canonical_identity.sql

-- Immutable content blobs — deduplicated by SHA-256
CREATE TABLE IF NOT EXISTS content_blobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sha256 TEXT NOT NULL,
    byte_size BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT content_blobs_sha256_unique UNIQUE (sha256)
);

-- Source provenance — where content came from
CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type TEXT NOT NULL,
    source_locator TEXT NOT NULL,
    source_alias TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT sources_type_locator_unique UNIQUE (source_type, source_locator)
);

-- Source-version linkage — one observation produces one document_version
CREATE TABLE IF NOT EXISTS source_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    document_version_id UUID NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
    content_blob_id UUID NOT NULL REFERENCES content_blobs(id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT source_versions_source_document_unique UNIQUE (source_id, document_version_id)
);

-- Link document versions to their content blob (nullable until backfill in Story 6.5)
ALTER TABLE document_versions
ADD COLUMN IF NOT EXISTS content_blob_id UUID REFERENCES content_blobs(id) ON DELETE CASCADE;

-- Link chunks to their document version (nullable until backfill in Story 6.5)
ALTER TABLE chunks
ADD COLUMN IF NOT EXISTS document_version_id UUID REFERENCES document_versions(id) ON DELETE CASCADE;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_content_blobs_sha256
    ON content_blobs(sha256);

CREATE INDEX IF NOT EXISTS idx_sources_type_locator
    ON sources(source_type, source_locator);

CREATE INDEX IF NOT EXISTS idx_source_versions_source_id
    ON source_versions(source_id);

CREATE INDEX IF NOT EXISTS idx_source_versions_document_version_id
    ON source_versions(document_version_id);

CREATE INDEX IF NOT EXISTS idx_source_versions_content_blob_id
    ON source_versions(content_blob_id);

CREATE INDEX IF NOT EXISTS idx_chunks_document_version_id
    ON chunks(document_version_id);

CREATE INDEX IF NOT EXISTS idx_document_versions_content_blob_id
    ON document_versions(content_blob_id);
