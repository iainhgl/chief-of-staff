import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from psycopg_pool import AsyncConnectionPool

from cos.config import CosConfig
from cos.llm.adapter import LLMAdapter
from cos.retrieval.citations import (
    CitedResponse,
    narrow_to_lineage,
    select_document_first_anchors,
    select_synthesis_evidence,
)
from cos.retrieval.context_expansion import expand_bounded_context
from cos.retrieval.search import hybrid_search_with_trace
from cos.retrieval.strategy import QueryStrategy, select_query_strategy_from_text
from cos.retrieval.telemetry import SearchStats

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

    async def query(self, text: str, role_pack: Any) -> CitedResponse:
        trace_id = str(uuid.uuid4())
        strategy = select_query_strategy_from_text(text)
        query_mode = _detect_query_type(text)
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
                    return CitedResponse(
                        answer="No relevant content found in the knowledge base.",
                        citations=[],
                    )

                # Route by strategy ──────────────────────────────────────────
                if strategy == QueryStrategy.BOUNDED:
                    anchors = select_document_first_anchors(cited_results)
                    post_lineage_count = len(anchors)
                    expanded = await expand_bounded_context(conn, anchors)
                    synthesis_chunks = expanded.synthesis_chunks
                    evidence = select_synthesis_evidence(expanded.evidence_chunks)
                    post_evidence_selection_count = len(evidence)
                    expansion_mode = "bounded"
                    expanded_context_count = len(synthesis_chunks)
                elif strategy == QueryStrategy.MULTI_SOURCE:
                    post_lineage_count = None
                    evidence = select_synthesis_evidence(
                        cited_results, require_multi_source=True
                    )
                    post_evidence_selection_count = len(evidence)
                    synthesis_chunks = evidence
                    expansion_mode = "none"
                    expanded_context_count = None
                else:  # DEFAULT
                    cited_results = narrow_to_lineage(cited_results)
                    post_lineage_count = len(cited_results)
                    evidence = select_synthesis_evidence(cited_results)
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

        if not evidence:
            _emit_retrieval_log(
                trace_id=trace_id,
                query_mode=query_mode,
                stats=search_stats,
                document_candidate_count=document_candidate_count,
                post_lineage_count=post_lineage_count,
                post_evidence_selection_count=post_evidence_selection_count,
                expansion_mode=expansion_mode,
                expanded_context_count=expanded_context_count,
                retrieval_latency_ms=retrieval_latency_ms,
                synthesis_latency_ms=None,
                total_latency_ms=(time.monotonic() - t_start) * 1000.0,
                provider=self._config.llm.provider,
                model=self._config.llm.model,
                outcome="no_content",
                failure_stage="evidence_selection",
            )
            return CitedResponse(
                answer="No relevant content found in the knowledge base.",
                citations=[],
            )

        prompt = _build_synthesis_prompt(text, role_pack)
        context = [chunk.content for chunk in synthesis_chunks]

        t_synthesis = time.monotonic()
        try:
            answer = await self._llm_adapter.complete(prompt=prompt, context=context)
            synthesis_latency_ms = (time.monotonic() - t_synthesis) * 1000.0
            _emit_retrieval_log(
                trace_id=trace_id,
                query_mode=query_mode,
                stats=search_stats,
                document_candidate_count=document_candidate_count,
                post_lineage_count=post_lineage_count,
                post_evidence_selection_count=post_evidence_selection_count,
                expansion_mode=expansion_mode,
                expanded_context_count=expanded_context_count,
                retrieval_latency_ms=retrieval_latency_ms,
                synthesis_latency_ms=synthesis_latency_ms,
                total_latency_ms=(time.monotonic() - t_start) * 1000.0,
                provider=self._config.llm.provider,
                model=self._config.llm.model,
                outcome="success",
                failure_stage=None,
            )
        except Exception:
            synthesis_latency_ms = (time.monotonic() - t_synthesis) * 1000.0
            _emit_retrieval_log(
                trace_id=trace_id,
                query_mode=query_mode,
                stats=search_stats,
                document_candidate_count=document_candidate_count,
                post_lineage_count=post_lineage_count,
                post_evidence_selection_count=post_evidence_selection_count,
                expansion_mode=expansion_mode,
                expanded_context_count=expanded_context_count,
                retrieval_latency_ms=retrieval_latency_ms,
                synthesis_latency_ms=synthesis_latency_ms,
                total_latency_ms=(time.monotonic() - t_start) * 1000.0,
                provider=self._config.llm.provider,
                model=self._config.llm.model,
                outcome="synthesis_degraded",
                failure_stage="synthesis",
            )
            return CitedResponse(answer=None, citations=evidence)

        return CitedResponse(answer=answer, citations=evidence)
