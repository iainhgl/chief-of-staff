import json
from unittest.mock import AsyncMock, MagicMock, patch

import cos.mcp_server.server as _server
import cos.mcp_server.tools  # noqa: F401 — ensure decorators run
from cos.mcp_server.tools import get_role_context, get_status, list_documents, retrieve


def _make_mock_config() -> MagicMock:
    mock_config = MagicMock()
    mock_config.database.libpq_dsn = "postgresql://test:test@localhost/cos_test"
    mock_config.tika.url = "http://tika:9998"
    return mock_config


async def test_get_status_returns_ok_envelope(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    healthy = [{"name": "postgres", "healthy": True}, {"name": "tika", "healthy": True}]
    with patch("cos.services.health.HealthService.check_all", new_callable=AsyncMock, return_value=healthy):
        result = json.loads(await get_status())

    assert result["status"] == "ok"
    assert result["citations"] == []


async def test_get_status_all_components_present(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    healthy = [{"name": "postgres", "healthy": True}, {"name": "tika", "healthy": True}]
    with patch("cos.services.health.HealthService.check_all", new_callable=AsyncMock, return_value=healthy):
        result = json.loads(await get_status())

    components = result["data"]["components"]
    names = [c["name"] for c in components]
    assert "postgres" in names
    assert "tika" in names


async def test_get_status_ready_false_when_unhealthy(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    unhealthy = [{"name": "postgres", "healthy": False}, {"name": "tika", "healthy": True}]
    with patch("cos.services.health.HealthService.check_all", new_callable=AsyncMock, return_value=unhealthy):
        result = json.loads(await get_status())

    assert result["data"]["ready"] is False


async def test_get_status_ready_true_when_all_healthy(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    healthy = [{"name": "postgres", "healthy": True}, {"name": "tika", "healthy": True}]
    with patch("cos.services.health.HealthService.check_all", new_callable=AsyncMock, return_value=healthy):
        result = json.loads(await get_status())

    assert result["data"]["ready"] is True


async def test_get_status_no_config_returns_error(monkeypatch):
    monkeypatch.setattr(_server, "_config", None)
    result = json.loads(await get_status())

    assert result["status"] == "error"
    assert "error" in result
    assert "detail" in result


async def test_retrieve_returns_error_envelope():
    result = json.loads(await retrieve(query="test query"))

    assert result["status"] == "error"
    assert "Not yet implemented" in result["error"]
    assert "detail" in result


async def test_get_role_context_returns_error_envelope():
    result = json.loads(await get_role_context())

    assert result["status"] == "error"
    assert "Not yet implemented" in result["error"]
    assert "detail" in result


async def test_list_documents_returns_error_envelope():
    result = json.loads(await list_documents())

    assert result["status"] == "error"
    assert "Not yet implemented" in result["error"]
    assert "detail" in result
