---
path: src/port/getopt_long.c
anchor_sha: e18b0cb7344
loc: 241
depth: read
---

# src/port/getopt_long.c

## Purpose

BSD-licensed implementation of `getopt_long()` for platforms lacking it
(most non-glibc Unices, Windows). Parses argc/argv with both single-letter
options (`-x`, `-fvalue`) and long options (`--option`, `--option=value`,
`--option value`). Unlike GNU `getopt_long`, this version uses argv
reordering as the strategy for permuting non-options to the end — the
"non-options at the end" promise is delivered by mutating argv (despite
the `const` qualifier in the prototype). `[verified-by-code]` `[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int getopt_long(int argc, char *const argv[], const char *optstring, const struct option *longopts, int *longindex)` | `getopt_long.c:60` | Returns next opt letter, or 0 if a long opt's `flag` was set, or `?`/`:` on error, or -1 at end |

(Reads/writes process globals `optind`, `optarg`, `optopt`, `opterr` defined
in `getopt.c`.)

## Internal landmarks

- Static state (`:64-67`) — `place` (current scan pointer within an arg),
  `nonopt_start` (index of first reordered non-option), `force_nonopt`
  (latched after `--`). Reset on -1 return so restart-with-optind=1 works.
  `[from-comment]`
- Restart-with-optind-1 contract (`:50-55`) — caller must reset `optind=1`
  before reusing on a new argv. This implementation does NOT use the
  optreset BSD extension. The internal reset in the -1 return path is
  what makes the contract holdable.
- Non-option permutation (`:96-108`) — when we hit something that doesn't
  start with `-` (or is just `-`, or follows a `--`), shift it to the end
  of argv (`for (i = optind; i < argc - 1; i++) args[i] = args[i+1]`) and
  decrement `nonopt_start` (or initialize it). Then `goto retry` and
  re-test the now-current optind. `[verified-by-code]`
- `--` end-of-options (`:112-118`) — advances optind past the `--` itself,
  sets `force_nonopt = true` so subsequent args don't even attempt option
  parsing.
- Long-option loop (`:120-196`) — for each entry in `longopts[]`, compares
  name length and bytes. Three has_arg cases (`no_argument`, `required_argument`,
  `optional_argument`) for handling `--opt=val` (val attached) vs
  `--opt val` (val in next argv). Missing-argument error path returns BADCH
  or BADARG depending on whether ostr starts with `':'` (silent mode).
- `longopts[i].flag` (`:180-186`) — if non-NULL, stores `val` into `*flag`
  and returns 0; else returns `val` directly. GNU-compatible behavior.
- Short-option arm (`:199-240`) — analogous to the BSD short-only getopt
  in `pg_getopt_ctx.c`.

## Invariants & gotchas

- **Mutates argv despite `char *const argv[]`.** This is the BSD pattern
  (also used by GNU when not in `+` mode). Callers can't assume argv is
  immutable; in practice PG only calls getopt_long once at process start
  on argv where the mutation doesn't matter. `[from-comment]`
- **Not reentrant.** Process-global state (`optind` etc.) plus static
  locals here. Reentrant short-option parsing lives in
  `pg_getopt_ctx.c`; there is no reentrant long-option API.
- **`longopts` is searched linearly per option.** Performance is fine for
  the dozens of options PG tools have, would matter at hundreds.
- **`namelen` comparison uses `strlen` + `strncmp`** (`:131-132`), so
  partial matches require the full name. GNU `getopt_long` allows
  unique-prefix abbreviation; this BSD port does NOT — `--ver` will not
  match `--version`. `[verified-by-code]`
- "XXX error?" comment at `:169` — a `no_argument` long option followed
  by `=value` is silently accepted with the `=value` part discarded. Not
  worth fixing, per the comment.

## Cross-refs

- `knowledge/files/src/port/getopt.c.md` — short-option-only sibling.
- `knowledge/files/src/port/pg_getopt_ctx.c.md` — reentrant short-option-only.
- `source/src/include/getopt_long.h` — `struct option` definition,
  `no_argument` / `required_argument` / `optional_argument` constants.
- `source/src/bin/*/main.c` — every PG CLI tool's argv parsing path.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
