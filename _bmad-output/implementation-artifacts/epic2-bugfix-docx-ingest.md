# Epic 2 Bugfix: DOCX Ingest Fallback

Status: done

## Story

As Iain (operator and platform maintainer),
I want `.docx` ingestion to succeed during Epic 2 manual testing even when Apache Tika returns an empty body,
So that Word documents remain ingestible and the Epic 2 operator validation path is reliable.

## Context

During manual test `T2.6.1` in [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md:276), `sample-memo.docx` failed with:

```text
Error ingesting sample-memo.docx: Tika returned no content for sample-memo.docx
```

Inspection of [`test-docs/sample-memo.docx`](/Users/iain.livingstone/Development/CoS/cos/test-docs/sample-memo.docx) confirmed the fixture contains valid WordprocessingML text, so the failure was not caused by an empty or corrupt test document.

## Acceptance Criteria

1. **Given** a `.docx` file is passed to the ingestion pipeline,
   **When** Tika returns extracted text,
   **Then** the existing Tika-based path is preserved unchanged.

2. **Given** a `.docx` file is passed to the ingestion pipeline,
   **When** Tika returns an empty body,
   **Then** the extractor falls back to reading `word/document.xml` directly from the DOCX package and returns plain text when present.

3. **Given** the fallback path is used,
   **When** the extracted text is non-empty,
   **Then** the rest of the ingest pipeline continues normally without special handling in the CLI or service layer.

4. **Given** invalid or empty DOCX XML content is encountered,
   **When** fallback extraction cannot recover usable text,
   **Then** a clear `ExtractionError` is still raised.

## Implementation Notes

- Added a DOCX-specific fallback in [`src/cos/ingestion/extractor.py`](/Users/iain.livingstone/Development/CoS/cos/src/cos/ingestion/extractor.py:1).
- The fallback opens the DOCX as a ZIP archive, reads `word/document.xml`, walks WordprocessingML paragraph/text nodes, and reconstructs plain text.
- Tika remains the primary extraction path for `.docx`; fallback is used only when Tika returns no content.
- PDF behavior is unchanged.

## Files Changed

- [`src/cos/ingestion/extractor.py`](/Users/iain.livingstone/Development/CoS/cos/src/cos/ingestion/extractor.py:1) — added `_extract_docx_xml()` fallback and wired it into `_extract_via_tika()`
- [`tests/ingestion/test_extractor.py`](/Users/iain.livingstone/Development/CoS/cos/tests/ingestion/test_extractor.py:1) — added unit coverage for DOCX XML fallback and the Tika-empty-body fallback path
- [`src/cos/cli.py`](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py:66) — improved folder ingest summary so full failure of supported files reports accurately

## Validation

- `uv run pytest tests/ingestion/test_extractor.py -q`
- `uv run pytest tests/services/test_ingestion_service.py tests/ingestion/test_pipeline.py -q`
- Manual verification: reran Epic 2 manual ingest flow with Zscaler disabled and confirmed `.docx` no longer fails because of empty Tika output

## Follow-up

- The separate Voyage embedding SSL failure was diagnosed as an environment trust issue related to Zscaler interception, not part of this DOCX fix.
- If Tika behavior differs across environments for Office documents, this fallback should remain in place as a resilience measure rather than a temporary workaround.
