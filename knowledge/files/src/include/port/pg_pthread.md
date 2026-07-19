# `src/include/port/pg_pthread.h`

## Role

POSIX thread compatibility shim. Currently only one purpose: emulate
`pthread_barrier_t` on macOS, which lacks it `[from-comment]`
`source/src/include/port/pg_pthread.h:1-10`. Includes `<pthread.h>`
unconditionally (via IWYU-pragma export, so consumers don't need to).

The comment explicitly notes this is not in port.h "because that'd
require <pthread.h> to be included by every translation unit"
`source/src/include/port/pg_pthread.h:6-8` — i.e. pthread.h is a heavy
include and PG avoids it in the global path.

## Public API

Gated by `!HAVE_PTHREAD_BARRIER_WAIT`:

- `typedef struct pg_pthread_barrier pthread_barrier_t` — note the
  user-visible name aliases the POSIX name `[verified-by-code]`
  `source/src/include/port/pg_pthread.h:24-31`.
- `pthread_barrier_init(barrier, attr, count)`
- `pthread_barrier_wait(barrier)`
- `pthread_barrier_destroy(barrier)`
- `PTHREAD_BARRIER_SERIAL_THREAD` macro (-1) — return value indicating
  the single "elected" thread per barrier round.

When `HAVE_PTHREAD_BARRIER_WAIT` is defined (Linux, FreeBSD, etc.),
none of the above are declared — the system's `<pthread.h>` provides
everything.

## Invariants

1. **macOS-only-path activation.** `HAVE_PTHREAD_BARRIER_WAIT` is set
   by configure/meson based on `pthread_barrier_wait` symbol probe.
   macOS doesn't implement POSIX barriers; everywhere else does
   `[inferred]` (no probe code in this header).
2. **Single-bit phase.** `sense` is a `bool` — only one phase bit
   needed for the standard two-phase barrier algorithm
   `[from-comment]` `source/src/include/port/pg_pthread.h:26`.
3. **Implementation must use `mutex`+`cond` together.** Both fields
   present in the struct; the .c implementation in
   `src/port/pthread_barrier_wait.c` `[unverified]` (not in scope here).
4. **Backend uses threads sparingly.** Per-connection fork model is
   the dominant paradigm; pthread shows up mainly in:
   - `libpq` (client-side, threadsafe API)
   - `pg_basebackup` parallel workers
   - `bgworker_main_loop` dispatch in some contrib (`pg_prewarm`)
   - parallel query worker startup (which uses ProcSignal not pthread)

## Trust-boundary / Phase D surface

- **No threading discipline inside the backend.** This shim exists for
  frontend tools and contrib; the postmaster never spawns threads.
  An extension that uses pthread + the backend's memory contexts would
  immediately break (palloc isn't thread-safe). The header doesn't
  document that boundary. **Phase-D-doc-issue:** the role section
  should explicitly say "if you're using this in a backend, you must
  not allocate, ereport, or touch shared memory from non-main threads."
- **The macOS path is the only diverging code-path.** Bugs in the
  emulation would only show on macOS, and PG's macOS CI is decent but
  not the primary platform. Risk surface: small (3 functions, ~50
  LOC in the .c) but the failure mode (deadlock or wrong thread
  elected) is silent.

## Cross-refs

- `source/src/port/pthread_barrier_wait.c` — the .c implementation
  (out of this header's scope).
- `source/src/bin/pg_basebackup/parallel_*.c` — primary consumers.

## Issues / unresolved

- **ISSUE-doc**: no warning that pthread APIs are safe for frontend
  tools but not for backend palloc/ereport context. (severity: low,
  doc-only)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../subsystems/port.md)
