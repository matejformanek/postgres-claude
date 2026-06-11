# `src/bin/scripts/pg_isready.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~242
- **Source:** `source/src/bin/scripts/pg_isready.c`

Server liveness probe. Uses libpq's `PQpingParams()` to attempt a
connection and reports one of four `PGPing` enum values: OK,
REJECT, NO_RESPONSE, NO_ATTEMPT. Exits with the enum value as
status, so the shell can test e.g. `$? -eq 0`. [verified-by-code]

## API / entry points

- `main(argc, argv)` — getopt loop, build keyword/value pairs,
  call `PQpingParams`, print the rendered host:port plus
  human-readable status, exit with the PGPing value.
  [verified-by-code]

## Notable invariants / details

- Connection timeout default `"3"` seconds (line 17), overridable
  via `-t/--timeout`. Passes through as the
  `connect_timeout` libpq option. [verified-by-code]
- Even on getopt errors (line 95-104) and "too many args" (line
  107-117), exits with `PQPING_NO_ATTEMPT` (3), NOT 1 — the
  comments explicitly state this is to avoid status-code
  collisions with PQPING_REJECT (1) and PQPING_NO_RESPONSE (2).
  [verified-by-code]
- Conninfo parsing: if `-d` looks like a URI
  (`postgresql://`, `postgres://`) or contains an `=`,
  it's parsed via `PQconninfoParse` so the displayed host/port
  comes from the URI rather than the explicit `-h`/`-p` (line
  138-149). [verified-by-code]
- Fallback display path (line 158-190): walks `PQconndefaults()`
  to find what libpq would have used for host/hostaddr/port,
  with preference order:
  1. The parsed conninfo (`opt->val`).
  2. The explicit CLI flag (`pghost`/`pgport`).
  3. The libpq default (`def->val`).
  4. Hard-coded `DEFAULT_PGSOCKET_DIR` for host.
  [verified-by-code]
- `fallback_application_name` set to `progname` (line 130-131)
  so the connection shows up tagged in `pg_stat_activity` (if it
  actually got far enough). [verified-by-code]
- Output format: `<host>:<port> - <status>` (line 196-198).
  `--quiet` suppresses the text but keeps the exit status.
  [verified-by-code]

## Potential issues

- The PGPing enum values as exit codes (0/1/2/3) are stable API
  but not documented in `pg_isready --help`; only in the man page.
  A shell user might assume "0=good, non-zero=bad" without
  realising 1 is the explicit-rejection case.
  [verified-by-code] [ISSUE-doc-drift: help text doesn't list
  exit status meanings; users must read man page (nit)]
- `PQconndefaults` allocates that's freed via the implicit
  process-exit; not via `PQconninfoFree(defs)`. Acceptable since
  pg_isready immediately exits. [verified-by-code]
  [ISSUE-leak: PQconninfoFree(defs) and PQconninfoFree(opts) not
  called before exit; process-exit cleanup masks it (nit)]
- Line 192: `PQpingParams(..., 1)` — third arg `expand_dbname`
  is 1, which means dbname can be a conninfo string. The
  earlier parse only kicks in when we explicitly saw the URI
  prefix; using `--dbname='dbname=foo host=bar'` would have its
  embedded host taken by libpq's own parsing but we'd display
  the wrong host in the output. Minor cosmetic bug.
  [verified-by-code] [ISSUE-correctness: when --dbname contains
  embedded host=, displayed host:port may not match what libpq
  actually connects to (nit)]
- Line 138-141: the URI detection misses `service=` conninfo
  strings (no `=` check would actually catch them; reading
  again: the `strchr(pgdbname, '=') != NULL` check DOES catch
  `service=foo`). So OK. [verified-by-code]
