# Issues — `lib`

Per-subsystem issue register for `src/backend/lib/` — the generic
data-structure utilities used across the backend (intrusive lists,
red-black trees, pairing heaps, dynamic shared-memory hash tables,
Bloom filters, HLL, integer sets, knapsack, bipartite matching).
See `knowledge/issues/README.md` for tag conventions and workflow.

**Parent subsystem docs:**
- `knowledge/files/src/backend/lib/*.c.md` (per-file)
- `knowledge/issues/include-lib.md` (header counterpart)

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | lib/bloomfilter.c:42 | undocumented-invariant | nit | `MAX_HASH_FUNCS = 10` silently clamps `optimal_k` when bitset/element ratio is very large — degrades FP rate without warning | open | knowledge/files/src/backend/lib/bloomfilter.c.md §Potential issues |
| 2026-06-11 | lib/hyperloglog.c:14 | doc-drift | nit | Header says "sparse representation … is used, with fixed space overhead" but the code is dense (one byte per register) | open | knowledge/files/src/backend/lib/hyperloglog.c.md §Potential issues |
| 2026-06-11 | lib/hyperloglog.c:7-12 | stale-todo | nit | "Heule/Nunkesser/Hall improvements not attempted" comment stale since 2014 — bias correction, sparse mode, 64-bit hashing all still missing | open | knowledge/files/src/backend/lib/hyperloglog.c.md §Potential issues |
| 2026-06-11 | lib/dshash.c:71-74 | question | maybe | Should `dshash_partition` array have cache-line padding to avoid false sharing on the per-partition count counter on write-heavy tables? | open | knowledge/files/src/backend/lib/dshash.c.md §Potential issues |
| 2026-06-11 | lib/dshash.c:8-9 | stale-todo | nit | "Future versions may support iterators and incremental resizing; for now the implementation is minimalist." Iterators landed; incremental resize never did | open | knowledge/files/src/backend/lib/dshash.c.md §Potential issues |
| 2026-06-11 | lib/dshash.c:868 | correctness | maybe | `delete_item` Asserts `false` if `delete_item_from_bucket` returns false. Non-assert build leaves partition count out of sync with actual bucket contents | open | knowledge/files/src/backend/lib/dshash.c.md §Potential issues |
| 2026-06-11 | lib/integerset.c:42-49 | stale-todo | nit | "None of these limitations [in-order only, no remove, no add-during-iter] are fundamental … could be lifted if needed" — has been the state since PG 12 | open | knowledge/files/src/backend/lib/integerset.c.md §Potential issues |
| 2026-06-11 | lib/integerset.c:218-220 | doc-drift | nit | Comment names `rightmost_parent[0]` / `rightmost_parent[1]` but the variable is `rightmost_nodes` | open | knowledge/files/src/backend/lib/integerset.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| | | | | | |

## Notes

- `dshash.c` is by far the highest-value file in this directory —
  used widely by pgstat shared memory and the cumulative-stats system
  rewritten in PG15. The "no shrink" + "growth-only resize" + "fixed
  128-partition lockset" trio drives a lot of pgstat shmem sizing
  behaviour. The "load-factor per partition is representative of the
  whole table" assumption (line 476-483 comment) is worth a future
  benchmark on skewed tables.
- `bloomfilter.c` is used by amcheck's `verify_nbtree` and was
  originally written for parallel-CREATE-INDEX deduplication. The
  2-bytes-per-element sizing target is tuned for those two callers.
- `hyperloglog.c` is used by tuplesort's abbreviated-key stats; the
  unimplemented "HLL in Practice" optimisations are a parking lot
  for any future revisit, but the dense-vs-sparse comment drift is
  the easy doc fix.
- `ilist.c` / `pairingheap.c` / `rbtree.c` / `knapsack.c` /
  `bipartite_match.c` are all textbook implementations with no
  surfaced issues; they're frozen design.
- `integerset.c` was the dead-TID tracker pre-PG17. PG17 moved to
  `tidstore.c` (radix-tree-based), so the limitations comment is
  now mostly historical — `integerset` remains for tests and as a
  Simple-8b reference.
