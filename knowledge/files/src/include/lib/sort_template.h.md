# `src/include/lib/sort_template.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** ~370

## Role

Templated qsort, generated per element-type via `#define ST_SORT
…; #include "lib/sort_template.h"`. Replaces ad-hoc qsorts in
tuplesort, btree-build, bitmapset operations, and elsewhere with
type-specialized inlineable code. Based on NetBSD `qsort.c` 1.13
with PG-specific modifications: presort-detection check (instead
of swap_cnt heuristic), bounded recursion via tail-call on the
larger partition, header-template form. [from-comment]
`source/src/include/lib/sort_template.h:65-78`

## Required parameters

- `ST_SORT` — function name to generate
- `ST_ELEMENT_TYPE` (or `ST_ELEMENT_TYPE_VOID` for generic
  void* with element_size)
- `ST_DECLARE` / `ST_DEFINE` / `ST_SCOPE`
- one of: `ST_COMPARE(a,b)`, `ST_COMPARE(a,b,arg)`, or
  `ST_COMPARE_RUNTIME_POINTER`
- optional: `ST_COMPARE_ARG_TYPE`, `ST_CHECK_FOR_INTERRUPTS`

[verified-by-code] header lines 11-64.

## Invariants

- INV-1: stack-bounded: PG-specific fix recurses on smaller
  partition only (line 73), so recursion depth ≤ log2(n). NetBSD
  upstream had unbounded recursion on adversarial inputs.
  [from-comment] line 73 — this is a documented hardening over
  upstream.
- INV-2: with `ST_CHECK_FOR_INTERRUPTS`, the sort yields to
  `CHECK_FOR_INTERRUPTS()` periodically — required for big
  tuplesorts.

## Trust boundary (Phase D)

- Recursion-depth hardening (INV-1) is the explicit
  defensive-coding feature. Cross-link with A7
  `record_recv` stack-depth: both rely on bounding recursion
  on attacker-influenced inputs.

## Cross-refs

- `knowledge/files/src/include/lib/qunique.h.md` — usually
  paired (sort then unique)
- A7 `record_recv` — recursion-depth cluster

## Issues

None — explicit upstream-divergence is documented in-tree.
