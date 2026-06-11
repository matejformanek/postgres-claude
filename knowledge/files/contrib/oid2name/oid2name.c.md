# `contrib/oid2name/oid2name.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~650
- **Source:** `source/contrib/oid2name/oid2name.c`

Client utility (libpq frontend, `postgres_fe.h`) that maps the
on-disk OID / filenode / tablespace numbers visible in
`$PGDATA/base/…/…` back to database / table / index names by SELECTing
`pg_catalog.pg_class`, `pg_database`, `pg_tablespace`. Single-file
program, no shared libs beyond libpq + common/. Replaced in modern
workflows by `psql` against `pg_relation_filepath`, but still ships
for DBA convenience. [verified-by-code]

## API / entry points

- `main` (oid2name.c:582-650) — allocs `struct options`, calls
  `get_opts`, connects, dispatches to one of four mode functions:
  - `sql_exec_dumpalltbspc` for `-s`
  - `sql_exec_searchtables` when any of `-o`/`-f`/`-t` given
  - `sql_exec_dumpalltables` for the named DB
  - `sql_exec_dumpalldbs` for no DB. [verified-by-code]
- `get_opts` (oid2name.c:62-198) — getopt_long parser; accepts
  `-d/--dbname`, `-h/--host`, `-H` (deprecated host alias),
  `-f/--filenode`, `-i/--indexes`, `-o/--oid`, `-p/--port`,
  `-q/--quiet`, `-s/--tablespaces`, `-S/--system-objects`,
  `-t/--table`, `-U/--username`, `-x/--extended`. No password option;
  password prompt is unconditional when server requests it.
  [verified-by-code]
- `sql_conn` (oid2name.c:294-366) — builds a 7-key `PQconnectdbParams`
  array, sets `fallback_application_name=progname`, loops on
  `PQconnectionNeedsPassword`, then unconditionally runs
  `ALWAYS_SECURE_SEARCH_PATH_SQL` (resets search_path to
  `pg_catalog`). [verified-by-code]
- `sql_exec` (oid2name.c:371-446) — runs query, formats output as a
  fixed-width text table. Exits process on query error.
  [verified-by-code]
- `add_one_elt` / `get_comma_elts` (oid2name.c:234-291) — grow-array
  for the `-o/-t/-f` repeatable options; `get_comma_elts` produces
  a comma-separated, single-quoted, `PQescapeString`-escaped SQL
  snippet for use in `IN (…)` clauses. [verified-by-code]

## Notable invariants / details

- Always sets `ALWAYS_SECURE_SEARCH_PATH_SQL` after connect
  (oid2name.c:353); all subsequent queries explicitly schema-qualify
  with `pg_catalog.` so unqualified names cannot be hijacked.
  [verified-by-code]
- The `-t/--table` argument is fed into `c.relname ~~ ANY (ARRAY[…])`
  (oid2name.c:539) — a LIKE pattern join, so `%` and `_` are
  interpreted as wildcards. This is **intentional** but undocumented
  in the `--help` text. [verified-by-code] [from-comment]
- Table name strings are quoted with `PQescapeString` inside
  `get_comma_elts` (oid2name.c:286), then dropped into a literal
  SQL clause. `PQescapeString` is the legacy non-connection-aware
  escape; works correctly for SQL string literals but does not
  handle `standard_conforming_strings = off` quirks the way
  `PQescapeStringConn` would. [verified-by-code] [ISSUE-style:
  legacy escape (nit)]
- `-o` and `-f` values are not numeric-validated client-side
  (oid2name.c:144-147, 129-131) — they are inserted into the SQL
  via `get_comma_elts` which **does** quote them. So even non-numeric
  input becomes `'…'::text` and yields a planner error rather than
  injection. The escape is the safety net here. [verified-by-code]
- Default DB is `"postgres"` (oid2name.c:603) and `nodb = true` makes
  the subsequent dispatch fall through to `sql_exec_dumpalldbs`.
  [verified-by-code]
- `--password` / `-W` / `-w` flags are absent (compare vacuumlo);
  there's no way to suppress password prompting. The `do { } while
  (new_pass)` loop (oid2name.c:306-343) will always prompt if the
  server says it needs one. [verified-by-code]
  [ISSUE-undocumented-invariant: no `-w`/no-password mode (nit)]

## Potential issues

- oid2name.c:286. `PQescapeString(ptr, eary->array[i], …)` — the
  non-connection-aware escape. Modern client utilities use
  `PQescapeStringConn` or `PQescapeLiteral`; this matches old
  vacuumlo style. Functionally safe as long as
  `standard_conforming_strings=on` (default since 9.1) and the
  client encoding is single-byte-or-UTF-8-compatible. On exotic
  multi-byte encodings the un-connection-aware variant can
  miscount byte vs char. [ISSUE-style: should be PQescapeStringConn
  (nit)]
- oid2name.c:518. `pg_malloc(strlen(comma_oids) + strlen(comma_tables)
  + strlen(comma_filenumbers) + 80)` — "+80" is a magic-number
  estimate of the SQL syntax overhead. If a future code change adds
  another disjunct, this buffer can overrun. The 3 `sprintf` and
  `sprintf` calls below it write without bounds checking.
  [ISSUE-correctness: hardcoded sprintf headroom (maybe)]
- oid2name.c:333. `pg_fatal("could not connect to database %s",
  my_opts->dbname)` is called when `PQconnectdbParams` returns NULL,
  i.e. allocation failure. The error message reveals the dbname even
  on early failure. Minor info-leak; matches the rest of the libpq
  CLI family. [ISSUE-style: dbname in OOM message (nit)]
- oid2name.c:391-395. On query error the entire process exits — fine
  for a one-shot CLI, but if `oid2name` is invoked in a shell loop
  by a DBA script, a transient ERROR in one DB stops the whole
  iteration. [ISSUE-style: no per-DB error recovery (nit)]
- oid2name.c:159-167. `-S/--system-objects` flips queries to include
  pg_catalog/information_schema/pg_toast objects, but the help text
  (line 213) says "show system objects too" without naming the
  schemas. [ISSUE-doc-drift: vague help text (nit)]
- oid2name.c:539. The `~~ ANY (ARRAY[…])` LIKE behaviour is
  surprising for users who expect exact match. `-t foo_bar` finds
  rows where `_` matches any char. [ISSUE-question: should we exact-
  match or document the LIKE behaviour (nit)]

## Cross-references

- `knowledge/issues/oid2name.md` — per-extension issue register
  (create from template if absent).
- `source/src/interfaces/libpq/fe-exec.c` — `PQescapeString` vs
  `PQescapeStringConn`.
- Companion utility: `vacuumlo` (same `_param` connect-loop pattern,
  also lives in contrib/).
