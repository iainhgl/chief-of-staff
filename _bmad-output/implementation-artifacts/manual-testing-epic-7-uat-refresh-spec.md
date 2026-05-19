---
title: 'Refresh Manual Testing Guide for Epic 7 UAT'
type: 'chore'
created: '2026-05-19'
status: 'done'
route: 'one-shot'
baseline_commit: '0d1615e3af12c7bd342ac3acf8c661a44ff6b92e'
---

# Refresh Manual Testing Guide for Epic 7 UAT

## Intent

**Problem:** The manual testing guide was still too centered on the older connected-source packs and did not clearly explain what Epic 7 adds, what the current product state is, or what the new retrieval-trust UAT is actually proving from a normal operator's perspective.

**Approach:** Reframe the guide around Test Pack 11 as the default Epic 7 gate, keep supporting packs for connected-source regressions, and add plain-English summaries alongside the technical runbook so operators can quickly tell what each path validates.

## Suggested Review Order

**Operator framing**

- Reframes the guide around the default Epic 7 path and clarifies scope boundaries.
  [`manual-testing.md:5`](../../docs/manual-testing.md#L5)

- Adds a quick route map and pack index so operators can choose the right test path.
  [`manual-testing.md:58`](../../docs/manual-testing.md#L58)

- Restructures bootstrap steps to keep the benchmark path clean and conditionalize connected-source setup.
  [`manual-testing.md:118`](../../docs/manual-testing.md#L118)

**Epic 7 gate**

- Explains, in user terms, what retrieval trust is actually checking before answer generation.
  [`manual-testing.md:1046`](../../docs/manual-testing.md#L1046)

- Clarifies benchmark-class intent, clean-database expectations, and retrieval-only scope.
  [`manual-testing.md:1062`](../../docs/manual-testing.md#L1062)

**Sign-off rules**

- Splits Epic 7 release-gate criteria from connected-source regression criteria.
  [`manual-testing.md:1303`](../../docs/manual-testing.md#L1303)
