# `src/backend/replication/logical/message.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 95
- **Source:** `source/src/backend/replication/logical/message.c`

## Purpose

Generic logical messages: arbitrary binary blobs WAL-logged so they
propagate through logical decoding (passed to the output plugin's
`message_cb`). Plain noop in normal redo. Transactional messages travel
with the surrounding xact; non-transactional are delivered as soon as
the WAL is read. Every message carries a prefix (extension name etc.) for
disambiguation. [from-comment] (`message.c:13-28`)

## Spine

- `LogLogicalMessage` (`:43`) — emits `XLOG_LOGICAL_MESSAGE`. For
  transactional messages, forces an xid via `GetCurrentTransactionId` so
  the message attaches to the right txn (`:50-56`). Sets
  `XLOG_INCLUDE_ORIGIN` so origin filtering works. Optionally flushes for
  non-transactional + `flush=true`.
- `logicalmsg_redo` (`:86`) — noop; only the decode side cares.

Wire format `xl_logical_message` (`message.h:20-28`): dbId, transactional
flag, prefix_size (incl trailing NUL), message_size, then prefix||message.

## Decoded via

`logicalmsg_decode` (declared in `decode.h`) — calls into reorderbuffer
either immediately (non-transactional) or via the txn's change queue.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
