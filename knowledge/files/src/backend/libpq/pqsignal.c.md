---
path: src/backend/libpq/pqsignal.c
anchor_sha: 4b0bf0788b0
loc: 99
depth: shallow
---

# pqsignal.c

- **Source path:** `source/src/backend/libpq/pqsignal.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 99

## Purpose

Backend-only initializer for the three global signal masks used everywhere
in the postmaster and its children. The file pairs with `src/port/pqsignal.c`
(the cross-platform `pqsignal()` wrapper for `sigaction()`); this one only
defines the masks themselves. [from-comment, pqsignal.c:1-13]

## Public API surface

| Line | Symbol | Semantics |
|---|---|---|
| 22-24 | `BlockSig`, `UnBlockSig`, `StartupBlockSig` (globals) | `sigset_t` masks shared by all backend code via `<libpq/pqsignal.h>` |
| 41 | `pqinitmask(void)` | Populate the three globals; called once during postmaster startup before any signal handlers are installed |

## Internal landmarks

- `UnBlockSig` starts empty (`sigemptyset`) — block nothing. [verified-by-code, pqsignal.c:43]
- `BlockSig` and `StartupBlockSig` start full (`sigfillset`) and then have
  the un-blockable / unmaskable signals removed: SIGTRAP, SIGABRT, SIGILL,
  SIGFPE, SIGSEGV, SIGBUS, SIGSYS, SIGCONT (synchronous fatal + SIGCONT for
  resume). [verified-by-code, pqsignal.c:48-87]
- `StartupBlockSig` additionally drops SIGQUIT, SIGTERM, SIGALRM — so that
  during startup-packet collection a misbehaving client can still be
  cancelled / killed. [from-comment, pqsignal.c:33-35] [verified-by-code, pqsignal.c:91-98]
- A side-channel comment notes `InitializeWaitEventSupport()` later mutates
  `UnBlockSig`. [from-comment, pqsignal.c:45]

## Invariants & gotchas

- The synchronous-fatal signals (SEGV/BUS/ILL/FPE/ABRT/TRAP/SYS) MUST NOT be
  blocked — if you block them you turn a deterministic crash into a hang or
  silent corruption. [inferred from convention]
- The set of "never blockable" signals is hardcoded; if a new platform
  introduces a synchronous fatal signal it must be added here. The `#ifdef`
  wall (lines 56-87) is defensive against platforms missing one of these
  symbols.
- Caller is responsible for using `sigprocmask(SIG_SETMASK, &BlockSig, …)`
  at the right moments; this file does no installing of its own.

## Cross-refs

- Header: `source/src/include/libpq/pqsignal.h`
- Sibling: `source/src/port/pqsignal.c` (defines `pqsignal()` wrapper)
- Used by: `postmaster.c`, every backend's signal-handler-install boilerplate

## Potential issues

(none surfaced — file is mechanical mask-init)

## Tally

`[verified-by-code]=4 [from-comment]=2 [inferred]=1`
