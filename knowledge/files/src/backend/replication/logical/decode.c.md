# `src/backend/replication/logical/decode.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 1346
- **Source:** `source/src/backend/replication/logical/decode.c`

## Purpose

Per-WAL-record decoder. Reads xlog records via `XLogReader` and
dispatches to `reorderbuffer.c` (to assemble transactions) and to
`snapbuild.c` (to maintain a historic catalog snapshot). Single entry
point: `LogicalDecodingProcessRecord(ctx, record)`. Has minimal
intelligence — it just turns records into the right RB / SB calls.
[from-comment] (`decode.c:1-26`)

## Dispatch

`LogicalDecodingProcessRecord` (`:89`) does two universal steps before
dispatch:

1. If the record has a top xid (via `XLogRecGetTopXid`), pre-assign the
   subxact with `ReorderBufferAssignChild` (`:108`).
2. Look up the resource manager (`GetRmgr`) and call its `rm_decode`
   callback — `xlog_decode`, `xact_decode`, `heap_decode`, `heap2_decode`,
   `standby_decode`, `logicalmsg_decode`. If `rm_decode` is NULL the
   record is just a no-op-with-xid-tracking (`:118-...`). [verified-by-code]

## Per-record handlers

- `DecodeInsert`, `DecodeUpdate`, `DecodeDelete`, `DecodeTruncate`,
  `DecodeMultiInsert`, `DecodeSpecConfirm` — heap mutation paths.
- `DecodeCommit` (`:52`) — picks up `xl_xact_parsed_commit`, advances
  snapbuild, calls `ReorderBufferCommit` (or `ReorderBufferAbort` for
  abort), passes `two_phase` flag.
- `DecodeAbort`, `DecodePrepare` — abort + 2PC paths.
- `DecodeXLogTuple` — common deserializer.

## Filter rules

- `FilterPrepare` — output plugin's `filter_prepare_cb` decides whether
  PREPARE / COMMIT PREPARED go via streaming or get coalesced.
- `DecodeTXNNeedSkip` (`:68`) — central skip predicate: wrong DB (each
  logical slot is DB-scoped), wrong origin (filter_by_origin), or
  snapbuild not yet consistent.

## Fast-forward

The whole module supports a `fast_forward` mode (set on
`LogicalDecodingContext`) where decoding only advances LSN/xmin
bookkeeping without invoking the output plugin — used by slot advance.
[from-comment] (`:84-87`)
