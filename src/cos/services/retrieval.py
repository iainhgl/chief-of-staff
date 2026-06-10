import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from psycopg_pool import AsyncConnectionPool

from cos.config import CosConfig
from cos.llm.adapter import LLMAdapter
from cos.retrieval.citations import (
    CitedResponse,
    RetrievalResult,
    narrow_to_lineage,
    select_document_first_anchors,
    select_synthesis_evidence,
)
from cos.retrieval.context_expansion import expand_bounded_context
from cos.retrieval.search import hybrid_search_with_trace
from cos.retrieval.strategy import QueryStrategy, select_query_strategy_from_text
from cos.retrieval.telemetry import SearchStats

_NO_CONTENT_ANSWER = "No relevant content found in the knowledge base."

_TASK_INSTRUCTIONS: dict[str, str] = {
    "draft": (
        "Structure your response as a formal document: title, body paragraphs, "
        "and a conclusion or sign-off where appropriate."
    ),
    "prioritise": (
        "Structure your response as a ranked list. For each item, give its rank "
        "position and a brief rationale."
    ),
    "compare": (
        "Structure your response as a structured comparison, covering key "
        "differences and similarities clearly."
    ),
    "summarise": (
        "Provide a concise synthesis of the key points from the provided context."
    ),
    "question": "",
}


def _detect_query_type(text: str) -> str:
    t = text.lower()
    if t.startswith(("draft ", "write a draft", "write a first draft")):
        return "draft"
    if any(
        kw in t
        for kw in (
            "prioritise",
            "prioritize",
            "rank the following",
            "rank these",
            "rank by",
        )
    ):
        return "prioritise"
    if any(
        kw in t
        for kw in (
            "compare ",
            "comparison between",
            "differences between",
            " vs ",
            " versus ",
        )
    ):
        return "compare"
    if any(
        kw in t
        for kw in (
            "summarise",
            "summarize",
            "summary of",
            "brief me on",
            "brief on",
        )
    ):
        return "summarise"
    return "question"


def _build_synthesis_prompt(text: str, role_pack: Any) -> str:
    tone = getattr(role_pack, "tone", "") if role_pack is not None else ""
    query_type = _detect_query_type(text)
    task_instruction = _TASK_INSTRUCTIONS[query_type]

    parts: list[str] = []
    if tone:
        parts.append(f"Tone: {tone}")
    parts.append(f"User query: {text}")
    if task_instruction:
        parts.append(task_instruction)
    return "\n".join(parts)


def _emit_retrieval_log(
    *,
    trace_id: str,
    query_mode: str,
    stats: SearchStats,
    document_candidate_count: int | None,
    post_lineage_count: int | None,
    post_evidence_selection_count: int | None,
    expansion_mode: str,
    expanded_context_count: int | None,
    retrieval_latency_ms: float,
    synthesis_latency_ms: float | None,
    total_latency_ms: float,
    provider: str,
    model: str,
    outcome: str,
    failure_stage: str | None,
) -> None:
    level = (
        "ERROR"
        if outcome in {"synthesis_degraded", "retrieval_failed"}
        else "INFO"
    )
    record: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "component": "retrieval",
        "event": "retrieval_run",
        "trace_id": trace_id,
        "query_mode": query_mode,
        "candidate_counts": {
            "keyword": stats.keyword_candidate_count,
            "semantic": stats.semantic_candidate_count,
            "merged": stats.merged_candidate_count,
            "post_threshold": stats.post_threshold_count,
            "post_pruning": stats.post_pruning_count,
            "final": stats.final_candidate_count,
            "document_candidates": document_candidate_count,
            "post_lineage": post_lineage_count,
            "post_evidence_selection": post_evidence_selection_count,
            "expansion_mode": expansion_mode,
            "expanded_context": expanded_context_count,
        },
        "latency_ms": {
            "retrieval": round(retrieval_latency_ms, 2),
            "synthesis": (
                round(synthesis_latency_ms, 2)
                if synthesis_latency_ms is not None
                else None
            ),
            "total": round(total_latency_ms, 2),
        },
        "provider": provider,
        "model": model,
        "outcome": outcome,
        "failure_stage": failure_stage,
    }
    if level == "ERROR":
        logging.error(json.dumps(record))
    else:
        logging.info(json.dumps(record))


@dataclass
class _RetrievalTelemetry:
    """Deferred telemetry context for an evidence-bearing retrieval. Carried
    from the retrieval phase to whichever caller emits the log, so the answer
    path can emit a single combined record (retrieval + synthesis) while the
    pure retrieve path emits a retrieval-only record."""

    trace_id: str
    query_mode: str
    stats: SearchStats
    document_candidate_count: int | None
    post_lineage_count: int | None
    post_evidence_selection_count: int | None
    expansion_mode: str
    expanded_context_count: int | None
    retrieval_latency_ms: float
    t_start: float


class RetrievalService:
    def __init__(
        self,
        config: CosConfig,
        pool: AsyncConnectionPool,
        llm_adapter: LLMAdapter,
    ) -> None:
        self._config = config
        self._pool = pool
        self._llm_adapter = llm_adapter

    def _emit(
        self,
        ctx: _RetrievalTelemetry,
        *,
        synthesis_latency_ms: float | None,
        outcome: str,
        failure_stage: str | None,
    ) -> None:
        _emit_retrieval_log(
            trace_id=ctx.trace_id,
            query_mode=ctx.query_mode,
            stats=ctx.stats,
            document_candidate_count=ctx.document_candidate_count,
            post_lineage_count=ctx.post_lineage_count,
            post_evidence_selection_count=ctx.post_evidence_selection_count,
            expansion_mode=ctx.expansion_mode,
            expanded_context_count=ctx.expanded_context_count,
            retrieval_latency_ms=ctx.retrieval_latency_ms,
            synthesis_latency_ms=synthesis_latency_ms,
            total_latency_ms=(time.monotonic() - ctx.t_start) * 1000.0,
            provider=self._config.llm.provider,
            model=self._config.llm.model,
            outcome=outcome,
            failure_stage=failure_stage,
        )

    async def _retrieve_with_telemetry(
        self, text: str, role_pack: Any
    ) -> tuple[RetrievalResult, _RetrievalTelemetry | None]:
        """Run the pure retrieval pipeline (search → strategy → evidence).

        Terminal outcomes (no candidates, no surviving evidence, retrieval
        failure) emit their own log and return ``ctx=None``. An evidence-bearing
        outcome defers logging: it returns the telemetry context so the caller
        decides whether to emit a retrieval-only or a combined record.
        """
        trace_id = str(uuid.uuid4())
        strategy = select_query_strategy_from_text(text)
        query_mode = _detect_query_type(text)
        strict_query_matching = query_mode in {"question", "compare"}
        t_start = time.monotonic()
        t_retrieval = time.monotonic()
        search_stats = SearchStats()
        try:
            async with self._pool.connection() as conn:
                cited_results, search_stats = await hybrid_search_with_trace(
                    text,
                    conn,
                    self._config,
                    role_pack,
                    min_score=self._config.retrieval.min_score,
                    max_chunks_per_source=self._config.retrieval.max_chunks_per_source,
                )

                document_candidate_count = len(
                    {c.document_version_id or c.source_locator for c in cited_results}
                )

                if not cited_results:
                    retrieval_latency_ms = (time.monotonic() - t_retrieval) * 1000.0
                    _emit_retrieval_log(
                        trace_id=trace_id,
                        query_mode=query_mode,
                        stats=search_stats,
                        document_candidate_count=document_candidate_count,
                        post_lineage_count=None,
                        post_evidence_selection_count=None,
                        expansion_mode="none",
                        expanded_context_count=None,
                        retrieval_latency_ms=retrieval_latency_ms,
                        synthesis_latency_ms=None,
                        total_latency_ms=(time.monotonic() - t_start) * 1000.0,
                        provider=self._config.llm.provider,
                        model=self._config.llm.model,
                        outcome="no_content",
                        failure_stage="retrieval",
                    )
                    return (
                        RetrievalResult(
                            evidence=[],
                            synthesis_context=[],
                            strategy=strategy.value,
                            trace_id=trace_id,
                            outcome="no_content",
                        ),
                        None,
                    )

                # Route by strategy ──────────────────────────────────────────
                if strategy == QueryStrategy.BOUNDED:
                    anchors = select_document_first_anchors(
                        cited_results,
                        query_text=text,
                        strict_matching=strict_query_matching,
                    )
                    post_lineage_count = len(anchors)
                    expanded = await expand_bounded_context(conn, anchors)
                    synthesis_chunks = expanded.synthesis_chunks
                    evidence = select_synthesis_evidence(
                        expanded.evidence_chunks,
                        query_text=text,
                        strict_matching=strict_query_matching,
                    )
                    post_evidence_selection_count = len(evidence)
                    expansion_mode = "bounded"
                    expanded_context_count = len(synthesis_chunks)
                elif strategy == QueryStrategy.MULTI_SOURCE:
                    post_lineage_count = None
                    evidence = select_synthesis_evidence(
                        cited_results,
                        require_multi_source=True,
                        query_text=text,
                        strict_matching=strict_query_matching,
                    )
                    post_evidence_selection_count = len(evidence)
                    synthesis_chunks = evidence
                    expansion_mode = "none"
                    expanded_context_count = None
                else:  # DEFAULT
                    cited_results = narrow_to_lineage(
                        cited_results,
                        query_text=text,
                        strict_matching=strict_query_matching,
                    )
                    post_lineage_count = len(cited_results)
                    evidence = select_synthesis_evidence(
                        cited_results,
                        query_text=text,
                        strict_matching=strict_query_matching,
                    )
                    post_evidence_selection_count = len(evidence)
                    synthesis_chunks = evidence
                    expansion_mode = "none"
                    expanded_context_count = None

        except Exception:
            retrieval_latency_ms = (time.monotonic() - t_retrieval) * 1000.0
            _emit_retrieval_log(
                trace_id=trace_id,
                query_mode=query_mode,
                stats=search_stats,
                document_candidate_count=None,
                post_lineage_count=None,
                post_evidence_selection_count=None,
                expansion_mode="none",
                expanded_context_count=None,
                retrieval_latency_ms=retrieval_latency_ms,
                synthesis_latency_ms=None,
                total_latency_ms=(time.monotonic() - t_start) * 1000.0,
                provider=self._config.llm.provider,
                model=self._config.llm.model,
                outcome="retrieval_failed",
                failure_stage="retrieval",
            )
            raise
        retrieval_latency_ms = (time.monotonic() - t_retrieval) * 1000.0

        ctx = _RetrievalTelemetry(
            trace_id=trace_id,
            query_mode=query_mode,
            stats=search_stats,
            document_candidate_count=document_candidate_count,
            post_lineage_count=post_lineage_count,
            post_evidence_selection_count=post_evidence_selection_count,
            expansion_mode=expansion_mode,
            expanded_context_count=expanded_context_count,
            retrieval_latency_ms=retrieval_latency_ms,
            t_start=t_start,
        )

        if not evidence:
            self._emit(
                ctx,
                synthesis_latency_ms=None,
                outcome="no_content",
                failure_stage="evidence_selection",
            )
            return (
                RetrievalResult(
                    evidence=[],
                    synthesis_context=[],
                    strategy=strategy.value,
                    trace_id=trace_id,
                    outcome="no_content",
                ),
                None,
            )

        return (
            RetrievalResult(
                evidence=evidence,
                synthesis_context=[chunk.content for chunk in synthesis_chunks],
                strategy=strategy.value,
                trace_id=trace_id,
                outcome="success",
            ),
            ctx,
        )

    async def retrieve(self, text: str, role_pack: Any) -> RetrievalResult:
        """Pure retrieval — find and return cited evidence with no LLM call.

        This is the model-agnostic seam: callers (e.g. an external harness)
        reason over the returned evidence themselves.
        """
        result, ctx = await self._retrieve_with_telemetry(text, role_pack)
        if ctx is not None:
            # Evidence-bearing retrieval that was not terminally logged: emit a
            # retrieval-only record (no synthesis on this path).
            self._emit(
                ctx,
                synthesis_latency_ms=None,
                outcome="success",
                failure_stage=None,
            )
        return result

    async def answer(self, text: str, role_pack: Any) -> CitedResponse:
        """Retrieve then synthesise a cited answer. Emits a single combined
        (retrieval + synthesis) telemetry record."""
        result, ctx = await self._retrieve_with_telemetry(text, role_pack)
        if not result.evidence:
            return CitedResponse(answer=_NO_CONTENT_ANSWER, citations=[])

        assert ctx is not None  # evidence present ⇒ deferred telemetry context
        prompt = _build_synthesis_prompt(text, role_pack)

        t_synthesis = time.monotonic()
        try:
            answer = await self._llm_adapter.complete(
                prompt=prompt, context=result.synthesis_context
            )
        except Exception:
            synthesis_latency_ms = (time.monotonic() - t_synthesis) * 1000.0
            self._emit(
                ctx,
                synthesis_latency_ms=synthesis_latency_ms,
                outcome="synthesis_degraded",
                failure_stage="synthesis",
            )
            return CitedResponse(answer=None, citations=result.evidence)

        synthesis_latency_ms = (time.monotonic() - t_synthesis) * 1000.0
        self._emit(
            ctx,
            synthesis_latency_ms=synthesis_latency_ms,
            outcome="success",
            failure_stage=None,
        )
        return CitedResponse(answer=answer, citations=result.evidence)

    async def query(self, text: str, role_pack: Any) -> CitedResponse:
        """Deprecated alias of :meth:`answer`, retained so existing callers and
        tests continue to work. New code should call :meth:`answer` (for a
        synthesised reply) or :meth:`retrieve` (for cited evidence only)."""
        return await self.answer(text, role_pack)
