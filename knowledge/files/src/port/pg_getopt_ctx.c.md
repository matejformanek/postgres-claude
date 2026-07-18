---
path: src/port/pg_getopt_ctx.c
anchor_sha: e18b0cb7344
loc: 136
depth: read
---

# src/port/pg_getopt_ctx.c

## Purpose

Re-entrant (thread-safe) implementation of POSIX `getopt(3)`. Original
BSD `getopt` keeps state in process-global `optind`/`optarg`/`optopt`/`opterr`
and an internal `place` pointer, which makes it unusable from multiple
threads or in nested option-parsing loops. This file packages all state
into a caller-owned `pg_getopt_ctx` struct; the legacy `getopt()` in
`getopt.c` is now a thin wrapper that calls this with a process-static
ctx. `[verified-by-code]` `[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `void pg_getopt_start(pg_getopt_ctx *ctx, int nargc, char *const *nargv, const char *ostr)` | `pg_getopt_ctx.c:54` | Initialize a parsing context |
| `int pg_getopt_next(pg_getopt_ctx *ctx)` | `:72` | Returns next option letter, `?` (BADCH), `:` (BADARG), or -1 at end |

## Internal landmarks

- `pg_getopt_start` (`:54`) — sets `optind = 1`, clears the rest. Comment
  notes `opterr` defaults to 1 and the caller can clear it after this call.
  `[from-comment]`
- `pg_getopt_next` "update scanning pointer" branch (`:76-89`) — handles
  end-of-argv (returns -1) and the `--` end-of-options sentinel
  (returns -1, advances `optind`).
- Unknown-option branch (`:90-107`) — returns BADCH (`'?'`), prints
  "illegal option" only if `opterr != 0` and the ostr doesn't start with
  `':'` (POSIX silent-mode convention).
- Missing-argument branch (`:114-128`) — returns BADARG (`':'`) when ostr
  is silent-mode; BADCH plus "option requires an argument" otherwise.
- Arg-attached vs arg-detached (`:115-131`) — `*ctx->place` means the arg
  was glued (`-fFILE`), else the next argv element is consumed (`-f FILE`).

## Invariants & gotchas

- **No support for `--` long options or argv reordering.** This is the BSD
  short-option-only variant; long-option support lives in `getopt_long.c`,
  which is a separate non-reentrant tree. Tools that need both run them
  in series: short opts via `pg_getopt_next`, then long opts via
  `getopt_long`. `[verified-by-code]`
- **Does not modify argv.** Unlike GNU `getopt_long`, no permutation; the
  first non-option terminates option parsing.
- **Reentrancy is per-ctx, not per-thread.** The same ctx must not be
  driven by two threads concurrently, but each thread holding its own
  ctx is safe.
- The wrapping `getopt()` in `getopt.c` uses a process-static ctx, so
  legacy callers are NOT thread-safe — but no PG callsite cares because
  argv parsing happens once at startup.

## Cross-refs

- `knowledge/files/src/port/getopt.c.md` — legacy wrapper around this.
- `knowledge/files/src/port/getopt_long.c.md` — long-option BSD implementation.
- `source/src/include/port/pg_getopt_ctx.h` — `pg_getopt_ctx` struct definition.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
