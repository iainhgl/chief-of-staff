import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import cos.mcp_server.server as _server
import cos.mcp_server.tools  # noqa: F401 — ensure decorators run
from cos.mcp_server.tools import (
    get_role_context,
    get_status,
    ingest_document,
    list_documents,
    retrieve,
)
from cos.retrieval.citations import CitedChunk, CitedResponse
from cos.rolepack.loader import RolePackConfig
from cos.services.health import ComponentStatus
from cos.services.ingestion import IngestResult
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
        source_alias="doc.md",
        source_locator="/test/doc.md",
        document_version_id="",
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
    assert "DB connection lost" not in result["detail"]
    assert "cos logs" in result["detail"]


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
    assert "DB unavailable" not in result["detail"]
    assert "cos logs" in result["detail"]


async def test_list_documents_returns_ok_envelope(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    docs = [
        DocumentSummary(
            id="abc123",
            source_alias="doc.md",
            source_locator="/test/doc.md",
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
            source_alias="doc.md",
            source_locator="/test/doc.md",
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
    assert "source_alias" in doc
    assert "source_locator" in doc
    assert "source_path" not in doc
    assert "ingested_at" in doc
    assert "current_version" in doc
    assert "chunk_count" in doc


async def test_retrieve_citations_include_source_alias_and_locator(monkeypatch):
    monkeypatch.setattr(_server, "_retrieval_service", _make_mock_retrieval_service())
    monkeypatch.setattr(_server, "_output_service", _make_mock_output_service())
    result = json.loads(await retrieve(query="workforce segmentation"))

    assert result["status"] == "ok"
    citations = result["citations"]
    assert len(citations) == 1
    assert "source_alias" in citations[0]
    assert "source_locator" in citations[0]
    assert "document_version_id" in citations[0]
    assert "source_path" not in citations[0]


async def test_list_documents_response_includes_source_alias_and_locator(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    docs = [
        DocumentSummary(
            id="abc123",
            source_alias="doc.md",
            source_locator="/test/doc.md",
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
    assert doc["source_alias"] == "doc.md"
    assert doc["source_locator"] == "/test/doc.md"
    assert "source_path" not in doc


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


# ─────────────────────────────────────────────
# ingest_document tool tests
# ─────────────────────────────────────────────


def _make_ingest_result(
    outcome: str = "new_content",
    message: str = "New content detected - full ingest will proceed.",
    warning: str | None = None,
    chunk_count: int = 3,
) -> IngestResult:
    return IngestResult(
        document_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        chunk_count=chunk_count,
        source_path="/data/connector-staging/mcp/test-note.md",
        outcome=outcome,
        message=message,
        source_alias="test-note.md",
        source_locator="mcp_note://mcp/test-id-123",
        warning=warning,
    )


async def test_ingest_document_success_envelope(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    with patch(
        "cos.services.ingestion.IngestService.ingest_note",
        new=AsyncMock(return_value=_make_ingest_result()),
    ):
        result = json.loads(
            await ingest_document(content="A strategic planning note.")
        )

    assert result["status"] == "ok"
    assert result["citations"] == []
    data = result["data"]
    assert "document_id" in data
    assert "chunk_count" in data
    assert "outcome" in data
    assert "message" in data
    assert "source_alias" in data
    assert "source_locator" in data
    assert "warning" not in data


async def test_ingest_document_duplicate_content_message(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    with patch(
        "cos.services.ingestion.IngestService.ingest_note",
        new=AsyncMock(
            return_value=_make_ingest_result(
                outcome="new_source_known_content",
                message=(
                    "Known content from a new source - provenance will be"
                    " linked without reprocessing."
                ),
                chunk_count=0,
            )
        ),
    ):
        result = json.loads(
            await ingest_document(content="Duplicate bytes content.")
        )

    assert result["status"] == "ok"
    data = result["data"]
    assert data["outcome"] == "new_source_known_content"
    assert "linked" in data["message"].lower() or "known" in data["message"].lower()
    assert data["chunk_count"] == 0


async def test_ingest_document_near_duplicate_warning_in_response(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    with patch(
        "cos.services.ingestion.IngestService.ingest_note",
        new=AsyncMock(
            return_value=_make_ingest_result(
                warning=(
                    "Semantically similar content already exists:"
                    " 'existing-doc.md' (similarity: 0.97)"
                )
            )
        ),
    ):
        result = json.loads(
            await ingest_document(content="A note very similar to an existing one.")
        )

    assert result["status"] == "ok"
    data = result["data"]
    assert "warning" in data
    assert "existing-doc.md" in data["warning"]
    assert data["outcome"] == "new_content"


async def test_ingest_document_empty_content_returns_error(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    result = json.loads(await ingest_document(content="   "))

    assert result["status"] == "error"
    assert "error" in result
    assert "detail" in result


async def test_ingest_document_invalid_metadata_returns_error(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    result = json.loads(
        await ingest_document(content="Some note content.", metadata=["bad"])  # type: ignore[arg-type]
    )

    assert result["status"] == "error"
    assert result["error"] == "Invalid input"
    assert "metadata must be an object" in result["detail"]


async def test_ingest_document_server_not_initialized(monkeypatch):
    monkeypatch.setattr(_server, "_config", None)
    result = json.loads(await ingest_document(content="Some note content."))

    assert result["status"] == "error"
    assert "Server not initialized" in result["error"]


async def test_ingest_document_service_exception_returns_error(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    with patch(
        "cos.services.ingestion.IngestService.ingest_note",
        new=AsyncMock(side_effect=RuntimeError("DB connection lost")),
    ):
        result = json.loads(await ingest_document(content="Some note content."))

    assert result["status"] == "error"
    assert result["error"] == "Ingest failed"
    assert "DB connection lost" not in result["detail"]
    assert "cos logs" in result["detail"]


# ── Story 6.13: citation pruning propagation ─────────────────────────────────


async def test_retrieve_envelope_contains_only_service_returned_citations(monkeypatch):
    pruned_citations = [
        CitedChunk(
            content="first supporting chunk",
            source_document_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            source_alias="policy.md",
            source_locator="/docs/policy.md",
            document_version_id="v1",
            chunk_index=0,
            score=0.9,
        ),
        CitedChunk(
            content="second supporting chunk",
            source_document_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            source_alias="policy.md",
            source_locator="/docs/policy.md",
            document_version_id="v1",
            chunk_index=1,
            score=0.8,
        ),
    ]
    svc = AsyncMock()
    svc.query = AsyncMock(
        return_value=CitedResponse(
            answer="synthesised answer", citations=pruned_citations
        )
    )
    monkeypatch.setattr(_server, "_retrieval_service", svc)
    monkeypatch.setattr(_server, "_output_service", _make_mock_output_service())

    result = json.loads(await retrieve(query="what is HR planning?"))

    assert result["status"] == "ok"
    citations = result["citations"]
    assert len(citations) == 2
    for c in citations:
        assert "source_alias" in c
        assert "source_locator" in c
        assert "document_version_id" in c
        assert "chunk_index" in c
        assert "score" in c
        assert "source_path" not in c


# ── Story 6.14: grounded citation lineage in MCP response ────────────────────


async def test_retrieve_grounded_citations_share_single_lineage(monkeypatch):
    # Service returns only the winning lineage after grounding (simulated here)
    grounded_citation = CitedChunk(
        content="leave policy from email body",
        source_document_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        source_alias="gmail://msg-001",
        source_locator="gmail://msg-001",
        document_version_id="ver-aaa-001",
        chunk_index=0,
        score=0.9,
    )
    svc = AsyncMock()
    svc.query = AsyncMock(
        return_value=CitedResponse(
            answer="The leave policy allows 20 days per year.",
            citations=[grounded_citation],
        )
    )
    monkeypatch.setattr(_server, "_retrieval_service", svc)
    monkeypatch.setattr(_server, "_output_service", _make_mock_output_service())

    result = json.loads(await retrieve(query="what is the leave policy?"))

    assert result["status"] == "ok"
    # Top-level citations and data.citations must both reflect the grounded lineage
    assert len(result["citations"]) == 1
    assert len(result["data"]["citations"]) == 1
    top_citation = result["citations"][0]
    assert top_citation["source_locator"] == "gmail://msg-001"
    assert top_citation["document_version_id"] == "ver-aaa-001"
    # data.citations matches top-level exactly
    assert result["data"]["citations"][0] == top_citation


async def test_retrieve_grounded_legacy_citations_use_source_locator(monkeypatch):
    # Legacy record with no document_version_id — source_locator is the lineage key
    legacy_citation = CitedChunk(
        content="leave policy content",
        source_document_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        source_alias="/docs/leave.md",
        source_locator="/docs/leave.md",
        document_version_id="",
        chunk_index=0,
        score=0.85,
    )
    svc = AsyncMock()
    svc.query = AsyncMock(
        return_value=CitedResponse(
            answer="The leave policy is detailed in docs.",
            citations=[legacy_citation],
        )
    )
    monkeypatch.setattr(_server, "_retrieval_service", svc)
    monkeypatch.setattr(_server, "_output_service", _make_mock_output_service())

    result = json.loads(await retrieve(query="what does the leave doc say?"))

    assert result["status"] == "ok"
    top_citation = result["citations"][0]
    assert top_citation["document_version_id"] == ""
    assert top_citation["source_locator"] == "/docs/leave.md"
    assert result["data"]["citations"][0] == top_citation
