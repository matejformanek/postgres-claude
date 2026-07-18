# `storage/pmsignal.h`

- **Source:** `source/src/include/storage/pmsignal.h` (109 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** full-read

Children → postmaster signaling. See `pmsignal.c.md`.

## PMSignalReason

```
PMSIGNAL_RECOVERY_STARTED
PMSIGNAL_RECOVERY_CONSISTENT
PMSIGNAL_BEGIN_HOT_STANDBY
PMSIGNAL_ROTATE_LOGFILE
PMSIGNAL_START_AUTOVAC_LAUNCHER
PMSIGNAL_START_AUTOVAC_WORKER
PMSIGNAL_IO_WORKER_GROW
PMSIGNAL_BACKGROUND_WORKER_CHANGE
PMSIGNAL_START_WALRECEIVER
PMSIGNAL_ADVANCE_STATE_MACHINE
PMSIGNAL_XLOG_IS_SHUTDOWN
```

`NUM_PMSIGNALS = 11`. Each reason is a `sig_atomic_t` flag in shared
memory; postmaster polls them in `ServerLoop`.

## QuitSignalReason (postmaster → children)

```
PMQUIT_NOT_SENT = 0
PMQUIT_FOR_CRASH    /* some other backend crashed; restart */
PMQUIT_FOR_STOP     /* immediate shutdown */
```

Read by `tcop/postgres.c::quickdie` so the error message reflects the
real reason.

## Fast `PostmasterIsAlive`

If the OS supports parent-death signals (`prctl PR_SET_PDEATHSIG` on
Linux; `procctl PROC_PDEATHSIG_CTL` on FreeBSD), `pmsignal.c` installs
a handler that sets `postmaster_possibly_dead`. The static inline
`PostmasterIsAlive()` first checks that flag — cheap fast path —
before falling back to `PostmasterIsAliveInternal()` (which actually
syscalls to read the dead-man pipe).

```c
static inline bool PostmasterIsAlive(void) {
    if (likely(!postmaster_possibly_dead)) return true;
    return PostmasterIsAliveInternal();
}
```

This is the call backed by `WL_POSTMASTER_DEATH` / `WL_EXIT_ON_PM_DEATH`.

## API

- `SendPostmasterSignal(reason)` — children set the flag + SIGUSR1.
- `CheckPostmasterSignal(reason)` — postmaster polls and clears.
- `SetQuitSignalReason` / `GetQuitSignalReason` — for the children-side
  SIGQUIT-reason readback.
- `MarkPostmasterChildSlotAssigned`, `MarkPostmasterChildSlotUnassigned`,
  `RegisterPostmasterChildActive`, `MarkPostmasterChildWalSender`,
  `IsPostmasterChildWalSender` — slot state-machine bookkeeping.
- `PostmasterDeathSignalInit` — install the PR_SET_PDEATHSIG handler.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/storage-ipc.md](../../../../subsystems/storage-ipc.md)
