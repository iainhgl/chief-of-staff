import json
import logging
from datetime import datetime, timezone
from typing import Any

from psycopg_pool import AsyncConnectionPool

from cos.config import CosConfig
from cos.llm.adapter import LLMAdapter
from cos.retrieval.citations import CitedResponse
from cos.retrieval.search import hybrid_search

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
            cited_results = await hybrid_search(text, conn, self._config, role_pack)

        if not cited_results:
            return CitedResponse(
                answer="No relevant content found in the knowledge base.",
                citations=[],
            )

        prompt = _build_synthesis_prompt(text, role_pack)
        context = [chunk.content for chunk in cited_results]

        try:
            answer = await self._llm_adapter.complete(prompt=prompt, context=context)
        except Exception as exc:
            logging.error(
                json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "level": "ERROR",
                        "component": "retrieval",
                        "message": "LLM synthesis failed",
                        "error": str(exc),
                    }
                )
            )
            logging.debug("LLM synthesis traceback", exc_info=True)
            return CitedResponse(answer=None, citations=cited_results)

        return CitedResponse(answer=answer, citations=cited_results)
