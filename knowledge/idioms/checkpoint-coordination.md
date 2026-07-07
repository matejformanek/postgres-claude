# Checkpoint coordination — RequestCheckpoint + the checkpointer

A checkpoint is a coordinated cluster-wide state save: every
dirty buffer flushed, control file updated, WAL marker
inserted, FSM and VM forks synced. A **dedicated checkpointer
process** owns the actual work; user backends and bgworkers
trigger checkpoints by signaling it. Coordination matters
because the checkpointer can be busy on the current checkpoint
while another request arrives.

Anchors:
- `source/src/backend/access/transam/xlog.c:CreateCheckPoint`
  + `CheckPointGuts` [verified-by-code]
- `source/src/backend/postmaster/checkpointer.c` — checkpointer
  process
- `source/src/include/access/xlog.h` — `RequestCheckpoint` API
- `knowledge/subsystems/access-transam.md` — xlog subsystem
- `knowledge/idioms/crash-recovery-startup.md` — recovery
  consumes checkpoint records

## The trigger entry point

```c
extern void RequestCheckpoint(int flags);
```

Flags are an OR of:
- `CHECKPOINT_IS_SHUTDOWN` — final checkpoint before postmaster
  exit
- `CHECKPOINT_END_OF_RECOVERY` — first checkpoint after recovery
- `CHECKPOINT_FAST` — minimum spread; do it asap
- `CHECKPOINT_FORCE` — even if no work to do
- `CHECKPOINT_WAIT` — block until completion
- `CHECKPOINT_CAUSE_XLOG` — triggered by `max_wal_size` limit
- `CHECKPOINT_CAUSE_TIME` — triggered by `checkpoint_timeout`

[verified-by-code `xlog.c:2524, 4848` show typical callsites]

The default policy: `RequestCheckpoint(CHECKPOINT_CAUSE_XLOG)`
or `..._CAUSE_TIME` — i.e. routine checkpoints driven by the
postgres background activity. Forced/wait flags are for explicit
shutdown sequences.

## The signal-and-condvar protocol

`RequestCheckpoint`:

1. Writes the flags into shared memory's checkpointer-request
   slot.
2. Increments a request counter so the checkpointer can detect
   a new request even if the current value is the same.
3. Signals the checkpointer process (SIGINT).
4. If `CHECKPOINT_WAIT`, blocks on a condition variable until
   the checkpoint completes.

The checkpointer:

1. Wakes on signal or periodic timer (`checkpoint_timeout`).
2. Reads the request slot; ORs accumulated flags.
3. Runs `CreateCheckPoint(flags)`.
4. On completion, increments a "completed" counter and
   broadcasts on the condvar.

## CreateCheckPoint — the actual work

[verified-by-code `xlog.c:703` `CheckPointGuts`]

Phases of a checkpoint:

1. **Lock postmaster's `controlFile`** — block concurrent
   start/stop.
2. **`XLogInsert(XLOG_CHECKPOINT)`** — write the checkpoint
   record into WAL. Records the redo-start LSN.
3. **Flush all dirty shared buffers** via `BufferSync` — the
   long pole. Spread over `checkpoint_completion_target` of
   the inter-checkpoint interval.
4. **Sync FSM + VM forks** via `ProcessSyncRequests`.
5. **Truncate old `pg_xact` / `pg_subtrans` / `pg_multixact`
   /` pg_serial`** if their cleanup horizon advanced.
6. **Update `pg_control`** with the new redo LSN. This is the
   atomic "checkpoint succeeded" moment.
7. **Remove obsolete WAL segments** from `pg_wal/`.

If anything fails mid-checkpoint, the partial work is harmless
— the checkpoint isn't complete until step 6 (pg_control
update). Recovery on a crashed mid-checkpoint cluster replays
from the PREVIOUS checkpoint's redo LSN.

## The spread

`checkpoint_completion_target` (default 0.9) tells the
checkpointer to spread the buffer-flush work over 90% of the
inter-checkpoint interval. If `checkpoint_timeout=5min` and
target=0.9, buffer flushing rate is sized so that all dirty
buffers finish at 4.5 minutes into the 5-minute window.

The spread mitigates the "checkpoint spike" — naive
implementations would dump all dirty buffers in one burst,
saturating IO.

## CHECKPOINT_FAST — no spread

`CHECKPOINT_FAST` overrides the spread — flushes are issued
back-to-back. Used for:
- Shutdown checkpoints (don't waste time spreading).
- End-of-recovery checkpoints.
- Explicit `CHECKPOINT;` SQL command (admin requesting
  immediate flush).

Be careful: a CHECKPOINT_FAST on a hot OLTP system can spike
IO and latency. The default policy is correct for normal
operation; only override with reason.

## The "skip if no work" optimization

If no dirty buffers exist and no clog truncation is pending,
`CreateCheckPoint` may return early with a no-op checkpoint
record. The intent: avoid spamming WAL with empty checkpoint
records when the cluster is idle.

`CHECKPOINT_FORCE` overrides this; the checkpoint runs even
if no work.

## Coordination with backends — controlLock + WALInsertLocks

During the buffer-flush phase, individual buffer flushes
take partition LWLocks; no global lock is held. Backends can
continue executing queries.

During the pg_control update, the `ControlFileLock` is held
exclusive. Brief — just a `write()` + `fsync()`. Backends
that need `pg_control` (rare; mostly during startup) wait
briefly.

WAL emission continues throughout via `WALInsertLocks` (one
per partition for scalability). The checkpoint just inserts
one xlog record at the START — backends keep writing during
the spread.

## Common review-time concerns

- **Don't call `RequestCheckpoint` from a hot path.** Each
  call signals the checkpointer; per-tuple usage = signal
  storm.
- **`CHECKPOINT_WAIT` blocks the caller** until completion,
  which may take minutes. Acceptable in shutdown paths,
  bad in user-facing code.
- **`CheckPointGuts` is the "actually do it" function.**
  Don't call directly; go through `RequestCheckpoint` so the
  checkpointer's coordination is preserved.
- **The buffer-flush spread depends on accurate timing.**
  System-clock jumps (NTP adjustment) can cause uneven
  flush rate; usually self-correcting on the next round.
- **`pg_control` corruption** = unrecoverable cluster. If
  the checkpoint update step fails mid-write, recovery
  may not find a valid pg_control. Standard backup
  protection covers this.

## Invariants

- **[INV-1]** Checkpoints are triggered via
  `RequestCheckpoint`; the checkpointer process does the
  work.
- **[INV-2]** Phase 6 (pg_control update) is the atomic
  success moment; failures before it are harmless.
- **[INV-3]** Buffer-flush is spread over
  `checkpoint_completion_target` of the interval to avoid IO
  spikes.
- **[INV-4]** `CHECKPOINT_FAST` skips the spread; for
  shutdown / recovery / explicit admin requests only.
- **[INV-5]** Coordination via signal + shared-memory
  request slot + condvar for WAIT semantics.

## Useful greps

- The trigger entry point:
  `grep -RIn 'RequestCheckpoint' source/src/backend | head -20`
- The CheckPointGuts phases:
  `grep -n 'CheckPointGuts\|BufferSync\|ProcessSyncRequests' source/src/backend/access/transam/xlog.c | head -15`
- The checkpointer process:
  `grep -n 'CheckpointerMain\|HandleCheckpointerInterrupts' source/src/backend/postmaster/checkpointer.c | head -15`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/transam/xlog.c`](../files/src/backend/access/transam/xlog.c.md) | — | CreateCheckPoint, CheckPointGuts |
| [`src/backend/postmaster/checkpointer.c`](../files/src/backend/postmaster/checkpointer.c.md) | — | process implementation |
| [`src/include/access/xlog.h`](../files/src/include/access/xlog.h.md) | — | RequestCheckpoint API |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-wal-record`](../scenarios/add-new-wal-record.md)
- [`bump-catversion`](../scenarios/bump-catversion.md)

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/crash-recovery-startup.md` — recovery
  reads the last checkpoint record from `pg_control`.
- `knowledge/idioms/wal-record-construction.md` — checkpoint
  is one of the WAL record types.
- `knowledge/subsystems/storage-buffer.md` — `BufferSync`
  is the buffer manager's flush primitive.
- `knowledge/subsystems/access-transam.md` — xlog
  subsystem context.
- `.claude/skills/wal-and-xlog/SKILL.md` — checkpoint cadence
  + recovery contract.
- `source/src/backend/postmaster/checkpointer.c` — process
  implementation.
- `source/src/backend/access/transam/xlog.c` —
  `CreateCheckPoint`, `CheckPointGuts`.
