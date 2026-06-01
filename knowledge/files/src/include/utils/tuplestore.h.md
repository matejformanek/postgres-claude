# `src/include/utils/tuplestore.h`

- **File:** `source/src/include/utils/tuplestore.h` (95 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Public interface for `tuplestore.c` — the "dumbed-down version of
`tuplesort.c`" used for materialized intermediate results (Materialize
plan nodes, hashjoin batches, holdable cursors, SRFs, trigger transition
tables). (`tuplestore.h:1-17` [from-comment])

## Opaque type

`Tuplestorestate` (`:41`) — opaque; details in `tuplestore.c`.

## Storage rules

> "Beginning in Postgres 8.2, what is stored is just MinimalTuples;
> callers cannot expect valid system columns in regurgitated tuples."
> (`:19-22` [from-comment])

So callers using the tuplestore API don't get visibility info back —
this is symmetric with `tuplesort_begin_heap` (also MinimalTuple-based).

## API surface

Constructor:
- `tuplestore_begin_heap(randomAccess, interXact, maxKBytes)` (`:48`)
  — only one variant currently exists (heap = MinimalTuple);
  comment at `:43-46` notes "Currently we only need to store
  MinimalTuples, but it would be easy to support the same behavior for
  IndexTuples and/or bare Datums."
- `tuplestore_set_eflags(state, eflags)` (`:52`) — must be called
  before any tuples are put.

Read-pointer management:
- `tuplestore_alloc_read_pointer(state, eflags)` (`:60`) — returns int ID.
- `tuplestore_select_read_pointer(state, ptr)` (`:62`).
- `tuplestore_copy_read_pointer(state, srcptr, destptr)` (`:64`) —
  this is also how mark/restore is implemented (no dedicated
  `markpos` API).

Write:
- `tuplestore_puttupleslot`, `tuplestore_puttuple`, `tuplestore_putvalues`.

Read (against active pointer):
- `tuplestore_gettupleslot(state, forward, copy, slot)` (`:74`) — the
  normal read.
- `tuplestore_gettupleslot_force` (`:77`) — variant that forces a fetch
  even if `eof_reached` etc. [usage [unverified]]
- `tuplestore_advance`, `tuplestore_skiptuples`, `tuplestore_rescan`,
  `tuplestore_ateof`, `tuplestore_tuple_count`.
- `tuplestore_trim` (`:67`) — slide-down INMEM array if no rewind is
  required at any read pointer.
- `tuplestore_get_stats(state, &max_storage_type, &max_space)`,
  `tuplestore_in_memory`.

Lifecycle end:
- `tuplestore_clear` (`:91`) — keep state, drop data.
- `tuplestore_end` (`:93`) — free everything.

## Distinguishing features (vs `tuplesort.h`)

- No comparison/sort key API at all — tuplestores preserve insertion
  order, no sorting.
- Multiple read pointers (`tuplestore_alloc_read_pointer`) — there's no
  parallel in tuplesort.
- No `performsort` boundary — read can interleave with write.
- `randomAccess` is constructor-time (changes on-disk format) — in
  tuplesort it's `TUPLESORT_RANDOMACCESS` in `sortopt` but also
  affects file format.
- `interXact` boolean — survival across transaction boundaries; no
  tuplesort equivalent.
- `maxKBytes` directly instead of `workMem` semantics (still
  effectively the same).

## Cross-references

- `source/src/backend/utils/sort/tuplestore.c` — implementation.
- `source/src/backend/executor/nodeMaterial.c`,
  `source/src/backend/utils/mmgr/portalmem.c` (holdable cursors),
  `source/src/backend/commands/trigger.c` (transition tables) — major
  callers.

## Confidence tag tally

- `[verified-by-code]` × ~4
- `[from-comment]` × ~3
- `[unverified]` × 1
