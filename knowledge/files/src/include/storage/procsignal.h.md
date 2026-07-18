# `storage/procsignal.h`

- **Source:** `source/src/include/storage/procsignal.h` (90 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** full-read

Cross-backend signal API. See `procsignal.c.md`.

## ProcSignalReason (the multiplex bits)

```
PROCSIG_CATCHUP_INTERRUPT          /* sinval catchup */
PROCSIG_NOTIFY_INTERRUPT           /* listen/notify */
PROCSIG_PARALLEL_MESSAGE           /* from parallel co-worker */
PROCSIG_WALSND_INIT_STOPPING       /* walsender shutdown prep */
PROCSIG_BARRIER                    /* global barrier event */
PROCSIG_LOG_MEMORY_CONTEXT
PROCSIG_PARALLEL_APPLY_MESSAGE
PROCSIG_SLOTSYNC_MESSAGE
PROCSIG_REPACK_MESSAGE
PROCSIG_RECOVERY_CONFLICT          /* reason in PGPROC->pendingRecoveryConflicts */
```

`NUM_PROCSIGNALS = PROCSIG_RECOVERY_CONFLICT + 1 = 10`. Bitmap fits in
a single `uint32` (with room to spare).

> "It's important that all the signals be defined so that no harm is
> done if a process mistakenly receives one." `:27-29`.

## ProcSignalBarrierType (for `EmitProcSignalBarrier`)

```
PROCSIGNAL_BARRIER_SMGRRELEASE                  /* close all smgr files */
PROCSIGNAL_BARRIER_UPDATE_XLOG_LOGICAL_INFO
PROCSIGNAL_BARRIER_CHECKSUM_OFF
PROCSIGNAL_BARRIER_CHECKSUM_INPROGRESS_ON
PROCSIGNAL_BARRIER_CHECKSUM_INPROGRESS_OFF
PROCSIGNAL_BARRIER_CHECKSUM_ON
```

Each barrier type has a `ProcessBarrier*` function in core code that
the absorbing backend runs.

## `MAX_CANCEL_KEY_LENGTH = 32`

Generated cancel keys are 32 bytes. The wire protocol allows longer or
shorter — both server (when accepting) and client mustn't hardcode
this length.

## API

- `ProcSignalInit(cancel_key, len)` — per-backend slot acquisition.
- `SendProcSignal(pid, reason, procNumber)` — `procNumber` optional
  for speed.
- `SendCancelRequest(pid, key, keylen)` — cancel-key-authenticated.
- `EmitProcSignalBarrier(type)` → generation; `WaitForProcSignalBarrier(gen)`;
  `ProcessProcSignalBarrier()` — the barrier dance.
- `procsignal_sigusr1_handler` — the actual signal handler installed
  by `BackgroundWorkerInitializeConnection` / postmaster fork path.

## `RECOVERY_CONFLICT` is single-bit

A backend can have *multiple* recovery conflict reasons pending. The
single bit `PROCSIG_RECOVERY_CONFLICT` is signaled; the **set of
reasons** is delivered separately via `PGPROC->pendingRecoveryConflicts`
(an array, not transmitted in the signal flags). `[from-comment] :41-43`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/storage-ipc.md](../../../../subsystems/storage-ipc.md)
- [subsystems/storage-lmgr.md](../../../../subsystems/storage-lmgr.md)
