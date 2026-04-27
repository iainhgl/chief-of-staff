from pathlib import Path

from conftest import TEST_DSN

from cos.store.db import run_migrations


def test_migration_files_exist() -> None:
    base = Path(__file__).parent.parent.parent / "src" / "cos" / "store"
    migrations_dir = base / "migrations"
    assert (migrations_dir / "001_initial.sql").exists()
    assert (migrations_dir / "002_jobs.sql").exists()
    assert (migrations_dir / "003_search_indexes.sql").exists()


async def test_run_migrations_creates_all_tables(migrated_db, db_conn) -> None:
    result = await db_conn.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = ANY(%s)",
        (["documents", "document_versions", "chunks", "embeddings"],),
    )
    tables = {row[0] for row in await result.fetchall()}
    assert tables == {"documents", "document_versions", "chunks", "embeddings"}


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
