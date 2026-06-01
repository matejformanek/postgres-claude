# `storage/ipc/pmsignal.c`

- **Source:** `source/src/backend/storage/ipc/pmsignal.c` (431 lines)
- **Header:** `source/src/include/storage/pmsignal.h`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

(Note: replaces the older sketch doc at this path that was written
before this corpus session.)

## Purpose

**Children → postmaster** signaling, plus the per-child slot used by
postmaster to detect "did this child exit cleanly?". Distinct from
`procsignal.c` (backend ↔ backend) and `latch.c` (generic wakeup).

The postmaster invariant: **it holds no lwlocks and never blocks on
shared memory.** [from-comment] `postmaster.c:14-23`. So children must
communicate via lock-free atomic flags. `pmsignal.c` is the
infrastructure for that.

## Shared state

```c
struct PMSignalData {
    sig_atomic_t PMSignalFlags[NUM_PMSIGNALS];      /* per-reason */
    QuitSignalReason sigquit_reason;                 /* PM→children */
    int          num_child_flags;
    sig_atomic_t PMChildFlags[FLEXIBLE_ARRAY_MEMBER];/* per-slot state */
};
```

Per-child slot state machine:

```
UNUSED  ─assign→  ASSIGNED  ─attach_shmem→  ACTIVE  ─walsender_switch→  WALSENDER
                                                ↘ exit/cleanup ↘ UNUSED
```

If a child is found dead while in `ACTIVE` (not `ASSIGNED` or
`UNUSED`), postmaster knows the child died after attaching to
shared memory — must do a crash-restart. `[from-comment] :47-60`.

## Reasons (`PMSIGNAL_*` in `pmsignal.h`)

`PMSIGNAL_RECOVERY_STARTED`, `PMSIGNAL_BEGIN_HOT_STANDBY`,
`PMSIGNAL_WAKEN_ARCHIVER`, `PMSIGNAL_ROTATE_LOGFILE`,
`PMSIGNAL_START_AUTOVAC_LAUNCHER`, `PMSIGNAL_START_AUTOVAC_WORKER`,
`PMSIGNAL_BACKGROUND_WORKER_CHANGE`,
`PMSIGNAL_START_WALRECEIVER`, `PMSIGNAL_ADVANCE_STATE_MACHINE`, etc.

These are flags, not queues — multiple children setting the same flag
in the same tick collapse to one postmaster observation. That's
fine for every current reason.

## API

- `SendPostmasterSignal(reason)` — child sets the flag and `kill(PostmasterPid, SIGUSR1)`.
- `CheckPostmasterSignal(reason)` — postmaster polls and clears.
- `PostmasterIsAlive()` — children's dead-man-switch check. Returns
  false once the postmaster process has died.
- `AssignPostmasterChildSlot(BackendType)` / `ReleasePostmasterChildSlot` —
  shared-mem mirror of the per-type pool logic in `pmchild.c`.
- `MarkPostmasterChildActive` / `MarkPostmasterChildInactive` /
  `MarkPostmasterChildWalSender` — state transitions.
- `MarkPostmasterChildAssigned` — postmaster side when forking.

## `PostmasterIsAlive` — the dead-man switch

`postmaster.c` keeps a self-pipe `pm_alive` open; reading from it
returns 0 (EOF) iff the postmaster process is gone (because its end
of the pipe was closed). Children poll this via `PostmasterIsAlive()`.
This is the mechanism behind `WL_POSTMASTER_DEATH` / `WL_EXIT_ON_PM_DEATH`.

## `sigquit_reason`

Postmaster broadcasts SIGQUIT for either "crash restart" or "immediate
shutdown" (`smart`/`fast` use SIGTERM). The reason is stored here so
`quickdie` handlers can give a matching client error
("the database system is in recovery mode" vs "the database is being
shut down"). [from-comment] `:62-65`.

## Cross-references

- `postmaster.c::ServerLoop` — calls `CheckPostmasterSignal` on each
  iteration.
- `postmaster/pmchild.c` — per-`BackendType` pool / `BackendStartup`.
- `tcop/postgres.c::quickdie` — reads `sigquit_reason`.

## Open questions

- Whether `MarkPostmasterChildActive` is called *before* the child
  has actually attached to shmem (in which case a crash between
  attach and Mark would still look like UNUSED to postmaster, and
  no crash-restart would happen). Reading the code path:
  `launch_backend.c` invokes the child main_fn after the attach
  in non-EXEC_BACKEND mode — `[unverified]` for the precise ordering.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/storage-ipc.md](../../../../../subsystems/storage-ipc.md)
