# Real-World Evaluation Source Corpus

This folder is for larger, more realistic source documents that complement the
small deterministic `retrieval_eval` corpus.

This corpus is **manual-only**:

- it is not part of the automated release gate
- it is not intended for CI
- it is meant for optional operator sanity passes after extraction, chunking, or
  format-handling changes

Use this corpus for:

- extraction and normalization checks on real PDFs, DOCX files, and HTML pages
- chunking and retrieval checks on longer structured documents
- format-regression checks when PDF/DOCX/HTML handling changes
- operator UAT scenarios that should feel closer to production ingest

Do not use this folder as the primary gold retrieval gate:

- the existing `tests/fixtures/retrieval_eval/` corpus is still the fast,
  deterministic contract test for lineage, no-answer, and citation behavior
- this corpus is intentionally larger and messier, so it is better suited to
  UAT, regression packs, and format-realism checks

## Seed Set

The initial seed set is deliberately official and public-domain friendly:

- NIST technical publications and handbook sections
- GAO accessible report PDFs
- GovInfo bill text in both PDF and HTML

These were chosen because they are:

- official
- stable enough to re-download
- long enough to exercise chunking and mid-document retrieval
- varied across PDF, DOCX, and HTML

## Files

Tracked in git:

- `manifest.tsv` -- curated seed list and official source URLs
- `checksums.sha256` -- pinned SHA256 hashes for the current local corpus files
- `download_sources.sh` -- one-time curation helper that pulls from official
  upstream sources
- `verify_originals.sh` -- verifies local files in `originals/` against the
  committed checksums
- `snapshot-manifest.example.tsv` -- template for a pinned snapshot location
- `fetch_snapshot.sh` -- operator fetch path for a pinned snapshot corpus

Ignored locally:

- `originals/` payload files
- `snapshot-manifest.tsv` if you create a local snapshot manifest with real
  storage URLs

## Recommended Workflow

1. Curate the corpus once from official upstream sources with
   `download_sources.sh`.
2. Verify the local copies with `verify_originals.sh`.
3. Upload the verified originals to an immutable snapshot location such as:
   GitHub release assets, versioned S3, or versioned Cloudflare R2.
4. Copy `snapshot-manifest.example.tsv` to `snapshot-manifest.tsv` and replace
   the `TBD` URLs with your pinned snapshot URLs.
5. For future manual sanity runs, use `fetch_snapshot.sh` instead of downloading
   from the live public source URLs again.
6. After the snapshot exists, remove local originals whenever you want a clean
   worktree. They can be re-fetched later.

The key policy is simple: upstream URLs are for curation; the snapshot manifest
is for repeatable manual testing.

## Public-Domain Notes

- NIST SP 800 publications are explicitly described by NIST as not subject to
  copyright in the United States.
- GAO accessible PDFs include a notice that the work is not subject to
  copyright protection in the United States, though embedded third-party images
  may have separate rights.
- GovInfo states that U.S. government works are generally public domain under
  17 U.S.C. § 105, while noting some publications may contain third-party
  material used with permission.

## Suggested Next Step

Once downloaded, the next useful addition would be a thin query manifest for a
small number of high-value long-document checks:

- answer found near the start
- answer found in the middle
- answer found near the end
- table or appendix lookup
- no-answer case
- cross-format duplicate or near-duplicate case
