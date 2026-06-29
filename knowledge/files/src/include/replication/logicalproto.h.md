# src/include/replication/logicalproto.h

## Purpose

The **wire-protocol** spec for the logical replication CopyData stream
between a publisher walsender (running `pgoutput`) and a subscriber
apply worker. This is the byte-level contract — every message type, every
tuple layout, every version gate.

Companion to `libpq/protocol.h` (the front-end / back-end framing
protocol). Where `protocol.h` says "frontend sends 'Q' then a string",
`logicalproto.h` says "publisher sends 'I' then a tuple, where each
column has a status byte and a length-prefixed payload".

## Role in PG

- **Publisher side** (`logicalrep_write_*`): pgoutput callbacks invoke
  these to serialize change events into the `StringInfo` that walsender
  flushes via CopyData. Defined in `src/backend/replication/logical/proto.c`.
- **Subscriber side** (`logicalrep_read_*`): the apply worker's
  `apply_dispatch` (`worker.c:3797`) reads the leading byte, then calls
  the matching `apply_handle_*` which in turn calls `logicalrep_read_*`
  to parse the rest.
- **Capability negotiation**: subscriber sends its desired version in
  `START_REPLICATION` options; publisher caps at
  `LOGICALREP_PROTO_MAX_VERSION_NUM` (line 45). Version bumps add
  feature gates (streaming v2, twophase v3, parallel-stream v4).

## Key types/struct fields

### Version constants (`logicalproto.h:40-45`)

```
LOGICALREP_PROTO_MIN_VERSION_NUM        1
LOGICALREP_PROTO_VERSION_NUM            1   (native, PG10+)
LOGICALREP_PROTO_STREAM_VERSION_NUM     2   (PG14 — streaming large xacts)
LOGICALREP_PROTO_TWOPHASE_VERSION_NUM   3   (PG15 — 2PC at PREPARE)
LOGICALREP_PROTO_STREAM_PARALLEL_VERSION_NUM 4   (PG16 — parallel apply)
LOGICALREP_PROTO_MAX_VERSION_NUM        = STREAM_PARALLEL
```

### Message-type byte (`logicalproto.h:57-78`)

Single ASCII byte at the front of each logical-rep message:

| Byte | Constant | Meaning |
|------|----------|---------|
| `B`  | BEGIN | xact start |
| `C`  | COMMIT | xact commit |
| `O`  | ORIGIN | origin id (cross-cluster echo prevention) |
| `I`/`U`/`D` | INSERT/UPDATE/DELETE | DML row events |
| `T`  | TRUNCATE | bulk truncate |
| `R`  | RELATION | schema/relation descriptor |
| `Y`  | TYPE | type descriptor |
| `M`  | MESSAGE | `pg_logical_emit_message` payload |
| `b`/`P`/`K`/`r` | BEGIN_PREPARE/PREPARE/COMMIT_PREPARED/ROLLBACK_PREPARED | 2PC |
| `S`/`E`/`c`/`A`/`p` | STREAM_START/STOP/COMMIT/ABORT/PREPARE | streamed-xact framing |

The case-sensitivity choice (uppercase = non-streamed, lowercase = some
streamed/prepared variants) is convention, not enforced semantics.

### Tuple format (`logicalproto.h:84-99`)

`LogicalRepTupleData` carries one received tuple. Each column is one of:

- `n` (NULL) — line 96
- `u` (UNCHANGED toast) — line 97; means "value didn't change in
  UPDATE, look at the old row"
- `t` (TEXT-mode value) — line 98; output of the type's text out
  function, length-prefixed
- `b` (BINARY value, PG14+) — line 99; output of the type's binary
  send function

The publisher decides text vs binary per `subscription.binary` + column
type capability; the subscriber must accept either.

### Relation descriptor (`logicalproto.h:104-116`)

`LogicalRepRelation` — the publisher tells the subscriber about a table:
`remoteid` (publisher's relation OID), `nspname`, `relname`, `natts`,
`attnames[]`, `atttyps[]` (REMOTE oid; needs mapping via TYPE message
or pg_type lookup), `replident`, `relkind`, `attkeys` (replica-identity
columns).

The subscriber caches this in `LogicalRepRelMapEntry` (see
`logicalrelation.h`) and maps it to a local relation by
`nspname.relname` lookup.

### Type descriptor (`logicalproto.h:119-124`)

`LogicalRepTyp` — `remoteid`, `nspname`, `typname`. Used by the
subscriber to interpret binary-mode column values whose remote type OID
doesn't match a local type by OID.

### Transaction frames (`logicalproto.h:127-192`)

- `LogicalRepBeginData` (line 127) — `final_lsn`, `committime`, `xid`.
- `LogicalRepCommitData` (line 134) — `commit_lsn`, `end_lsn`, `committime`.
- `LogicalRepPreparedTxnData` (line 144) — adds `gid[GIDSIZE]`.
- `LogicalRepCommitPreparedTxnData` (line 156) and
  `LogicalRepRollbackPreparedTxnData` (line 173) — note the latter
  carries `prepare_end_lsn` so the subscriber can tell "I never received
  this PREPARE, skip the rollback" (lines 165-172, important
  correctness comment).
- `LogicalRepStreamAbortData` (line 186) — `xid` + `subxid` + LSN +
  timestamp; used by v4 streaming for sub-xact abort.

### Wire write/read pairs (`logicalproto.h:194-275`)

Each message type has a symmetric write/read pair, both operating on
`StringInfo` buffers. The write functions are publisher-side; the read
functions are subscriber-side. None of the read functions return errors
— they `elog(ERROR)` on protocol violation. `[verified-by-code]`
(`proto.c:68, 104, 206, 218, …`)

`logicalrep_message_type(action)` (line 275) — human-readable name for
log messages.

`logicalrep_should_publish_column` (line 276) — publisher-side filter for
column lists + generated columns.

## Phase D notes

### Message-type validation

Dispatch on the leading byte happens in `apply_dispatch`
(`worker.c:3797-3897`). The `default:` arm raises
`ERRCODE_PROTOCOL_VIOLATION` `[verified-by-code]`. So an unknown byte
kills the apply worker (which restarts via launcher). That's strict —
no silent skip — and the right call.

But: `LOGICAL_REP_MSG_MESSAGE` ('M') is parsed but its body is
**discarded** (`worker.c:3848-3855`, comment "Logical replication does
not use generic logical messages yet"). A malformed M-message therefore
does NOT crash apply, but a maliciously oversized one will be allocated
into the apply worker's StringInfo — see DoS issue below.

### Length-prefix discipline

All variable-length fields use `pq_getmsgstring` (null-terminated) or
`pq_getmsgbytes(len)` after reading an explicit length. `pq_getmsg*`
helpers enforce buffer bounds and `elog(ERROR)` on overrun. So
truncated messages fail loudly. `[verified-by-code]` via callers
in `proto.c`.

### Binary vs text mode hazards

Per `logicalproto.h:99`, binary mode was added in PG14. A
publisher-subscriber version mismatch where publisher sends 'b' and
subscriber predates v2 of `LogicalRepTupleData` would mis-parse.
Guarded by `LOGICALREP_PROTO_VERSION_NUM` negotiation, but the version
gate for binary specifically isn't in the constants block — it's a
runtime check in proto.c. `[inferred]`

### Schema/Type message caching

A relation descriptor ('R') invalidates / replaces the subscriber's
`LogicalRepRelMapEntry` for that `remoteid`. Subscribers trust the
publisher's `nspname`/`relname` and look up a LOCAL relation by name —
this is the foot-gun: a renamed local table is silently un-mapped, and a
malicious publisher with the same `nspname.relname` could write into any
table the subscription owner can write to. See `worker_internal.h` doc
for the trust posture.

## Potential issues

- [ISSUE-wire-protocol: `LOGICAL_REP_MSG_MESSAGE` ('M') (line 68 +
  `worker.c:3848-3855`) is parsed-but-ignored by core apply. The bytes
  are still read into `StringInfo`, so a publisher can force the
  subscriber to allocate up to message_size per emit. With
  `pg_logical_emit_message` open to PUBLIC by default (no proacl in
  `pg_proc.dat:11731-11740`), any role on the publisher can pump bytes
  through every subscriber. (medium DoS / amplification)]
- [ISSUE-trust-boundary: tuple `colstatus` byte (lines 96-99) is read
  directly from the wire and switched on; any byte that isn't n/u/t/b
  triggers an error in `logicalrep_read_tuple` (`proto.c` around line
  900+). Strict, good. But the `u` ("unchanged toast") case shifts
  responsibility onto the subscriber to find the prior value — for
  REPLICA IDENTITY FULL with no PK, this is correctness-fragile.
  (correctness, low)]
- [ISSUE-undocumented-invariant: the version-negotiation rule
  (`MIN_VERSION_NUM=1`, `MAX_VERSION_NUM=4`) is asymmetric — old
  subscribers can talk to new publishers but a v1 subscriber cannot
  consume v2+ messages. The header doesn't spell out the downgrade
  contract; pgoutput in walsender does it. (low)]
- [ISSUE-wire-protocol: `LogicalRepRelation` (line 104) carries
  `remoteid` (publisher OID) as the cache key but the subscriber maps
  by `nspname.relname` (resolved at `logicalrep_rel_open`). A publisher
  swapping the OID for the same name silently re-binds; a publisher
  changing the name forces a fresh lookup. Subscriber TRUSTS the
  publisher-chosen schema-qualified name to identify the local target.
  (trust-boundary, medium — covered more in logicalrelation.h doc)]
- [ISSUE-wire-protocol: `LogicalRepTyp` (line 119) sends type by remote
  `nspname.typname`; subscriber resolves to local OID at apply time.
  If the publisher sends a name that the subscriber-side role can't
  see (search_path / RLS / dropped type), the apply worker errors out
  and the subscription stalls. Not a vuln, but a known footgun for
  cross-version replication. (low)]
- [ISSUE-state-transition: STREAM_START/STOP framing (`S`/`E`, lines
  73-74) implies a per-subscriber implicit state — "are we inside a
  streamed xact?" — that isn't reified in this header. Tracked in
  worker.c state. (maybe)]
- [ISSUE-undocumented-invariant: `LOGICALREP_COLUMN_*` macros (lines
  96-99) are wire bytes AND in-memory markers — the comment
  "These values are also used in the on-the-wire protocol" (line 95)
  is the only thing keeping them stable. A reviewer who only sees the
  C side might re-letter them. (low / coupling hazard)]

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new replication / logical-decoding message](../../../../scenarios/add-new-replication-message.md)

<!-- scenarios:auto:end -->

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-replication`](../../../../issues/include-replication.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [idioms/apply-worker-loop-and-dispatch.md](../../../../idioms/apply-worker-loop-and-dispatch.md)
