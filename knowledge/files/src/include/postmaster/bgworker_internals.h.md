# bgworker_internals.h

- **Source:** `source/src/include/postmaster/bgworker_internals.h`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** skim

## What's here (postmaster-private bgworker state)

- `RegisteredBgWorker` — the in-memory record postmaster keeps per
  registered worker: copy of `BackgroundWorker`, slot pointer, crash time,
  terminate flag, dlist link.
- `BackgroundWorkerList` — the postmaster's private dlist of all
  registrations.
- Internal flags / state enum for `BackgroundWorkerSlot::pm_status`.
- Prototypes consumed only by `postmaster.c` and `bgworker.c`:
  `BackgroundWorkerStateChange`, `ForgetBackgroundWorker`,
  `ReportBackgroundWorkerPID`, `ReportBackgroundWorkerExit`,
  `BackgroundWorkerStopNotifications`, `ForgetUnstartedBackgroundWorkers`,
  `ResetBackgroundWorkerCrashTimes`, `bgworker_should_start_now`.

## Why split from `bgworker.h`

Extensions only need the public registration API. Internal state must not
be touched outside postmaster/bgworker.c — the slot handshake is lockless
and relies on a specific ownership protocol.
