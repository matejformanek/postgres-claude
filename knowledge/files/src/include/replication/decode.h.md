# src/include/replication/decode.h

## Purpose

Tiny dispatch header for logical-decoding's WAL-record-to-change
transformation. One `*_decode` function per resource manager (xlog,
xlog2, heap, heap2, xact, standby, logicalmsg) plus the entry point
`LogicalDecodingProcessRecord`.

## Role in PG

The logical walsender (or `pg_logical_slot_get_changes()` SQL function)
reads WAL via `XLogReaderState` and calls
`LogicalDecodingProcessRecord(ctx, record)` for each record.
`LogicalDecodingProcessRecord` dispatches on `XLogRecGetRmid(record)`
and calls the rmgr-specific `*_decode` function, which builds a
`ReorderBufferChange` and queues it on the reorder buffer (see
`reorderbuffer.h`). Once the xact commits, the reorder buffer replays
queued changes to the output plugin.

See `knowledge/subsystems/replication.md` (logical decoding section).

## Key types/struct fields

- `XLogRecordBuffer` (lines 17-22) — bundle passed to each decoder:
  `origptr` (record start LSN), `endptr` (next record LSN), and the
  full `XLogReaderState *record`. Cheaper than re-passing three args.
  [verified-by-code]

- Decoder functions (lines 24-30) — one per rmgr that emits records
  logical decoding cares about:
  - `xlog_decode` — RM_XLOG_ID (checkpoint, switch, ...).
  - `xlog2_decode` — RM_XLOG_ID secondary info recs (newer additions).
  - `heap_decode` / `heap2_decode` — RM_HEAP_ID / RM_HEAP2_ID
    (insert/update/delete + multi-insert, lock, freeze).
  - `xact_decode` — RM_XACT_ID (commit, abort, prepare, assignment).
  - `standby_decode` — RM_STANDBY_ID (lock, running-xacts).
  - `logicalmsg_decode` — RM_LOGICALMSG_ID
    (`pg_logical_emit_message()`).
  [verified-by-code]

- `LogicalDecodingProcessRecord(ctx, record)` (lines 32-33) — top-level
  dispatch by rmgr id. [verified-by-code]

- `change_useless_for_repack(buf)` (line 36) — odd one out: lives in
  `commands/repack_worker.c`, declared here so the decoder can skip
  irrelevant changes during an in-place repack. [from-comment]

## Phase D notes

**New WAL record types & old subscribers.** The set of rmgrs handled
is closed — adding a new builtin rmgr means editing this header AND
adding a decode function. Subscribers running older protocol versions
won't recognize new logical message types; the protocol versioning
lives in `logicalproto.h`, not here. Decoder gates on protocol version
inside the `*_decode` function (e.g. sequence decoding added in PG17 is
guarded by checking the slot's logical protocol version). [inferred]

**Unknown rmgr handling.** Custom rmgrs (registered via
`RegisterCustomRmgr`) are NOT in this list. `LogicalDecodingProcessRecord`
falls through for unknown rmgrs — extension authors of custom rmgrs
that emit logically-relevant changes have no in-tree hook to plug into
the decoder. [inferred — would need to verify in `decode.c`]

**Wire-protocol attack surface.** The decoders read the publisher's own
WAL (trusted, written by this very backend cluster's commit machinery),
not bytes from a remote. So the decoder is not an untrusted-input
parser. Where the untrusted-input boundary IS: the subscriber-side
apply worker parses the logical protocol via `logicalproto.h` decoders,
and the publisher-side walsender parses replication commands via
`walsender_private.h`'s yyparse. This header is on the trusted side.
[verified-by-code]

## Potential issues

- [ISSUE-dead-code: `change_useless_for_repack` is declared here but
  lives in `commands/repack_worker.c` — coupling decode.h to a feature
  branch / contrib module; check whether repack_worker.c is actually
  in-tree at the pinned revision (maybe)]
- [ISSUE-undocumented-invariant: dispatch table for `RmgrId` → decoder
  not in header; new rmgrs that need decoding must touch
  `LogicalDecodingProcessRecord` and there's no compile-time
  enforcement (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-replication`](../../../../issues/include-replication.md)
<!-- issues:auto:end -->
