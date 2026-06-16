# `src/fe_utils/string_utils.c`

- **File:** `source/src/fe_utils/string_utils.c` (1387 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-04)

## Purpose

The identifier-quoting and SQL-name-pattern chokepoint shared by `psql`,
`pg_dump`/`pg_dumpall`/`pg_restore`, and most `src/bin/scripts` utilities. It
provides the routines that take untrusted text (object names, string values,
bytea, shell arguments, connection-string values, database names) and emit
correctly quoted/escaped SQL or shell fragments into a `PQExpBuffer`. It also
implements `processSQLNamePattern`/`patternToSQLRegex`, which translate the
shell-style `\d foo*` patterns into anchored SQL regular expressions used in
`WHERE` clauses. As frontend code it allocates with `pg_malloc`/`createPQExpBuffer`
(not `palloc`) and has no access to backend catalogs, so quoting decisions are
made from a hard-coded copy of the scanner rules plus the shared keyword list
(`common/keywords.h`). [verified-by-code: includes at `string_utils.c:16-22`]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `quote_all_identifiers` | :27 | Global int; when set, `fmtIdEnc` quotes every identifier. Mirror of the backend GUC. |
| `getLocalPQExpBuffer` | :28 | Function pointer (default `defaultGetLocalPQExpBuffer`) returning the shared scratch buffer for `fmtId`. Overridable for thread-safety. |
| `setFmtEncoding` | :69 | Set the process-global encoding used by `fmtId`/`fmtQualifiedId`. |
| `fmtIdEnc` | :101 | Quote an identifier if needed, with explicit encoding. The core worker. |
| `fmtId` | :248 | `fmtIdEnc` using the process-global encoding (`getFmtEncoding`). |
| `fmtQualifiedIdEnc` | :263 | `schema.id` with per-part quoting, explicit encoding. |
| `fmtQualifiedId` | :296 | As above, process-global encoding. |
| `formatPGVersionNumber` | :313 | Render `PQserverVersion()` int into a caller-supplied buffer. |
| `appendStringLiteral` | :351 | Append SQL string literal; explicit encoding + `std_strings`. No PGconn. |
| `appendStringLiteralConn` | :446 | Same, but escaping rules taken from a live `PGconn` (`PQescapeStringConn`). |
| `appendStringLiteralDQ` | :484 | Dollar-quote a string, choosing a non-colliding delimiter. |
| `appendByteaLiteral` | :527 | Hex-format `bytea` literal. |
| `appendShellString` | :576 | Shell-quote one argument; `pg_fatal`-style die on LF/CR. |
| `appendShellStringNoError` | :588 | As above but strips LF/CR and returns false instead of exiting. |
| `appendConnStrVal` | :692 | Quote a value for a libpq keyword/value connection string. |
| `appendPsqlMetaConnect` | :737 | Emit a `\connect` meta-command for a given dbname. |
| `parsePGArray` | :813 | Parse `{a,b,c}` array text into a `char **`. |
| `appendPGArray` | :896 | Append one element to array text, with `array_out`-matching quoting. |
| `appendReloptionsArray` | :960 | Render a reloptions array as `name=value, ...`. |
| `processSQLNamePattern` | :1047 | Turn a name pattern into `WHERE` clauses appended to a query buffer. |
| `patternToSQLRegex` | :1219 | Turn a (possibly qualified) shell pattern into up to 3 anchored SQL regexps. |

## Internal landmarks

- `defaultGetLocalPQExpBuffer:42` — returns a single `static` `PQExpBuffer`,
  reset on each call. This is why every `fmtId`/`fmtQualifiedId` doc comment warns
  "use the result before calling again." [verified-by-code:44-57]
- `fmtIdEncoding` static + `getFmtEncoding:78` — process-global encoding. In
  assertion builds an unset encoding trips `Assert(fmtIdEncoding != -1)`; in
  production it silently defaults to `PG_UTF8`. [verified-by-code:80-91]
- `fmtIdEnc:101` quoting decision tree: (1) `quote_all_identifiers`; (2) first
  char not `[a-z_]`; (3) any char not `[a-z0-9_]`; (4) `ScanKeywordLookup` against
  `ScanKeywords` where category != `UNRESERVED_KEYWORD`. The char checks are
  deliberately ASCII-range comparisons "to match the identifier production in
  scan.l. Don't use islower()." [from-comment:111-112, verified-by-code:113-148]
- `fmtIdEnc` multibyte handling (`:180-228`): for high-bit bytes it validates the
  multibyte char via `pg_encoding_mblen` + `pg_encoding_verifymbchar`; an invalid
  sequence is replaced in-place with `pg_encoding_set_invalid` so the server
  rejects it, rather than silently passing bytes that could "skip" over a quote
  char. Embedded `"` is doubled per SQL99. [from-comment:186-202, verified-by-code:172-228]
- `appendStringLiteral:351` mirrors libpq's `PQescapeStringInternal`; same
  invalid-multibyte-replacement trick (`:410`). Buffer pre-sized to `2*length+2`
  (`:359`). `SQL_STR_DOUBLE` doubles a quote/backslash depending on `std_strings`.
- `appendStringLiteralConn:446` carries an explicit kluge (`:451-463`): if the
  string contains a backslash and the server is `< 190000`, it prefixes an
  `ESCAPE_STRING_SYNTAX` (`E''`) literal to silence `escape_string_warning`.
  Marked to be removed once pre-v19 servers are unsupported. [from-comment:451-453]
- `appendStringLiteralDQ:484` picks a `$tag$` delimiter, extending it from a fixed
  `"_XXXXXXX"` suffix table until `strstr` confirms it does not appear in `str`
  (without trailing `$`). [verified-by-code:486-512]
- `appendShellStringNoError:588` — a fast path emits the string verbatim if it is
  nonempty and matches `strspn(... safe-set ...)==len` (`:600-605`). The non-WIN32
  branch single-quotes and renders embedded `'` as `'"'"'`. The WIN32 branch
  (`:623-681`) does caret + backslash-doubling for cmd.exe and CommandLineToArgvW.
  LF/CR are dropped and force `ok=false`. [verified-by-code]
- `appendConnStrVal:692` — quotes with single quotes (escaping `'` and `\` with
  backslash) unless the value is purely `[A-Za-z0-9_.]`. [verified-by-code:702-728]
- `appendPsqlMetaConnect:737` — LF/CR in dbname is fatal (`:751-757`). For
  "complex" names it forces `\encoding SQL_ASCII`, builds a `dbname=<connstrval>`
  string, then wraps it with `fmtIdEnc(..., PG_SQL_ASCII)` and `\connect
  -reuse-previous=on`. The encoding is forced to SQL_ASCII so psql forwards the
  bytes unchanged. [from-comment:772-788, verified-by-code]
- `patternToSQLRegex:1219` is a small state machine over `inquotes`/`left`,
  emitting into `buf[0..2]` (db/schema/name). `*` → `.*`, `?` → `.`, `.` splits to
  the next buffer (or is literal once `maxbuf` is hit), unquoted uppercase is
  `pg_tolower`'d, and `$` is always backslash-escaped (`:1326`). Outside quotes,
  regexp metacharacters pass through unless `force_escape`; `[]` is always escaped
  to favor array-type-name interpretation. The `left_literal` buffer captures the
  un-regexp'd db-name when `want_literal_dbname`. Result regexps are anchored
  `^(...)$`. [from-comment:1192-1196, verified-by-code:1260-1387]
- `processSQLNamePattern:1047` wraps `patternToSQLRegex` and emits
  `OPERATOR(pg_catalog.~)` comparisons, always schema-qualifying operators against
  a hostile `search_path`, with a `COLLATE pg_catalog.default` appended for servers
  `>= 120000`. The `WHEREAND()` macro (`:1058`) tracks whether a `WHERE`/`AND` was
  already emitted. A literal `"^(.*)$"` is optimized away. [from-comment:1093-1102]

## Invariants & gotchas

- **Single shared return buffer.** `fmtId`, `fmtIdEnc`, `fmtQualifiedId`,
  `fmtQualifiedIdEnc` all return a pointer into one `static` buffer
  (`defaultGetLocalPQExpBuffer`). Nesting two live `fmtId` results, or holding one
  across another call, corrupts the first. `fmtQualifiedIdEnc` works around this by
  building into a freshly `createPQExpBuffer`'d local first, then copying into the
  shared buffer last (`:266-280`). [verified-by-code]
- **Encoding must be set first.** `fmtId`/`fmtQualifiedId` rely on a prior
  `setFmtEncoding()` call. Without it, assert builds fail and production silently
  assumes UTF-8 — which can mis-handle multibyte boundaries. Prefer the explicit
  `*Enc` variants. The file comment says "Eventually we should get rid of
  fmtId()." [from-comment:60-66, 89-91]
- **Quoting depends on the server-encoding allowlist only indirectly.** The
  multibyte safety in `fmtIdEnc`/`appendStringLiteral` comes from
  `pg_encoding_verifymbchar` + in-place `pg_encoding_set_invalid`, NOT from a
  client/server-encoding match. An invalid sequence is deliberately left invalid so
  the *server* errors out, since the frontend cannot raise a SQL error itself.
  [from-comment:186-202, 390-409]
- **Memory ownership (frontend).** Buffers come from `createPQExpBuffer` /
  `initPQExpBuffer` and must be freed by `destroyPQExpBuffer` / `termPQExpBuffer`.
  `parsePGArray` returns one `malloc`'d block; freeing `*itemarray` frees
  everything (`:810`). `appendReloptionsArray` must `free(options)` even on the
  parse-failure path (`:967-971`). All allocation is `pg_malloc`/`malloc`, never
  `palloc`. [verified-by-code]
- **`appendByteaLiteral` is hard-wired to hex format** (`:536-540`) because the
  destination server version is unknown; pre-9.0 servers cannot read hex bytea.
  Doc comment flags this. [from-comment:535-540]
- **`appendPGArray` quoting must track `array_out`** (`:904`) and
  `appendReloptionsArray` must track backend `flatten_reloptions` (`:956-957`); a
  drift in either backend routine silently desyncs dump output. [from-comment]
- **`patternToSQLRegex` dot overflow is the caller's job.** If a pattern has more
  `.`-separated parts than buffers, extra dots become literal but are still counted
  in `*dotcnt`; callers must check `dotcnt` and report the error. [from-comment:1186-1191]

## Cross-references

- Consumed by `src/bin/psql/describe.c` (every `\d` query funnels through
  `processSQLNamePattern`) and `src/bin/psql/command.c` (`\connect` generation via
  `appendPsqlMetaConnect`).
- Consumed by `src/bin/pg_dump/pg_dump.c` / `dumputils.c` for identifier and
  string-literal quoting, and `pg_dumpall` for `appendConnStrVal` /
  `appendPsqlMetaConnect`.
- `source/src/include/fe_utils/string_utils.h` — declarations.
- `source/src/common/keywords.c` + `source/src/include/common/keywords.h` —
  `ScanKeywordLookup`, `ScanKeywords`, `ScanKeywordCategories` used at
  `string_utils.c:144-146`.
- `source/src/backend/parser/scan.l` — the identifier production the ASCII checks
  at `string_utils.c:111-126` deliberately mirror.
- `source/src/backend/utils/adt/ruleutils.c` — `flatten_reloptions`, the backend
  twin of `appendReloptionsArray` (`string_utils.c:956-957`).
- `source/src/interfaces/libpq/fe-exec.c` — `PQescapeStringConn` /
  `PQescapeStringInternal`, the libpq twin of `appendStringLiteral`.

<!-- issues:auto:begin -->
- [Issue register — `fe_utils`](../../../issues/fe_utils.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: fmtId callers must serialize use of the shared static buffer]** `string_utils.c:44` — every `fmtId`/`fmtIdEnc` return value aliases the same `static` buffer; a caller that does `printf("%s.%s", fmtId(a), fmtId(b))` silently prints `b.b`. This is documented per-function ("use the result before calling again") but there is no compile-time guard and the failure is silent. Established design, but a perennial footgun for new callers. (maybe)
- **[ISSUE-question: appendConnStrVal needquotes initialization]** `string_utils.c:701-711` — `needquotes` is set true before the loop, then set false on each fully-safe char and true-and-break on the first unsafe char. For an empty string the loop body never runs, leaving `needquotes = true`, so an empty value is quoted as `''` — which is the intended outcome, but the control flow (init true, last-iteration assignment decides) is non-obvious and easy to break in edits. Not a current bug. (nit)
- **[ISSUE-stale-todo: pre-v19 escape_string_warning kluge]** `string_utils.c:451-463` — `appendStringLiteralConn` carries a documented kluge gated on `PQserverVersion(conn) < 190000`, to be removed "once pre-v19 servers are out of support." Tracked in-comment; flagged so a future cleanup sweep can find it. (nit)
- **[ISSUE-undocumented-invariant: appendShellString safe-set is the security boundary]** `string_utils.c:600-605` — the shell-injection safety of `appendShellString` rests entirely on the `strspn` allowlist plus the single-quote wrapping; the allowlist excludes shell metacharacters by construction, so any future widening of that set (e.g. adding `~` or `=`) would be a real injection risk. Correct today, but the invariant is implicit. (maybe)

## Confidence tag tally

- `[verified-by-code]` × 19
- `[from-comment]` × 12
- `[inferred]` × 0
