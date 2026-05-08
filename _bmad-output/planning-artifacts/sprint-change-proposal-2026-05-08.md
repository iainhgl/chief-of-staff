# Sprint Change Proposal - Epic 6 UAT Open Findings

**Project:** CoS  
**Date:** 2026-05-08  
**Prepared by:** Codex via `bmad-correct-course`  
**Mode used:** Batch

## 1. Issue Summary

### Trigger

This proposal is driven by the open findings in [epic-6-uat-findings-2026-05-07.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epic-6-uat-findings-2026-05-07.md):

- `UAT-05` retrieval grounding and citation precision
- `UAT-06` Gmail re-scan / re-queue behavior after successful processing
- `UAT-07` connected-source operator setup and troubleshooting documentation

`UAT-01` through `UAT-04` were already fixed in PR #44 and are out of scope for backlog changes.

### Problem Statement

This is a **post-UAT quality and operational hardening change**, not a product pivot.

- `UAT-05` shows the retrieval path is functionally working but not yet trustworthy enough for operator-facing cited Q&A in a mixed-source corpus.
- `UAT-06` shows Gmail sync is data-safe but operationally inefficient because already-processed matching messages can still be discovered and re-queued.
- `UAT-07` shows connected-source onboarding is still too dependent on tribal knowledge, even after Story 6.12's documentation pass.

### Evidence

- The UAT artifact records at least one concrete mixed-source retrieval answer that blended a correct Gmail body citation with an unrelated attachment fact from a different record.
- The UAT artifact also confirms repeated Gmail scans continue to enqueue work for messages that still match the Gmail query after successful processing.
- Current operator docs in [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md) and [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) already cover the main Epic 6 workflow, which means `UAT-07` is better understood as a deeper support/onboarding need than as a missing core feature.

## 2. Checklist Findings

### Section 1 - Trigger and Context

- `[x] 1.1` Trigger identified: Epic 6 live UAT, especially Story 6.11 validation across Gmail, Calendar, MCP ingest, and mixed-source retrieval
- `[x] 1.2` Core problem defined: retrieval trust needs hardening; Gmail processed-message semantics need to be explicit; operator setup still needs a stronger support layer
- `[x] 1.3` Evidence gathered from the UAT findings artifact, current planning documents, and current operator docs

### Section 2 - Epic Impact Assessment

- `[x] 2.1` Epic 6 can still complete as planned in principle, but it should remain open until retrieval trust and Gmail re-queue semantics are addressed
- `[x] 2.2` Epic-level change required: add follow-on hardening stories to Epic 6
- `[x] 2.3` Future-epic impact confirmed: Epic 7 depends on trustworthy retrieval and predictable connected-source behavior
- `[x] 2.4` No new epic is required; the change fits as additional Epic 6 hardening stories
- `[x] 2.5` Epic priority change recommended: finish Epic 6 hardening before starting Epic 7

### Section 3 - Artifact Conflict and Impact Analysis

- `[x] 3.1` PRD conflict: no immediate PRD conflict; the open findings mostly show current implementation falling short of existing grounded-answer and operator-usability expectations
- `[x] 3.2` Architecture impact: targeted clarification is needed for retrieval evidence selection and Gmail processed-message semantics
- `[N/A] 3.3` UI/UX impact: no dedicated UI/UX artifact exists for this backend platform
- `[x] 3.4` Secondary artifacts affected: `epics.md`, `sprint-status.yaml`, connector/operator docs, and a focused UAT rerun plan

### Section 4 - Path Forward Evaluation

- `[x] 4.1` Option 1 Direct Adjustment: **Viable**. Effort: Medium. Risk: Medium.
- `[ ] 4.2` Option 2 Potential Rollback: **Not viable**. The UAT issues do not justify reverting Epic 6 work.
- `[ ] 4.3` Option 3 PRD MVP Review: **Not viable as the main path**. MVP/Growth scope is still valid.
- `[x] 4.4` Recommended path: **Direct adjustment inside Epic 6 with targeted architecture clarification**

### Section 5 - Proposal Components

- `[x] 5.1` Issue summary prepared
- `[x] 5.2` Epic impact and artifact adjustments documented
- `[x] 5.3` Recommended path and rationale documented
- `[x] 5.4` MVP impact and action plan documented
- `[x] 5.5` Handoff plan defined

### Section 6 - Final Review

- `[x] 6.1` Checklist reviewed for completeness
- `[x] 6.2` Proposal reviewed for internal consistency
- `[!] 6.3` User approval still required before updating `epics.md` or `sprint-status.yaml`
- `[!] 6.4` Story creation should follow approval of this proposal

## 3. Impact Analysis

### Epic Impact

**Epic 6: Canonical Source Identity & Connected Ingestion**

- Directly affected.
- The epic should stay `in-progress`.
- Story 6.12 already covered the broad documentation alignment pass, but UAT shows two additional product-behavior hardening gaps remain.
- The cleanest correction is to append follow-on stories after Story 6.12 rather than reopen earlier Epic 6 implementation stories.

**Epic 7: Ambient Messaging Intelligence**

- Indirectly but materially affected.
- Telegram Q&A, web-augmented answers, morning briefs, and meeting prep all amplify the consequences of weak retrieval grounding.
- Epic 7 should not start until the `UAT-05` stories are complete and validated.

### Story Impact

`UAT-05` should become **two concrete stories**:

1. `retrieval-result-thresholding-and-citation-pruning`
2. `single-source-factual-grounding-for-retrieve`

Rationale:

- the first story addresses noisy mixed-result retrieval sets and over-inclusive citations
- the second story addresses answer-generation behavior for direct factual prompts where blending across source locators is unsafe

`UAT-06` should become **one concrete story**:

3. `gmail-processed-message-semantics-and-requeue-prevention`

Rationale:

- this is a stable operator-behavior contract question, not just a local bugfix
- it likely touches connector semantics, sync bookkeeping, and possibly future OAuth-scope choices

`UAT-07` should **not** become a product backlog story yet.

Rationale:

- Story 6.12 already delivered the general docs alignment pass
- the remaining gap is operator support depth, not missing platform capability
- the best documentation set depends on the final Gmail processed-message workflow chosen in `UAT-06`

### Artifact Impact

**PRD**

- **No update recommended now.**
- Existing PRD language already expects grounded answers with citations and operator-manageable setup.
- These findings are better treated as implementation shortfalls against current expectations, not as new requirements.
- Revisit only if the chosen Gmail solution explicitly requires mailbox mutation as the normal contract, which would justify documenting a higher-permission connector model.

**Architecture**

- **Targeted update recommended.**
- Add or revise sections that define:
  - retrieval evidence filtering before synthesis
  - citation emission limited to evidence actually supporting the answer
  - a default single-source grounding rule for direct factual queries unless the prompt clearly requests synthesis/comparison
  - Gmail processed-message tracking semantics, with label mutation explicitly documented as optional future behavior rather than assumed MVP/Growth behavior

**Epics**

- **Update required.**
- Add three new follow-on Epic 6 stories after Story 6.12.
- Keep `UAT-07` as a documentation/support planning note, not a new product story.

**Sprint Status**

- **Update required after approval and story creation.**
- Keep `epic-6` as `in-progress`.
- Add the new stories in `backlog` or `ready-for-dev` once story files are created.
- Do not add a new backlog item for `UAT-07` at this stage.

### Technical / Operational Impact

- Retrieval ranking and synthesis inputs need a stronger evidence contract.
- Citation formatting must distinguish between retrieved candidates and cited supporting evidence.
- Gmail sync needs a durable notion of "already processed successfully" beyond canonical deduplication alone.
- Operator docs need a focused support/troubleshooting extension only after those behavior decisions land.

## 4. Recommended Approach

### Recommendation

Proceed with a **Moderate-scope direct adjustment** inside Epic 6:

1. Add two retrieval-hardening stories for `UAT-05`
2. Add one Gmail processing-semantics story for `UAT-06`
3. Hold `UAT-07` as documentation/support follow-up work outside the current product backlog
4. Delay Epic 7 start until the retrieval-hardening stories are complete and revalidated

### Why This Path

- It fixes the highest-trust issue first without reopening earlier epics.
- It keeps the change bounded to Epic 6 hardening instead of creating a new epic.
- It avoids prematurely codifying operator docs for a Gmail workflow that is still unsettled.
- It preserves momentum while reducing the risk that Epic 7 amplifies already-known retrieval weaknesses.

### Effort / Risk / Timeline

- **Effort:** Medium
- **Risk if done now:** Medium
- **Risk if deferred into Epic 7:** High
- **Timeline impact:** Epic 6 likely gains three follow-on stories and remains open for one additional hardening cycle before Epic 7 begins

## 5. Detailed Change Proposals

### 5.1 PRD Changes

**Recommendation:** No PRD edit now.

Reasoning:

- `UAT-05` and `UAT-06` fit inside existing requirements for grounded cited answers, retrieval usefulness, and connected-source ingestion.
- The only plausible PRD trigger would be a deliberate decision that Gmail processing must mutate mailbox labels as the standard product contract. That should be decided in the `UAT-06` story first, not precommitted in planning.

### 5.2 Architecture Changes

#### Architecture Change A - Retrieval Evidence Contract

**Section:** `architecture.md` -> retrieval layer / response contract

**CURRENT**

- Retrieval and citation integrity are defined at a high level.
- The architecture does not yet explicitly separate:
  - candidate retrieval set
  - evidence passed into synthesis
  - citations returned to the user

**PROPOSED**

- Introduce an explicit retrieval evidence-selection rule:
  - apply a configurable relevance floor before synthesis
  - allow synthesis to operate only on the filtered evidence set
  - emit citations only for evidence actually used to support the answer
- Introduce a direct-factual grounding rule:
  - when a prompt is a factual lookup about one apparent source item, default to single-source grounding
  - require the prompt to explicitly request synthesis/comparison before blending across source locators

**Rationale**

This converts `UAT-05` from an informal quality expectation into an architectural contract that stories can implement and test against.

#### Architecture Change B - Gmail Processed-Message Semantics

**Section:** `architecture.md` -> connectors / jobs / Gmail connector behavior

**CURRENT**

- Gmail sync is queue-backed and fault-isolated.
- The architecture does not yet define how the connector knows a matching message has already been processed successfully.

**PROPOSED**

- Add a processed-message rule for Gmail:
  - successful processing should create or update durable bookkeeping that prevents default re-queue of the same observed Gmail message body or attachment source on later scans
  - canonical deduplication remains the integrity backstop, not the normal operator-facing mechanism for repeated scans
  - mailbox label mutation may be documented as an optional future enhancement, not the default required behavior

**Rationale**

This keeps the connector read-friendly by default while giving operators predictable "work remaining" semantics.

### 5.3 Epic / Story Changes

#### Epic Change A - Extend Epic 6 With Retrieval Hardening

**Section:** `epics.md` -> append after Story 6.12

**CURRENT**

- Epic 6 ends with Story 6.12 documentation and housekeeping.

**PROPOSED**

Add:

##### Story 6.13: Retrieval Result Thresholding and Citation Pruning

As a user,  
I want retrieval to filter low-signal results and cite only supporting evidence,  
So that grounded answers stay precise in a mixed-source corpus.

**Acceptance Criteria (proposed):**

- Given a mixed-source retrieval query, when the search results are assembled, then chunks below a configurable relevance threshold are excluded from synthesis input.
- Given an answer is synthesized, when citations are returned, then the citation list includes only chunks or source records that materially support the answer rather than the full pre-filter retrieval set.
- Given no result clears the relevance threshold, when `retrieve` completes, then it returns the normal no-relevant-content behavior rather than forcing a weakly grounded answer.
- Given the filtered retrieval path runs under normal conditions, when measured end to end, then it remains within the existing retrieval latency target.

##### Story 6.14: Single-Source Factual Grounding for `retrieve`

As a user,  
I want direct factual questions to stay grounded in the source actually being asked about,  
So that the answer layer does not blend facts across similar but distinct records.

**Acceptance Criteria (proposed):**

- Given a direct factual query about one apparent source item, when the retrieval service prepares synthesis context, then it defaults to evidence from the best matching single source locator or document version rather than mixing multiple unrelated source items.
- Given a query explicitly asks for synthesis, comparison, or aggregation, when retrieval runs, then multi-source evidence remains allowed.
- Given a single-source grounded answer is returned, when citations are inspected, then they point to the same source lineage that supports the factual claim.
- Given a mixed-source corpus containing semantically similar Gmail, local-file, or MCP-note records, when a factual lookup is tested, then the answer does not import unsupported facts from sibling records.

#### Epic Change B - Extend Epic 6 With Gmail Processed-Message Semantics

**Section:** `epics.md` -> append after Story 6.14

**PROPOSED**

##### Story 6.15: Gmail Processed-Message Semantics and Requeue Prevention

As an operator,  
I want Gmail sync to skip already-processed matching messages by default,  
So that normal operation does not keep re-scanning and re-queueing work that has already completed successfully.

**Acceptance Criteria (proposed):**

- Given a Gmail message body or attachment source has already been processed successfully, when the same message still matches the configured query on a later sync, then the connector skips re-queueing it by default.
- Given a Gmail message changes in a way that should be treated as new ingestable content or a new source observation, when sync runs, then the connector still submits the appropriate work safely.
- Given the connector resumes after restart, when it evaluates whether to queue matching Gmail content, then processed-message bookkeeping survives restart and does not depend on in-memory state.
- Given the operator needs to intentionally reprocess Gmail content, when they follow the documented recovery path, then a supported override exists without requiring manual database surgery.

### 5.4 Sprint Status Changes

**Section:** `sprint-status.yaml`

**CURRENT**

- `epic-6: in-progress`
- stories through `6-12-documentation-and-housekeeping`
- `epic-7: backlog`

**PROPOSED**

After approval and story creation, append:

- `6-13-retrieval-result-thresholding-and-citation-pruning: backlog`
- `6-14-single-source-factual-grounding-for-retrieve: backlog`
- `6-15-gmail-processed-message-semantics-and-requeue-prevention: backlog`

Keep:

- `epic-6: in-progress`
- `epic-7: backlog`

Do not add:

- any new sprint-status line for `UAT-07` at this time

### 5.5 Documentation / Support Handling

**Recommendation:** Keep `UAT-07` as documentation/support work, not product backlog work.

**Suggested handling:**

- reopen or extend operator docs only after Stories 6.13 to 6.15 land
- package the work as a support guide or operator runbook refinement, not a core feature story
- focus the future doc pass on:
  - exact `config.yaml` shape expectations for Google OAuth
  - service recreate/restart rules after config changes
  - host-vs-container command boundary
  - Google test-user setup in Testing-mode apps
  - explicit Gmail API and Calendar API enablement checklist
  - expected Docker health states, especially `worker`
  - a short troubleshooting decision tree

This can be handled as:

- a documentation patch attached to the eventual story completion, or
- a later support/documentation planning item if a standalone operator handoff pack becomes a priority

## 6. Suggested Story Ordering and Scheduling Impact

### Recommended Order

1. Merge PR #44 and close out the already-fixed UAT defects
2. Create Story 6.13 `retrieval-result-thresholding-and-citation-pruning`
3. Create Story 6.14 `single-source-factual-grounding-for-retrieve`
4. Re-run a focused retrieval UAT pass against mixed-source corpus examples
5. Create Story 6.15 `gmail-processed-message-semantics-and-requeue-prevention`
6. Refresh operator support docs only after the final Gmail semantics are settled
7. Start Epic 7

### Scheduling Impact

- Epic 6 remains open and becomes the active hardening epic until these follow-on stories are complete.
- Epic 7 should stay in backlog until the two retrieval trust stories are done and revalidated.
- `UAT-06` can follow immediately after retrieval hardening; it is important, but less blocking to user trust than `UAT-05`.
- `UAT-07` should not delay story creation or sprint tracking now.

## 7. Implementation Handoff

### Scope Classification

**Moderate**

This requires backlog reorganization and targeted planning-artifact updates, but not a fundamental replan and not a PRD reset.

### Recommended Handoff

- **Product Owner / planning workflow**
  - approve this sprint change proposal
  - create the three new Epic 6 story files
  - update `epics.md` and `sprint-status.yaml`

- **Developer workflow**
  - implement Stories 6.13 through 6.15 in order
  - add focused regression coverage for mixed-source retrieval and processed-message requeue behavior
  - rerun the relevant UAT slice before Epic 7 begins

### Success Criteria

- retrieval answers no longer cite irrelevant low-signal chunks in the tested mixed-source scenarios
- direct factual queries do not blend unsupported facts across sibling source records
- repeated Gmail sync runs do not normally re-queue already-processed messages
- Epic 6 can be closed with retrieval trust and Gmail operator behavior explicitly validated

## 8. Final Recommendation Summary

- **PRD:** no change now
- **Architecture:** yes, targeted clarification
- **Epics:** yes, add three follow-on Epic 6 stories
- **Sprint status:** yes, after approval and story creation
- **Concrete stories:** create stories for `UAT-05` and `UAT-06`; do not create one yet for `UAT-07`
- **Documentation/support only:** keep `UAT-07` out of the backlog for now and revisit after the behavior stories land
