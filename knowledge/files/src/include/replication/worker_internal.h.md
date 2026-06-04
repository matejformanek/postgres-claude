# src/include/replication/worker_internal.h

## Purpose

The **subscriber-side** internal API shared by the apply worker, parallel
apply workers, table-sync workers, and sequence-sync workers. Defines
the `LogicalRepWorker` slot struct (lives in shmem, one per allowed
worker), the parallel-apply shared-state machinery, and dozens of
helper entry points (`logicalrep_worker_*`, `pa_*`, `apply_*`).

## Role in PG

- Allocated in shared memory at startup, sized by
  `max_logical_replication_workers`. Slots are reused; `generation`
  (line 49) increments on each new owner to detect stale references.
- The launcher (`logicallauncher.h`) calls `logicalrep_worker_launch`
  (line 264) to claim a slot and fork a background worker with the
  matching `*Main` function (`logicalworker.h`).
- Each worker, once running, calls `logicalrep_worker_attach` (line 258)
  to bind to its slot and sets up `MyLogicalRepWorker` (line 250).
- Per-subscription state — owner OID, dbid, two-phase state, apply LSN
  cursors — lives partly in this struct and partly in `MySubscription`
  (line 249, loaded from `pg_subscription`).

## Key types/struct fields

### `LogicalRepWorkerType` (`worker_internal.h:28-35`)

`UNKNOWN`, `TABLESYNC`, `SEQUENCESYNC`, `APPLY`, `PARALLEL_APPLY`. The
launcher itself is `UNKNOWN`.

### `LogicalRepWorker` (lines 37-111)

- `type`, `launch_time`, `in_use`, `generation` (lines 40-49) — slot
  bookkeeping.
- `proc` (line 52) — PGPROC * or NULL.
- `dbid`, `userid`, `subid` (lines 55-61) — `userid` is THE
  trust-boundary anchor (see Phase D notes). Comment line 57: "User to
  use for connection (will be same as owner of subscription)."
- `relid`, `relstate`, `relstate_lsn`, `relmutex` (lines 63-67) — for
  table-sync workers; protected by `relmutex` (spinlock).
- `stream_fileset` (line 78) — `FileSet *` for spilling streamed
  transactions (v2+). Per-xact buffiles inside.
- `leader_pid` (line 84), `parallel_apply` (line 87) — parallel-apply
  linkage.
- `oldest_nonremovable_xid` (line 101, comment 89-100) — published to
  the cluster-wide `pg_conflict_detection` slot for conflict-detection
  xmin advancement.
- `last_lsn` … `reply_time` (lines 104-108) — protocol-flow stats.
- `last_seqsync_start_time` (line 110) — sequencesync rate-limiter.

### `ParallelTransState` (lines 119-124) and `PartialFileSetState` (lines 142-148)

State enums driving the leader↔parallel-apply handshake. Comment on
the state machines is unusually thorough — lines 119-124, 128-148.

### `ParallelApplyWorkerShared` (lines 154-199)

Lives in a DSM segment owned by the leader. Fields gated by `mutex` plus
one atomic counter (`pending_stream_count`, line 179). Holds the
`fileset` (line 198) that bridges leader→parallel for spill-on-timeout.

### `ParallelApplyWorkerInfo` (lines 204-234)

Leader-side handle for each spawned parallel worker: `mq_handle` (line
210), `error_mq_handle` (line 216), `dsm_seg` (line 218),
`serialize_changes` (line 225), `shared` (line 233).

### Globals (lines 237-256)

- `ApplyContext` (line 237) — long-lived MemoryContext (worker
  lifetime).
- `ApplyMessageContext` (line 239) — per-message context.
- `MyParallelShared` (line 243) — non-NULL only in parallel apply
  workers.
- `LogRepWorkerWalRcvConn` (line 246) — libpqwalreceiver connection.
- `MySubscription`, `MyLogicalRepWorker` (lines 249-250).
- `in_remote_transaction` (line 252), `InitializingApplyWorker` (line
  254).

### Entry points (lines 258-360)

Worker-slot lifecycle (`logicalrep_worker_attach/find/launch/stop/wakeup`),
sync-rel housekeeping (`ProcessSyncingTablesForApply/Sync`,
`AllTablesyncsReady`), stream framing helpers
(`stream_start_internal`/`stream_stop_internal`/`apply_spooled_messages`),
the central `apply_dispatch(StringInfo s)` (line 306), error-callback
glue, and the `pa_*` parallel-apply family.

Helper inline predicates `am_tablesync_worker`,
`am_sequencesync_worker`, `am_leader_apply_worker`,
`am_parallel_apply_worker`, `get_logical_worker_type`
(lines 369-400).

## Phase D notes

### Trust posture — what does apply trust from publisher?

`userid` (line 58) is the **subscription owner** at the time of
`CREATE SUBSCRIPTION` (or last `ALTER SUBSCRIPTION ... OWNER TO`). Every
INSERT/UPDATE/DELETE issued by `apply_handle_*` runs with this userid's
privileges. The apply worker `SetUserIdAndSecContext` to this OID and
then executes commands derived from publisher-supplied bytes.

What the publisher CAN dictate, per `apply_dispatch`
(`worker.c:3797`) + `apply_handle_*`:

- WHICH local relation is touched (via RELATION message's
  `nspname`/`relname`; resolved by NAME on the subscriber — see
  `logicalrelation.h` doc).
- WHICH columns and what values, including arbitrary text/binary
  payloads parsed as the local column types.
- WHEN a transaction begins/commits/prepares — including injecting
  prepared-xact GIDs.
- That `pg_logical_emit_message` 'M' messages should be DISCARDED
  (apply ignores them, but other plugins surface them).

What the publisher CANNOT (in core apply):

- Issue arbitrary DDL — only DML, TRUNCATE, and TYPE/RELATION metadata.
- Trigger arbitrary functions — except via column input functions
  applied to publisher-supplied values, and via subscription-side
  triggers and rules. (BEFORE/AFTER triggers fire on apply unless
  disabled via `session_replication_role=replica` + trigger settings.)

The classic threat: a malicious publisher with the same `nspname.relname`
as a sensitive table on the subscriber can write to that table if the
subscription owner has INSERT privileges on it — even if the publisher
never published that table in its publication. This is the
`logicalrelation.h` trust-boundary issue.

### Conflict-detection xmin coupling

`oldest_nonremovable_xid` (line 101) is read asynchronously by the
launcher's `pg_conflict_detection` slot maintenance (comment lines
89-100). A stuck apply worker that never advances this — or one that's
killed without clearing it — can pin xmin cluster-wide. Operator
nightmare.

### Parallel apply state machines

The `ParallelTransState` ordering (lines 121-123:
`UNKNOWN → STARTED → FINISHED`) is enforced by the comment but not by
type — leader and parallel both poke it under `mutex`. The
`PartialFileSetState` (lines 142-148) is a 4-state ratchet (EMPTY →
SERIALIZE_IN_PROGRESS → SERIALIZE_DONE → READY).

### Memory contexts

`ApplyContext` (worker lifetime) vs `ApplyMessageContext` (per-message)
matters for plugin-style work inside `apply_handle_*`. Leaks into
`ApplyContext` accrete across the whole subscription run — a
long-lived subscription can grow.

## Potential issues

- [ISSUE-trust-boundary: apply worker runs as `MyLogicalRepWorker->userid`
  (line 58, same as subscription owner). Every row applied uses this
  identity; publisher controls column values + target relation name.
  Subscription owners should not own sensitive tables that an
  attacker-controlled publisher could name-collide. Documented above.
  (medium, by-design)]
- [ISSUE-trust-boundary: column input functions invoked on
  publisher-supplied text values run arbitrary code (e.g. `int4in`,
  `json_in`, custom type's input function). A custom type with a
  buggy/expensive input function is attacker-reachable from the
  publisher. (medium, well-known)]
- [ISSUE-dos: `oldest_nonremovable_xid` (line 101) is read async by
  launcher; a wedged apply worker can pin cluster-wide xmin. Comment
  lines 98-99 acknowledge the dependency. No header-level escape hatch
  for "force-clear xmin for stuck subscription". (medium, operational)]
- [ISSUE-state-transition: `relmutex` (line 67) is a slock_t protecting
  `relid`/`relstate`/`relstate_lsn`, but the rest of the struct relies
  on `LogicalRepWorkerLock` (in shmem) for ordering. Mixing a spinlock
  with an LWLock-protected struct is a code-smell trap for new
  contributors. (low)]
- [ISSUE-undocumented-invariant: `generation` (line 49) is the
  ABA-prevention token but the header doesn't say WHO is required to
  read it and compare. (low)]
- [ISSUE-info-disclosure: `apply_error_callback` (line 327) is meant to
  decorate error messages with origin info. Publisher-controlled
  strings (relname, nspname) can land in subscriber server logs and
  client error responses; a high-volume malicious publisher can fill
  logs with arbitrary text. (low-medium)]
- [ISSUE-state-transition: `PartialFileSetState` (lines 142-148)
  4-state machine has no explicit reverse arrows; if a parallel apply
  worker dies after READY, the leader's cleanup path
  (`stream_cleanup_files`, line 310) must converge — but the contract
  isn't asserted. (maybe)]
- [ISSUE-stale-todo: comment on `MyParallelShared` (line 243)
  "InvalidPid otherwise" — but `leader_pid` (line 84) is `pid_t`, and
  Postgres's "InvalidPid" symbol is `0` by convention. Header doesn't
  cite the constant. (very low)]
- [ISSUE-secret-scrub: `apply_error_callback` may format SQLSTATE +
  publisher-supplied data into server logs; no scrubbing layer on the
  subscriber side. If a publisher includes credentials in a payload
  (e.g. an UPDATE on a table with hashed_password), errors during
  apply will surface the value to the subscriber's log. (low,
  by-design)]
