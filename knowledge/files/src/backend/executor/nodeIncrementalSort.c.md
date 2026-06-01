# nodeIncrementalSort.c

- **Source:** `source/src/backend/executor/nodeIncrementalSort.c` (≈1400 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Optimization for the common case: input is **already sorted by a prefix** of
the requested keys (`presorted_keys`), so we only need to sort within
prefix-equal groups. Memory and CPU drop from O(N log N) over the whole
input to O(g log g) per group of size g. [from-comment] `:13-43`

## State machine

Two Tuplesort instances alternate: one is being built ("current group"),
one yields rows ("output group"). Per step:

1. **Find prefix boundary** — pull rows from outer; while their prefix-key
   matches the current group, push into `prefixsort_state`. On first
   mismatch, hold that row in `transfer_tuple`.
2. **Finish sort, drain** — `tuplesort_performsort`, switch to it as the
   output Tuplesort; emit rows until empty.
3. **Switch sorts and continue** — the previously-output sort is reused
   for the new group; insert `transfer_tuple` as the new group's first row.

## Mode flip: "full sort" vs "prefix sort"

If a prefix group turns out very large (the typical "skew" case where one
prefix value dominates), the node switches to full sort mode and just
absorbs everything; otherwise we'd lose the win to per-group overhead. The
heuristic threshold is `DEFAULT_MIN_GROUP_SIZE = 32` (see file constants).

## Parallel

Has DSM/Worker hooks to participate in parallel partial plans, same shape
as nodeSort.

## Tags

- [verified-by-code] dual-tuplesort state.
- [from-comment] the worked (X, Y) example at top.
