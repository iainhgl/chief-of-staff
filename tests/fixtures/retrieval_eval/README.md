# Retrieval Evaluation Corpus

Version-controlled benchmark assets for the CoS retrieval harness.

## Layer Layout

```
retrieval_eval/
  generated/   Synthetic candidate documents — safe to commit, reproducible fixtures
  gold/        Curated benchmark queries with expected lineage and answerability
  stress_fuzz/ Adversarial and noisy cases, one per major query class
```

- **generated/**: Markdown documents ingested into Postgres for each benchmark run.
  Filenames use a stable slug so fixture IDs remain consistent.
- **gold/**: Query manifests in YAML. These are the authoritative benchmark cases.
  Each entry maps directly to the query-class taxonomy defined in the harness.
- **stress_fuzz/**: Additional YAML manifests with adversarial inputs (noisy phrasing,
  misleading topic overlap, empty-corpus cases). Included in full benchmark runs.

## Manifest Schema

Each YAML manifest contains a top-level `queries` list. Every item must have:

```yaml
queries:
  - id: string                     # stable, unique across all manifests
    query: string                  # the query text passed to the retrieval service
    query_class: string            # one of the seven classes below
    answerable: bool               # true = expect grounded evidence, false = no-answer
    expected_lineage:              # list of acceptable source_locator values
      - string                     # at least one required when answerable is true
    notes: string                  # optional context for reviewers
```

### Query Classes

| Class | Description |
|-------|-------------|
| `direct_fact` | Single-fact lookup from one document |
| `exact_phrase` | Verbatim phrase retrieval |
| `date_timeline` | Date or chronological fact |
| `single_doc_interpretation` | Interpretation of one document |
| `cross_doc_synthesis` | Explicit multi-source synthesis or comparison |
| `briefing` | Briefing-style aggregation (may span sources) |
| `no_answer` | Query that should return no grounded evidence |

### Answerability Contract

- `answerable: true` → the system must return at least one citation whose
  `source_locator` appears in `expected_lineage`.
- `answerable: false` → the system must return an empty citation set (no-answer
  response). Any grounded answer is scored as a failure.

### Expected Lineage

For `direct_fact`, `exact_phrase`, `date_timeline`, and `single_doc_interpretation`
queries, list exactly one acceptable locator. The harness resolves that locator to the
full citation contract at run time: `source_alias`, `source_locator`,
`document_version_id`, and `chunk_index`. Any returned citation outside that resolved
set is treated as a precision error.

For `cross_doc_synthesis` and `briefing` queries, list every acceptable locator.
The harness allows the returned evidence set to be a subset of the acceptable set, but
every returned citation still must resolve to one of those approved sources.

## Versioning

The corpus version is derived from the corpus file paths and file contents at run time.
Reports include the resolved version so results from different runs are comparable even
outside a git checkout.
