# interrupt.h

- **Source:** `source/src/include/postmaster/interrupt.h`
- **Depth:** read

## Symbols

- Globals: `ConfigReloadPending`, `ShutdownRequestPending` (sig_atomic_t).
- `ProcessMainLoopInterrupts(void)` — drain barriers, reload, exit, mem-ctx dump.
- `SignalHandlerForConfigReload(SIGNAL_ARGS)` — generic SIGHUP handler.
- `SignalHandlerForCrashExit(SIGNAL_ARGS)` — generic SIGQUIT → `_exit(2)`.
- `SignalHandlerForShutdownRequest(SIGNAL_ARGS)` — generic SIGTERM (or
  SIGUSR2 for checkpointer/parallel-apply).

Consumers: all aux processes and many bgworkers use these as their signal
handlers + main-loop drain. See `interrupt.c.md` for the rationale.
