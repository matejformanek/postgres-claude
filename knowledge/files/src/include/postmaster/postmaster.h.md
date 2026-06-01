# postmaster.h

- **Source:** `source/src/include/postmaster/postmaster.h`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## What's here

Public prototypes for `postmaster.c`. Notable symbols:

- `PostmasterMain(int argc, char *argv[])`.
- Globals: `PostmasterPid`, `PostmasterContext`, `IsPostmasterEnvironment`,
  `Shutdown`, `FatalError`, `AbortStartTime`, `connsAllowed`, etc.
- Listen socket bookkeeping: `ListenSockets[]`, `NumListenSockets`.
- `PostmasterIsAlive()` (also via `pmsignal.h` for the actual implementation).
- `PostmasterMarkPIDForWorkerNotify`, `PostmasterChildName`,
  `postmaster_child_launch` (the cross-file fork entry).
- `BTYPE_*` / process-kind helpers.

## Header for

`postmaster.c`, `launch_backend.c`, `pmchild.c`, plus consumers in
`tcop/`, `replication/`, `storage/ipc/pmsignal.c`.
