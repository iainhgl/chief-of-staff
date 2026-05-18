# CoS Retrieval Evaluation Corpus: Generation Approach and Schema

Date: 2026-05-15  
Author: Codex technical research synthesis  
Status: Input to future backlog correction and Epic 8 definition

## Purpose

This note captures a practical recommendation for how CoS should create and maintain a retrieval evaluation corpus.

It is intended to serve as a direct input to the next BMAD `bmad-correct-course` workflow, especially if the backlog is updated to add a retrieval trust and evaluation epic before broader ambient or agentic expansion.

## Executive Summary

The CoS evaluation corpus should be built as a layered asset rather than a single monolithic test set.

Recommended structure:

1. A **generated candidate set** for breadth
2. A **curated gold benchmark set** for release confidence
3. A **stress / fuzz set** for robustness testing

The key recommendation is:

> Generate many candidate questions automatically, but do not treat fully synthetic questions and answers as final ground truth without review.

This balances speed, realism, and trust.

## Why This Matters

If CoS is going to improve retrieval quality in a disciplined way, it needs a repeatable way to test:

- whether the correct evidence was found
- whether the system ranked it well
- whether single-source questions stayed single-source
- whether multi-source questions allowed synthesis appropriately
- whether the final answer remained grounded in the cited evidence

Without a corpus, future retrieval changes are difficult to compare reliably.

## Recommended Corpus Layers

## Layer 1: Generated Candidate Set

Purpose:

- create broad initial coverage quickly
- explore many query forms and styles
- seed future curation

Characteristics:

- large
- mostly generated
- lightly reviewed
- not the final release gate

Good uses:

- find obvious ranking failures
- test paraphrase tolerance
- expand coverage across source types

## Layer 2: Curated Gold Benchmark Set

Purpose:

- serve as the trusted regression suite
- support release and backlog decisions
- provide a stable comparison point for retrieval changes

Characteristics:

- smaller
- explicitly reviewed
- version-controlled
- trusted enough for pass/fail gating

Good uses:

- retrieval baseline comparisons
- acceptance testing for retrieval improvements
- proving whether a new retrieval strategy is actually better

## Layer 3: Stress / Fuzz Set

Purpose:

- test robustness rather than exact correctness
- catch brittle retrieval behavior
- probe edge cases

Characteristics:

- large
- heavily generated
- may include adversarial and noisy prompts
- not always strictly gold-labeled

Good uses:

- paraphrase stress
- under-specified questions
- mixed-source ambiguity
- mobile-message style noise

## Recommended Query Categories

The corpus should explicitly cover at least these categories:

- direct factual lookup
- exact phrase lookup
- entity lookup
- date and chronology questions
- single-document interpretation
- cross-document synthesis
- compare / contrast
- briefing / summary
- meeting-prep style questions
- stakeholder / relationship questions
- no-answer / insufficient-evidence questions

This taxonomy matters because different retrieval approaches perform differently by query type.

## Recommended Source Coverage

The corpus should draw from the actual source shapes CoS is expected to handle:

- local Markdown documents
- PDFs
- Word documents
- Gmail messages
- Gmail attachments
- Google Calendar events
- MCP-ingested notes
- later, message-captured notes

At least the gold benchmark set should represent multiple source classes rather than only polished static docs.

## What Should Be Generated

The following are good candidates for automatic generation:

- question variants from a document
- paraphrases
- short mobile-style phrasings
- direct factual prompts
- summary prompts
- compare prompts
- timeline prompts
- stakeholder prompts
- adversarial wording variants

Generation can be driven from:

- one document at a time
- one thread at a time
- one event plus related materials
- one topic cluster at a time

## What Should Be Reviewed or Curated

The following should usually be reviewed by a human or via a tighter curation pass:

- expected evidence set
- whether multiple sources are allowed
- whether the question is truly answerable from the source set
- whether the question is ambiguous
- whether the "gold" answer criteria are too broad or too narrow

At minimum, the benchmark set used as a release gate should be curated.

## Recommended Generation Methods

## Method A: Template-Driven Generation

Create deterministic prompt templates such as:

- "What did [person] decide about [topic]?"
- "What happened on [date] regarding [project]?"
- "Summarise the key points from [artifact]?"
- "Compare [initiative A] and [initiative B]?"

Advantages:

- high control
- easier to classify by query type
- lower risk of vague or low-value questions

## Method B: Document-Grounded LLM Generation

Feed a real document or event record to an LLM and ask it to generate only questions answerable from that material.

Advantages:

- more realistic wording
- faster coverage expansion
- better alignment with actual corpus content

Constraint:

- must not blindly trust generated answer labels

## Method C: Transformation-Based Expansion

Take one reviewed query and generate variants:

- paraphrase
- executive phrasing
- short mobile phrasing
- typo/noisy phrasing
- partial-memory phrasing

Advantages:

- good robustness coverage
- cheap expansion from a trusted base case

## Method D: Contrastive / Hard-Negative Generation

Generate questions that are close to answerable but should fail or should prefer one source over another.

Examples:

- sibling documents with similar names
- two meetings on similar topics
- changed-content reingest scenarios
- confusing stakeholder overlap

Advantages:

- directly tests ranking precision
- helps catch source blending and false positives

## Recommended Gold Record Schema

A simple and practical schema for the benchmark set would look like this:

```yaml
id: rq-0001
query: "What did the CHRO decide about workforce planning in the April 12 memo?"
query_type: direct_fact
source_scope:
  multi_source_allowed: false
  preferred_source_types:
    - file
expected_evidence:
  source_locators:
    - "/data/markdown/chro/april-12-memo.md"
  document_version_ids: []
  minimum_match_count: 1
must_not_use:
  source_locators:
    - "/data/markdown/chro/draft-workforce-plan.md"
gold_notes:
  required_facts:
    - "workforce planning decision"
    - "April 12 memo"
answerability: answerable
difficulty: medium
tags:
  - chronology
  - memo
  - single-source
```

## Recommended Fields

Core fields:

- `id`
- `query`
- `query_type`
- `source_scope.multi_source_allowed`
- `expected_evidence`
- `gold_notes`
- `answerability`
- `difficulty`
- `tags`

Useful optional fields:

- `must_not_use`
- `preferred_source_types`
- `role_pack`
- `notes_for_reviewer`
- `origin`
- `generated_from`

## Recommended Generated-Candidate Schema

For a larger generated set, a lighter schema is enough:

```yaml
id: gc-0198
query: "Brief me on the latest workforce planning update"
query_type: briefing
generated_from:
  source_locators:
    - "/data/markdown/chro/april-12-memo.md"
generation_method: document_grounded_llm
review_status: unreviewed
tags:
  - generated
  - synthesis
```

This keeps the generated pool cheap and flexible.

## Recommended Stress / Fuzz Schema

The stress set can be even lighter:

```yaml
id: sf-0042
query: "what did sarah say about the plan thing last week"
query_type: noisy_fact_lookup
generated_from:
  base_case: rq-0001
fuzz_type: colloquial
review_status: unreviewed
```

## Suggested File Layout

One workable repo structure would be:

```text
tests/
  retrieval_eval/
    benchmark/
      gold/
        queries.yaml
      generated/
        candidate_queries.yaml
      stress/
        fuzz_queries.yaml
    fixtures/
      corpus_manifest.yaml
      source_snapshots/
    reports/
      latest/
```

This keeps evaluation artifacts close to tests while separating trusted and untrusted sets.

## Corpus Generation Workflow

Recommended flow:

1. Select a bounded source slice from real CoS materials.
2. Generate candidate questions from those materials.
3. Classify candidates by query type.
4. Review a subset into the gold benchmark set.
5. Generate paraphrase and fuzz variants from approved gold cases.
6. Run retrieval evaluations.
7. Promote or retire cases over time based on usefulness.

## Recommended Initial Corpus Strategy

For the first usable version, keep it small and real.

Suggested first benchmark size:

- 40 to 60 curated gold cases
- 150 to 300 generated candidate cases
- 50 to 100 fuzz cases

Suggested initial composition:

- 15 direct factual queries
- 10 single-document interpretation queries
- 10 cross-document synthesis queries
- 10 briefing / summarization queries
- 5 no-answer cases

This is enough to guide improvement without creating an evaluation program too large to maintain.

## Suggested Evaluation Outputs

The evaluation harness should ideally record:

- retrieval hit/miss
- top-k evidence match
- single-source discipline pass/fail
- citation precision notes
- answer grounding notes
- latency
- provider/model used for synthesis if applicable

This makes the corpus useful not only for retrieval tuning but also for later model-routing decisions.

## Risks to Avoid

Avoid:

- treating generated answers as unquestioned gold truth
- using only synthetic documents instead of real corpus content
- over-indexing on summary-style prompts without factual cases
- mixing gold and unreviewed generated cases without clear labels
- tying the benchmark to one temporary document snapshot without version awareness

## Recommended Backlog Impact

If Epic 8 or an equivalent retrieval trust epic is added, the corpus work should become one of its first stories.

Suggested story themes:

- retrieval benchmark corpus and schema
- generated candidate corpus bootstrap
- evaluation harness and reporting
- operator validation of benchmark trustworthiness

## Final Recommendation

The best practical approach for CoS is:

> build the retrieval test corpus from real ingested materials, generate many candidate questions automatically, curate a smaller trusted benchmark set, and keep stress cases separate from release-gating cases.

That approach is fast enough to start soon, but disciplined enough to support real retrieval decisions later.
