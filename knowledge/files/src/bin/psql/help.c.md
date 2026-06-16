---
path: src/bin/psql/help.c
anchor_sha: 4b0bf0788b0
loc: 775
depth: deep
---

# help.c

- **Source path:** `source/src/bin/psql/help.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 775

## Purpose

Hand-written help text for psql: `--help` command-line synopsis, `\?`
backslash-command catalogue, `\? variables` env/psql-variable list,
`\h <topic>` SQL-syntax help (dispatched into the auto-generated
`QL_HELP[]` table in `sql_help.h`), and the BSD `\copyright` text.
Every string is wrapped in `_()` for gettext and pushed through a
`PageOutput` pager once the total newline count is known. There is no
SQL assembly here.

## Role in psql

`startup.c` calls `usage()` when `--help` is on the command line.
`command.c` dispatches `\?` (no arg / `commands` / `options` /
`variables`) to `slashUsage` / back to `usage(0)` / `helpVariables`, and
`\h [TOPIC]` to `helpSQL`. `\copyright` calls `print_copyright`.
[from-comment, help.c:29-34]

## Key functions

- **`usage(pager)`** (47) — builds the `psql --help` text. Pure
  string append via `HELP0`/`HELPN` macros (wrappers over
  `appendPQExpBufferStr` / `appendPQExpBuffer` with `_()`).
  `HELPN("  -F, ... default: \"%s\"", DEFAULT_FIELD_SEP)` and
  `HELPN("Report bugs to <%s>.", PACKAGE_BUGREPORT)` interpolate
  compile-time constants only. [verified-by-code, help.c:47-139]
- **`slashUsage(pager)`** (148) — `\?` output. Echoes a handful of
  current `pset` settings into the text:
  `ON(pset.popt.topt.format == PRINT_HTML)`,
  `ON(pset.popt.topt.tuples_only)`, expanded mode (auto / on / off),
  `ON(pset.timing)`, and the current database name via `PQdb(pset.db)`
  (303-306). Database name is rendered with `%s` — no quoting — but
  the output target is stdout / pager, not SQL. [verified-by-code,
  help.c:148-361]
- **`helpVariables(pager)`** (370) — `\? variables`. Hard-coded list
  of psql variables (AUTOCOMMIT, ECHO, ON_ERROR_STOP, …), display
  settings (`\pset` keys), and environment variables. Uses
  `DEFAULT_WATCH_INTERVAL`, `DEFAULT_CSV_FIELD_SEP`, `DEFAULT_FIELD_SEP`
  for default-value interpolation. [verified-by-code, help.c:370-584]
- **`helpSQL(topic, pager)`** (593) — `\h`. Two modes:
  - No topic → grids the `QL_HELP[i].cmd` list at screen width
    from `TIOCGWINSZ` (fallback 80). [verified-by-code, help.c:597-641]
  - Topic given → up-to-3-pass match: exact match first, then
    first-two-words, then first-word-only. Uses `pg_strncasecmp`
    for prefix match, `pg_strcasecmp` for exact match (early-exit
    on exact — comment "Fixes \h SELECT"). On match, calls
    `QL_HELP[i].syntaxfunc(&buffer)` (the auto-generated per-statement
    builder), formats with command name + description + syntax + URL.
    URL is `psprintf("https://www.postgresql.org/docs/%s/%s.html",
    strstr(PG_VERSION, "devel") ? "devel" : PG_MAJORVERSION,
    QL_HELP[i].docbook_id)`. [verified-by-code, help.c:642-749]
- **`print_copyright()`** (754) — fixed `puts()` of the BSD copyright
  block. [verified-by-code, help.c:754-775]

## SQL-assembly discipline

None — no SQL is built in this file. All output is text. The only
user-controlled input that flows through any function is the `topic`
argument to `helpSQL`, and it's only matched against compile-time
strings (`QL_HELP[i].cmd`) and used in a `psprintf` URL whose other
fields (`PG_VERSION`, `PG_MAJORVERSION`, `docbook_id`) are
compile-time constants. The `topic` itself reaches output only in the
"No help available for \"%s\"." failure message (743), which is a
local stderr-style print, not SQL or shell. [verified-by-code]

## Phase D notes

- **Locale / encoding.** All strings pass through `_()`/gettext.
  Translated strings come from the binary's compiled-in `.mo` files
  (under `share/locale/...`); a malicious `LC_*` env wouldn't inject
  text but could pick a different translation. Not a trust boundary.
  [inferred]
- **`PQdb(pset.db)` echo in `slashUsage`** (304-306). The database
  name is server-supplied (the user provided it at connect time, or
  `\connect` accepted server-redirected variants). If the database
  name contains a `\n`, it could spoof an extra `\?` output line.
  But `\?` is a local help command, not a logging interface, and the
  output goes to the pager / stdout — there's no log-injection
  surface. [verified-by-code, help.c:303-306]
- **`TIOCGWINSZ` fallback (80)** in `helpSQL`. If `ioctl` fails, the
  column count is 80; the grid layout never overflows. Safe.
  [verified-by-code, help.c:608-616]
- **Magic `nl_count` constant (`+ 7`)** at help.c:692. The comment
  "magic constant here must match format below!" and the matching one
  at 719 "# of newlines in format must match constant above!" are an
  obvious foot-gun: changing the `fprintf` format at 720-723 without
  updating the constant overruns the pager's line budget. Just a
  maintenance hazard, not a correctness bug today. [from-comment,
  help.c:691-723]
- **`\h SELECT` exact-match early-exit** (694-696, 731-733). Without
  this, the prefix scan would output multiple entries (e.g. `SELECT
  INTO` and `SELECT`). [from-comment, help.c:694]
- **DocBook URL composition** at 716-727: hard-coded
  `postgresql.org/docs/<ver>/<docbook_id>.html`. URL is rendered as
  text, not opened. If a hostile build flipped `PG_VERSION` it could
  redirect users to a different doc tree — but that's a build-time
  trust issue, not a runtime one. [verified-by-code]

## Potential issues

- **[ISSUE-stale-todo: magic newline-count constant in `helpSQL` could
  drift]** `help.c:691-723` — paired comments explicitly call out the
  hazard. Severity: nit.
- **[ISSUE-info-disclosure: `slashUsage` echoes current database name
  unquoted into `\?` output]** `help.c:303-306` — newline / control
  characters in `PQdb(pset.db)` would corrupt the help banner. Not a
  security issue (local stdout); flagged for completeness. Severity:
  nit.
- **[ISSUE-undocumented-invariant: `helpVariables` list must be kept
  in sync with `settings.h` + `command.c` variable hooks]** — no
  test asserts the help list covers all real psql variables (e.g.
  HISTSIZE / SHELL_ERROR / SQLSTATE are listed; if a new variable is
  added to `settings.h` without a help.c entry, users won't see it).
  Severity: nit (documentation-drift class).
- **[ISSUE-dead-code: `LASTOID` variable]** `help.c:421-422` — listed
  in `helpVariables`. `LASTOID` is tied to legacy `INSERT ... RETURNING
  oid` semantics; modern PG with default `WITHOUT OIDS` tables sets it
  to 0. Documentation kept for historical reasons. Severity: nit.

## Cross-references

- `sql_help.h` / `sql_help.c` — auto-generated from
  `doc/src/sgml/ref/*.sgml` by `create_help.pl`. Provides `QL_HELP[]`
  and per-command `syntaxfunc` builders.
- `command.c` — dispatch site for `\?`, `\h`, `\copyright`.
- `startup.c` — calls `usage()` for `psql --help`.
- `mainloop.c` — uses `helpSQL` indirectly via command.
- `settings.h` — defines the psql variables that `helpVariables`
  describes.

<!-- issues:auto:begin -->
- [Issue register — `psql`](../../../../issues/psql.md)
<!-- issues:auto:end -->

## Confidence tag tally
`[verified-by-code]=10 [from-comment]=4 [inferred]=1`
