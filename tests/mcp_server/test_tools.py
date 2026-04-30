import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import cos.mcp_server.server as _server
import cos.mcp_server.tools  # noqa: F401 — ensure decorators run
from cos.mcp_server.tools import get_role_context, get_status, list_documents, retrieve
from cos.retrieval.citations import CitedChunk, CitedResponse
from cos.rolepack.loader import RolePackConfig
from cos.services.health import ComponentStatus
from cos.services.rolepack import RolePackService
from cos.store.models import DocumentSummary


def _make_mock_config() -> MagicMock:
    mock_config = MagicMock()
    mock_config.database.libpq_dsn = "postgresql://test:test@localhost/cos_test"
    mock_config.tika.url = "http://tika:9998"
    mock_config.role_pack.path = "role_packs/chro.yaml"
    return mock_config


def _make_chunk() -> CitedChunk:
    return CitedChunk(
        content="test content",
        source_document_id="12345678-1234-1234-1234-123456789012",
        source_path="/test/doc.md",
        chunk_index=0,
        score=0.9,
    )


def _make_mock_retrieval_service(
    answer: str | None = "synthesised answer",
) -> AsyncMock:
    svc = AsyncMock()
    svc.query = AsyncMock(
        return_value=CitedResponse(
            answer=answer,
            citations=[_make_chunk()] if answer is not None else [],
        )
    )
    return svc


def _make_mock_output_service() -> AsyncMock:
    svc = AsyncMock()
    svc.send = AsyncMock()
    return svc


def _make_role_pack_service() -> RolePackService:
    role_pack = RolePackConfig(
        role_name="CHRO",
        goals=["Drive HR transformation"],
        tone="Strategic and evidence-based",
        knowledge_taxonomy=["HR operating models"],
        stakeholder_map={"CEO": "partner"},
        retrieval_priorities=["HR frameworks"],
        active_workflows=["hr_diagnostic"],
        output_channels=["local"],
    )
    return RolePackService(role_pack=role_pack)


async def test_get_status_returns_ok_envelope(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    healthy = [
        ComponentStatus("Postgres", True, "healthy"),
        ComponentStatus("Tika", True, "healthy"),
    ]
    with patch(
        "cos.services.health.HealthService.check_all",
        new_callable=AsyncMock,
        return_value=healthy,
    ):
        result = json.loads(await get_status())

    assert result["status"] == "ok"
    assert result["citations"] == []


async def test_get_status_all_components_present(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    healthy = [
        ComponentStatus("Postgres", True, "healthy"),
        ComponentStatus("Tika", True, "healthy"),
        ComponentStatus("MCP server", True, "listening on stdio"),
        ComponentStatus("Role pack", True, "CHRO loaded"),
        ComponentStatus("Database", True, "connected (0 documents indexed)"),
    ]
    with patch(
        "cos.services.health.HealthService.check_all",
        new_callable=AsyncMock,
        return_value=healthy,
    ):
        result = json.loads(await get_status())

    components = result["data"]["components"]
    assert len(components) == 6
    assert components[0] == {
        "name": "cos",
        "healthy": True,
        "message": "healthy",
        "recovery_hint": "",
    }
    assert components[1]["name"] == "Postgres"
    assert components[1]["message"] == "healthy"
    assert components[2]["name"] == "Tika"
    assert components[2]["message"] == "healthy"
    assert components[3]["name"] == "MCP server"
    assert components[4]["name"] == "Role pack"
    assert components[5]["name"] == "Database"


async def test_get_status_ready_false_when_unhealthy(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    unhealthy = [
        ComponentStatus("Postgres", False, "container not running", "Run: cos restart"),
        ComponentStatus("Tika", True, "healthy"),
    ]
    with patch(
        "cos.services.health.HealthService.check_all",
        new_callable=AsyncMock,
        return_value=unhealthy,
    ):
        result = json.loads(await get_status())

    assert result["data"]["ready"] is False


async def test_get_status_ready_true_when_all_healthy(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    healthy = [
        ComponentStatus("Postgres", True, "healthy"),
        ComponentStatus("Tika", True, "healthy"),
        ComponentStatus("MCP server", True, "listening on stdio"),
        ComponentStatus("Role pack", True, "CHRO loaded"),
        ComponentStatus("Database", True, "connected (0 documents indexed)"),
    ]
    with patch(
        "cos.services.health.HealthService.check_all",
        new_callable=AsyncMock,
        return_value=healthy,
    ):
        result = json.loads(await get_status())

    assert result["data"]["ready"] is True


async def test_get_status_no_config_returns_error(monkeypatch):
    monkeypatch.setattr(_server, "_config", None)
    result = json.loads(await get_status())

    assert result["status"] == "error"
    assert "error" in result
    assert "detail" in result


async def test_retrieve_returns_ok_envelope(monkeypatch):
    monkeypatch.setattr(_server, "_retrieval_service", _make_mock_retrieval_service())
    monkeypatch.setattr(_server, "_output_service", _make_mock_output_service())
    result = json.loads(await retrieve(query="what is workforce segmentation?"))

    assert result["status"] == "ok"
    assert "answer" in result["data"]
    assert isinstance(result["data"]["answer"], str)
    assert isinstance(result["citations"], list)


async def test_retrieve_no_content_found(monkeypatch):
    svc = AsyncMock()
    svc.query = AsyncMock(
        return_value=CitedResponse(
            answer="No relevant content found in the knowledge base.",
            citations=[],
        )
    )
    monkeypatch.setattr(_server, "_retrieval_service", svc)
    monkeypatch.setattr(_server, "_output_service", _make_mock_output_service())
    result = json.loads(await retrieve(query="unknown topic"))

    assert result["status"] == "ok"
    assert "no relevant content" in result["data"]["answer"].lower()
    assert result["data"]["citations"] == []


async def test_retrieve_server_not_initialized(monkeypatch):
    monkeypatch.setattr(_server, "_retrieval_service", None)
    result = json.loads(await retrieve(query="test"))

    assert result["status"] == "error"
    assert "error" in result
    assert "detail" in result


async def test_retrieve_synthesis_failure(monkeypatch):
    svc = AsyncMock()
    svc.query = AsyncMock(return_value=CitedResponse(answer=None, citations=[]))
    monkeypatch.setattr(_server, "_retrieval_service", svc)
    monkeypatch.setattr(_server, "_output_service", _make_mock_output_service())
    result = json.loads(await retrieve(query="test"))

    assert result["status"] == "error"
    assert "error" in result
    assert "detail" in result
    assert "citations" not in result


async def test_retrieve_service_exception(monkeypatch):
    svc = AsyncMock()
    svc.query = AsyncMock(side_effect=RuntimeError("DB connection lost"))
    monkeypatch.setattr(_server, "_retrieval_service", svc)
    monkeypatch.setattr(_server, "_output_service", _make_mock_output_service())
    result = json.loads(await retrieve(query="test"))

    assert result["status"] == "error"
    assert "error" in result
    assert "detail" in result


async def test_list_documents_service_exception(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    with patch(
        "cos.services.provenance.ProvenanceService.list_documents",
        new=AsyncMock(side_effect=RuntimeError("DB unavailable")),
    ):
        result = json.loads(await list_documents())

    assert result["status"] == "error"
    assert "error" in result
    assert "detail" in result


async def test_list_documents_returns_ok_envelope(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    docs = [
        DocumentSummary(
            id="abc123",
            source_path="/test/doc.md",
            ingested_at=datetime(2026, 4, 27, tzinfo=timezone.utc),
            current_version=1,
            chunk_count=5,
        )
    ]
    with patch(
        "cos.services.provenance.ProvenanceService.list_documents",
        new=AsyncMock(return_value=docs),
    ):
        result = json.loads(await list_documents())

    assert result["status"] == "ok"
    assert "documents" in result["data"]
    assert isinstance(result["data"]["documents"], list)


async def test_list_documents_no_config_returns_error(monkeypatch):
    monkeypatch.setattr(_server, "_config", None)
    result = json.loads(await list_documents())

    assert result["status"] == "error"


async def test_list_documents_document_fields_present(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    docs = [
        DocumentSummary(
            id="abc123",
            source_path="/test/doc.md",
            ingested_at=datetime(2026, 4, 27, tzinfo=timezone.utc),
            current_version=1,
            chunk_count=5,
        )
    ]
    with patch(
        "cos.services.provenance.ProvenanceService.list_documents",
        new=AsyncMock(return_value=docs),
    ):
        result = json.loads(await list_documents())

    doc = result["data"]["documents"][0]
    assert "id" in doc
    assert "source_path" in doc
    assert "ingested_at" in doc
    assert "current_version" in doc
    assert "chunk_count" in doc


async def test_get_role_context_returns_live_role_pack_data(monkeypatch):
    monkeypatch.setattr(_server, "_role_pack_service", _make_role_pack_service())

    result = json.loads(await get_role_context())

    assert result["status"] == "ok"
    assert result["data"]["role_name"] == "CHRO"
    assert result["data"]["goals"] == ["Drive HR transformation"]
    assert result["data"]["tone"] == "Strategic and evidence-based"
    assert result["data"]["knowledge_taxonomy"] == ["HR operating models"]
    assert result["data"]["active_workflows"] == ["hr_diagnostic"]
    assert result["citations"] == []


async def test_get_role_context_no_role_pack_service_returns_error(monkeypatch):
    monkeypatch.setattr(_server, "_role_pack_service", None)

    result = json.loads(await get_role_context())

    assert result["status"] == "error"
    assert "error" in result
    assert "detail" in result


async def test_retrieve_passes_role_pack_to_service(monkeypatch):
    role_pack_service = _make_role_pack_service()
    retrieval_service = _make_mock_retrieval_service()
    output_service = _make_mock_output_service()
    monkeypatch.setattr(_server, "_role_pack_service", role_pack_service)
    monkeypatch.setattr(_server, "_retrieval_service", retrieval_service)
    monkeypatch.setattr(_server, "_output_service", output_service)

    result = json.loads(await retrieve(query="test"))

    assert result["status"] == "ok"
    assert (
        retrieval_service.query.call_args.kwargs["role_pack"]
        == role_pack_service.get_active()
    )
