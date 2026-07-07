# Crash recovery startup — the StartupXLOG flow

When PostgreSQL starts, the **startup process** (a special
auxiliary backend) decides whether the cluster crashed last
time, what kind of recovery to perform, and how far to replay
WAL. Three modes compose: ordinary crash recovery, archive
recovery, and standby (streaming-replication) mode. The
distinction matters because each one terminates differently.

Anchors:
- `source/src/backend/access/transam/xlogrecovery.c` — top-
  level recovery driver [verified-by-code]
- `source/src/backend/access/transam/xlog.c:StartupXLOG` —
  entry point
- `knowledge/subsystems/access-transam.md` — the xlog
  subsystem
- `knowledge/idioms/xlog-region-replay.md` — what
  per-rmgr redo does, called from this flow

## The three orthogonal flags

[verified-by-code `xlogrecovery.c:127-151`]

| Flag | Meaning when true |
|---|---|
| `ArchiveRecoveryRequested` | Cluster was started with a `recovery.signal` (or `standby.signal`) file; we must use the archive_command for missing WAL |
| `InArchiveRecovery` | Currently consuming WAL from the archive (not from `pg_wal/`); transitions to false when archive exhausted |
| `StandbyModeRequested` | `standby.signal` was present; replay continues indefinitely |
| `StandbyMode` | Currently in standby mode; replay tails primary's WAL |

`ArchiveRecoveryRequested && !InArchiveRecovery` is the late-
phase state: we're done with archive WAL but still in
recovery-mode (handling crash recovery + recovery-target logic).

## The four scenario combinations

| `ArchiveRecoveryRequested` | `StandbyModeRequested` | Mode |
|---|---|---|
| false | false | **Crash recovery** — replay WAL in `pg_wal/` from last checkpoint to end |
| true | false | **Archive recovery (PITR)** — replay from archive WAL to `recovery_target_*` |
| true | true | **Streaming standby** — replay forever, fetching WAL from primary's stream after archive exhausted |
| false | true | (Invalid; signals reset to crash-recovery if no `recovery.signal`) |

The "promote" command on a standby flips
`StandbyMode = false` mid-replay; recovery proceeds to the next
clean checkpoint and exits to normal operation.

## The startup process flow

`StartupXLOG()` in `xlog.c` is the entry. Phases:

1. **Read the control file** (`pg_control`). Determines the
   last checkpoint LSN, the `state` field
   (`DB_SHUTDOWNED` / `DB_IN_CRASH_RECOVERY` / etc.).
2. **Check signal files** — `recovery.signal`,
   `standby.signal`. Set `ArchiveRecoveryRequested` +
   `StandbyModeRequested`.
3. **Locate the last checkpoint record**. If the control file
   says `DB_SHUTDOWNED` (clean shutdown), no replay needed.
   Otherwise, start replay from the checkpoint.
4. **Enter the replay loop** — `ReadRecord` →
   per-rmgr `redo` → next.
5. **Reach end-of-WAL**:
   - Crash recovery → switch to "normal operation."
   - Archive recovery → wait for next WAL file from
     archive_command.
   - Standby mode → connect to primary via streaming.
6. **Open for connections** when:
   - All three "end recovery" conditions met (consistent
     LSN reached, no pending records, mode-specific signal
     received).

## The consistent-point concept

Streaming replicas can accept queries **before** replay reaches
end-of-WAL — as soon as the consistent point is reached. The
consistent point is the LSN at which all in-progress
transactions from the moment recovery started have either
committed, aborted, or had their state recorded in the running-
xacts WAL records.

Pre-consistent-point reads would see in-flight transactions in
indeterminate states; the standby refuses connections until
this is past.

`hot_standby = on` enables connection acceptance during
recovery; standalone crash recovery never accepts connections
until exit.

## ReadRecord — the WAL consumer

```c
static XLogRecord *ReadRecord(XLogPrefetcher *xlogprefetcher,
                              int emode, bool fetching_ckpt,
                              TimeLineID replayTLI);
```

[verified-by-code `xlogrecovery.c:368`]

- **`xlogprefetcher`** — optional async-prefetch state for
  buffers the next records will need. Improves replay
  throughput on slow disks.
- **`emode`** — error mode (PANIC / WARNING / etc.) for
  malformed records.
- **`fetching_ckpt`** — true only when locating the initial
  checkpoint record; relaxes some validation.
- **`replayTLI`** — the timeline ID we're currently following
  (timeline switches happen via promotion / point-in-time
  branch).

Each call returns one record or NULL if no more available.
NULL means "ready to advance the WAL position" — for crash
recovery that means we're done; for streaming, wait for next
record.

## Per-rmgr redo dispatch

After `ReadRecord` returns, the rmgr-table is consulted:

```c
XLogRedoOp[rmid].rm_redo(record);
```

Where `RmgrTable` is the table of resource managers (heap,
btree, gin, transam, etc.). Each rmgr's `rm_redo` follows the
`XLogReadBufferForRedo` pattern documented in
`xlog-region-replay.md`.

## End-of-recovery checkpoint

When recovery ends, a special **end-of-recovery checkpoint** is
emitted before normal operation begins. This serves as the
recovery anchor — a subsequent crash recovers from THIS
checkpoint, not the original pre-recovery one. Time-travel
debugging across recovery boundaries is consequently impossible
without the original WAL.

## Common review-time concerns

- **`StandbyMode` ≠ `StandbyModeRequested`.** The former is
  current state; the latter is initial intent. They differ when
  promotion is in flight.
- **Don't write to shared catalogs during recovery.** Recovery
  is read-mostly except for crash-recovery write operations
  (e.g. relmap files). Adding catalog writes from a redo
  function is a guaranteed corruption bug.
- **The `recovery.signal` file is the trigger** — its mere
  presence enables archive recovery. Forgetting to clean it up
  after a successful recovery means the next start re-enters
  recovery mode.
- **`InArchiveRecovery` transitions to false** when the archive
  is exhausted; subsequent records come from `pg_wal/`. Code
  branching on this flag may behave differently mid-replay.

## Invariants

- **[INV-1]** Recovery starts from the **last checkpoint
  record** found in the control file, not the most recent
  record.
- **[INV-2]** Standby mode replays indefinitely; archive
  recovery stops at the recovery target.
- **[INV-3]** Pre-consistent-point connections rejected (unless
  `hot_standby=on` after consistency reached).
- **[INV-4]** End-of-recovery checkpoint must succeed before
  normal operation; failure = re-enter recovery.
- **[INV-5]** `ArchiveRecoveryRequested` set by
  `recovery.signal` OR `standby.signal`.

## Useful greps

- The startup flow:
  `grep -n 'StartupXLOG\|EnableStandbyMode\|ReadRecord' source/src/backend/access/transam/xlogrecovery.c | head -20`
- The dispatch table:
  `grep -n 'RmgrTable\|rm_redo' source/src/backend/access/transam/xlog.c`
- Signal-file handling:
  `grep -n 'recovery.signal\|standby.signal' source/src/backend/access/transam/xlogrecovery.c`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/transam/xlog.c`](../files/src/backend/access/transam/xlog.c.md) | — | StartupXLOG entry point |
| [`src/backend/access/transam/xlogrecovery.c`](../files/src/backend/access/transam/xlogrecovery.c.md) | — | implementation; ReadRecord, mode flags, recovery-target logic |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-wal-record`](../scenarios/add-new-wal-record.md)
- [`bump-catversion`](../scenarios/bump-catversion.md)

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/xlog-region-replay.md` — what each rmgr's
  `rm_redo` callback does at the per-page level.
- `knowledge/idioms/wal-record-construction.md` — the
  build-time emission this flow consumes.
- `knowledge/subsystems/access-transam.md` — the xlog
  subsystem.
- `knowledge/subsystems/replication.md` — the streaming /
  logical replication subsystem; standby mode integrates here.
- `.claude/skills/wal-and-xlog/SKILL.md` — skill on WAL
  format + recovery contracts.
- `knowledge/data-structures/xlogreaderstate.md` — the
  `XLogReaderState` used by `ReadRecord`.
- `source/src/backend/access/transam/xlogrecovery.c` —
  the implementation; `ReadRecord`, mode flags,
  recovery-target logic.
- `source/src/backend/access/transam/xlog.c` —
  `StartupXLOG` entry point.
