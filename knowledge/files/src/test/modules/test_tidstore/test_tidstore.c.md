---
path: src/test/modules/test_tidstore/test_tidstore.c
anchor_sha: e18b0cb7344
loc: 358
depth: read
---

# src/test/modules/test_tidstore/test_tidstore.c

## Purpose

SQL-callable harness for `src/include/access/tidstore.h` — the **TID store**
data structure used by VACUUM `lazy_scan_prune` to remember dead-tuple TIDs
between the heap scan and the index-vacuum phase. Exercises both backing modes
(local-memory and DSA-shared), insert via `TidStoreSetBlockOffsets`, membership
via `TidStoreIsMember`, and iteration via `TidStoreBeginIterate /
TidStoreIterateNext / TidStoreEndIterate`, cross-checked against a flat
verification array. Locking calls (`TidStoreLockExclusive / TidStoreLockShare`)
are exercised but pointless in this single-process harness — kept as a usage
example per the header comment. `[from-comment]` `test_tidstore.c:6-8`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `test_create(bool shared)` | `:97` | Allocates the singleton `tidstore` in `TopMemoryContext`; `shared=true` uses `TidStoreCreateShared` + `dsa_pin_mapping`, else `TidStoreCreateLocal` |
| `do_set_block_offsets(int64 blkno, int2[] offs)` | `:181` | qsorts offsets ascending (required), calls `TidStoreSetBlockOffsets`, updates verification array |
| `check_set_block_offsets()` | `:234` | Three-way cross-check: per-TID `IsMember`, exhaustive-per-block `IsMember`, full `Iterate` — all must agree with verification array |
| `test_is_full()` | `:333` | Returns `TidStoreMemoryUsage(tidstore) > tidstore_empty_size` — sanity probe, not real fullness |
| `test_destroy()` | `:346` | `TidStoreDestroy` + frees the three verification arrays |

No `_PG_init`; no hooks installed. Module is loaded by the test SQL on demand.

## Internal landmarks

- File-scope singletons: `static TidStore *tidstore` and
  `static ItemArray items` (`:35-48`) — the harness is one-tidstore-per-backend.
- `itemptr_cmp` (`:52`) — `(blkno, offset)` lexicographic compare used to sort
  verification + iter results before equality check.
- `purge_from_verification_array(blkno)` (`:168`) — needed because
  `TidStoreSetBlockOffsets` **replaces** the per-block set; the verification
  array must mirror that semantic.
- `check_set_block_offsets` (`:234-325`) runs three independent reads and
  asserts all three match: pointwise lookup, exhaustive `FirstOffsetNumber ..
  MaxOffsetNumber` per distinct block, and full iteration.

## Invariants & gotchas

- **TEST MODULE — never load in production.** Single-process; `Lock*` calls
  are no-ops in effect (`:6-8` from-comment).
- `TidStoreSetBlockOffsets` **requires strictly ascending offsets** — the
  harness qsorts before calling (`:194-195`). Pre-sorted is a precondition of
  the API, not a convenience.
- `TidStoreCreateShared` stores live in DSA but the **handle is not shared**:
  only the creating backend can use it. `dsa_pin_mapping` keeps the mapping
  alive across SQL statements within that backend (`:122-128`).
- `test_is_full` only checks `MemoryUsage > empty_size` — a weak post-condition
  meant to catch a totally-broken accounting, not to validate the configured
  VACUUM `maintenance_work_mem` limit.
- Failures show up as `elog(ERROR, ...)` with the offending `(blkno, offset)`
  pair — useful as a fuzz oracle if the SQL test feeds adversarial inputs.

## Cross-refs

- `knowledge/files/src/include/access/tidstore.h.md` — the API under test.
- `knowledge/subsystems/vacuum.md` — the production caller (`lazy_scan_prune`
  → `TidStoreSetBlockOffsets`, index vacuum → `TidStoreIsMember`).
- `knowledge/files/src/include/lib/integerset.h.md` — older sibling structure
  superseded by TidStore for VACUUM since PG17.
