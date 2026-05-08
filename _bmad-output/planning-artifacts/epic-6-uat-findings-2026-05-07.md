---
date: 2026-05-07
project: CoS
sourceArtifacts:
  - docs/manual-testing.md
  - _bmad-output/implementation-artifacts/6-11-operator-validation-connected-sources-live.md
  - _bmad-output/implementation-artifacts/6-12-documentation-and-housekeeping.md
relatedPullRequests:
  - https://github.com/iainhgl/chief-of-staff/pull/44
status: draft
---

# Epic 6 UAT Findings

**Date:** 2026-05-07  
**Project:** CoS  
**Context:** Full Epic 6 manual UAT run against the connected-ingestion platform using local file ingest, Gmail, Google Calendar, MCP note ingest, restart/recovery, and retrieval flows.

## Purpose

This document captures the concrete findings from Epic 6 UAT in a form that can be triaged into:

- immediate patch work
- planned implementation stories
- backlog or architecture corrections
- future operator/support documentation work

It is intentionally separate from the implementation PR and separate from the future support/getting-started document.

---

## UAT Outcome Summary

Epic 6 UAT is a **functional pass** overall:

- local ingest works
- canonical identity and cross-source exact-byte dedupe work
- Gmail, Calendar, and MCP ingest all work end to end
- restart and token persistence work
- version history works

However, UAT surfaced several issues that should drive follow-on work:

1. four concrete product defects were found and patched during UAT
2. retrieval quality is functionally acceptable but not trustworthy enough for operator use without follow-up improvement
3. Gmail reprocessing behavior is operationally safe but not operationally efficient
4. connected-source setup has enough friction that a dedicated operator support doc should be planned

---

## Triage Summary

| ID | Finding | Severity | Disposition | BMAD Next Step |
|----|---------|----------|-------------|----------------|
| UAT-01 | Worker container booted the MCP server instead of `cos-worker` | High | Fixed in PR | None after merge |
| UAT-02 | Worker startup logs were not visible in Docker logs | Medium | Fixed in PR | None after merge |
| UAT-03 | Gmail sync used invalid API parameter `format=\"FULL\"` | High | Fixed in PR | None after merge |
| UAT-04 | Long Gmail attachment IDs caused staged filename overflow | High | Fixed in PR | None after merge |
| UAT-05 | Retrieval returns noisy/unrelated citations and may blend facts across sources | High | Open | `bmad-correct-course`, then create story/stories |
| UAT-06 | Gmail messages that still match the query are re-scanned and re-queued after successful processing | Medium | Open | `bmad-correct-course`, then create story |
| UAT-07 | Connected-source onboarding and operator setup required non-trivial troubleshooting | Medium | Open | Create docs/support story later |

---

## Resolved Defects

### UAT-01: Worker container booted the wrong long-running process

**Symptom**  
`docker compose up` showed `worker` starting and then exiting. The worker container launched the MCP server process instead of the worker loop.

**Impact**  
Background Gmail and Calendar ingest could never drain the jobs queue in a stable way.

**Root Cause**  
The image used a hard Docker `ENTRYPOINT` for `cos-mcp`, while the `worker` service only overrode `command`. Docker appended the worker command rather than replacing the entrypoint.

**Resolution**  
Changed the image default from `ENTRYPOINT` to `CMD` so the worker service can cleanly run `cos-worker`.

**Disposition**  
Fixed in PR #44.

### UAT-02: Worker logs were effectively invisible

**Symptom**  
The manual test expected `worker starting` in `docker compose logs worker`, but the worker process did not initialize logging output.

**Impact**  
Operator verification was confusing and reduced observability for queue-drain troubleshooting.

**Root Cause**  
`src/cos/worker.py` did not call `logging.basicConfig(...)` in its entrypoint.

**Resolution**  
Initialized worker logging at startup.

**Disposition**  
Fixed in PR #44.

### UAT-03: Gmail sync fetched messages with an invalid API parameter

**Symptom**  
Gmail sync scanned messages but failed to fetch them, logging that parameter `format=\"FULL\"` was invalid.

**Impact**  
No Gmail body or attachment jobs could be enqueued for real messages.

**Root Cause**  
The Gmail API expects lowercase `full`, not uppercase `FULL`.

**Resolution**  
Changed the request parameter to `format=\"full\"`.

**Disposition**  
Fixed in PR #44.

### UAT-04: Long Gmail attachment IDs overflowed staged-path filename limits

**Symptom**  
Gmail sync failed with `[Errno 36] File name too long` while staging an attachment file on disk.

**Impact**  
Certain real-world Gmail attachments could not be ingested even though provenance and content were otherwise valid.

**Root Cause**  
The staged filename embedded the full Gmail attachment slug, which can exceed filesystem filename limits.

**Resolution**  
Shortened only the on-disk staged filename while preserving the full Gmail provenance locator in the database and tool responses. Added regression coverage.

**Disposition**  
Fixed in PR #44.

---

## Open Product / Planning Findings

### UAT-05: Retrieval grounding and citation precision need follow-up work

**Symptom**  
Mixed-source retrieval succeeded functionally, but responses included:

- unrelated low-signal citations
- citations for chunks that did not clearly support the final answer
- at least one answer that blended facts from multiple retrieved records into a single factual claim

**Concrete UAT Example**  
The retrieval question about the seeded Gmail message returned the correct Gmail body marker, but also asserted an attachment fact pulled from a different Gmail source. That fact existed elsewhere in the corpus, but not in the specific seeded retrieval message being asked about.

**Impact**  
This is a trust issue. The retrieval path is operational, but the system is not yet precise enough for operator-facing cited Q&A when the corpus contains many semantically similar UAT or production records.

**Likely Causes**

- retrieval always returns up to `top_k` chunks with no minimum relevance threshold
- the synthesis layer receives the full mixed-source chunk set
- the returned citation list is the full retrieval set, not just the evidence actually used in the answer
- direct factual questions are not constrained to stay within a single source locator unless the user explicitly asks for synthesis

**Recommended Change**

Split this into one or two follow-on stories:

1. retrieval result filtering and citation precision
2. factual-answer grounding rules for single-source queries

**Recommended BMAD Path**

- Run `bmad-correct-course` because this affects behavior, quality expectations, and likely story boundaries.
- Then create one or more implementation stories.

**Story Candidates**

- `retrieval-result-thresholding-and-citation-pruning`
- `single-source-factual-grounding-for-retrieve`

### UAT-06: Gmail messages are re-scanned and re-queued after successful processing

**Symptom**  
If a Gmail message still matches the configured query after a successful sync, the next `cos sync gmail` run will discover it again and enqueue the same source locators again. Canonical identity prevents duplicate content creation, but the queue work still repeats.

**Impact**

- unnecessary queue churn
- avoidable worker activity
- confusing operator behavior if mailbox state is meant to represent “work remaining”

**Current State**

- safe from a data-integrity perspective
- not ideal from an operational perspective

**Design Direction Discussed During UAT**

Best likely direction:

1. a Gmail filter or label marks messages as eligible
2. the app tracks or detects already-processed message identity
3. optionally, a successful sync applies a processed label or removes the ingest label

This would likely require a future move from read-only Gmail scope to `gmail.modify` if the product is expected to mutate mailbox labels directly.

**Recommended Change**

Treat this as a product behavior story, not just a local patch.

**Recommended BMAD Path**

- Run `bmad-correct-course` because this changes connector semantics, OAuth scope expectations, and operator workflow.
- After approval, create an implementation story for processed-message handling.

**Story Candidate**

- `gmail-processed-message-semantics-and-requeue-prevention`

### UAT-07: Connected-source operator setup needs a dedicated support/onboarding document

**Symptom**  
The connected-source UAT required several manual recovery and setup clarifications beyond the existing docs:

- how `config.yaml` must be shaped for Google OAuth
- which services must be recreated after config changes
- difference between bind-mounted config and image-baked source code
- Google test-user setup for apps in Testing mode
- separate enablement of Gmail API and Google Calendar API
- expected Docker health states, especially `worker` being `Up` rather than `healthy`
- manual restart and validation flow

**Impact**  
This is manageable for a technical operator, but it is too much tribal knowledge to leave only in chat history.

**Recommended Change**

Create a support/getting-started document after planning decides the desired operator workflow and after any Gmail-processing semantics story is settled.

**Recommended BMAD Path**

- Do **not** convert this directly into a product story yet.
- Hold it as a documentation/support follow-up for the next planning phase.

**Story Candidate (later)**

- `connected-sources-operator-setup-and-troubleshooting-guide`

---

## Suggested Next Scheduling Order

If the goal is to convert UAT learnings into schedulable work, the recommended order is:

1. Merge PR #44
2. Run `bmad-correct-course` for retrieval-quality and Gmail processed-message behavior
3. Approve the resulting change proposal
4. Create follow-on stories
5. Add those stories to `sprint-status.yaml`
6. Keep the operator/support doc as a separate documentation planning item

Recommended priority:

1. Retrieval grounding and citation precision
2. Gmail processed-message semantics / requeue prevention
3. Connected-source operator support document

---

## Proposed Story Backlog Seeds

These are placeholders, not approved story files yet:

- `retrieval-result-thresholding-and-citation-pruning`
  - goal: reduce noisy citations and improve result precision for direct questions

- `single-source-factual-grounding-for-retrieve`
  - goal: prevent the answer layer from blending facts across unrelated source locators for direct factual prompts

- `gmail-processed-message-semantics-and-requeue-prevention`
  - goal: avoid rescanning and re-queuing already processed Gmail messages in normal operation

- `connected-sources-operator-setup-and-troubleshooting-guide`
  - goal: capture the connected-source bootstrap, auth, API enablement, restart, and troubleshooting workflow

---

## Notes For Future Planning Session

- The near-duplicate warning flow worked, but only reliably after lowering the threshold for the test environment. This is a validation note, not currently a defect.
- The retrieval UAT should be treated as a **quality finding**, not a total failure of Epic 3 or Epic 6 functionality.
- The Gmail requeue behavior is currently acceptable for integrity, but not yet ideal for production operator ergonomics.
- This findings document should be used as the input artifact for the next `bmad-correct-course` session rather than rewritten from scratch.
