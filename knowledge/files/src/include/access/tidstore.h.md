# `src/include/access/tidstore.h`

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**55 lines.**

## Role

Opaque-handle interface to **TidStore** — a set of `ItemPointerData`
(TIDs) backed by a radix tree. Introduced in PG17 to replace vacuum's
legacy "lazy_tid_reaped" sorted-array dead-tid bitmap; the radix tree
gives bounded-memory growth even with very large dead-tuple counts and
supports both local (process) and DSA-shared (parallel-vacuum) modes.
[verified-by-code] `source/src/include/access/tidstore.h:1-21`

## Public API

Opaque types (lines 20-21): `TidStore`, `TidStoreIter`.

`TidStoreIterResult` struct (lines 27-31): copyable but opaque; holds
`blkno` and an `internal_page` pointer. Real consumers call
`TidStoreGetBlockOffsets()` to extract offsets.

Sixteen externs (lines 33-52):
- Create/attach/destroy: `TidStoreCreateLocal`, `TidStoreCreateShared`,
  `TidStoreAttach`, `TidStoreDetach`, `TidStoreDestroy`.
- Lock: `TidStoreLockExclusive`, `TidStoreLockShare`, `TidStoreUnlock`.
- Mutate: `TidStoreSetBlockOffsets(ts, blkno, offsets[], n)`.
- Read: `TidStoreIsMember(ts, *tid)`,
  `TidStoreBeginIterate`, `TidStoreIterateNext`,
  `TidStoreGetBlockOffsets(result, out_offsets[], max)`,
  `TidStoreEndIterate`.
- Introspect: `TidStoreMemoryUsage`, `TidStoreGetHandle`,
  `TidStoreGetDSA`.

## Invariants

- **INV-tidstore-block-grouped:** the store is keyed by `BlockNumber`,
  with the per-block offsets stored compactly (typically as a small
  bitmap of `OffsetNumber`s). `TidStoreSetBlockOffsets` REPLACES the
  prior offsets for that block — repeated calls overwrite, they don't
  union. [inferred from the API shape]
- **INV-tidstore-locking:** in shared mode the caller must hold the
  appropriate lock for read (`Share`) or write (`Exclusive`); in local
  mode the lock calls are no-ops. The API exposes lock helpers rather
  than locking internally — caller drives the protocol.
- **INV-tidstore-result-opaque:** `TidStoreIterResult` may be copied,
  but the `internal_page` pointer is owned by the iterator; do NOT
  use it after `TidStoreEndIterate`. The `TidStoreGetBlockOffsets`
  call extracts offsets into a caller buffer for safe handoff.
- **INV-tidstore-bounded:** `max_bytes` at creation is a soft cap;
  the radix tree won't grow beyond it (vacuum uses this to size to
  `maintenance_work_mem`).

## Notable internals

The radix-tree backing comes from `lib/radixtree.h` (template-style
header that generates a typed radix tree per use). The PG17 vacuum
patch replaced the old "1024-bytes-per-TID worst-case" array bitmap
with this; net effect was a 70-90% memory reduction for vacuums on
relations with many dead tuples in widely scattered blocks.

DSA-backed mode (`TidStoreCreateShared`) lets parallel vacuum workers
all SetBlockOffsets into the same store, with the lock helpers
coordinating concurrent inserts.

## Trust-boundary / Phase D surface

Not directly user-facing. But: TidStore now backs the vacuum dead-tid
buffer, and a Phase-D-style "limit how much heap state vacuum sees in
one pass" tool would need to interact with the TidStore — there's no
"forget block X" API in this header, only "set the offsets for block
X" (which can be set to an empty list). A custom vacuum extension
that wanted to whitelist/blacklist blocks for cleanup would have to
SetBlockOffsets(..., empty) per excluded block before
`heap_vacuum_rel` consults the store.

The `internal_page` exposure (line 30) is the one "leaky" spot — it's
a pointer into the radix tree's internal node. Misuse (use after
end-iterate) is UB. Acceptable in PG-internal code; should NOT be
exposed to extensions without an opacity layer.

## Cross-refs

- `lib/radixtree.h` — the underlying data structure.
- `utils/dsa.h` — `dsa_area`/`dsa_pointer`/`dsa_handle` for shared mode.
- `storage/itemptr.h` — `ItemPointerData`.
- `src/backend/access/common/tidstore.c` — implementation.
- `src/backend/commands/vacuumlazy.c` — primary consumer.
- `subsystems/vacuum.md` (if written) — vacuum dead-tid lifecycle.

## Issues

- **ISSUE-doc**: `TidStoreIterResult.internal_page` is documented as
  opaque ("treated as opaque") but is still a raw pointer; extension
  authors using TidStore (in future) might dereference it.
- **ISSUE-API-gap**: no "forget block" or "remove specific TID" API —
  only block-level overwrite. Intentional (vacuum's use pattern is
  append-only-per-pass), but limits reuse.
