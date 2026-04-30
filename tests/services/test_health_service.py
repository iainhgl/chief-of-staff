from unittest.mock import AsyncMock, patch

import pytest

from cos.services.health import ComponentStatus, HealthService


# These fixtures override the autouse clean_tables(migrated_db) fixtures in
# tests/services/conftest.py so that health service tests can run without a live DB.
@pytest.fixture
async def migrated_db() -> None:
    yield


@pytest.fixture(autouse=True)
async def clean_tables() -> None:
    yield


async def test_check_all_returns_all_component_statuses_in_order() -> None:
    svc = HealthService(
        db_dsn="postgresql://user:pass@localhost/db",
        tika_url="http://tika:9998",
        role_pack_path="role_packs/chro.yaml",
    )
    postgres = ComponentStatus("Postgres", True, "healthy")
    tika = ComponentStatus("Tika", True, "healthy")
    mcp_server = ComponentStatus("MCP server", True, "listening on stdio")
    role_pack = ComponentStatus("Role pack", True, "CHRO loaded")
    database = ComponentStatus("Database", True, "connected (3 documents indexed)")

    with (
        patch.object(svc, "_check_postgres", new=AsyncMock(return_value=postgres)),
        patch.object(svc, "_check_tika", new=AsyncMock(return_value=tika)),
        patch.object(svc, "_check_mcp_server", return_value=mcp_server),
        patch.object(svc, "_check_role_pack", return_value=role_pack),
        patch.object(svc, "_check_database", new=AsyncMock(return_value=database)),
    ):
        result = await svc.check_all()

    assert result == [postgres, tika, mcp_server, role_pack, database]


async def test_check_postgres_returns_healthy_status() -> None:
    svc = HealthService(
        db_dsn="postgresql://user:pass@localhost/db",
        tika_url="http://tika:9998",
    )
    mock_conn = AsyncMock()
    mock_conn.__aenter__.return_value = mock_conn
    mock_conn.__aexit__.return_value = False
    mock_conn.execute = AsyncMock(return_value=None)

    with patch(
        "cos.services.health.psycopg.AsyncConnection.connect",
        new=AsyncMock(return_value=mock_conn),
    ):
        result = await svc._check_postgres()

    assert result == ComponentStatus("Postgres", True, "healthy")


async def test_check_postgres_returns_recovery_hint_on_exception() -> None:
    svc = HealthService(
        db_dsn="postgresql://bad:bad@localhost/db",
        tika_url="http://tika:9998",
    )
    with patch(
        "cos.services.health.psycopg.AsyncConnection.connect",
        side_effect=Exception("refused"),
    ):
        result = await svc._check_postgres()

    assert result == ComponentStatus(
        "Postgres",
        False,
        "container not running",
        "Run: cos restart",
    )


async def test_check_tika_returns_healthy_on_200() -> None:
    svc = HealthService(
        db_dsn="postgresql://user:pass@localhost/db",
        tika_url="http://tika:9998",
    )
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_http = AsyncMock()
    mock_http.__aenter__.return_value = mock_http
    mock_http.__aexit__.return_value = False
    mock_http.get = AsyncMock(return_value=mock_resp)

    with patch("cos.services.health.httpx.AsyncClient", return_value=mock_http):
        result = await svc._check_tika()

    assert result == ComponentStatus("Tika", True, "healthy")


async def test_check_tika_returns_unhealthy_status_on_500() -> None:
    svc = HealthService(
        db_dsn="postgresql://user:pass@localhost/db",
        tika_url="http://tika:9998",
    )
    mock_resp = AsyncMock()
    mock_resp.status_code = 500
    mock_http = AsyncMock()
    mock_http.__aenter__.return_value = mock_http
    mock_http.__aexit__.return_value = False
    mock_http.get = AsyncMock(return_value=mock_resp)

    with patch("cos.services.health.httpx.AsyncClient", return_value=mock_http):
        result = await svc._check_tika()

    assert result == ComponentStatus(
        "Tika",
        False,
        "service unhealthy",
        "Run: cos restart",
    )


async def test_check_tika_returns_recovery_hint_on_exception() -> None:
    svc = HealthService(
        db_dsn="postgresql://user:pass@localhost/db",
        tika_url="http://tika:9998",
    )
    mock_http = AsyncMock()
    mock_http.__aenter__.side_effect = Exception("timeout")
    mock_http.__aexit__.return_value = False

    with patch("cos.services.health.httpx.AsyncClient", return_value=mock_http):
        result = await svc._check_tika()

    assert result == ComponentStatus(
        "Tika",
        False,
        "service not responding",
        "Run: cos restart",
    )


def test_check_mcp_server_returns_healthy_status() -> None:
    svc = HealthService(
        db_dsn="postgresql://user:pass@localhost/db",
        tika_url="http://tika:9998",
    )

    result = svc._check_mcp_server()

    assert result == ComponentStatus("MCP server", True, "listening on stdio")


def test_check_role_pack_returns_not_configured_when_path_missing() -> None:
    svc = HealthService(
        db_dsn="postgresql://user:pass@localhost/db",
        tika_url="http://tika:9998",
        role_pack_path=None,
    )

    result = svc._check_role_pack()

    assert result == ComponentStatus(
        "Role pack",
        False,
        "not configured",
        "Set role_pack.path in config.yaml",
    )


def test_check_role_pack_returns_file_not_found_message(tmp_path) -> None:
    missing_path = str(tmp_path / "missing-role-pack.yaml")
    svc = HealthService(
        db_dsn="postgresql://user:pass@localhost/db",
        tika_url="http://tika:9998",
        role_pack_path=missing_path,
    )

    result = svc._check_role_pack()

    assert result == ComponentStatus(
        "Role pack",
        False,
        "not loaded",
        f"file not found: {missing_path}. Check config.yaml role_pack_path.",
    )


def test_check_role_pack_returns_invalid_yaml_message(tmp_path) -> None:
    role_pack_path = tmp_path / "broken-role-pack.yaml"
    role_pack_path.write_text("role_name: [broken\n", encoding="utf-8")
    svc = HealthService(
        db_dsn="postgresql://user:pass@localhost/db",
        tika_url="http://tika:9998",
        role_pack_path=str(role_pack_path),
    )

    result = svc._check_role_pack()

    assert result == ComponentStatus(
        "Role pack",
        False,
        "not loaded",
        f"invalid role pack: {role_pack_path}. Fix the role pack file and restart.",
    )


def test_check_role_pack_returns_loaded_message_for_valid_yaml(tmp_path) -> None:
    role_pack_path = tmp_path / "role-pack.yaml"
    role_pack_path.write_text(
        "\n".join(
            [
                "role_name: CHRO",
                "goals:",
                "  - Improve workforce planning",
                "tone: Strategic",
                "knowledge_taxonomy:",
                "  - HR",
                "stakeholder_map:",
                "  CEO: partner",
                "retrieval_priorities:",
                "  - HR policies",
                "active_workflows:",
                "  - weekly_brief",
                "output_channels:",
                "  - local",
            ]
        ),
        encoding="utf-8",
    )
    svc = HealthService(
        db_dsn="postgresql://user:pass@localhost/db",
        tika_url="http://tika:9998",
        role_pack_path=str(role_pack_path),
    )

    result = svc._check_role_pack()

    assert result == ComponentStatus("Role pack", True, "CHRO loaded")


async def test_check_database_reports_zero_documents_indexed() -> None:
    svc = HealthService(
        db_dsn="postgresql://user:pass@localhost/db",
        tika_url="http://tika:9998",
    )
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(return_value=(0,))
    mock_conn = AsyncMock()
    mock_conn.__aenter__.return_value = mock_conn
    mock_conn.__aexit__.return_value = False
    mock_conn.execute = AsyncMock(return_value=mock_cursor)

    with patch(
        "cos.services.health.psycopg.AsyncConnection.connect",
        new=AsyncMock(return_value=mock_conn),
    ):
        result = await svc._check_database()

    assert result == ComponentStatus(
        "Database",
        True,
        "connected (0 documents indexed)",
    )


async def test_check_database_reports_document_count() -> None:
    svc = HealthService(
        db_dsn="postgresql://user:pass@localhost/db",
        tika_url="http://tika:9998",
    )
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(return_value=(42,))
    mock_conn = AsyncMock()
    mock_conn.__aenter__.return_value = mock_conn
    mock_conn.__aexit__.return_value = False
    mock_conn.execute = AsyncMock(return_value=mock_cursor)

    with patch(
        "cos.services.health.psycopg.AsyncConnection.connect",
        new=AsyncMock(return_value=mock_conn),
    ):
        result = await svc._check_database()

    assert result == ComponentStatus(
        "Database",
        True,
        "connected (42 documents indexed)",
    )


async def test_check_database_returns_recovery_hint_on_exception() -> None:
    svc = HealthService(
        db_dsn="postgresql://bad:bad@localhost/db",
        tika_url="http://tika:9998",
    )
    with patch(
        "cos.services.health.psycopg.AsyncConnection.connect",
        side_effect=Exception("refused"),
    ):
        result = await svc._check_database()

    assert result == ComponentStatus(
        "Database",
        False,
        "could not connect",
        "Run: cos restart",
    )
