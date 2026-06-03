# logging.h

Public interface to the frontend `pg_log_*` family implemented in
`src/common/logging.c`. (`source/src/include/common/logging.h`)
[verified-by-code]

## Purpose

Lets every binary in `src/bin/` plus libpq's command-line helpers
emit GNU-style `progname: error: …` messages with consistent
detail/hint structure, optional ANSI colorization, and a single
global threshold (`__pg_log_level`).

## Key declarations

- `enum pg_log_level { PG_LOG_NOTSET, PG_LOG_DEBUG, PG_LOG_INFO,
  PG_LOG_WARNING, PG_LOG_ERROR, PG_LOG_OFF }` — ordered so
  *smaller = noisier*. `NOTSET` and `OFF` are sentinels; not for
  actual messages. (`logging.h:16-49`)
- `extern enum pg_log_level __pg_log_level` — global threshold.
- `enum pg_log_part { PG_LOG_PRIMARY, PG_LOG_DETAIL, PG_LOG_HINT }`
  — mirrors backend `errmsg/errdetail/errhint`. Multi-part messages
  must be emitted in this order. (`logging.h:61-80`)
- `PG_LOG_FLAG_TERSE = 1` — psql uses this to match regression
  test output (no `progname:` prefix). (`logging.h:86`)
- Setup: `pg_logging_init(argv0)`, `pg_logging_config(flags)`,
  `pg_logging_set_level`, `pg_logging_increase_verbosity`,
  `pg_logging_set_pre_callback`, `pg_logging_set_locus_callback`,
  `pg_logging_set_logfile`, `pg_logging_unset_logfile`.
- `pg_log_generic(level, part, fmt, …)` and
  `pg_log_generic_v(level, part, fmt, ap)` — printf-attributed.
- Convenience macros:
  `pg_log_error`, `pg_log_error_detail`, `pg_log_error_hint`,
  `pg_log_warning`, `pg_log_warning_detail`, `pg_log_warning_hint`,
  `pg_log_info`, `pg_log_info_detail`, `pg_log_info_hint`,
  `pg_log_debug`, `pg_log_debug_detail`, `pg_log_debug_hint`.
  Debug macros are wrapped in `if (unlikely(__pg_log_level <=
  PG_LOG_DEBUG))` so they compile to no-op when off.
  (`logging.h:108-148`)
- `pg_fatal(...)` — `pg_log_error(...)` + `exit(1)`.
  `pg_log_error_internal` / `pg_fatal_internal` — same as the
  non-internal versions, intended for "can't happen" messages
  where translating would be a waste. (`logging.h:151-163`)

## Phase D notes

[ISSUE-secret-scrub: every `pg_log_error` callsite that includes
`PQerrorMessage(conn)` may print a secret-bearing parse error
verbatim (maybe)] See `logging.c` doc. The header doesn't carry a
"do not pass untrusted strings" warning; new callers tend to
follow the existing pattern.
