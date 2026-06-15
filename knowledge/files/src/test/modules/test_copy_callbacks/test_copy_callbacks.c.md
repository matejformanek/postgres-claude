---
path: src/test/modules/test_copy_callbacks/test_copy_callbacks.c
anchor_sha: e18b0cb7344
loc: 51
depth: read
---

# src/test/modules/test_copy_callbacks/test_copy_callbacks.c

## Purpose

Demonstrates the programmatic `COPY TO` API for extensions — `BeginCopyTo`,
`DoCopyTo`, `EndCopyTo` — where a caller supplies a write callback instead
of letting COPY write to a file or to the client. Used by extensions like
`pg_stat_statements` (for `query_id` rotation logs) and by `pg_dump --inserts`
adjacent paths to capture COPY output programmatically. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `test_copy_to_callback` | `test_copy_callbacks.c:32` | Opens a relation by OID, runs `BeginCopyTo/DoCopyTo/EndCopyTo` with `to_cb` as the writer |
| `to_cb` (static) | `:24` | Emits each chunk as `NOTICE: COPY TO callback called with data "..." and length N` |

## Internal landmarks

- `BeginCopyTo(NULL, rel, NULL, relid, NULL, false, to_cb, NIL, NIL)`
  (`:40`) — the `NULL` query/whereClause + `is_program=false` shape selects
  the "copy whole relation, no transform" path; the `to_cb` argument
  swaps in the callback writer.
- `table_open(.., AccessShareLock)` (`:36`) — COPY TO only needs share
  lock; matched by `table_close(.., NoLock)` (`:48`) since the lock is
  released at xact commit.
- `DoCopyTo` returns the processed row count as `int64` — reported in the
  NOTICE at `:45`.

## Invariants & gotchas

- **Test module — never load in production.** The NOTICE-per-chunk overhead
  would crush a real workload.
- The callback receives raw COPY-formatted bytes (text or binary depending
  on options); it's the caller's job to deal with the framing.
- The relation OID is the only argument — there's no `WHERE` filter or
  column list, so the function always copies all rows / all columns.

## Cross-refs

- `source/src/backend/commands/copyto.c` — `BeginCopyTo` / `DoCopyTo` /
  `EndCopyTo`.
- `source/src/include/commands/copy.h` — API + the `copy_data_dest_cb`
  typedef for `to_cb`.
