# receivelog.c

- **Last verified commit:** `a75bd485b5ea` (re-verified 2026-06-17; the
  `START_REPLICATION`/`TIMELINE_HISTORY` command construction moved from a
  fixed `char query[128]` stack buffer to a dynamic `PQExpBuffer` — see
  "Command construction" below. "Key functions" cites re-pinned: early funcs
  +1 line, post-`ReceiveXlogStream`-buffer funcs +6/+7 lines.)

## Command construction (`PQExpBuffer`, since `a75bd485b5ea`)

`ReceiveXlogStream` previously formatted `TIMELINE_HISTORY %u` and
`START_REPLICATION %s%X/%08X TIMELINE %u` into a fixed `char query[128]`
stack buffer via `snprintf`. Since `a75bd485b5ea` the local is a
`PQExpBuffer query` (line 455), built with `createPQExpBuffer()` /
`appendPQExpBuffer*()` / `destroyPQExpBuffer()`. The slot name is now
emitted via `AppendQuotedIdentifier(query, stream->replication_slot)`
(line 580) — the frontend twin of `libpqwalreceiver.c`'s
`appendQuotedIdentifier` — so a slot name containing a `"` is doubled and
can no longer truncate or break the command. The dynamic buffer is what
makes a variable-length quoted identifier safe; the old 128-byte fixed
buffer is gone. [verified-by-code, receivelog.c:455,535-538,574-585 @ a75bd485b5ea]

## Purpose

The streaming-replication receive loop used by `pg_basebackup`'s
background WAL receiver, `pg_receivewal`, and (in a different mode)
`pg_recvlogical`. Issues `START_REPLICATION`, handles the
CopyBoth-Data stream, writes WAL into segment files via the
`WalWriteMethod`, sends standby-status-update feedback packets, and
handles timeline switches when the upstream promotes.

## Role in pg_basebackup

The background bgworker process (forked at `pg_basebackup.c:723`) runs
`LogStreamerMain` → `ReceiveXlogStream`. The main process meanwhile
receives the base-tar; when it has the end-of-backup LSN it pipes it
over `bgpipe[1]` and the receive loop's `reached_end_position`
callback returns true.

## Wire/protocol surface

Consumes a CopyBoth stream of CopyData packets, each preceded by a
single byte:

- `PqReplMsg_Keepalive` (`k`) — server pings with walEnd + sendTime +
  replyRequested. Parsed at `receivelog.c:1000` (`ProcessKeepaliveMsg`).
- `PqReplMsg_WALData` (`w`) — dataStart + walEnd + sendTime, then raw
  WAL bytes. Parsed at `receivelog.c:1054` (`ProcessWALDataMsg`).
- Anything else → "unrecognized streaming header" + abort. Line 853.

Also receives:
- `IDENTIFY_SYSTEM` response (verified against caller-supplied
  sysidentifier; line 505).
- `TIMELINE_HISTORY` response — 2-field row (filename, content),
  written to disk. Filename validated against
  `TLHistoryFileName(stream->timeline)`. Line 285-291.
- End-of-stream tuple result after the COPY ends — 2 fields
  (next_tli, next_tli_startpos). Parsed by `ReadEndOfStreamingResult`
  at line 705.

Sends back: 38-byte `PqReplMsg_StandbyStatusUpdate` (`r`) feedback
packets formed in `sendFeedback` at line 337.

## Key functions

- `CheckServerVersionForStreaming(conn)` `receivelog.c:375` — refuses
  < 9.3 and > client. [verified-by-code]
- `ReceiveXlogStream(conn, stream)` `receivelog.c:453` — top-level
  loop. After timeline-history fetch and `START_REPLICATION`, calls
  `HandleCopyStream`. On end-of-copy with a TUPLES_OK result, parses
  next timeline and loops; on COMMAND_OK calls the caller's stop
  callback. `error:` label closes the open walfile with
  `CLOSE_NO_RENAME` (keeps `.partial`).
- `HandleCopyStream(conn, stream, &stoppos)` `receivelog.c:751` — the
  inner receive loop. Handles synchronous mode (flush + feedback
  every cycle), periodic feedback, dispatch on message type.
- `CopyStreamPoll`, `CopyStreamReceive` `receivelog.c:884,946` — select
  + PQgetCopyData wrapper that also watches `stop_socket`.
- `ProcessWALDataMsg` `receivelog.c:1054` — validates dataStart aligns
  with the WAL segment offset we expect, opens a new segment via
  `open_walfile` if at offset 0, writes through the walmethod,
  closes (rename from `.partial`) at segment boundary, calls
  `stream_stop` to see if the caller wants to end.
- `open_walfile` `receivelog.c:90` / `close_walfile` `receivelog.c:192`
  — segment file lifecycle. Includes a paranoid pre-existing-file
  check: if the file exists, it must be either 0 bytes or exactly
  `WalSegSz`; anything else is treated as corrupt and refused.

## State / globals

- `walfile` (static `Walfile *`) — the currently-open segment; `NULL`
  between segments and at startup. `receivelog.c:29`
- `reportFlushPosition` (static bool) — true when feedback should
  include a real `lastFlushPosition`; false to send InvalidXLogRecPtr.
  Caller-controlled via slot or synchronous mode. `receivelog.c:30,478`
- `lastFlushPosition` — running max of flushed LSN.
- `still_sending` — false once we've sent `PQputCopyEnd`. Stops the
  duplicate-close path in `HandleEndOfCopyStream`. `receivelog.c:33`

## Phase D notes

[ISSUE-trust-boundary: server can announce next_tli and next-startpos
after end-of-COPY; only minimal sanity (`newtimeline <= stream->timeline`
+ `startpos > stoppos`) is checked (wire-protocol, low)] — Lines
621-640. If the server lies — say, announces timeline 99 with a
startpos in the past (≤ stoppos) — the code catches it via the
explicit `pg_log_error` paths and goes to `error:`. So spoofing is
detected. But a misbehaving server CAN force an arbitrary upward
timeline jump (`newtimeline` must just be > current). Worst case is
the receiver starts asking for that timeline; the server then has to
serve it, which would fail in turn. [verified-by-code]

[ISSUE-trust-boundary: timeline-history filename comes from server
(line 560 `PQgetvalue(res, 0, 0)`), verified against
`TLHistoryFileName(stream->timeline)` (line 285) before write
(path-traversal, low)] — The validation closes the obvious "server
sends `../foo` as filename" attack. [verified-by-code]

[ISSUE-trust-boundary: WAL data dataStart and offset relationship
checked but not against any sysident again (wire-protocol, low)] —
`ProcessWALDataMsg` (line 1095) reads dataStart from the message
and checks `xlogoff == walfile->currpos` for the in-progress segment,
or `xlogoff == 0` if no file is open. This catches gaps/overlaps
within a single connection. But mid-stream sysident is NOT
re-verified; if the server's identity changed (unlikely on the same
TCP connection), we'd happily write WAL from the new sysident on top
of the old segments. [inferred]

[ISSUE-state-transition: open file left in `.partial` state after
write-then-disconnect, with caller in error path
(stale-todo, low)] — `error:` at line 693 closes the walfile with
`CLOSE_NO_RENAME` so the `.partial` suffix is preserved. Resume via
`pg_receivewal` works because `open_walfile` will detect an
appropriately-sized file. [verified-by-code]

[ISSUE-undocumented-invariant: `static` globals (`walfile`,
`reportFlushPosition`, `lastFlushPosition`, `still_sending`) mean a
process can only have ONE active receive loop at a time
(state-transition, low)] — These are file-scope statics. If a future
refactor tries to multiplex streams, the code will silently corrupt.
[verified-by-code]

[ISSUE-stale-todo: `FIXME: we might send it ok, but get an error`
(line 541) on the `TIMELINE_HISTORY` command error path — the comment
notes the send may succeed yet the result be an error, but the code
just `pg_log_error`s the result. Not security; minor error-message
infidelity. Mis-cited as `pg_basebackup.c:542` in the pg_basebackup
issue register at seed (2026-06-03); re-anchored here 2026-07-04 —
the FIXME lives in receivelog.c, not pg_basebackup.c. (low)]
[verified-by-code]

`existsTimeLineHistoryFile` returns true for timeline 1 without
checking — comment "Timeline 1 never has a history file" (line 263).
Server can never make us write a `00000001.history` file, which is
correct because tli 1 has no parent. [verified-by-code]

No decompression in receivelog itself — compression is delegated to
the WalWriteMethod (walmethods.c). So no decompression-bomb risk in
this file.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_basebackup`](../../../../issues/pg_basebackup.md)
<!-- issues:auto:end -->
