# src/include/replication/walsender_private.h

## Purpose

Walsender internal state: per-walsender `WalSnd` shared-memory slot, the
cluster-wide `WalSndCtl` (with sync-rep queue heads and bitfield
flags), and the replication-grammar bison/flex entry points.

## Role in PG

`max_wal_senders` slots of `WalSnd` are allocated in shared memory at
postmaster start. Each active walsender attaches to one slot
(`MyWalSnd`) and publishes its state (LSN pointers, lag, sync-rep
priority) for monitoring views (`pg_stat_replication`) and for the
sync-rep machinery to find synchronous standbys.

## Key types/struct fields

- `WalSndState` enum (lines 24-31) — STARTUP → BACKUP → CATCHUP →
  STREAMING → STOPPING. BACKUP is for `BASE_BACKUP` command, distinct
  from streaming. [verified-by-code]

- `WalSnd` (lines 41-79) — one per walsender slot. Comment (lines
  34-40) describes the locking discipline: spinlock `mutex` (line 71)
  protects most fields, BUT some fields are only written by the owning
  walsender, so the walsender itself may read them without the lock.
  `pid` and `needreload` ALWAYS need the lock. The "some" fields are
  not enumerated in the comment — undocumented invariant. [verified-by-code]

- LSN/lag triplets: `sentPtr` (line 46), then standby-reported
  `write`/`flush`/`apply` (lines 55-57) plus measured
  `writeLag`/`flushLag`/`applyLag` (lines 60-62). Drives
  `pg_stat_replication.write_lag`/`flush_lag`/`replay_lag`.
  [verified-by-code]

- `sync_standby_priority` (line 68) — position of this walsender's name
  in `synchronous_standby_names`, or 0 if not listed. Read by the
  sync-rep wait machinery. [verified-by-code]

- `replyTime` (line 76) — timestamp of last reply message from standby,
  for timeout detection (`wal_sender_timeout`). [verified-by-code]

- `kind` (line 78, `ReplicationKind`) — physical vs logical, set at
  walsender init. [verified-by-code]

- `WalSndCtlData` (lines 84-117) — single cluster-wide struct,
  `WalSndCtl` pointer (line 134). Contains:
  - `SyncRepQueue[NUM_SYNC_REP_WAIT_MODE]` (line 90) — dlist heads, one
    per sync-commit wait mode (WRITE, FLUSH, APPLY, REMOTE_APPLY).
    Waiting commit backends enqueue themselves; walsenders dequeue and
    wake when standby confirms the appropriate LSN.
  - `lsn[NUM_SYNC_REP_WAIT_MODE]` (line 96) — head LSN per queue.
  - `sync_standbys_status` (line 103) — uint8 bitfield, set by
    checkpointer (NOT by waiting backends, because they can't safely
    reload config — comment lines 99-102).
  - `wal_flush_cv`, `wal_replay_cv`, `wal_confirm_rcv_cv` (lines 106,
    107, 114) — condition variables walsenders wait on.
    `wal_confirm_rcv_cv` is newer (PG17 failover slots): physical
    walsenders holding slots in `synchronized_standby_slots` use it
    to wake logical walsenders that hold failover-enabled slots.
  - `walsnds[FLEXIBLE_ARRAY_MEMBER]` (line 116) — the actual per-slot
    array, sized `max_wal_senders` at shmem init.
  [verified-by-code]

- `sync_standbys_status` flags (lines 119-132):
  - `SYNC_STANDBY_INIT` (1<<0) — first-time-processed marker.
  - `SYNC_STANDBY_DEFINED` (1<<1) — non-empty `synchronous_standby_names`.
  [verified-by-code]

- Replication grammar entry points (lines 139-150):
  `replication_yyparse`, `replication_yylex`, `replication_yyerror`,
  `replication_scanner_init`/`finish`,
  `replication_scanner_is_replication_command`. Generated from
  `repl_gram.y` + `repl_scanner.l`. The lex/yacc grammar parses the
  replication command stream (`START_REPLICATION`,
  `CREATE_REPLICATION_SLOT`, `IDENTIFY_SYSTEM`, etc.); it is small and
  separate from `gram.y`. [verified-by-code]

## Phase D notes

**Wire-protocol attack surface.** `replication_yyparse` parses the
command portion of the replication protocol — input from an
authenticated REPLICATION-role user. Lex/yacc parsers historically have
buffer-overflow tendencies, but bison/flex generated code is reasonably
robust. The interesting check is that a syntax error returns the user
to command mode rather than crashing the backend.
`replication_yyerror` is declared `pg_noreturn` (line 147), so it
ereport(ERROR)s — the backend's normal error-recovery returns to the
command loop. [verified-by-code]

**Sync-rep queue invariants.** The dlist `SyncRepQueue[]` (line 90)
links backends waiting for `synchronous_commit`. Walsenders walk the
queue under `SyncRepLock` to release waiters when their reported LSN
crosses `WalSndCtl->lsn[mode]`. Bug class: if a walsender dies mid-walk
without releasing the lock, all commits hang. The lock is heavy-weight
(LWLock), so abort handlers release it; risk is low but real.
[inferred]

**Failover-slot wakeup (PG17+).** `wal_confirm_rcv_cv` (line 114) is
used when a physical walsender attached to a slot listed in
`synchronized_standby_slots` confirms WAL receipt — it then wakes
logical walsenders holding failover-enabled logical slots so they can
advance their confirmed_flush_lsn safely (a logical slot can't release
WAL the physical standby hasn't yet flushed, or post-failover the new
primary won't have it). Subtle ordering: physical-confirms → logical-
release. [from-comment]

**`sync_standbys_status` updated by checkpointer.** Comment lines
99-102: waiting backends can't safely reload config, so checkpointer is
the single writer. This avoids a race where multiple waiters
concurrently re-parse `synchronous_standby_names`. [from-comment]

## Potential issues

- [ISSUE-undocumented-invariant: `WalSnd` lock discipline comment
  (lines 34-40) says "some members are only written by the walsender
  process itself" without enumerating which — error-prone for future
  edits (low)]
- [ISSUE-wire-protocol: `replication_yyparse` parses bytes from an
  authenticated remote; bison-generated code is safer than hand-rolled
  but worth fuzz-targeting (low)]
- [ISSUE-state-transition: `WalSndState` transitions undocumented in
  header; STARTUP→BACKUP vs STARTUP→CATCHUP→STREAMING paths only clear
  after reading walsender.c (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-replication`](../../../../issues/include-replication.md)
<!-- issues:auto:end -->
