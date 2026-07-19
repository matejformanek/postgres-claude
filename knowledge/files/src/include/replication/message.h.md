# src/include/replication/message.h

## Purpose

`pg_logical_emit_message(transactional, prefix, content, flush)` — the
SQL-level escape hatch for injecting arbitrary bytes into the logical
replication WAL stream. Downstream output plugins see the bytes via
their `message_cb`; core apply ignores them (`worker.c:3848-3855`).

Also exposes the small custom RMGR (`RM_LOGICALMSG_ID`) wiring.

## Role in PG

- SQL functions `pg_logical_emit_message_text` and
  `pg_logical_emit_message_bytea` (`pg_proc.dat:11731-11740`, OIDs 3577
  and 3578) live in `logicalfuncs.c:371-389` and are thin wrappers over
  `LogLogicalMessage(prefix, message, size, transactional, flush)` (line 32).
- For transactional messages, the function forces XID assignment so the
  message is replayed inside the xact (`logicalfuncs.c` /
  `message.c:52-56`).
- For non-transactional messages with `flush=true`, the WAL is flushed
  before returning (`message.c:77-79`) — useful for "ping" patterns.
- RMGR entries `XLOG_LOGICAL_MESSAGE` (line 37), `logicalmsg_redo`
  (line 38), `logicalmsg_desc` (line 39), `logicalmsg_identify` (line 40).
  `logicalmsg_redo` is a no-op except for sanity-checking `info`
  (`message.c:91-92` — `elog(PANIC)` on unknown opcode).

## Key types/struct fields

`xl_logical_message` (`message.h:20-28`) — on-disk WAL record body:

- `dbId` (line 22) — emitting database; lets logical decoding filter
  out messages from other databases on the same cluster.
- `transactional` (line 23) — whether the consumer sees it at COMMIT or
  immediately.
- `prefix_size` (line 24) — length INCLUDING the trailing NUL (see
  `message.c:60-61` — "trailing zero is critical; see logicalmsg_desc").
- `message_size` (line 25) — payload length, no embedded NUL contract.
- `message[FLEXIBLE_ARRAY_MEMBER]` (line 27) — prefix bytes first
  (null-terminated), then payload bytes.

`SizeOfLogicalMessage` (line 30) — header size for `XLogRegisterData`.

## Phase D notes

### Privilege posture

`pg_proc.dat:11731-11740` does NOT specify `proacl` — there's no REVOKE
in `system_functions.sql` either. So **EXECUTE is PUBLIC by default**:
any role with a SQL connection can inject WAL bytes via
`pg_logical_emit_message`. There's no REPLICATION-role gate.
`[verified-by-code]`

The bytes only matter if some downstream output plugin reads them. Core
pgoutput's apply ignores 'M' messages (`worker.c:3848-3855`). Other
plugins (wal2json, custom plugins) DO surface them. So the threat is:
PUBLIC users on the publisher can stuff arbitrary bytes through every
subscriber's apply path AND through external CDC consumers.

### Prefix trust

The publisher comment (`message.c:25-27`) says: "Every message carries
prefix to avoid conflicts between different decoding plugins. The plugin
authors must take extra care to use unique prefix." That's a SOCIAL
contract, not enforced. A PUBLIC role can spoof any prefix it knows
about, including one another extension uses for control-plane signaling.

### Size discipline

`message_size` is a `Size` (line 25) — no documented upper bound in this
header. WAL-record-size limits will cap it, but a malicious caller can
fill `max_wal_size` with garbage emit-messages.

## Potential issues

- [ISSUE-trust-boundary: `pg_logical_emit_message` (OIDs 3577/3578) is
  EXECUTE PUBLIC by default — no REPLICATION privilege gate, no row
  filter. Any logged-in role on the publisher can write to the WAL
  stream consumed by every logical subscriber. (medium — by design but
  rarely documented)]
- [ISSUE-trust-boundary: `prefix` (line 24) is unfiltered
  caller-supplied text. Output plugins keying off prefix for control
  commands can be impersonated. Documented as a social contract only
  (`message.c:25-27`). (medium for plugin authors, low for core)]
- [ISSUE-dos: no per-call size limit on `message` payload — bounded
  only by `XLogRecord` max. A PUBLIC role calling in a loop can pump
  the WAL stream and pin subscriber bandwidth. (medium)]
- [ISSUE-info-disclosure: messages are logged into WAL with `dbId` but
  no role/oid; a snapshot of WAL retains arbitrary bytes that a
  compromised user injected, which can later be embarrassing in
  backups. Note in passing. (low)]
- [ISSUE-undocumented-invariant: `prefix_size = strlen(prefix) + 1`
  (`message.c:61`) includes the NUL, but the header comment only says
  "length of prefix" (line 24). Future refactor risk. (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-replication`](../../../../issues/include-replication.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/replication.md](../../../../subsystems/replication.md)
