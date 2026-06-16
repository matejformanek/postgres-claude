---
path: src/bin/psql/describe.c
anchor_sha: 4b0bf0788b0
loc: 7699
depth: deep
---

# describe.c

- **Source path:** `source/src/bin/psql/describe.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 7699 (largest file in `src/bin/psql/` by a wide margin)

## Purpose

Backend of every `\d*` family backslash command in psql. Each
function builds a `pg_catalog.*` SELECT against the server connection,
runs it via `PSQLexec(buf.data)` (defined in `common.c`), and feeds
the result into `printQuery()` for tabular display. The contract
(`describe.c:4-8`):

> all functions in this file will succeed when working with servers
> of versions 9.2 and up. It's okay to omit irrelevant information
> for an old server, but not to fail outright. (But failing
> against a pre-9.2 server is allowed.)

So `pset.sversion >= NNNNN` gates appear on roughly every other
function (101 `pset.sversion` references). [from-comment, describe.c:4-8;
verified-by-code, grep]

## Role in psql

`command.c::exec_command_d` (and siblings `_l`, `_z`, `_dF*`, …)
parses the slash-command argv, then jumps into one of the `describe*`/
`list*` entry points declared in `describe.h`. Each entry point returns
`bool`; the caller propagates that as the command result. Every query
is run synchronously through `PSQLexec` — there is no streaming or
cursor here, results are buffered server-side and pulled in full.
[inferred from describe.c:131-142 idiom; verified-by-code, common.c
`PSQLexec`]

## Key functions

| Slash command | Function | File:line |
|---|---|---|
| `\da` | `describeAggregates` | 78 |
| `\dA` | `describeAccessMethods` | 149 |
| `\db` | `describeTablespaces` | (extern only here) |
| `\df / \dfa / \dfn / \dft / \dfw` | `describeFunctions` | ~280 |
| `\dT` | `describeTypes` | ~700 |
| `\do` | `describeOperators` | ~900 |
| `\du / \dg` | `describeRoles` | ~1100 |
| `\d <name>` | `describeTableDetails` → `describeOneTableDetails` | 1503, 1588 |
| `\dt / \di / \ds / …` | `listTables` | 4237 |
| `\dP` | `listPartitionedTables` | |
| `\dn` | `listSchemas` | |
| `\dx` | `listExtensions` | |
| `\dRp+` | `describePublications` | 6843 area |
| `\dRs` | `describeSubscriptions` | 7103 area |
| (helper, file-static) | `validateSQLNamePattern` | 6631 |
| (helper, file-static) | `map_typename_pattern` | (early) |

`describeOneTableDetails` (1588) is the monster — ~800 LOC of
context-sensitive SELECTs for one relation: pg_class flags, attrs,
constraints, indexes, rules, triggers, partitioning, policies, FDW
options, ACL footers. The comment at 1583-1585 acknowledges "the
information presented here is so complicated that it cannot be done
in a single query." [from-comment, describe.c:1581-1586]

## SQL-assembly discipline

### Pattern-input path — `validateSQLNamePattern`

Every `\d*` query that takes a user pattern funnels through
`validateSQLNamePattern(buf, pattern, have_where, force_escape,
schemavar, namevar, altnamevar, visibilityrule, &added_clause,
maxparts)` (6631). It wraps `processSQLNamePattern(pset.db, buf,
pattern, …)` from `fe_utils/string_utils.c` and adds (a) a dot-count
check (`maxparts` — typically 2 or 3, more for `\df` with arg patterns)
that rejects "too many dotted names" and (b) a cross-database-reference
check (`if (strcmp(PQdb(pset.db), dbbuf.data) != 0)` → "cross-database
references are not implemented"). [verified-by-code, describe.c:6620-6675]

`processSQLNamePattern` itself is the central escape boundary. It
converts `pattern` into LIKE / regex predicates appended to `buf`,
with **encoding-aware quoting via `PQescapeStringConn` and
`appendStringLiteralConn`** (see `string_utils.c`). Pattern fragments
become string-literal LIKE values — they never become identifiers in
the assembled SQL. This is the key Phase-D-relevant invariant:
**`\d "foo'; DROP TABLE bar; --"` produces a SELECT whose WHERE
predicate compares `c.relname LIKE 'foo''; DROP TABLE bar; --'` — the
pattern is a value, not interpolated code.** [verified-by-code,
fe_utils/string_utils.c processSQLNamePattern; inferred from
describe.c usage pattern]

### Second-pass identifier path — `describeOneTableDetails` → schema.relname

After `describeTableDetails` resolves a user pattern to one or more
(oid, nspname, relname) rows, it calls `describeOneTableDetails` with
the server-returned `schemaname`/`relationname` strings. These are
used in:

- **Display only** (printfPQExpBuffer for the title at 1917, 1920,
  1972, 2140-2192, 2430-2431) — printed into the `printTable` title
  via `%s`. Server-supplied; if a malicious owner crafts a relname
  with newlines / ANSI escapes, the title prints them. Not a SQL
  injection. [verified-by-code]
- **SQL identifier** at 1827-1829: the only place schemaname /
  relationname are spliced back into SQL:
  ```
  appendPQExpBuffer(&buf, "FROM %s", fmtId(schemaname));
  /* must be separate because fmtId isn't reentrant */
  appendPQExpBuffer(&buf, ".%s;", fmtId(relationname));
  ```
  This is the canonical `fmtId` two-call idiom (cf.
  `dumputils.c::emitShSecLabels`). `fmtId` quote-escapes per
  PG identifier rules — safe even for crafted names. [verified-by-code,
  describe.c:1825-1830]

### OID path — `%s` with `oid` string

The bulk of `describeOneTableDetails` subqueries use the OID
(server-returned `PQgetvalue(res, i, 0)` from the first pass) as
`WHERE c.oid = '%s'` (e.g. 1662, 1958, 2420, 2444, …). That's a string
representation of an integer OID returned by the server in the prior
SELECT — never user input. Not parameterized, but safe by source.
[verified-by-code, describe.c:1662, 2420]

### Catalog OID / kind constants

Heavy use of `CppAsString2(PROKIND_AGGREGATE)`,
`CppAsString2(RELKIND_RELATION)`, etc. — the `_d.h` catalog headers
expose these constants at psql build time. Examples 106, 356-358,
698, 1076, 2451-2459. [verified-by-code]

That means the psql binary is locked to the catalog-constant set that
existed when it was compiled. **Talking to a server with a newer
relkind / prokind code that this psql doesn't know about: the SELECT
runs (no SQL error), but the CASE WHEN won't match the new value and
the column will display blank or "?".** [inferred from CppAsString2
expansion + WHERE clauses]

## Tab-completion specifics

N/A — this file is the `\d*` backend, not the readline completer.

## Phase D notes

- **Pattern parsing is the trust boundary** for the user-supplied
  pattern, and `processSQLNamePattern` handles it correctly (encoding-
  aware escaping via `PQescapeStringConn`). The whole `\d*` family
  is therefore safe from user-pattern SQL injection. [verified-by-code,
  via string_utils.c]
- **Server-supplied identifier round-trip** is also safe: the only
  place a server-returned name is re-spliced into SQL (1827-1829)
  goes through `fmtId`. Other server-returned names are used only
  for display titles (`printfPQExpBuffer`). [verified-by-code]
- **Hardcoded catalog OID constants** are a forward-compatibility
  liability: a psql linked against PG N talking to a PG N+M server
  with a new `relkind`/`prokind`/`amtype` will silently produce
  incomplete output (CASE WHEN falls through). The contract at the
  top of the file (4-8) explicitly only covers ≥9.2 servers and only
  guarantees graceful degradation on OLD servers — newer-server
  behavior is undefined. [inferred + from-comment, describe.c:4-8]
- **`PSQLexec` returns NULL** on error and most callers do a clean
  `termPQExpBuffer + return false`. A few paths use `goto error_return`
  with elaborate cleanup (`describeOneTableDetails` 1593 has 14
  `goto error_return` points before the actual label). One missing
  goto would leak a `PGresult`/PQExpBuffer; not a security issue, but
  a recurring footgun. [verified-by-code, describe.c:1588-2200]
- **`cancel_pressed` polling** inside the for-loop of
  `describeTableDetails` (1569) and elsewhere lets Ctrl-C interrupt
  the multi-relation expansion. Polled, not signal-async — safe.
  [verified-by-code]
- **`relam` and AM-name display** is suppressed when `pset.hide_tableam`
  is set (`HIDE_TABLEAM` env / psql variable). That's a UI nicety, not
  a security feature — the SELECT still runs and ships the AM name to
  the client. [inferred, verified by grep of `hide_tableam`]
- **No use of `appendStringLiteralConn` in describe.c** for
  user-supplied strings — confirms the design choice that patterns
  go through `processSQLNamePattern` (which uses it internally) and
  identifiers go through `fmtId`. [verified-by-code, grep]
- **Untranslated column-header strings** are wrapped in
  `gettext_noop` (e.g. `"Schema"`, `"Name"`, `"Owner"`). They are
  later translated by `printQuery` when `translate_header = true` is
  set on the `printQueryOpt`. [verified-by-code, describe.c:96-99]
- **`map_typename_pattern`** (file-static, near top of file) — handles
  the legacy alias case where `\dT "char"` and `\dT character` should
  both resolve to the underlying type. This rewrites the pattern
  string BEFORE handing it to `processSQLNamePattern`, but only for a
  small whitelist of known synonyms. Not a Phase D concern — the
  rewrite is to canonical pg_type-syntax forms, not SQL fragments.
  [inferred from function name + usage]

## Potential issues

- **[ISSUE-undocumented-invariant: hardcoded RELKIND_/PROKIND_/AMTYPE_
  constants assume catalog-stable values]** `describe.c` (many sites,
  e.g. 106, 356-358, 1076) — adding a new relkind/prokind/amtype on
  the server side requires recompiling psql to recognize it. Older
  psql talking to newer server silently displays blanks in the
  affected column. Severity: maybe (architectural; the contract only
  promises graceful degradation on OLDER servers).
- **[ISSUE-info-disclosure: server-supplied relnames printed unquoted
  in printTable titles]** `describe.c:1917-2192` etc. — a hostile
  owner can craft a relname containing ANSI escapes or newlines that
  corrupt the terminal display when another role runs `\d` on it.
  The same hazard exists in pg_dump (TOC sanitize handles dump-script
  case; psql's interactive `\d` does not sanitize). Severity: maybe
  (terminal-spoof class, well-known).
- **[ISSUE-correctness: 14 `goto error_return` sites in
  `describeOneTableDetails`]** `describe.c:1588-2200` — large
  cognitive load to verify every error path frees `cont` /
  `printTableInitialized` / `tmpbuf` etc. Not a known bug but a
  fragility hot-spot. Severity: nit.
- **[ISSUE-trust-boundary: cross-database reference check in
  `validateSQLNamePattern` compares `PQdb(pset.db)` to the parsed
  database part]** `describe.c:6655-6667` — the comparison is byte-for-
  byte `strcmp`. If the database name contains characters that
  `processSQLNamePattern` normalizes (case folding, quote stripping),
  a mismatch could throw a misleading "cross-database references are
  not implemented" instead of the actual reason. Severity: nit.
- **[ISSUE-undocumented-invariant: `pset.sversion` gates assume
  `sversion` is reliable]** `describe.c` (101 sites) — `pset.sversion`
  is set from `PQserverVersion(pset.db)`, which reads the server's
  reported version. A man-in-the-middle protocol attack could lie
  about server version to coax the older code paths (less-strict
  pg_catalog queries) out of psql. Severity: maybe (requires SSL
  bypass; cross-references to libpq trust model).
- **[ISSUE-dos: no LIMIT clause on `\d` pattern queries]** Unlike
  `tab-complete.in.c` (1000-row LIMIT), the `\d*` queries return
  all matches. A pattern matching a million-row catalog
  (e.g. `\dt pg_temp*` on a busy server with thousands of temp
  schemas) loads the entire result set into memory. Severity:
  nit (user controls pattern; documented behavior).
- **[ISSUE-stale-todo: 9.2 minimum-version contract]** `describe.c:4-8`
  — the comment says "9.2 and up", but pg_dump's `minRemoteVersion =
  90200` is the canonical floor. Different binaries have drifted
  on the support floor before; worth a synchronized bump when
  pre-9.2 is finally dropped. Severity: nit.
- **[ISSUE-undocumented-invariant: `fmtId` non-reentrancy comment is
  the only marker]** `describe.c:1828` — "must be separate because
  fmtId isn't reentrant". If a future edit collapses these two
  appends into one statement (`appendPQExpBuffer(&buf, "FROM %s.%s",
  fmtId(s), fmtId(r))`), the second `fmtId` overwrites the static
  buffer the first one returned. Caught by code review historically;
  no compiler-level guard exists. Severity: nit (latent).

## Cross-references

- Header: `knowledge/files/src/bin/psql/describe.h.md`.
- Pattern parsing: `source/src/fe_utils/string_utils.c`
  (`processSQLNamePattern`, `appendStringLiteralConn`,
  `PQescapeStringConn`).
- Identifier quoting: `source/src/fe_utils/string_utils.c::fmtId`.
- Common SQL-exec wrapper: `source/src/bin/psql/common.c::PSQLexec`.
- Slash dispatch: `source/src/bin/psql/command.c` (`exec_command_d`,
  `exec_command_l`, `exec_command_z`).

<!-- issues:auto:begin -->
- [Issue register — `psql`](../../../../issues/psql.md)
<!-- issues:auto:end -->

## Confidence tag tally
`[verified-by-code]=20 [from-comment]=4 [inferred]=6 [unverified]=0`
