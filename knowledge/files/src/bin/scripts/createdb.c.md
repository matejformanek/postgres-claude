# `src/bin/scripts/createdb.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~330
- **Source:** `source/src/bin/scripts/createdb.c`

CLI wrapper that connects to a maintenance database and issues a
single `CREATE DATABASE` SQL statement, optionally followed by a
`COMMENT ON DATABASE`. Parses many CREATE DATABASE options on the
command line (encoding, owner, tablespace, template, locale
settings — including PG17 builtin-locale and ICU options) and
forwards them as SQL clauses. [verified-by-code]

## API / entry points

- `main(argc, argv)` — parses options, picks a maintenance DB
  (`template1` if the target is `postgres`), connects via
  `connectMaintenanceDatabase`, emits `CREATE DATABASE`, then
  optionally `COMMENT ON DATABASE`. [verified-by-code]

## Notable invariants / details

- Database name defaults: `$PGDATABASE`, then `$PGUSER`, then the
  OS user (`get_user_name_or_exit`) (line 178-186).
  [verified-by-code]
- Auto-fallback to `template1` when target is `postgres` (line
  189-190). This avoids the "cannot connect to template database"
  surprise. [verified-by-code]
- Encoding name is parsed locally via `pg_char_to_encoding` (line
  174) — early failure rather than letting the server complain.
  [verified-by-code]
- All identifier-style args (`owner`, `tablespace`, `template`,
  `locale_provider`, `strategy`) are passed through `fmtId` for
  proper double-quoting. String-style args (`encoding`,
  `locale`, `lc_collate`, `lc_ctype`, `builtin_locale`,
  `icu_locale`, `icu_rules`) go through `appendStringLiteralConn`
  for proper SQL literal escaping (which uses the connection's
  client_encoding and standard_conforming_strings).
  [verified-by-code]
- Two-positional-args form: `createdb DBNAME COMMENT` (line
  161-164). [verified-by-code]
- The `COMMENT ON DATABASE` failure path emits "comment creation
  failed (database was created)" so the user knows the partial
  success state (line 281). [verified-by-code]
- PG17 additions: `--builtin-locale`, `--icu-locale`,
  `--icu-rules`, `--locale-provider`. [verified-by-code]

## Potential issues

- `STRATEGY` value (line 218): passed through `fmtId`, treating
  it as an identifier. The current valid values are `wal_log`
  and `file_copy`, both lowercase ASCII, so this works. But
  `fmtId` will double-quote any non-identifier-looking value and
  the server will then reject it — fine for safety, but a typo
  like `--strategy=WAL_LOG` will trigger a server error rather
  than be normalised. [verified-by-code]
- `LOCALE_PROVIDER` likewise (line 242). [verified-by-code]
- No client-side check that the locale settings are
  self-consistent (e.g. `--locale-provider=libc` with
  `--icu-locale=...` is sent to the server, which then rejects).
  Probably intentional — the server owns the validation logic.
  [verified-by-code]
- `comment` is taken straight from `argv[optind + 1]` without
  any escaping until it hits `appendStringLiteralConn`, which
  handles SQL literals correctly. Safe. [verified-by-code]
- The maintenance-database connection's password is prompted from
  TTY if needed; for unattended use, `--no-password` rejects any
  password prompt. Standard wrapper behaviour. [verified-by-code]
