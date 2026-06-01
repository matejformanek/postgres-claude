# walwriter.c

- **Source:** `source/src/backend/postmaster/walwriter.c` (270 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (entire file)

## Purpose

Background process (since PG 8.3) that periodically flushes WAL pages so
regular backends rarely block doing it themselves, and guarantees that
**async-commit transactions reach disk within ≤ 3 × `wal_writer_delay`**.
[from-comment] `:5-11`

## Lifecycle

- Singleton, postmaster-spawned, `main_fn = WalWriterMain` (declared in
  `proctypelist.h`).
- Started by postmaster as soon as the startup subprocess finishes.
  [from-comment] `:23-24`
- Normal exit: SIGTERM. Emergency: SIGQUIT.
- Unexpected exit ⇒ postmaster treats as backend crash. [from-comment] `:29-31`
- **Not essential** — backends fall back to writing WAL themselves if
  walwriter falls behind. [from-comment] `:12-15`

## Why nothing else gets loaded onto it

The cycle is the SLA for async-commit durability; piling on extra work would
stretch that bound. The comment explicitly warns against it.
[from-comment] `:17-21`

## Main loop (sketch — same pattern as bgwriter)

1. `AuxiliaryProcessMainCommon`.
2. Install signal handlers (SIGHUP/SIGTERM/SIGUSR1).
3. sigsetjmp error recovery.
4. Loop: `XLogBackgroundFlush()`, sleep `wal_writer_delay` via WaitLatch.

## Interactions

- Calls into `xlog.c::XLogBackgroundFlush`.
- Header: `postmaster/walwriter.h`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
