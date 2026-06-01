# async.h

- **Source path:** `source/src/include/commands/async.h`
- **Lines:** 49
- **Last verified commit:** `ef6a95c7c64`

Prototypes plus GUC externs for NOTIFY/LISTEN/UNLISTEN. Exports `Trace_notify`, `max_notify_queue_pages`, `notifyInterruptPending` (volatile sig_atomic_t set from signal handler, polled in `CHECK_FOR_INTERRUPTS`). `NotifyMyFrontEnd` is the protocol-emit helper called from `ProcessIncomingNotify`.
