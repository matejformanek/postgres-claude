# logging.c

The frontend `pg_log_*` family (`pg_log_error`, `pg_log_warning`,
`pg_log_info`, `pg_log_debug`, plus the `_detail`/`_hint`/`_fatal`
variants from `logging.h`). Used by every binary in `src/bin/` and
by libpq's command-line helpers, but **not** by the backend.
(`source/src/common/logging.c:1-13`, `#ifndef FRONTEND #error`)
[verified-by-code]

## Purpose

A small, GNU-style "`progname: error: …`" logger with optional
detail/hint sub-lines and PG_COLOR/PG_COLORS-driven ANSI SGR
escapes, all going to stderr. Designed to mirror backend
`ereport(ERROR, errmsg(...) errdetail(...) errhint(...))` style so
human-readable messages match between server logs and client tools.

## Key functions

- `pg_logging_init(argv0)` — call this once at program start.
  Captures `progname`, sets default level to `PG_LOG_INFO`, decides
  whether to colorize (`PG_COLOR=auto/always` + `isatty(stderr)` +
  Windows VT-100 probe). Parses `PG_COLORS` as `key=value:…` for
  per-class SGR overrides. `setvbuf(stderr, _IONBF)` forces stderr
  unbuffered. (`source/src/common/logging.c:84-162`)
- `pg_logging_config(flags)` — currently only `PG_LOG_FLAG_TERSE`
  (used by psql to match regression test output).
  (`source/src/common/logging.c:167-171`)
- `pg_logging_set_level`, `pg_logging_increase_verbosity` —
  monotonically decrease `__pg_log_level`. The enum is ordered so
  smaller = noisier. (`source/src/common/logging.c:177-195`)
- `pg_logging_set_pre_callback`, `pg_logging_set_locus_callback`,
  `pg_logging_set_logfile`, `pg_logging_unset_logfile` — hooks for
  e.g. ecpg to add `file:line:` prefixes and to tee to a logfile.
  (`source/src/common/logging.c:197-219`)
- `pg_log_generic(level, part, fmt, …)` /
  `pg_log_generic_v(level, part, fmt, ap)` — the workhorse.
  Suppresses below threshold, flushes stdout, invokes pre/locus
  callbacks, writes the colored prefix (`progname:`/`error:`/etc.),
  `vsnprintf`s into a `pg_malloc_extended(MCXT_ALLOC_NO_OOM)`
  buffer, strips trailing newline (so libpq `PQerrorMessage`'s
  embedded newline doesn't double up), and writes one final line
  plus optional logfile. On malloc failure falls back to
  `vfprintf(stderr, fmt, ap)`.
  (`source/src/common/logging.c:221-364`)

## State / globals

- `__pg_log_level` (extern enum) — global threshold.
  (`logging.c:21`)
- `progname` (static) — captured at init.
- `log_flags` (static int) — bitfield with `PG_LOG_FLAG_TERSE`.
- `log_pre_callback`, `log_locus_callback`, `log_logfile` —
  optional hooks.
- `sgr_error`, `sgr_warning`, `sgr_note`, `sgr_locus` — color
  strings (NULL = no color).

All single-threaded by assumption; no synchronization.

## Phase D notes

[ISSUE-secret-scrub: frontend log messages can carry secrets
verbatim through PQerrorMessage (maybe)] `pg_log_error("connection
failed: %s", PQerrorMessage(conn))` is the canonical pattern
across `src/bin/*`. libpq builds `PQerrorMessage` from a mix of
server-supplied text and locally formatted parse errors; if a
client passed a malformed conninfo like
`"host=h password=secret garbage"`, the parser's `"missing = in
…"` error has historically embedded the offending substring.
`pg_log_generic_v` then writes it to stderr **and** to
`log_logfile` (lines 357-361) without redaction. No
`explicit_bzero` of the vsnprintf'd `buf` either (line 363:
`free(buf)`). This compounds the sprompt.c finding.

[ISSUE-info-disclosure: `assert(fmt[strlen(fmt)-1] != '\n')`
ensures callers omit the trailing newline (line 246) — debug-only
guard; release builds silently double-newline (low)]

[ISSUE-undocumented-invariant: `pg_logging_init` writes to
`getenv("PG_COLORS")` parsing without bounds check beyond
`strdup`/`strsep` (low)] A pathological PG_COLORS value can leak
heap allocations (`sgr_error = strdup(value)` is never freed when
reassigned — but it's a one-shot at init).

[ISSUE-secret-scrub: pg_malloc_extended buffer in pg_log_generic_v
is `free()`'d, not zeroed (line 363) (maybe)] Same root cause as
fe_memutils.c — no helper for secret-bearing temporary buffers.

## Potential issues

- The "memory trouble" fallback at lines 343-348 calls
  `vfprintf(stderr, fmt, ap)` — without the
  `progname:`/`error:` prefix. Quietly noisy in OOM scenarios.
- Thread safety: callers from `src/bin/pgbench` use threads;
  concurrent calls into `pg_log_generic` will interleave the
  multi-`fprintf` prefix sequence. There's no lock.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->
