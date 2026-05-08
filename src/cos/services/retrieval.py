import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from psycopg_pool import AsyncConnectionPool

from cos.config import CosConfig
from cos.llm.adapter import LLMAdapter
from cos.retrieval.citations import CitedResponse, narrow_to_lineage
from cos.retrieval.search import hybrid_search

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
        async with self._pool.connection() as conn:
            cited_results = await hybrid_search(
                text,
                conn,
                self._config,
                role_pack,
                min_score=self._config.retrieval.min_score,
                max_chunks_per_source=self._config.retrieval.max_chunks_per_source,
            )

        if not cited_results:
            return CitedResponse(
                answer="No relevant content found in the knowledge base.",
                citations=[],
            )

        if not _is_multi_source_query(text):
            cited_results = narrow_to_lineage(cited_results)

        if not cited_results:
            return CitedResponse(
                answer="No relevant content found in the knowledge base.",
                citations=[],
            )

        prompt = _build_synthesis_prompt(text, role_pack)
        context = [chunk.content for chunk in cited_results]

        try:
            answer = await self._llm_adapter.complete(prompt=prompt, context=context)
        except Exception:
            logging.error(
                json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "level": "ERROR",
                        "component": "retrieval",
                        "message": "LLM synthesis failed",
                    }
                )
            )
            return CitedResponse(answer=None, citations=cited_results)

        return CitedResponse(answer=answer, citations=cited_results)
