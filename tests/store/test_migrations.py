from pathlib import Path


def test_migration_files_exist() -> None:
    base = Path(__file__).parent.parent.parent / "src" / "cos" / "store"
    migrations_dir = base / "migrations"
    assert (migrations_dir / "001_initial.sql").exists()
    assert (migrations_dir / "002_jobs.sql").exists()
