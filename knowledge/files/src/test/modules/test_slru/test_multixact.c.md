# src/test/modules/test_slru/test_multixact.c

**Pin:** `b78cd2bda5b1a306e2877059011933de1d0fb735`
**LOC:** 54
**Verification depth:** full read

## Role

A small companion to `test_slru` providing SQL-callable helpers to create and read a MultiXactId, exercising the multixact SLRU code paths (offsets/members) from regression SQL. It creates a multixact containing the current xid twice (under two different lock statuses) and reads it back after discarding the local cache to force a real SLRU lookup. [verified-by-code] `source/src/test/modules/test_slru/test_multixact.c:3` [verified-by-code] `source/src/test/modules/test_slru/test_multixact.c:25`

## Public API

- `test_create_multixact()` — returns a freshly created `MultiXactId` with two current-xid members (`MultiXactStatusUpdate` and `MultiXactStatusForShare`). [verified-by-code] `source/src/test/modules/test_slru/test_multixact.c:27`
- `test_read_multixact(id xid)` — discards local multixact caches then reads the multixact's members; errors if not found. [verified-by-code] `source/src/test/modules/test_slru/test_multixact.c:41`

## Invariants

- INV-1: Before creating a multixact member, the backend must register its oldest member via `MultiXactIdSetOldestMember` so truncation cannot remove a still-needed multixact. [verified-by-code] `source/src/test/modules/test_slru/test_multixact.c:32`
- INV-2: `GetMultiXactIdMembers` returning `-1` means the multixact was not found; the test treats this as an error. [verified-by-code] `source/src/test/modules/test_slru/test_multixact.c:50`

## Notable internals

- `test_read_multixact` calls `AtEOXact_MultiXact()` to flush the per-backend multixact cache, ensuring the subsequent `GetMultiXactIdMembers` performs a genuine on-disk/SLRU read rather than a cache hit. [verified-by-code] `source/src/test/modules/test_slru/test_multixact.c:48`
- `GetMultiXactIdMembers(id, &members, false, false)` is called with `allow_old = false` and `isLockOnly = false`. [verified-by-code] `source/src/test/modules/test_slru/test_multixact.c:50`
- No `PG_MODULE_MAGIC` here; it lives in the sibling `test_slru.c` of the same shared library. [verified-by-code] `source/src/test/modules/test_slru/test_multixact.c:15`

## Cross-refs

- `source/src/backend/access/transam/multixact.c` — `MultiXactIdCreate`, `GetMultiXactIdMembers`, `MultiXactIdSetOldestMember`, `AtEOXact_MultiXact`.
- `source/src/include/access/multixact.h` — `MultiXactMember`, `MultiXactStatus*`.
- Companion: `source/src/test/modules/test_slru/test_slru.c`.

## Potential issues

None.
