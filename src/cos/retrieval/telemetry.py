"""Stage-count telemetry captured during a hybrid search run.

Content-safety contract: this module captures only counts, latencies, and
configuration metadata.  Raw query text, prompt text, chunk content, API keys,
OAuth tokens, and DSNs must never enter these structures.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SearchStats:
    """Intermediate candidate counts from each stage of hybrid_search."""

    keyword_candidate_count: int = 0
    semantic_candidate_count: int = 0
    merged_candidate_count: int = 0
    post_threshold_count: int = 0
    post_pruning_count: int = 0
    final_candidate_count: int = 0
