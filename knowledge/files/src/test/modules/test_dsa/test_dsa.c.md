---
path: src/test/modules/test_dsa/test_dsa.c
anchor_sha: e18b0cb7344
loc: 162
depth: read
---

# src/test/modules/test_dsa/test_dsa.c

## Purpose

Exercises the dynamic shared memory area (DSA) allocator — basic
allocate-free correctness, behavior across `ResourceOwner` boundaries,
and the pagemap-sizing path in `make_new_segment` for a range of
allocation sizes. Uses `GetNamedDSMSegment` for the per-cluster tranche
id so the test can be loaded standalone (no preload required).
`[verified-by-code]` `test_dsa.c:23-30,125-132`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `test_dsa_basic()` | `:34` | Allocate 100×1KB, verify contents, free, detach |
| `test_dsa_resowners()` | `:73` | Allocate 10000×1KB under a child ResourceOwner, release the child, ensure DSA is unaffected |
| `test_dsa_allocate(start_pages, end_pages, step)` | `:134` | Allocate a single chunk of size `usable_pages * FPM_PAGE_SIZE` over a range, recreating the DSA each iteration to hit fresh-segment paths |

## Internal landmarks

- `init_tranche` (`:24`) — DSM initializer that registers a new LWLock
  tranche via `LWLockNewTrancheId("test_dsa")`. The named DSM segment
  just stores the resulting `tranche_id`.
- `test_dsa_resowners` (`:73`) — creates a child ResourceOwner, switches
  `CurrentResourceOwner` to it, allocates in the DSA, frees half, then
  releases the child through all three `ResourceOwnerRelease` phases
  (`BEFORE_LOCKS` / `LOCKS` / `AFTER_LOCKS`) and `ResourceOwnerDelete`s
  it. The DSA itself survives because it was created under the parent
  owner.
- `test_dsa_allocate` (`:134`) — recreates the DSA for each iteration
  (`:154-158`) so each call exercises `make_new_segment` with a fresh
  pagemap, including the odd-sized segment path
  (`[from-comment]` `:125-132`).

## Invariants & gotchas

- TEST MODULE — exercises DSA internals; not for production.
- The DSA tranche id must be stable across calls within a cluster — the
  DSM registry ensures the initializer fires exactly once and later
  attachers see the same id.
- `ResourceOwner` test (`test_dsa_resowners`) confirms that releasing a
  child owner doesn't free DSA allocations made under it — DSA
  allocations are not resource-owner-tracked, so the user is responsible
  for `dsa_free` (the test deliberately leaks half the allocations and
  detaches anyway).
- `FPM_PAGE_SIZE` is the freepage-manager page size used inside DSA
  (typically 4 KiB).

## Cross-refs

- `source/src/backend/utils/mmgr/dsa.c` — DSA implementation.
- `source/src/backend/utils/mmgr/freepage.c` — the freepage manager
  driving DSA segment allocation.
- `source/src/include/utils/dsa.h` — public API.
- `knowledge/files/src/test/modules/test_dsm_registry/test_dsm_registry.c.md`
  — DSM-registry-driven sibling test.
