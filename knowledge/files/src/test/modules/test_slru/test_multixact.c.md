---
path: src/test/modules/test_slru/test_multixact.c
anchor_sha: e18b0cb7344
loc: 54
depth: read
---

# src/test/modules/test_slru/test_multixact.c

## Purpose

Smoke-tests the MultiXact API by creating a multixact containing two members
both pointing at the current transaction (with different lock modes) and
then reading it back, deliberately discarding the local cache first so a real
SLRU read happens. Co-located with `test_slru.c` because MultiXact storage is
the canonical "real" SLRU. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `test_create_multixact` | `test_multixact.c:27` | Calls `MultiXactIdSetOldestMember` then `MultiXactIdCreate(xid, MultiXactStatusUpdate, xid, MultiXactStatusForShare)` |
| `test_read_multixact` | `:41` | Calls `AtEOXact_MultiXact()` to flush cache, then `GetMultiXactIdMembers(.., false, false)` |

## Internal landmarks

- The "two members are both the current XID" construction (`:33-34`) is
  artificial — in real life a multixact tracks N distinct transactions
  locking one tuple, but for testing the round-trip a degenerate case is
  enough.
- `AtEOXact_MultiXact()` (`:48`) is normally called at xact commit/abort to
  invalidate the per-backend MXact cache; reusing it mid-transaction here
  forces the next `GetMultiXactIdMembers` to hit SLRU instead of cache.

## Invariants & gotchas

- **Test module — never load in production.**
- This file does not have its own `PG_MODULE_MAGIC` — it's compiled into
  the same `.so` as `test_slru.c` (which has the magic block).
- `MultiXactIdSetOldestMember()` must precede `MultiXactIdCreate` or the
  freeze horizon machinery will get confused.

## Cross-refs

- `source/src/backend/access/transam/multixact.c` — implementation.
- `source/src/include/access/multixact.h` — API.
- `knowledge/files/src/test/modules/test_slru/test_slru.c.md` — sibling.
