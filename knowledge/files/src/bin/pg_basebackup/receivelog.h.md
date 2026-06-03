# receivelog.h

## Purpose

Public interface for the WAL streaming-receive loop used by
`pg_basebackup` (background WAL receiver), `pg_receivewal`, and (with
slight repurposing) `pg_recvlogical`.

## Key types

- `stream_stop_callback` — predicate the caller supplies. The receive
  loop calls it before each read and after each WAL segment; returning
  true ends streaming.
  `source/src/bin/pg_basebackup/receivelog.h:23`
- `StreamCtl` — bag of parameters for `ReceiveXlogStream()`.
  `source/src/bin/pg_basebackup/receivelog.h:29`
  Notable fields:
  - `sysidentifier` — when set, the receiver issues an extra
    `IDENTIFY_SYSTEM` and aborts if the server's sysident does not
    match (anti-misconnection check, line 33-34).
  - `synchronous` (bool) — fsync after every write rather than at
    segment close.
  - `mark_done` (bool) — write `archive_status/<name>.done` after a
    completed segment, matching backend walreceiver behavior.
  - `partial_suffix` — partial-file suffix discipline (".partial").
  - `stop_socket` — optional FD whose readability also wakes the
    select() loop so the parent process can hand off a stop LSN
    promptly.
  - `walmethod` — pluggable WAL writer (directory or tar). See
    `walmethods.h`.

## Public functions

- `CheckServerVersionForStreaming(conn)` — gate. Refuses servers
  older than 9.3 and newer than client.
  `source/src/bin/pg_basebackup/receivelog.h:53`
- `ReceiveXlogStream(conn, stream)` — the loop. Issues
  `START_REPLICATION`, runs the CopyData receive loop, handles
  timeline switches, returns true on clean stop, false on error.
  `source/src/bin/pg_basebackup/receivelog.h:54`

## Phase D notes

- `StreamCtl.sysidentifier` is the only trust check that catches
  reconnect-to-wrong-server. `ReceiveXlogStream` compares it
  against the server's IDENTIFY_SYSTEM response
  (`receivelog.c:506`). If caller passes NULL, no check. [verified-by-code]
- `stream_stop` is the trust boundary between caller-controlled
  termination (parent gave us a final LSN) and server-driven end of
  COPY. The header comment for `stream_stop_callback` (line 22)
  notes "Return true to stop streaming." Mis-implementation by a
  caller could leak indefinitely.
