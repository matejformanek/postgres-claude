# src/test/modules/test_dsa/test_dsa.c

**Pin:** `b78cd2bda5b1a306e2877059011933de1d0fb735`
**LOC:** 162
**Verification depth:** full read

## Role

Test module for dynamic shared memory areas (DSAs). It exercises three scenarios: basic allocate/read/free/detach round-trips, DSA usage across nested resource owners, and allocation across a range of sizes to stress the pagemap-sizing path in `make_new_segment()`. [from-comment] `source/src/test/modules/test_dsa/test_dsa.c:4,32,71,125-132`. Each function obtains an LWLock tranche id from the DSM registry, creates a fresh DSA, and validates that addresses written via `dsa_get_address` survive across the area. [verified-by-code] `source/src/test/modules/test_dsa/test_dsa.c:42-69`

## Public API

- `test_dsa_basic()` — allocates 100 × 1000-byte blocks, writes `"foobar%d"`, reads them back, frees all, detaches. [verified-by-code] `source/src/test/modules/test_dsa/test_dsa.c:33-69`
- `test_dsa_resowners()` — creates a DSA under the parent resource owner, does 10000 allocations under a child owner, frees 500, then releases/deletes the child owner and detaches. [verified-by-code] `source/src/test/modules/test_dsa/test_dsa.c:72-123`
- `test_dsa_allocate(int4 start, int4 end, int4 step)` — for each page count in `[start,end)` by `step`, creates a fresh DSA, allocates `pages * FPM_PAGE_SIZE`, frees, detaches. [verified-by-code] `source/src/test/modules/test_dsa/test_dsa.c:133-162`
- `init_tranche(void *ptr, void *arg)` — DSM-registry init callback assigning `*tranche_id = LWLockNewTrancheId("test_dsa")`. [verified-by-code] `source/src/test/modules/test_dsa/test_dsa.c:24-30`

## Invariants

- INV-1: The LWLock tranche id is obtained once via the named DSM segment `"test_dsa"` (init callback runs at creation); all three functions reuse the same registered segment. [verified-by-code] `source/src/test/modules/test_dsa/test_dsa.c:42-43,83-84,149-150`
- INV-2: Every `dsa_create` is balanced by a `dsa_detach`; allocations are freed before detach in the basic/allocate paths. [verified-by-code] `source/src/test/modules/test_dsa/test_dsa.c:45-66,154-158`
- INV-3: `test_dsa_allocate` rejects `start_num_pages > end_num_pages`. [verified-by-code] `source/src/test/modules/test_dsa/test_dsa.c:146-147`
- INV-4: In `test_dsa_resowners`, the DSA is created under the parent owner but allocations happen under a child owner; releasing the child via all three `ResourceOwnerRelease` phases must not invalidate the DSA, which is detached afterward under the parent. [verified-by-code] `source/src/test/modules/test_dsa/test_dsa.c:86-120`

## Notable internals

- Resource-owner test issues the full three-phase release sequence (`RESOURCE_RELEASE_BEFORE_LOCKS`, `RESOURCE_RELEASE_LOCKS`, `RESOURCE_RELEASE_AFTER_LOCKS`) then `ResourceOwnerDelete`, restoring `CurrentResourceOwner` first. [verified-by-code] `source/src/test/modules/test_dsa/test_dsa.c:107-118`
- `test_dsa_allocate` creates a fresh DSA per iteration so each allocation forces a new segment, including the odd-sized segment path in `make_new_segment()`. [from-comment] `source/src/test/modules/test_dsa/test_dsa.c:125-132,152-159`
- Allocation sizes use `FPM_PAGE_SIZE` from the freepage manager header. [verified-by-code] `source/src/test/modules/test_dsa/test_dsa.c:19,155`
- Read-back validation compares `dsa_get_address` output against a locally formatted `"foobar%d"` and errors "no match" on mismatch. [verified-by-code] `source/src/test/modules/test_dsa/test_dsa.c:52-59`

## Cross-refs

- `source/src/backend/utils/mmgr/dsa.c` — dsa_create/dsa_allocate/dsa_free/dsa_get_address/dsa_detach, make_new_segment.
- `source/src/include/utils/dsa.h` — DSA API and dsa_pointer.
- `source/src/include/utils/freepage.h` — FPM_PAGE_SIZE.
- `source/src/backend/utils/resowner/resowner.c` — ResourceOwnerCreate/Release/Delete.
- `source/src/backend/storage/ipc/dsm_registry.c` — GetNamedDSMSegment.

## Potential issues

- **[ISSUE-correctness: large on-stack array]** `test_dsa.c:79` — `dsa_pointer p[10000]` is a ~80 KB stack array (8 bytes × 10000). Within the default backend stack limit and only in a test module, but a notably large stack allocation. Severity: nit.
