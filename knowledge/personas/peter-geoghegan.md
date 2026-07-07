# Persona: Peter Geoghegan

- Last verified: 2026-06-12
- Source pin: e18b0cb7344
- Method: git log mining of source/ + cross-cut against committer-map.md,
  contributor-map.md, domain-ownership.md.

## Role + email(s)

- Long-time committer.
- Author/committer email in trailers: `Peter Geoghegan <pg@bowt.ie>`.
  [verified-by-code]

## Activity profile (last 24mo)

| Vector                                              | Count |
|-----------------------------------------------------|------:|
| Commits as author (24mo)                            | 92    |
| `Reviewed-by: Peter Geoghegan` in others' commits   | 18    |
| Distinct co-authors of his commits (24mo)           | ~4 (Matthias van de Meent ×3, plus 1-offs) |

Counts via `rtk proxy git -C source/ log --since='24 months ago'
--author='Peter Geoghegan' --oneline`. [verified-by-code]

### Subsystem footprint (file touches, 24mo, top areas)

| Path                            | Touches |
|---------------------------------|--------:|
| src/backend/access              | 179     |
| src/test/regress                | 33      |
| src/include/access              | 27      |
| doc/src/sgml                    | 21      |
| src/backend/utils               | 14      |
| src/backend/executor            | 10      |
| src/backend/commands            | 9       |
| src/include/utils               | 8       |
| src/include/storage             | 7       |
| src/backend/storage             | 6       |

`src/backend/access/nbtree/` alone receives **78 of his 92 commits**
(file touches; subjects also dominated by nbtree). [verified-by-code]

## Domain ownership

- **nbtree (B-tree index AM).** 78 of his 92 commits over 24mo touch
  `src/backend/access/nbtree/` or `src/include/access/nbtree.h` —
  **55.7%** of all distinct nbtree-touching commits in that window
  (78/140). This exactly matches the figure in `domain-ownership.md`.
  [verified-by-code]
- The next-largest nbtree contributor is **Peter Eisentraut (22)**,
  but inspection of those commits shows they are tree-wide cleanup
  sweeps (const-correctness, `fallthrough` attribute, `BufferGetPage()`
  cast removal, `amcancrosscompare` rename, etc.), not nbtree design
  work. The remaining authors (Álvaro 7, Tom Lane 6, Paquier 5,
  Plageman 5, Heikki 4, David Rowley 4, Andres 4) are all in
  single-digit incidental-edit territory. [verified-by-code]
- Themes within his nbtree work (24mo):
  - **Skip scan / skip arrays** — 7 commits (`92fe23d93aa3` "Add nbtree
    skip scan optimization" is the headline; followed by polish:
    parallel-alloc accounting, NULL-tuple advancement, primitive-scan
    scheduling, comment fixups).
  - **Parallel nbtree scans** — 7 commits hardening parallel-scan
    correctness (LWLock-based coordination, currPos confusion,
    pgstats accounting, SAOP hang fix, endpoint contract).
  - **`_bt_readpage` / `_bt_killitems` performance & invariants** —
    pointer-chasing avoidance, backwards-scan TID ordering,
    `_bt_search` stack allocation removal, killitems sort doc.
  - **Index-scan/heapam interface** — backed `dropPin` work via fake
    LSNs (moved fake-LSN infrastructure out of GiST to shared
    layer), reshaped `IndexFetchHeapData` to track heap blocks, added
    fake-LSN support to hash AM. This is the cross-AM cleanup arm.
  - **`IndexScanInstrumentation`** — converted to pointer in executor
    scan nodes; tied to his parallel-scan accounting work.

## Style + patterns

- **Title style:** terse, often domain-prefixed
  ("nbtree: …", "heapam: …"). Almost always imperative.
  [verified-by-code, sample of 30 subjects]
- **Body style:** dense, technically detailed multi-paragraph
  explanations of an invariant — what was held before, what is held
  now, why a corner case is/isn't reachable. He commits long
  comment-only patches ("Clarify why `_bt_killitems` sorts its items
  array", "Document nbtree row comparison design") — sign of an
  owner curating the subsystem's *narrative* in the source, not just
  the code.
- **Mixed author/committer activity:** 55 of his commits have
  `Author: Peter Geoghegan` self-attribution; 3 are
  Matthias van de Meent patches he committed; the rest cite him
  alone. He authors most of what he commits. [verified-by-code]
- **Cross-AM extraction work:** when a feature he wants for nbtree
  has analogues elsewhere (fake LSNs, index-scan instrumentation,
  buffer-pin tracking), he refactors the infrastructure into shared
  code rather than copying. This is a strong style signal — expect
  refactoring patches around any nbtree feature.


## Scenarios I'd review
<!-- persona-scenarios:auto -->

*Derived from Domain-ownership paths overlapping each scenario's §Files section. If this persona claims a directory and a scenario mentions any file under it, they're a likely reviewer.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

| Scenario | Via path(s) |
|---|---|
| [`add-new-operator-class`](../scenarios/add-new-operator-class.md) | `src/include/access/nbtree.h`, `src/backend/access/nbtree` |

<!-- /persona-scenarios:auto -->


## Subsystems I know
<!-- persona-subsystems:auto -->

*Derived from Domain-ownership paths overlapping each subsystem's `## Files owned` block.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

- [`access-nbtree`](../subsystems/access-nbtree.md)

<!-- /persona-subsystems:auto -->

## Common reviewer/collaborator partners

`Reviewed-by:` trailers inside his own commits (24mo) were sparse —
many of his commits have no `Reviewed-by:` line at all, consistent
with him being the resident expert and pushing his own polished
work. Where reviewers appear, the recurring names are Matthias
van de Meent (also a co-author, 3×), Heikki Linnakangas, and Tomas
Vondra (from broader signals; explicit per-commit trailer counts
are low). [inferred from sparse trailer data; needs deeper grep if
precise ranking matters — flagged `[partially verified]`]

Going outward: he is named as `Reviewed-by` in 18 commits over
24mo, spread across mostly storage / executor / index-related
work. He is not a fan-out reviewer for the wider tree.

## What to expect on a patch he would review

- He'll review **nbtree, hash, and the indexam/heapam interface
  layer**. Anything touching `IndexScanDesc`, `amgettuple`,
  `aminsert`, or `_bt_*` is in scope. Outside that, expect silence.
- Will push back on **invariant claims that aren't precisely
  stated**. His own commit messages document invariants down to
  the case analysis; he expects the same in patches he reviews.
- Strong attention to **parallel-scan correctness** —
  serialization order of `currPos`, LWLock vs. spinlock choice for
  per-scan coordination, advance/rescan races. If your patch
  touches parallel index scans, expect a deep read.
- Likes **separate refactor + behavior commits**. He himself
  routinely splits an infrastructure move from the change that
  uses it (e.g. fake-LSN move out of GiST → use in nbtree
  dropPin). Mixed-purpose patches will draw a "split this" reply.
- Will **document the design** alongside the code; if your nbtree
  patch lacks a README update or comment in
  `src/backend/access/nbtree/README`, expect a comment.

## Landmark commits (last 12mo)

- **`92fe23d93aa3`** (2025-) — "Add nbtree skip scan optimization."
  The headline feature: skip-scan over leading index columns.
  Followed by ~6 polish commits over the next 12 months
  (`b75fedcab791`, `9d924dbb37103`, `454c046094ab3`,
  `21a152b37f36c`, `748d871b7cb08`, `8aed8e168fd2d`). The series
  embodies his "land it, then polish for a year" pattern.
  [verified-by-code]
- **`67fc4c9fd7fa`** — "Make parallel nbtree index scans use an
  LWLock." Headline of the parallel-scan correctness theme.
  [verified-by-code]
- **`d8adfc18bebf`** — "Avoid parallel nbtree index scan hangs with
  SAOPs." A concurrency-bug fix that ties his array-key /
  skip-scan work to the parallel-scan plumbing. [verified-by-code]
- **`d774072f0040`** + **`8a879119a1d1`** — fake-LSN refactor (move
  out of GiST) followed by use in nbtree dropPin. Canonical
  example of his "refactor infra, then consume it" pattern.
  [verified-by-code]
- **`83a26ba59b18`** + **`65d6acbc5649`** + **`d071e1cfec23`**
  (2025-12) — `_bt_readpage` micro-perf series: pointer chasing
  avoidance, code relocation, stack-allocation removal. Indicates
  he periodically does performance passes on the hot read path.
  [verified-by-code]

## Notes / hedges

- **HIGH bus-factor — confirmed.** No one else does sustained
  nbtree design work. 78/140 nbtree commits (55.7%) are his; the
  next-largest contributor (Peter Eisentraut, 22) is doing
  tree-wide cleanup, not nbtree-specific design. Beyond that the
  drop is sharp — Álvaro 7, Tom Lane 6, Paquier 5, Plageman 5,
  none of which are nbtree-specialists. No obvious second-tier
  nbtree committer is shadowing him. **If he steps back, nbtree
  feature work and deep-bug triage have no clear successor.**
  [verified-by-code, corroborates domain-ownership.md]
- Possible shadows worth tracking (any of these picking up nbtree
  design work would lower the risk): **Matthias van de Meent**
  (3× co-author on his patches), **Heikki Linnakangas** (historical
  nbtree contributor, 4 commits 24mo), **Tomas Vondra** (3 nbtree
  touches 24mo). None of them is currently driving an nbtree
  feature series. [inferred]
- His **single-domain focus** means he is the natural reviewer for
  nbtree-touching patches but should not be expected to weigh in on
  optimizer, replication, or planner work; routing a non-index
  patch his way will likely get no reply.
- The 24mo throughput (92 commits, including a major feature in
  skip scan plus parallel-scan hardening and cross-AM refactors)
  is high and sustained. No sign of slowdown as of mid-2026.
  [verified-by-code]
