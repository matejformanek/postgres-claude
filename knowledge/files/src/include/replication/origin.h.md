# src/include/replication/origin.h

## Purpose

Exports for **replication origins**: a small server-wide registry that
maps a 16-bit `ReplOriginId` to a human-readable name (≤ 512 bytes),
used by logical replication to tag WAL records with "this row change
came from origin X" so that downstream apply workers can avoid
re-applying their own changes back to themselves (loop avoidance) and
so that conflict resolution can attribute changes to a source. Source
pin `4b0bf0788b066a4ca1d4f959566678e44ec93422`.

## Role in PG

The `pg_replication_origin` catalog stores the (oid, name) registry;
runtime per-origin progress (the highest `remote_lsn` we've applied
from that origin, plus the local LSN that wrote the apply commit) is
kept in shared memory and checkpointed via `CheckPointReplicationOrigin`.
Apply workers call `replorigin_session_setup(node, acquired_by)` to bind
their session to one origin, then `replorigin_session_advance` after
each apply. The output plugin `filter_by_origin_cb` lets pgoutput drop
changes whose origin doesn't match what the subscriber wants. WAL is
written for origin changes via `XLOG_REPLORIGIN_SET` and
`XLOG_REPLORIGIN_DROP` so that physical standbys mirror the registry.

## Key types/struct fields

- `xl_replorigin_set` / `xl_replorigin_drop` (lines 18-28) — WAL
  payloads. `set` carries (`remote_lsn`, `node_id`, `force`); `drop`
  carries just `node_id`. [verified-by-code]
- `XLOG_REPLORIGIN_SET = 0x00`, `XLOG_REPLORIGIN_DROP = 0x10` (lines
  30-31) — rmgr info bits for `RM_REPLORIGIN_ID`. [verified-by-code]
- `InvalidReplOriginId = 0` (line 33), `DoNotReplicateId =
  PG_UINT16_MAX` (line 34) — sentinel ids; `DoNotReplicateId` marks
  changes that must never be forwarded (e.g. internal bookkeeping).
  [verified-by-code]
- `MAX_RONAME_LEN = 512` (line 41) — comment line 37-40 explains the
  cap is chosen to avoid needing a TOAST table on
  `pg_replication_origin`. [from-comment]
- `ReplOriginXactState` (lines 43-48) — per-xact slot holding the
  current origin id, the source's commit LSN, and timestamp; consulted
  during commit-record write to embed origin metadata in the WAL.
  [verified-by-code]
- `replorigin_xact_state` (line 50) — process-global instance of the
  above. [verified-by-code]
- `max_active_replication_origins` (line 53) — GUC bounding the size of
  the shmem progress array. [verified-by-code]
- Registry API (lines 56-60): `replorigin_by_name`, `replorigin_create`,
  `replorigin_drop_by_name`, `replorigin_by_oid`. [verified-by-code]
- Progress API (lines 63-73): `replorigin_advance`,
  `replorigin_get_progress`, `replorigin_session_advance`,
  `replorigin_session_setup(node, acquired_by)`,
  `replorigin_session_reset`, `replorigin_session_get_progress`.
  [verified-by-code]
- WAL hooks (lines 83-85): `replorigin_redo`, `replorigin_desc`,
  `replorigin_identify`. [verified-by-code]

## Phase D notes

Replication origins are a server-wide namespace, not a per-database
one — origin names and ids are visible across all databases via the
shared catalog `pg_replication_origin`. A subscription in database A
sees the names of all origins, including those created by
subscriptions in database B. The information disclosed is just the
name (typically `pg_<subscription_oid>` for managed origins) plus the
last applied LSN, but it leaks the count and approximate activity of
foreign subscriptions across databases.

`replorigin_create` and `replorigin_drop_by_name` are SQL-callable via
`pg_replication_origin_create(text)` and `pg_replication_origin_drop(text)`,
gated by superuser-or-`pg_create_subscription`-membership. The name is
the only identity; collision detection is by string equality on
`MAX_RONAME_LEN` bytes.

`acquired_by` in `replorigin_session_setup` is the ProcNumber that
"owns" the origin in this session — a different backend trying to bind
to the same origin will be told it's busy. This is the only mutex
between concurrent apply workers for the same origin; subscription
workers rely on it to prevent two workers from advancing the same
origin progress concurrently.

## Potential issues

- [ISSUE-info-disclosure: `pg_replication_origin` is a shared catalog
  visible from every database; subscription origin names and progress
  LSNs leak cross-database to any role that can SELECT the catalog
  (sev=maybe)]
- [ISSUE-trust-boundary: `replorigin_create` is gated by
  `pg_create_subscription` role membership, not by superuser, since
  PG16 — wider attack surface than pre-16 (sev=unlikely)]
- [ISSUE-state-transition: `acquired_by` (a ProcNumber) is the
  origin's "lease holder"; if a backend crashes without calling
  `replorigin_session_reset`, the lease is released by PROC cleanup
  but the header doesn't document this — relies on origin.c cleanup
  hooks (sev=unlikely)]
- [ISSUE-undocumented-invariant: `DoNotReplicateId = PG_UINT16_MAX`
  must NEVER appear in the catalog; header asserts it as a sentinel
  but doesn't say where the check lives (origin.c) (sev=unlikely)]
