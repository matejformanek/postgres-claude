# src/include/replication/logicalrelation.h

## Purpose

Subscriber-side relation-mapping cache: bridges a `LogicalRepRelation`
descriptor received over the wire (`logicalproto.h`) to a LOCAL
`Relation` plus an attribute map.

## Role in PG

- Populated when the apply worker receives a RELATION ('R') message:
  `apply_handle_relation` calls `logicalrep_relmap_update` (line 42).
- Queried at every DML apply: `apply_handle_insert/update/delete` call
  `logicalrep_rel_open(remoteid, lockmode)` (line 45) which lazily
  resolves the local OID by name lookup, opens the relation, computes
  the attribute map, and caches the result in `LogicalRepRelMapEntry`.
- Companion `logicalrep_partition_open` (line 47) handles partitioned
  tables: given the root mapping and a specific partition `Relation`,
  builds a per-partition entry with its own attmap.
- `IsIndexUsableForReplicaIdentityFull` (line 51) and
  `GetRelationIdentityOrPK` (line 52) help the apply path pick an index
  to locate the row when REPLICA IDENTITY isn't a PK.

## Key types/struct fields

`LogicalRepRelMapEntry` (`logicalrelation.h:19-40`):

- `remoterel` (line 21) — embedded `LogicalRepRelation`; the hash key is
  `remoterel.remoteid` (the publisher's OID, treated opaquely on the
  subscriber).
- `localrelvalid` (line 28) — invalidation flag. Set false on any
  relevant relcache invalidation; revalidated at next `_rel_open`.
  Comment on lines 24-27: while the local relation is OPEN, the lock
  guarantees the cached info stays good — so invalidation matters only
  between dispatches.
- `localreloid`, `localrel` (lines 31-32) — resolved local Oid plus the
  open `Relation` (or NULL between dispatches).
- `attrmap` (line 33) — `AttrMap *` mapping local attnums to remote ones
  (by NAME). Lets the subscriber tolerate column reordering and dropped
  columns.
- `updatable` (line 34) — false if the remote replica-identity columns
  aren't all present locally; UPDATE/DELETE then ereports.
- `localindexoid` (line 35) — pre-picked index for REPLICA IDENTITY FULL
  searches (or InvalidOid for seqscan / PK path).
- `state`, `statelsn` (lines 38-39) — initial table-sync state for this
  relation; one of SUBREL_STATE_INIT/DATASYNC/SYNCDONE/READY (see
  `pg_subscription_rel.h`).

## Phase D notes

- The subscriber resolves `remoterel.nspname` + `remoterel.relname` to a
  local Oid by **name lookup** (in `logicalrep_rel_open`'s implementation
  in `relation.c`). This is the trust hinge: a malicious or
  out-of-sync publisher controls which local table the apply worker
  touches by choosing the name. The publisher's *OID* is opaque/just a
  cache key.
- Attmap is built by attname match — a local column added with the same
  name as a remote one silently joins replication. Whether that's a
  feature or a foot-gun depends on operator intent.
- The `updatable=false` rail is a safety: a publisher claiming REPLICA
  IDENTITY DEFAULT but the subscriber's PK doesn't cover the remote PK
  columns → updates/deletes refused with a documented error.

## Potential issues

- [ISSUE-trust-boundary: subscriber resolves the local relation by
  publisher-supplied `nspname`/`relname` (via the cached
  `remoterel.nspname`/`remoterel.relname`, lines 21 → publisher-controlled).
  An apply worker running as the subscription owner with broad write
  privileges will happily INSERT/UPDATE/DELETE on any table the
  publisher names — INCLUDING tables the publisher never advertised in
  its PUBLICATION, IF a malicious publisher can send a forged RELATION
  message. Real-world risk depends on whether the publisher is
  authenticated/trusted; in a compromised-publisher scenario, the
  subscriber's data perimeter equals the subscription owner's write
  perimeter. (trust-boundary, medium)]
- [ISSUE-state-transition: `localrelvalid` (line 28) is a single bool;
  the rule "valid while lock held" (lines 24-27) depends on the caller
  always reacquiring the lock through `_rel_open`. Direct field access
  bypassing `_rel_open` is a gun. (low)]
- [ISSUE-undocumented-invariant: header doesn't say what happens when
  `nspname.relname` resolves to a VIEW or a FOREIGN TABLE on the
  subscriber. The .c file handles this with relkind checks, but the
  contract isn't in the header. (low)]
- [ISSUE-info-disclosure: failed mappings produce ereport messages that
  may include the publisher-supplied `nspname`/`relname` verbatim
  (server logs, possibly subscriber error tables). Low risk on its own.
  (low)]
