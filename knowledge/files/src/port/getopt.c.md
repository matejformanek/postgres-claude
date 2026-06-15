---
path: src/port/getopt.c
anchor_sha: e18b0cb7344
loc: 88
depth: read
---

# src/port/getopt.c

## Purpose

Legacy non-reentrant `getopt(3)` API exposed on top of the reentrant
`pg_getopt_start`/`pg_getopt_next` machinery in `pg_getopt_ctx.c`. Exists
because callers (PG CLI tools, third-party libraries) expect the POSIX
`getopt()` symbol with `optind`/`optarg`/`optopt`/`opterr` globals. This
file defines those globals (only when libc doesn't already provide them,
gated by `HAVE_INT_OPTERR`) and wraps a process-static `pg_getopt_ctx`.
`[verified-by-code]` `[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int getopt(int nargc, char *const *nargv, const char *ostr)` | `getopt.c:67` | Standard POSIX getopt; not thread-safe |
| `int opterr` / `int optind` / `int optopt` / `char *optarg` | `:46-49` | Defined here only if `!HAVE_INT_OPTERR` |

## Internal landmarks

- `HAVE_INT_OPTERR` gate (`:44-51`) — on OpenBSD and some Solaris,
  `opterr`/`optind`/`optopt`/`optarg` live in core libc. The configure
  probe (testing `opterr`) decides whether we define them here or rely
  on libc's. `[from-comment]`
- Process-static ctx (`:69-70`) — one `pg_getopt_ctx` shared by all
  `getopt()` callers in the process. `active = false` means
  "next call should re-initialize via `pg_getopt_start`".
- Init-on-first-call (`:73-78`) — calls `pg_getopt_start` and copies
  the caller's current `opterr` into the ctx (so suppression set before
  the first call is honored).
- Per-call sync (`:80-86`) — copy ctx state OUT to globals after each
  call (so caller-visible `optind` etc. update normally). Reset
  `active = false` when reaching -1, allowing restart with `optind=1`.

## Invariants & gotchas

- **NOT thread-safe.** Process-global state. For new code use
  `pg_getopt_start`/`pg_getopt_next` directly. Existing PG bins use
  this single-threaded at startup, so safe in practice.
- **Restart contract: reset `optind` to 1 before second use.** Mirrors
  the GNU/BSD getopt contract. The internal `active = false` flag at
  -1 return is what enables this; setting `optind = 1` triggers re-init.
  `[from-comment]`
- **`opterr` is bidirectional through the ctx.** Caller can set `opterr =
  0` to silence error messages; the value is copied INTO the ctx on init,
  then OUT after each call. So mid-parse changes to opterr take effect
  on the next call (after copy-in/copy-out cycle). `[verified-by-code]`
- The `optopt` global gets the bad option letter on `?`/`:` returns —
  use it to distinguish "unknown option" vs "missing argument" when ostr
  begins with `:` (silent mode).

## Cross-refs

- `knowledge/files/src/port/pg_getopt_ctx.c.md` — the reentrant
  implementation this wraps.
- `knowledge/files/src/port/getopt_long.c.md` — long-option variant
  (separate non-reentrant tree).
- `source/src/include/pg_getopt.h` — public prototype.
