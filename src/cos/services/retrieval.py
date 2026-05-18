import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from psycopg_pool import AsyncConnectionPool

from cos.config import CosConfig
from cos.llm.adapter import LLMAdapter
from cos.retrieval.citations import CitedResponse, narrow_to_lineage
from cos.retrieval.search import hybrid_search_with_trace
from cos.retrieval.telemetry import SearchStats

_COMPARE_SIGNALS = (
    "compare ",
    "comparison between",
    "differences between",
    " vs ",
    " versus ",
)

_EXPLICIT_MULTI_SOURCE_SIGNALS = (
    "from all sources",
    "across sources",
    "multiple sources",
)

_SYNTHESIS_SIGNALS = (
    "summarise",
    "summarize",
    "summary of",
    "brief me on",
    "brief on",
    "synthesise",
    "synthesize",
    "synthesis of",
    "combine",
    "combined",
    "using both",
    "use both",
)

_AGGREGATION_SIGNALS = (
    "aggregate",
    "aggregated",
)

_SOURCE_TERM_PATTERN = (
    r"(?:source|sources|document|documents|doc|docs|file|files|email|emails|"
    r"message|messages|note|notes|record|records)"
)

_MULTI_SOURCE_REFERENCE_PATTERNS = (
    re.compile(rf"\bboth\b.*\b{_SOURCE_TERM_PATTERN}\b"),
    re.compile(rf"\b{_SOURCE_TERM_PATTERN}\b.*\band\b.*\b{_SOURCE_TERM_PATTERN}\b"),
    re.compile(
        rf"\b(?:between|across all)\b.*\b{_SOURCE_TERM_PATTERN}\b"
    ),
)


def _contains_any(text: str, signals: tuple[str, ...]) -> bool:
    return any(signal in text for signal in signals)


def _mentions_multiple_sources(text: str) -> bool:
    return any(pattern.search(text) for pattern in _MULTI_SOURCE_REFERENCE_PATTERNS)


def _is_multi_source_query(text: str) -> bool:
    """Return True if the query explicitly requests multi-source synthesis."""
    t = text.lower()
    if _contains_any(t, _COMPARE_SIGNALS):
        return True
    if _contains_any(t, _EXPLICIT_MULTI_SOURCE_SIGNALS):
        return True
    if _mentions_multiple_sources(t):
        return True
    if _contains_any(t, _SYNTHESIS_SIGNALS) and _mentions_multiple_sources(t):
        return True
    if _contains_any(t, _AGGREGATION_SIGNALS) and _mentions_multiple_sources(t):
        return True
    return False


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
    post_lineage_count: int | None,
    retrieval_latency_ms: float,
    synthesis_latency_ms: float | None,
    total_latency_ms: float,
    provider: str,
    model: str,
    outcome: str,
    failure_stage: str | None,
) -> None:
    level = "ERROR" if outcome == "synthesis_degraded" else "INFO"
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
            "post_lineage": post_lineage_count,
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
        query_mode = _detect_query_type(text)
        t_start = time.monotonic()

        async with self._pool.connection() as conn:
            t_retrieval = time.monotonic()
            cited_results, search_stats = await hybrid_search_with_trace(
                text,
                conn,
                self._config,
                role_pack,
                min_score=self._config.retrieval.min_score,
                max_chunks_per_source=self._config.retrieval.max_chunks_per_source,
            )
            retrieval_latency_ms = (time.monotonic() - t_retrieval) * 1000.0

        if not cited_results:
            _emit_retrieval_log(
                trace_id=trace_id,
                query_mode=query_mode,
                stats=search_stats,
                post_lineage_count=None,
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

        if not _is_multi_source_query(text):
            cited_results = narrow_to_lineage(cited_results)

        post_lineage_count = len(cited_results)

        if not cited_results:
            _emit_retrieval_log(
                trace_id=trace_id,
                query_mode=query_mode,
                stats=search_stats,
                post_lineage_count=0,
                retrieval_latency_ms=retrieval_latency_ms,
                synthesis_latency_ms=None,
                total_latency_ms=(time.monotonic() - t_start) * 1000.0,
                provider=self._config.llm.provider,
                model=self._config.llm.model,
                outcome="no_content",
                failure_stage="lineage_narrowing",
            )
            return CitedResponse(
                answer="No relevant content found in the knowledge base.",
                citations=[],
            )

        prompt = _build_synthesis_prompt(text, role_pack)
        context = [chunk.content for chunk in cited_results]

        t_synthesis = time.monotonic()
        try:
            answer = await self._llm_adapter.complete(prompt=prompt, context=context)
            synthesis_latency_ms = (time.monotonic() - t_synthesis) * 1000.0
            _emit_retrieval_log(
                trace_id=trace_id,
                query_mode=query_mode,
                stats=search_stats,
                post_lineage_count=post_lineage_count,
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
                post_lineage_count=post_lineage_count,
                retrieval_latency_ms=retrieval_latency_ms,
                synthesis_latency_ms=synthesis_latency_ms,
                total_latency_ms=(time.monotonic() - t_start) * 1000.0,
                provider=self._config.llm.provider,
                model=self._config.llm.model,
                outcome="synthesis_degraded",
                failure_stage="synthesis",
            )
            return CitedResponse(answer=None, citations=cited_results)

        return CitedResponse(answer=answer, citations=cited_results)
