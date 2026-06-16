# `src/bin/scripts/common.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~168
- **Source:** `source/src/bin/scripts/common.c`

Shared helpers for the simple wrapper scripts in `bin/scripts/`
(`createdb`, `dropdb`, `createuser`, `dropuser`, `clusterdb`,
`reindexdb`, `vacuumdb`). Three exports: split a
`TABLE(COLUMNS)` spec, resolve a possibly-schema-qualified table
name against the live server's `pg_class`, and a localised yes/no
prompt. [verified-by-code]

## API / entry points

- `splitTableColumnsSpec(spec, encoding, &table, &columns)` —
  splits `TABLE(COLUMNS)` into the leading TABLE part and the
  trailing `(COLUMNS)`. Respects double-quoted identifiers and
  `""` pair-escapes inside them (same parsing as
  `dequote_downcase_identifier`). The `columns` output is a
  pointer into `spec`, not a copy. [verified-by-code]
- `appendQualifiedRelation(buf, spec, conn, echo)` — runs
  `RESET search_path; SELECT relname, nspname FROM pg_class JOIN
  pg_namespace ... WHERE oid = '<table>'::regclass`, then appends
  the fully-qualified name plus any `(COLUMNS)` tail. Restores the
  always-secure search path before returning.
  [verified-by-code]
- `yesno_prompt(question)` — loops on `simple_prompt`, accepting
  the localised yes/no letters via `gettext_noop`. Used by
  `dropdb -i`, `dropuser -i`, and `createuser` interactive
  attribute prompts. [verified-by-code]

## Notable invariants / details

- The SQL in `appendQualifiedRelation` is deliberately written so
  every identifier is schema-qualified (`pg_catalog.pg_class`,
  `OPERATOR(pg_catalog.=)`) — comment line 79-82 emphasises this
  is to avoid hijack via search_path. [verified-by-code]
- `RESET search_path` is issued before the query so the user's
  `--table=foo` resolves the same way it would inside psql.
  After the query, we issue `ALWAYS_SECURE_SEARCH_PATH_SQL`
  (defined in `common/connect.h`) to restore the locked-down
  search path. [verified-by-code]
- A query result of any number of rows other than 1 is treated as
  a hard error (line 104-112), including the rare-but-real case
  where the regclass cast accepts an OID-string but no
  pg_class row matches. [verified-by-code]
- `yesno_prompt` translator hooks use `PG_YESLETTER`/`PG_NOLETTER`
  abbreviations; localised yes/no strings come from the .po files
  for the `pgscripts` text domain. [verified-by-code]

## Potential issues

- Line 117: `appendPQExpBufferStr(buf, columns)` appends the
  trailing `(COLUMNS)` AS-IS — no validation that columns is a
  syntactically-valid column list. A user can pass
  `--table='foo (col1); DROP DATABASE evil'` and the trailing
  garbage flows straight into the constructed SQL. The relevant
  callers (e.g. `vacuuming.c`, `clusterdb.c`) inherit this trust.
  [verified-by-code] [ISSUE-security: appendQualifiedRelation
  appends trailing (COLUMNS) verbatim with no syntax check; SQL
  injection possible via --table value (likely)]
- `splitTableColumnsSpec` doesn't recognise embedded `(`
  inside double-quotes correctly if the quote is itself part of a
  column-list expression. Reading again: it splits on the first
  `(` not inside identifier quotes. A column spec like
  `tab(col1,col2)` is fine; a relname like `"a(b)"` is fine; but
  `"a)b"` then trailing `(` is fine too. The parser is
  reasonable. [verified-by-code]
- Line 110-112: on failure we `PQfinish(conn)` and `exit(1)`,
  losing any cleanup the caller may have wanted to do. Acceptable
  for these one-shot scripts. [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `scripts`](../../../../issues/scripts.md)
<!-- issues:auto:end -->
