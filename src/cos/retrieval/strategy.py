"""Query strategy classification for retrieval pipeline routing.

Shared between the runtime service and the benchmark harness so that
classification logic stays in one place and cannot drift between them.
"""

from __future__ import annotations

import re
from enum import Enum

# ── Strategy enum ─────────────────────────────────────────────────────────────


class QueryStrategy(Enum):
    DEFAULT = "default"  # chunk-first, single-lineage narrowing
    BOUNDED = "bounded"  # document-first, bounded context expansion
    MULTI_SOURCE = "multi_source"  # multi-lineage synthesis


# ── Benchmark class → strategy ────────────────────────────────────────────────

_BOUNDED_QUERY_CLASSES = frozenset({"single_doc_interpretation"})

# Only explicit cross-document comparison requires multi-source enforcement.
# "briefing" queries aggregate what is available and must not fail on a narrow
# corpus where only one source is relevant.
_MULTI_SOURCE_QUERY_CLASSES = frozenset({"cross_doc_synthesis"})


def select_query_strategy_for_class(query_class: str) -> QueryStrategy:
    """Map a benchmark query class to a retrieval strategy."""
    if query_class in _BOUNDED_QUERY_CLASSES:
        return QueryStrategy.BOUNDED
    if query_class in _MULTI_SOURCE_QUERY_CLASSES:
        return QueryStrategy.MULTI_SOURCE
    return QueryStrategy.DEFAULT


# ── Text → strategy (runtime) ─────────────────────────────────────────────────

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

_BOUNDED_DOCUMENT_TERM_PATTERN = (
    r"(?:document|documents|doc|docs|email|emails|message|messages|note|notes|"
    r"record|records|review|reviews|meeting|meetings|policy|policies|report|"
    r"reports|plan|plans)"
)

_MULTI_SOURCE_REFERENCE_PATTERNS = (
    re.compile(rf"\bboth\b.*\b{_SOURCE_TERM_PATTERN}\b"),
    re.compile(rf"\b{_SOURCE_TERM_PATTERN}\b.*\band\b.*\b{_SOURCE_TERM_PATTERN}\b"),
    re.compile(rf"\b(?:between|across all)\b.*\b{_SOURCE_TERM_PATTERN}\b"),
)

_BOUNDED_CONTEXT_SIGNALS = (
    "full context",
    "in detail",
    "full details",
    "walk me through",
)

_BOUNDED_TOPIC_TERMS = (
    "protocol",
    "programme",
    "program",
    "procedure",
    "process",
    "conversation",
    "discussion",
    "findings",
    "context",
    "timeline",
)

_BOUNDED_INTERPRETATION_PATTERNS = (
    re.compile(
        r"\bwhat did (?:the|this)\b.*\b"
        rf"{_BOUNDED_DOCUMENT_TERM_PATTERN}\b.*\b"
        r"(?:conclude|concluded|decide|decided|recommend|recommended|find|found)\b"
    ),
    re.compile(r"\bwhat was the conclusion\b"),
    re.compile(r"\bwhat was concluded\b"),
    re.compile(r"\bwhat was decided\b"),
    re.compile(r"\bwhat was recommended\b"),
    re.compile(r"\bwhat was found\b"),
    re.compile(r"\bwhat are the findings\b"),
    re.compile(rf"\baccording to the {_BOUNDED_DOCUMENT_TERM_PATTERN}\b"),
    re.compile(r"\bwhat happened in\b"),
    re.compile(r"\bwhat was discussed in\b"),
    re.compile(r"\bwhat was covered in\b"),
)


def _contains_any(text: str, signals: tuple[str, ...]) -> bool:
    return any(signal in text for signal in signals)


def _mentions_multiple_sources(text: str) -> bool:
    return any(pattern.search(text) for pattern in _MULTI_SOURCE_REFERENCE_PATTERNS)


def _is_multi_source(text: str) -> bool:
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


def _is_bounded_interpretation(text: str) -> bool:
    """Return True if the query asks for document-centric interpretation."""
    t = text.lower()
    if any(pattern.search(t) for pattern in _BOUNDED_INTERPRETATION_PATTERNS):
        return True
    if (
        "say about" in t
        and _contains_any(t, _BOUNDED_TOPIC_TERMS)
        and re.search(_BOUNDED_DOCUMENT_TERM_PATTERN, t)
    ):
        return True
    if _contains_any(t, _BOUNDED_CONTEXT_SIGNALS) and re.search(
        _BOUNDED_DOCUMENT_TERM_PATTERN, t
    ):
        return True
    return False


def select_query_strategy_from_text(text: str) -> QueryStrategy:
    """Classify a free-text query to determine retrieval strategy.

    Precedence: MULTI_SOURCE > BOUNDED > DEFAULT.
    """
    if _is_multi_source(text):
        return QueryStrategy.MULTI_SOURCE
    if _is_bounded_interpretation(text):
        return QueryStrategy.BOUNDED
    return QueryStrategy.DEFAULT
