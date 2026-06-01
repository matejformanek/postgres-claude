# nodeSort.c

- **Source:** `source/src/backend/executor/nodeSort.c` (≈420 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Wraps `utils/sort/tuplesort.c` as an executor node. First call drains the
outer plan into a Tuplesort, performs the sort, then yields rows on demand.
Supports rewind / mark-restore (used by MergeJoin's inner) and backward
scan. [from-comment] `:24-40`

## Two physical sort modes

- **Datum sort** (single-column result) — uses `tuplesort_putdatum` /
  `tuplesort_getdatum`. Much faster for pass-by-value (int4, int8) than the
  tuple variant; avoids HeapTuple construction.
- **Tuple sort** (multi-column) — `tuplesort_putheaptuple` etc.

The node chooses at init based on output TupleDesc.

## Parallel sort

Sort can run inside a parallel worker as part of a partial plan
(Gather Merge above). When the parent is `Gather Merge`, the planner sets
`sort_parallel_workers`; each worker drains its share of input, sorts
locally, and emits via the worker's tuple queue.

There is also a **shared-tape final-merge** mode (PG 10+) for the
parallel-aware path: each worker hands its sorted run as a tape to a
SharedTuplesort, and one elected backend (or the leader) does the final
merge. This is what `ExecSortEstimate/InitializeDSM/InitializeWorker` set
up.

## ReScan + bounded sort

If the outer plan's params are unchanged, ReScan rewinds without re-sorting
(re-reads the cached results). If params changed, the Tuplesort is reset
and rebuilt.

Bounded sort: when an enclosing Limit communicates `tuples_needed`, Sort
switches to a heap-of-k algorithm (`tuplesort_set_bound`) that retains only
the top-k rows, dramatically reducing work for `LIMIT k`.

## Tags

- [verified-by-code] datum vs tuple branch + DSM hooks.
- [from-comment] purpose + datum-sort rationale at file head.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
