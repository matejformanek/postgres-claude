# util.c

## Purpose

Logging, status, and small string helpers for pg_upgrade. Defines
`pg_log`, `pg_fatal`, `report_status`, `prep_status` (+ progress
variant), `check_ok`, plus `quote_identifier`, `get_user_info`,
`str2uint`, and the cleanup-on-exit routine `cleanup_output_dirs`.

## Role in pg_upgrade

Every other file in `pg_upgrade/` calls into here for user output
and the internal log file (`log_opts.internal`, a FILE* opened in
`pg_upgrade.c::main()` for `pg_upgrade_internal.log`). This is the
mirror of `src/bin/pg_dump/pg_backup_archiver.c`'s logging layer but
purpose-built for pg_upgrade's "padded status line + ok/failed"
idiom.

## Key functions

- `pg_log_v(type, fmt, ap)` `util.c:176` (static) — central dispatcher.
  Asserts the format string does NOT end with `\n` (line 182), then
  `vsnprintf`s into a fixed `QUERY_ALLOC`-sized buffer with `_(fmt)`
  for translation. Writes to `log_opts.internal` (if non-NULL and
  not a verbose-only suppression) AND to stdout per the level.
- `pg_log(type, fmt, ...)` `util.c:259` — public varargs wrapper.
- `pg_fatal(fmt, ...)` `util.c:270` — calls pg_log_v with PG_FATAL,
  which itself `exit(1)`s; the wrapper has a defensive trailing
  exit(1) anyway.
- `report_status(type, fmt, ...)` `util.c:32` — notationally distinct
  from pg_log but functionally identical (comment line 26).
- `prep_status(fmt, ...)` / `prep_status_progress(fmt, ...)`
  `util.c:129,156` — print left-padded status line of
  MESSAGE_WIDTH columns; the matching `check_ok()` later writes
  "ok" on the same line.
- `end_progress_output()` `util.c:43` — terminates a
  prep_status_progress run.
- `cleanup_output_dirs()` `util.c:63` — close the internal log file,
  if `!log_opts.retain` `rmtree(basedir)` (twice on Windows for race
  tolerance), then conditionally rmtree the rootdir if empty.
- `quote_identifier(s)` `util.c:299` — SQL-quote: double-up `"`
  characters, wrap in `"..."`. Caller is expected to free.
- `get_user_info(&user_name)` `util.c:323` — `geteuid()` +
  `get_user_name()` from `common/username.c`. Result `pg_strdup`'d.
- `str2uint(str)` `util.c:352` — `strtoul(..., 10)`. No range check;
  callers in controldata.c rely on the input being a pg_resetwal
  string.

## State / globals

`LogOpts log_opts` (definition, line 17). Fields used here: `internal`
(FILE *), `verbose`, `isatty`, `retain`, `basedir`, `rootdir`.

## Phase D notes — secret-scrub story (vs A5's logging.c)

[from-code] **No PII-style scrubbing.** `pg_log_v` passes `fmt`
through `_()` (gettext) then `vsnprintf`s. If a caller passes a
format like `"connection failure: %s", PQerrorMessage(conn)`, the
PQerrorMessage text—which can include hostnames, usernames, dbnames,
and server-side detail messages—lands verbatim in:

1. `log_opts.internal` (the persistent log under
   `pg_upgrade_output.d/<ts>/log/pg_upgrade_internal.log`).
2. stdout (terminal).

There is no equivalent of the password-redaction filter you'd want
here. Callers that print `PQerrorMessage` include:
- `server.c:34` (connectToServer fatal path).
- `server.c:262` (start_postmaster fatal).
- `server.c:142` (executeQueryOrDie fatal).
- `task.c:218,269,284,295` (parallel task fatal paths).
- `function.c:217,226` (loadable-library check).

[ISSUE-secret-scrub: pg_log_v writes server error messages verbatim
to log_opts.internal which is retained when `--retain` is set or on
upgrade failure (maybe-medium)] — `util.c:189-198`. Mirrors the A5
logging.c gap in pg_dump: there's no central scrub, and the upgrade
log file is what you'd attach to a support ticket. Same risk
surface.

[ISSUE-secret-scrub: `pg_log_v` Assertion at line 182 forbids
trailing newlines but does NOT strip control characters from
interpolated strings (low)] — A malicious db_name containing `\n` +
ANSI escape could rewrite the terminal display. The Assert is the
only check.

[ISSUE-info-disclosure: `log_opts.internal` opened in
pg_upgrade.c::setup() with broad mode (verify there?); util.c only
fcloses it (low)] — `util.c:65`. Per the corpus comment in
pg_upgrade.sgml, the log dir is meant to be group-readable.

[from-code] **`cleanup_output_dirs` behavior on `--retain`** (line
68): if user passed `--retain`, ALL the dump files, log files, and
per-call .log files (including pg_dump output with PQerrorMessage
in them — see `dump.c.md`) stay on disk. There's no "scrub then
retain" mode. This is the explicit user-controlled trade-off.

[from-code] **`quote_identifier`** (line 299) handles `"` doubling
correctly; never used for shell quoting. Callers in version.c
(`REINDEX INDEX %s.%s`) and similar SQL-emitting helpers.

[ISSUE-correctness: `str2uint` returns `strtoul(str, NULL, 10)`
without checking endptr — silently returns 0 on garbage (low)] —
`util.c:354`. controldata.c callers assume pg_resetwal output is
well-formed; a corrupted pg_resetwal binary would feed garbage,
producing 0-valued ctrl fields that mostly fail later
`check_control_data` checks.

[from-code] **`get_user_info` uses `geteuid()` then
`get_user_name`** (line 330-335) which can fail with `errstr` —
fatal. Used for the connect-string `user=` field; no setuid
considerations because pg_upgrade is intended to run as the cluster
owner.
