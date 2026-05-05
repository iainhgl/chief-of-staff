from pathlib import Path

from conftest import TEST_DSN

from cos.store.db import run_migrations


def test_migration_files_exist() -> None:
    base = Path(__file__).parent.parent.parent / "src" / "cos" / "store"
    migrations_dir = base / "migrations"
    assert (migrations_dir / "001_initial.sql").exists()
    assert (migrations_dir / "002_jobs.sql").exists()
    assert (migrations_dir / "003_search_indexes.sql").exists()
    assert (migrations_dir / "004_canonical_identity.sql").exists()


async def test_run_migrations_creates_all_tables(migrated_db, db_conn) -> None:
    result = await db_conn.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = ANY(%s)",
        (
            [
                "documents",
                "document_versions",
                "chunks",
                "embeddings",
                "content_blobs",
                "sources",
                "source_versions",
            ],
        ),
    )
    tables = {row[0] for row in await result.fetchall()}
    assert tables == {
        "documents",
        "document_versions",
        "chunks",
        "embeddings",
        "content_blobs",
        "sources",
        "source_versions",
    }


async def test_run_migrations_is_idempotent(migrated_db, db_conn) -> None:
    await run_migrations(TEST_DSN)


async def test_documents_table_has_status_column(migrated_db, db_conn) -> None:
    result = await db_conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'documents' AND column_name = 'status'"
    )
    assert await result.fetchone() is not None


async def test_embeddings_table_has_model_and_provider_columns(
    migrated_db,
    db_conn,
) -> None:
    result = await db_conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'embeddings' AND column_name = ANY(%s)",
        (["model", "provider"],),
    )
    columns = {row[0] for row in await result.fetchall()}
    assert columns == {"model", "provider"}


async def test_chunks_table_has_content_tsv_column(migrated_db, db_conn) -> None:
    result = await db_conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'chunks' AND column_name = 'content_tsv'"
    )
    assert await result.fetchone() is not None


async def test_chunks_table_has_content_tsv_index(migrated_db, db_conn) -> None:
    result = await db_conn.execute(
        "SELECT indexname FROM pg_indexes "
        "WHERE schemaname = 'public' AND tablename = 'chunks' "
        "AND indexname = 'idx_chunks_content_tsv'"
    )
    assert await result.fetchone() is not None


async def test_content_blobs_sha256_unique_constraint_exists(
    migrated_db,
    db_conn,
) -> None:
    result = await db_conn.execute(
        "SELECT conname FROM pg_constraint "
        "WHERE conrelid = 'content_blobs'::regclass AND contype = 'u'"
    )
    names = {row[0] for row in await result.fetchall()}
    assert "content_blobs_sha256_unique" in names


async def test_sources_type_locator_unique_constraint_exists(
    migrated_db,
    db_conn,
) -> None:
    result = await db_conn.execute(
        "SELECT conname FROM pg_constraint "
        "WHERE conrelid = 'sources'::regclass AND contype = 'u'"
    )
    names = {row[0] for row in await result.fetchall()}
    assert "sources_type_locator_unique" in names


async def test_document_versions_has_content_blob_id_column(
    migrated_db,
    db_conn,
) -> None:
    result = await db_conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'document_versions' AND column_name = 'content_blob_id'"
    )
    assert await result.fetchone() is not None


async def test_chunks_has_document_version_id_column(migrated_db, db_conn) -> None:
    result = await db_conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'chunks' AND column_name = 'document_version_id'"
    )
    assert await result.fetchone() is not None


async def test_source_versions_fks_reference_correct_tables(
    migrated_db,
    db_conn,
) -> None:
    result = await db_conn.execute(
        "SELECT conname, confrelid::regclass::text "
        "FROM pg_constraint "
        "WHERE conrelid = 'source_versions'::regclass AND contype = 'f'"
    )
    constraints = {row[0]: row[1] for row in await result.fetchall()}
    assert constraints == {
        "source_versions_source_id_fkey": "sources",
        "source_versions_document_version_id_fkey": "document_versions",
        "source_versions_content_blob_id_fkey": "content_blobs",
    }


async def test_source_versions_source_document_unique_constraint_exists(
    migrated_db,
    db_conn,
) -> None:
    result = await db_conn.execute(
        "SELECT conname FROM pg_constraint "
        "WHERE conrelid = 'source_versions'::regclass AND contype = 'u'"
    )
    names = {row[0] for row in await result.fetchall()}
    assert "source_versions_source_document_unique" in names


async def test_canonical_identity_migration_is_idempotent(
    migrated_db,
    db_conn,
) -> None:
    await run_migrations(TEST_DSN)


def test_jobs_migration_has_no_executable_sql() -> None:
    base = Path(__file__).parent.parent.parent / "src" / "cos" / "store"
    sql = (base / "migrations" / "002_jobs.sql").read_text()
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped:
            assert stripped.startswith("--"), f"Unexpected executable SQL: {line!r}"


def test_search_indexes_migration_is_idempotent() -> None:
    base = Path(__file__).parent.parent.parent / "src" / "cos" / "store"
    sql = (base / "migrations" / "003_search_indexes.sql").read_text()
    assert "ADD COLUMN IF NOT EXISTS content_tsv" in sql
    assert "CREATE INDEX IF NOT EXISTS idx_chunks_content_tsv" in sql
