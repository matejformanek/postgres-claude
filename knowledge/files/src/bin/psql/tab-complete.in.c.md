---
path: src/bin/psql/tab-complete.in.c
anchor_sha: 4abf411e2328
loc: 7343
depth: deep
---

# tab-complete.in.c

- **Source path:** `source/src/bin/psql/tab-complete.in.c`
- **Last verified commit:** `4abf411e2328` (re-pinned 2026-06-29 from `4b0bf0788b0`)
- **LOC:** 7343

> **AUDIT 2026-06-29.** Anchor-bump trigger: `56b2792cf84f` (Fujii
> Masao) added tab completion for the subscription `wal_receiver_timeout`
> option — the new `"wal_receiver_timeout"` entries land in the
> CREATE/ALTER SUBSCRIPTION option lists at `:2384` and `:3970` (a
> region this doc does not cite by line). Re-pinning from the long-stale
> `4b0bf0788b0` also surfaced an accumulated **~+2/+3 downward drift** in
> the identifier-round-trip / exec_query region (6700-7100): `make_like_pattern`
> encodings comment `:6793→:6797`, `parse_identifier` `:6826→:6829`,
> `requote_identifier` `:6926→:6928`, `exec_query` `:7041→:7043`. The
> SQL-building interpolation cites (`:6128`–`:6224`) and catalog-suppression
> cites (`:6157-6164`, `:6182-6184`) are block landmarks accurate to ±2 and
> were left as-is.

## Purpose

Readline tab-completion logic. Driven by `rl_attempted_completion_function
= psql_completion` installed in `initialize_readline()` (1537). On
every Tab keypress, readline calls `psql_completion(text, start, end)`,
which (a) reconstructs the previous words from `rl_line_buffer` +
`tab_completion_query_buf`, (b) walks a long match-rule table to pick
the right completion source (keyword list / SchemaQuery / VersionedQuery
/ simple query), and (c) issues a catalog query via `exec_query()`
that returns up to 1000 candidate names.

**`.in.c` suffix:** the file is preprocessed by `gen_tabcomplete.pl`
before build, which extracts `Matches`/`HeadMatches`/`TailMatches`
guards into a `tcpatterns[]` array and rewrites the else-if chain in
`match_previous_words()` into a switch keyed by pattern id. Both
forms compile (under `#ifdef SWITCH_CONVERSION_APPLIED`), so the
file is readable as-is. [from-comment, tab-complete.in.c:7-13]

## Role in psql

`mainloop.c` reserves the `tab_completion_query_buf` and feeds
multi-line statement context into it before each readline cycle.
`startup.c` invokes `initialize_readline()` once at psql start
(under `#ifdef USE_READLINE`). Each interactive Tab keypress runs
**inside the user's current transaction** on the SAME connection as
the interactive session — see "Phase D notes" for the implications.

## Key functions and structures

| Symbol | Purpose | File:line |
|---|---|---|
| `psql_completion` (callback) | readline entry point | ~1990 |
| `match_previous_words(pattern_id, …)` | rule body, post-extraction switch | 2192 |
| `_complete_from_query` (called via callbacks) | the universal "run a SELECT, return matches" core | 6050 area |
| `_complete_from_const` / `_complete_from_list` / `_complete_from_files` | non-SQL completion sources | (file-static) |
| `make_like_pattern(word)` | LIKE-prefix builder with `\_`/`\%` escaping + multibyte | 6781 |
| `escape_string(text)` | `PQescapeStringConn` wrapper | 6758 |
| `requote_identifier(nsp, item, …)` | quote-aware identifier rejoiner | 6926 |
| `parse_identifier(ident, …)` | quote-aware splitter for `schema.name` | 6826 |
| `exec_query(query)` | `PQexec` wrapper that silently swallows errors | 7043 |
| `get_previous_words(point, …)` | parse `rl_line_buffer` (+ buffered multi-line) into words | 7080 |
| `initialize_readline` | startup hook | 1537 |
| `SchemaQuery` (struct) | declarative catalog query for a class of names | 129 |
| `VersionedQuery` (struct) | a list of (min_server_version, query) | 107 |
| `Query_for_list_of_aggregates / _arguments / _attributes / …` | ~30+ static `SchemaQuery` instances | 519-700+ |
| `tcpatterns[]` (generated) | match-rule table for the switch dispatcher | 2207+ |
| `completion_max_records` | hardcoded 1000 LIMIT | 218, 1575 |
| `tab_completion_query_buf` | global buffer holding prior multi-line input | 93 |

## SQL-assembly discipline

### Pattern path — `_complete_from_query` (the only SQL-assembly site)

The body around lines 6050-6248 is the central catalog-query builder.
Inputs are the partial word from readline (`text`) plus context
(`completion_ref_object`, `completion_ref_schema`). Discipline:

- **`escape_string(text)`** = `PQescapeStringConn(pset.db, ...)` —
  encoding-aware string-literal escape. Used for `e_schemaname`,
  `e_ref_object`, `e_ref_schema`. [verified-by-code, tab-complete.in.c:
  6758-6769]
- **`make_like_pattern(word)`** — escapes `_`/`%` with backslashes,
  transfers multibyte characters byte-for-byte via
  `PQmblenBounded(word, pset.encoding)`, appends `%`, then
  funnels through `escape_string`. The multibyte handling is
  explicitly there "to avoid getting confused in unsafe client
  encodings." [from-comment, tab-complete.in.c:6797-6799;
  verified-by-code, 6783-6813]
- **SQL building**: all the `'%s'` interpolations at 6128, 6137,
  6175, 6212, 6215, 6220, 6224 take ONLY pre-escaped strings
  (`e_object_like`, `e_schemaname`, `e_ref_object`, `e_ref_schema`).
  The query template fragments (`schema_query->result`,
  `schema_query->catname`, `schema_query->selcondition`,
  `schema_query->viscondition`, `schema_query->namespace`,
  `schema_query->refname`, `schema_query->refnamespace`,
  `schema_query->refviscondition`) are **compile-time constants** from
  the static `Query_for_list_of_*` definitions — never user input.
  [verified-by-code, tab-complete.in.c:6100-6231 + 519-700]
- **`simple_query`** (6238) is also a compile-time `const char *`
  used as an sprintf-style format that consumes the three escaped
  args. Same trust model. [verified-by-code]
- **Hard LIMIT 1000** appended at 6244 from `completion_max_records`
  (set in `initialize_readline`). Caps result rows; no time cap.
  [verified-by-code, tab-complete.in.c:6245-6247, 1575]
- **`exec_query` uses `PQexec`, not `PQexecParams`.** Errors are
  swallowed silently (the `#ifdef NOT_USED` block at 7059-7062
  shows where a `pg_log_error` would go). [verified-by-code,
  tab-complete.in.c:7043-7068]

### Identifier round-trip path — `parse_identifier` / `requote_identifier`

When the user types `"foo'; DROP --"`<Tab>, `parse_identifier` (6829)
walks the input; the `inquotes` flag flips on `"`, doubles `""`, and
the unquoted-vs-quoted state is propagated to `objectquoted` /
`schemaquoted` booleans. The dequoted name string is then fed through
`make_like_pattern` + `escape_string` for the SQL. The user's literal
quote characters reach the server only as the LIKE-pattern value
inside a `'…'` string literal — they cannot escape it because
`PQescapeStringConn` doubles embedded single quotes per the
connection's `standard_conforming_strings` and encoding state.
[verified-by-code, tab-complete.in.c:6829 ff., 6760-6771]

`requote_identifier` (6928) does the inverse on the way back: takes
the server-returned (schema, name) and re-quotes the visible string
the user sees in the completion list, with `identifier_needs_quotes`
checking whether the name actually requires quoting (6295-6298: if the
user did NOT type a quote, completion never inserts one for a name
that would need quoting — to avoid surprise).

### Verbatim mode

Some completion sources are flagged "verbatim" (6278-6282), meaning
the server-returned string is used as-is without re-quoting. This is
used for enum values (`Query_for_list_of_enum_values_quoted` vs
`_unquoted`, 623, 632) and time-zone names — values that the user
will paste literally into their SQL. Verbatim values are still
escaped on the way IN to the catalog query; they just bypass the
re-quoting on the way OUT. [verified-by-code]

## Tab-completion specifics — Phase D-critical

### Every Tab is a server round-trip

`exec_query` calls `PQexec(pset.db, query)` synchronously. This means:

- **Tab completion runs on the SAME connection as the interactive
  session.** Inside a `BEGIN; … <Tab>` block, the completion query
  participates in the user's open transaction — same snapshot, same
  locks-held state. A long-running uncommitted CREATE TABLE blocks
  Tab on `\d <Tab>` until the transaction either commits or rolls
  back. [inferred from `exec_query` using `pset.db`]
- **No savepoint wrapping.** If the catalog query errors (e.g. role
  lacks SELECT on `pg_class`), the user's transaction state may flip
  to "aborted", invalidating subsequent commands until ROLLBACK.
  The silent-failure `exec_query` path doesn't notify the user that
  Tab caused this. [verified-by-code, 7050-7062 — error is swallowed;
  inferred for the txn-abort consequence]
- **Implicit autocommit semantics:** outside an explicit `BEGIN`,
  each Tab query runs in its own short txn (PG's default
  one-statement-per-txn behavior). No user-visible commit.
- **Multi-line buffer leaks intent.** `tab_completion_query_buf`
  holds the user's previously-typed continuation lines so
  `get_previous_words` can scan them. When tab fires, `psql_completion`
  uses them ONLY for client-side pattern matching against
  `Matches/HeadMatches/TailMatches` — they are NOT sent to the server
  as part of the query. The server sees only the catalog SELECT,
  not the user's in-progress SQL. [verified-by-code, get_previous_words
  builds local buf; exec_query sends only query_buffer.data]
- **Rate-limited only by 1000-row LIMIT on output**, not by request
  count. A misbehaving readline that fires Tab in a loop would issue
  one PQexec per Tab. No client-side throttle. [verified-by-code]

### Newer rule sources

Beyond the `else if (Matches(…))` chain, three "fallthrough" lookup
paths exist after the rule scan (2104-2123): the `words_after_create[]`
table for `CREATE <noun> <Tab>` patterns dispatches into either
`COMPLETE_WITH_QUERY_LIST` (simple `const char *` query),
`COMPLETE_WITH_VERSIONED_QUERY_LIST` (chosen by server version), or
`COMPLETE_WITH_VERSIONED_SCHEMA_QUERY_LIST` (full `SchemaQuery`).
All three use the same escape pipeline. [verified-by-code, 2104-2123]

## Phase D notes

- **No SQL injection from user-typed identifier**, even for inputs
  designed to break out of the LIKE literal: `"foo'; DROP --"`<Tab>
  becomes `SELECT … WHERE (c.relname) LIKE 'foo''%' AND
  pg_catalog.pg_table_is_visible(c.oid) LIMIT 1000`. The `'` is
  doubled by `PQescapeStringConn`; the LIKE meta `%`/`_` are
  backslash-escaped by `make_like_pattern`. [verified-by-code, by
  tracing 6083 + 6128]
- **Information leak via Tab.** Every Tab keypress reveals catalog
  contents to the connected role. That's by design (it's the role's
  own database), but worth noting for shared-cluster threat models:
  a role with SELECT on `pg_catalog` (the default) can enumerate
  objects belonging to OTHER schemas faster via repeated Tab than
  via explicit `\d`. Not a vulnerability — Tab uses the same
  catalog visibility as any other query. [inferred]
- **Tab-inside-transaction side channel.** If autocommit is OFF and
  the user types `INSERT INTO important_audit_log VALUES (1); <Tab>`,
  the Tab catalog query joins the user's open transaction. If the
  tab-completion query errors (catalog lock contention, dropped
  role, dropped catalog table — rare, but possible during pg_upgrade
  / catalog reindex on a misconfigured cluster), the user's
  transaction aborts silently and their next `COMMIT` becomes a
  surprise ROLLBACK. The `#ifdef NOT_USED` error-log path at 7057
  acknowledges this is hard to debug. [verified-by-code +
  inferred-consequence]
- **`tab_completion_query_buf` is process-global** with no readline
  reentrancy guard. The comment at 89-92 notes "we have to use this
  global variable to let `get_previous_words()` get at the previous
  lines of the current command. Ick." If a SIGINT during Tab leaves
  the buffer in a half-initialized state, the next Tab sees junk.
  Practical impact: weird completions, not a security issue.
  [from-comment, tab-complete.in.c:89-92]
- **`completion_max_records = 1000`** is hardcoded. Not user-tunable
  via `\pset` or psql variable. A future patch exposing this as a
  variable would want to bound it to prevent server-side huge results.
  [verified-by-code, 1575, 218]
- **System-catalog suppression** at 6157-6164: if the user types
  anything not starting with `pg_`, tab completion suppresses
  `pg_catalog.*` matches. This is purely UX (avoid swamping with
  `pg_*`) but means the user can't tab-complete `pg_class` unless
  they type `pg_<Tab>` first. [from-comment, 6151-6155]
- **System-schema suppression** at 6182-6184 uses
  `n.nspname NOT LIKE E'pg\\_%'` — the `E''` string syntax is required
  because `standard_conforming_strings = on` is the default since 9.1.
  If a connection has `standard_conforming_strings = off` (legacy),
  the E-string still works. [verified-by-code, inferred safe]
- **`text_copy`** and per-cycle frees at the end of `psql_completion`
  (2141-2149): completion_ref_object/completion_ref_schema are
  globals freed and NULLed each cycle. If a future code path adds
  a `return matches` somewhere before 2141 without freeing these,
  next cycle leaks the previous values. [verified-by-code,
  2141-2149]
- **No SSL / connection-status check inside `exec_query`** beyond
  `PQstatus(pset.db) != CONNECTION_OK` (7047-7048). If the connection
  is in a TLS-renegotiation state, `PQexec` blocks the readline UI
  thread. Practical impact: visible UI freeze, not a security
  issue. [verified-by-code]

## Potential issues

- **[ISSUE-trust-boundary: Tab queries join the user's open
  transaction with no savepoint]** `tab-complete.in.c:7043-7068` —
  a catalog query error inside an explicit `BEGIN` aborts the
  user's transaction silently. The error is swallowed at 7057
  (`#ifdef NOT_USED`). Severity: maybe (debug-pain class; rare in
  practice but real).
- **[ISSUE-undocumented-invariant: `completion_max_records = 1000`
  silently truncates]** `tab-complete.in.c:1575, 218, 6246` — if the
  matching catalog object count exceeds 1000, the user sees an
  arbitrary subset. No order-by clause, so the subset is
  server-implementation-dependent. Severity: nit (UX, not security).
- **[ISSUE-info-disclosure: server-supplied identifiers used to
  build the next completion-list display]** `tab-complete.in.c:6291,
  requote_identifier:6912` — output is to readline, which renders to
  the terminal. A relname with ANSI escapes would corrupt the
  completion display, similar to the `\d` title hazard. Severity:
  maybe (terminal-spoof class).
- **[ISSUE-dos: no per-second cap on Tab firing]**
  `tab-complete.in.c:7043` — a held-down Tab key issues one PQexec per
  press. Cluster-side rate limiting (pg_stat_statements throttle, role
  connection limits) is the only mitigation. Severity: nit (user
  controls own keyboard).
- **[ISSUE-undocumented-invariant: `tab_completion_query_buf` is
  process-global]** `tab-complete.in.c:89-93` — comment "Ick" already
  acknowledges. No reentrancy guard; readline is single-threaded in
  psql. Severity: nit.
- **[ISSUE-stale-todo: `#ifdef NOT_USED` debug log path for
  exec_query failures]** `tab-complete.in.c:7059-7062` — perpetually
  compiled-out. A `\set DEBUG_TAB_COMPLETE` GUC-style toggle would
  be useful for troubleshooting; today the only debug path is the
  server log via `log_min_messages`. Severity: nit.
- **[ISSUE-wire-protocol: tab-completion's `PQexec` doesn't use
  prepared statements]** All catalog queries are issued as fresh
  text every Tab. With a busy cluster, the parse/plan cost is
  noticeable. Severity: nit (perf, not security).
- **[ISSUE-undocumented-invariant: `parse_identifier` accepts
  partially-quoted names per "psql metacommand tradition"]**
  `tab-complete.in.c:6817-6826` — `"foo".bar` AND `foo."bar"` both
  parse. Backend parser doesn't. Edge cases where psql tab-completes
  to a form the server then rejects exist. Severity: nit (cited in
  the function header comment as deliberate).
- **[ISSUE-trust-boundary: `exec_query` returns NULL on any error
  including connection loss]** `tab-complete.in.c:7047-7066` — psql
  user sees Tab "doing nothing" instead of "your connection
  dropped". The next real query then fails with a confusing error.
  Severity: nit.
- **[ISSUE-info-disclosure: `PQescapeStringConn` falls back to a
  warning-emitting path on encoding error]** Not in this file
  directly, but psql's stderr surface during Tab is suppressed —
  any libpq warning fires into the void. Severity: nit (defense in
  depth, not exploitable).

## Cross-references

- Header: `knowledge/files/src/bin/psql/tab-complete.h.md`.
- Generator: `source/src/bin/psql/gen_tabcomplete.pl`
  (preprocesses `.in.c` → `.c`).
- Escape primitives: `source/src/interfaces/libpq/fe-exec.c`
  (`PQescapeStringConn`).
- Multibyte: `source/src/common/wchar.c` (`PQmblenBounded`).
- Readline install / startup: `source/src/bin/psql/startup.c`.
- Multi-line buffer producer: `source/src/bin/psql/mainloop.c`
  (writes to `tab_completion_query_buf`).
- Catalog-OID constants: `source/src/include/catalog/pg_am_d.h` and
  `pg_class_d.h` (included for `AMOID_*` and `RELKIND_*`
  CppAsString2 expansion).

<!-- issues:auto:begin -->
- [Issue register — `psql`](../../../../issues/psql.md)
<!-- issues:auto:end -->

## Confidence tag tally
`[verified-by-code]=22 [from-comment]=6 [inferred]=5 [unverified]=0`

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new index access method](../../../../scenarios/add-new-index-am.md)
- [Scenario — Add a new SQL keyword](../../../../scenarios/add-new-sql-keyword.md)
- [Scenario — Add a new utility statement](../../../../scenarios/add-new-utility-statement.md)

<!-- scenarios:auto:end -->
