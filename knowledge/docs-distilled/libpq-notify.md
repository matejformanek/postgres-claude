---
source_url: https://www.postgresql.org/docs/current/libpq-notify.html
fetched_at: 2026-07-20T19:50:00Z
anchor_sha: d451ca6917e3
title: "libpq §34.8 — Asynchronous Notification (PQnotifies is passive; select()+PQconsumeInput idiom; PGnotify.be_pid)"
maps_to_skill: wire-protocol
---

# libpq §34.8 — Asynchronous Notification (LISTEN / NOTIFY)

The client half of `LISTEN`/`NOTIFY`. The one thing everyone gets wrong: libpq
**never pushes** notifications at you — `PQnotifies` only drains a queue that
some *other* libpq call already filled from the socket.

## Non-obvious claims

- **`PQnotifies` does no I/O.** "`PQnotifies` does not actually read data from the
  server; it just returns messages previously absorbed by another libpq
  function." It returns the next `PGnotify*` or NULL, marking it handled. So a
  notification only becomes visible *after* a `PQexec` / `PQgetResult` /
  `PQconsumeInput` has pulled bytes off the wire. [from-docs]
- **The consequence: check `PQnotifies` after every command.** "Remember to check
  `PQnotifies` after each `PQgetResult` or `PQexec`, to see if any notifications
  came in during the processing of the command." A NOTIFY that arrived
  interleaved with your SELECT's result rows is sitting in the queue. [from-docs]
- **`PGnotify` layout** (`source/src/interfaces/libpq/libpq-fe.h:241-248`):
  `char *relname` (channel name — historical name, need not be a relation),
  `int be_pid` (PID of the notifying backend), `char *extra` (the payload string
  from `NOTIFY chan, 'payload'`). `next` is private list-link; apps must not
  touch it. [verified-by-code]
- **`be_pid` is the *notifier's* backend PID** since Postgres 6.4 — the header
  even carries the historical note that "in earlier versions it was always your
  own backend's PID" (`libpq-fe.h:238-240`). Join it against your own
  `PQbackendPID` to detect self-notifications. A session's own `NOTIFY` **is**
  delivered back to it (standard LISTEN/NOTIFY semantics). [verified-by-code]
- **Free the whole `PGnotify` with `PQfreemem`, once.** "It is sufficient to free
  the `PGnotify` pointer; the `relname` and `extra` fields do not represent
  separate allocations." Using `free()` instead of `PQfreemem` is a heap-crossing
  bug on Windows (see [[knowledge/docs-distilled/libpq-misc.md]]). [from-docs]
- **The CPU-efficient idiom is `select()` + `PQsocket` + `PQconsumeInput`.** "A
  better way to check for `NOTIFY` messages when you have no useful commands to
  execute is to call `PQconsumeInput`, then check `PQnotifies`. You can use
  `select()` to wait for data to arrive from the server, thereby using no CPU
  power unless there is something to do." Get the fd from `PQsocket`. [from-docs]
- **The old poll-with-empty-queries pattern is deprecated.** Submitting empty
  commands just to force a socket read "is deprecated as a waste of processing
  power." [from-docs]
- **NOTIFY delivery is transactional on the server side** — notifications are only
  sent at the notifier's commit, and payloads are queued in the SLRU-backed
  async queue. The client never sees an uncommitted NOTIFY. (Server mechanism, not
  on this page; see corpus links.) [inferred]

## Links into corpus

- Backend NOTIFY queue + commit-time delivery: the `async.c` async-notify SLRU
  machinery, [[knowledge/subsystems/slru-infrastructure.md]] (the async queue is
  an SLRU consumer); NotifyResponse protocol message in
  [[knowledge/docs-distilled/protocol-message-formats.md]].
- `be_pid` ↔ `PQbackendPID`: [[knowledge/docs-distilled/libpq-status.md]].
- Passive-drain also underpins notice delivery:
  [[knowledge/docs-distilled/libpq-notice-processing.md]].
- Same `PQconsumeInput` / `PQsocket` async loop as query results:
  [[knowledge/docs-distilled/libpq-async.md]].
- `PQfreemem` heap rule: [[knowledge/docs-distilled/libpq-misc.md]].
- Source: [[knowledge/files/src/interfaces/libpq/libpq-fe.h.md]],
  [[knowledge/files/src/interfaces/libpq/fe-exec.c.md]] (PQnotifies queue),
  [[knowledge/files/src/interfaces/libpq/fe-protocol3.c.md]] (parses the wire message).
