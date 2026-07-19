---
path: src/port/pgstrsignal.c
anchor_sha: e18b0cb7344
loc: 61
depth: read
---

# src/port/pgstrsignal.c

## Purpose

Provides `pg_strsignal(int signum)` — a portable wrapper around POSIX
`strsignal(3)` that translates a Unix signal number into a human-readable
string (e.g. `"Terminated"` for `SIGTERM`). On modern POSIX-compliant
platforms it just delegates to libc `strsignal()`; elsewhere it returns a
constant `"(signal names not available on this platform)"`. Used in backend
log lines (`postmaster.c`, child-exit handling) and in `pg_ctl` output where
a process died on a signal. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `const char *pg_strsignal(int signum)` | `pgstrsignal.c:39` | Always non-NULL; result may share libc storage and is not guaranteed valid across further `strsignal()` calls (see comment) |

## Internal landmarks

- `HAVE_STRSIGNAL` arm (`pgstrsignal.c:46-49`) — calls libc `strsignal()` and
  defends against a NULL return from buggy libc by substituting
  `"unrecognized signal"`. `[from-comment]`
- Fallback arm (`:50-58`) — constant string. A historical `sys_siglist[]`
  branch was removed because every platform with that array also ships
  `strsignal()`. `[from-comment]`

## Invariants & gotchas

- **Always non-NULL.** Callers may safely `errmsg("died with signal %d: %s",
  sig, pg_strsignal(sig))` without a NULL check — this is the entire
  reason the wrapper exists. `[from-comment]`
- The returned pointer can become stale after another `strsignal()` call; in
  practice PG callers use it immediately in an `ereport`/`fprintf` and never
  cache it.
- Project style (per the file header comment) is to print the numeric signal
  along with the string, so the fallback's generic string is acceptable.
  `[from-comment]`

## Cross-refs

- `source/src/backend/postmaster/postmaster.c` — child-exit reporting via
  `WTERMSIG` is a primary caller.
- `knowledge/files/src/port/kill.c.md` — Win32 `pgkill` shim sibling.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
