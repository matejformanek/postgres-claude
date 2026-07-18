# `src/include/port/pg_getopt_ctx.h`

## Role

Re-entrant version of standard `getopt(3)`. POSIX `getopt` uses
**global state** (`optarg`, `optind`, `optopt`, `optreset` etc.),
which prevents nested or concurrent option parses. `pg_getopt_ctx`
moves all state into a caller-supplied struct.

Header is recent — 2026 copyright `[verified-by-code]`
`source/src/include/port/pg_getopt_ctx.h:4`.

## Public API

`[verified-by-code]` `source/src/include/port/pg_getopt_ctx.h:11-37`:

- `typedef struct { int nargc; char *const *nargv; const char *ostr;
   int opterr; char *optarg; int optind; int optopt; char *place; }
   pg_getopt_ctx`
- `void pg_getopt_start(ctx, nargc, nargv, ostr)` — initialize.
- `int pg_getopt_next(ctx)` — return next option char, or -1 at end,
  or `'?'` on unknown / missing-arg.

Fields equivalent to standard getopt globals:
- `opterr` — caller-set; controls whether `pg_getopt_next` prints
  error messages.
- `optarg`, `optind`, `optopt` — read by caller after each
  `pg_getopt_next` to consume the option's argument / index / char.
- `place` — internal; tracks position within a clustered short-option
  group (`-abc` style).

## Invariants

1. **All state is per-ctx.** Multiple ctxs can be parsed concurrently
   or recursively `[inferred from struct shape]`
   `source/src/include/port/pg_getopt_ctx.h:11-34`.
2. **`opterr` is mutable between start and first next call.** Comment
   `source/src/include/port/pg_getopt_ctx.h:19-22`.
3. **No `optreset` equivalent** — re-parsing the same argv requires
   a fresh `pg_getopt_start` call.

## Notable internals

The .c implementation lives in `src/port/pg_getopt_ctx.c`
`[unverified path]`; this header is just the declarations.

`getopt(3)` is famously non-reentrant; PG already had `getopt_long`
forks for Windows and a `pg_getopt` wrapper. The `_ctx` variant is
the cleanest answer for tools that want to parse argv inside a
library function without clobbering caller state — e.g. test
harnesses, REPL-style frontends, certain bgworker arg parsing.

## Trust-boundary / Phase D surface

- **Used in frontends, not backends.** The backend itself doesn't
  invoke getopt; it parses command-line in `postmaster.c` via
  custom code. The reentrant version exists primarily for libpq
  consumers and pg_dump-style tools that need to parse subcommands.
- **No buffer-overrun surface** — `nargv` is a `char *const *`, the
  caller owns the strings. `place` is an internal pointer into one
  of those strings; lifetime is tied to argv's.
- **No env-var trust surface either** — unlike `getenv("POSIXLY_CORRECT")`
  which standard glibc getopt honors, the PG version doesn't (per
  the .c, out of scope here `[inferred]`).

## Cross-refs

- `source/src/port/getopt.c`, `source/src/port/pg_getopt_ctx.c`
  `[unverified path]` — implementations.
- `source/src/include/getopt_long.h` — long-option variant.

## Issues / unresolved

- (none; small, internal-use header)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../subsystems/port.md)
