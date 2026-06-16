# pqsignal.h

- **Source path:** `source/src/include/libpq/pqsignal.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Backend signal(2) support (see also src/port/pqsignal.c)" — declares the
canonical signal masks every backend uses (`UnBlockSig`, `BlockSig`,
`StartupBlockSig`) and, under WIN32, defines a `sigaction` emulation layer
[from-comment].

## Public API surface

- Globals: `UnBlockSig`, `BlockSig`, `StartupBlockSig` (all `sigset_t`).
- `void pqinitmask(void)` — populate the above masks at backend start.
- WIN32 shims: `sigset_t` (typedef'd to `int`), `struct sigaction`,
  `pqsigprocmask`, `pqsigaction`, plus `SIG_BLOCK`/`SIG_UNBLOCK`/`SIG_SETMASK`
  constants and macro redirects (`sigprocmask` → `pqsigprocmask`,
  `sigaction` → `pqsigaction`, `sigemptyset`/`sigfillset`/`sigaddset`/
  `sigdelset` implemented inline as bitmask ops on the `int`).

## Internal landmarks

- WIN32 `sigaction.sa_mask` is the bitmask `int`; the comment notes
  "sa_sigaction not yet implemented" [from-comment].
- `sigemptyset(set)` etc. assume `set` is a single-word `sigset_t` — fine
  on Windows because the typedef makes it `int`; on POSIX the real header
  takes over.

## Cross-refs

- Related: `src/port/pqsignal.c`,
  `src/backend/utils/init/miscinit.c` (`pqinitmask` callers).

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-stale-todo: sa_sigaction not yet implemented]** `pqsignal.h:28`
  — long-standing limitation of the WIN32 shim; any code that wants
  `SA_SIGINFO`-style info would fail silently on Windows. Severity: low.

## Tally

`[verified-by-code]=3 [from-comment]=2`
