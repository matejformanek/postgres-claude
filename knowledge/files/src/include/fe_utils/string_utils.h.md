---
path: src/include/fe_utils/string_utils.h
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 69
depth: read
---

# `src/include/fe_utils/string_utils.h`

- **File:** `source/src/include/fe_utils/string_utils.h` (69 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-05)

## Purpose

Public API for the frontend string-quoting and name-pattern helpers implemented in
[[knowledge/files/src/fe_utils/string_utils.c]] — the single most security-relevant header in
`fe_utils`. It exports `fmtId`/`fmtQualifiedId` (identifier quoting), the `appendStringLiteral*`
family (SQL literal quoting), `appendShellString` (shell-argument quoting), `appendConnStrVal`
(conninfo-value quoting), and the `\d`-pattern engine `processSQLNamePattern` /
`patternToSQLRegex`. These are the chokepoints through which psql, pg_dump, pg_amcheck, and the
bin/scripts tools build injection-safe SQL and shell commands. `[verified-by-code]`

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `quote_all_identifiers` | :23 | Global: force-quote even non-reserved identifiers (mirrors backend GUC). |
| `getLocalPQExpBuffer` | :24 | Function-pointer global: returns the rotating scratch buffer `fmtId` writes into. |
| `fmtId` / `fmtIdEnc` | :27-28 | Quote a raw identifier (encoding-aware variant). |
| `fmtQualifiedId` / `fmtQualifiedIdEnc` | :29-30 | Quote `schema.id`. |
| `setFmtEncoding` | :31 | Set the encoding used by the non-`Enc` variants. |
| `formatPGVersionNumber` | :33 | Render a numeric version into `maj.min` text. |
| `appendStringLiteral` / `Conn` / `DQ` | :36-41 | SQL string-literal quoting (server-version/std_strings/dollar-quote aware). |
| `appendByteaLiteral` | :42 | Quote a bytea constant. |
| `appendShellString` / `NoError` | :46-47 | Shell-argument quoting (`pg_fatal` vs bool-return on unsafe input). |
| `appendConnStrVal` | :48 | Quote a value for a libpq conninfo string. |
| `appendPsqlMetaConnect` | :49 | Build a `\connect` meta-command line. |
| `parsePGArray` / `appendPGArray` | :51-52 | Parse/emit a backend array literal. |
| `appendReloptionsArray` | :54 | Expand a `reloptions` text[] into `name=value` SQL. |
| `processSQLNamePattern` | :57 | Translate a `\d`-style pattern into a WHERE clause (the chokepoint). |
| `patternToSQLRegex` | :64 | Lower-level: split a dotted pattern into db/schema/name regexes. |

## Internal landmarks

- `fmtId` writes into a **shared rotating buffer** obtained via the `getLocalPQExpBuffer`
  function pointer (`:24`) — the indirection lets pg_dump swap in its own per-thread buffer.
  The return value is `const char *` pointing into that buffer. `[verified-by-code]`
- `processSQLNamePattern` (`:57-62`) is the multi-arg entry every `\d*`/`-t`/`-n` pattern
  flows through; it parameterizes schema/name/visibility and writes a safe WHERE clause. The
  A4 sweep identified it as the single chokepoint for `\d*` pattern injection. `[verified-by-code]`

## Invariants & gotchas

- **`fmtId` return-value lifetime is a one-call window.** Because the result aliases the shared
  `getLocalPQExpBuffer` buffer, `printf("%s.%s", fmtId(a), fmtId(b))` silently prints `b.b` —
  the second call clobbers the first. Callers must consume the result before the next `fmtId`.
  No compile-time guard. This is the canonical fmtId footgun (tracked in
  `knowledge/issues/fe_utils.md` row `string_utils.c:44`). `[verified-by-code]`
- `appendShellString` safety rests entirely on the `.c`-side `strspn` allowlist + single-quote
  wrapping (register row `string_utils.c:600`); the header gives no hint, so a caller cannot
  tell from the signature that the input set is constrained. `[verified-by-code]`
- `getLocalPQExpBuffer` is a *mutable function pointer*: pg_dump reassigns it at startup to a
  thread-local buffer so parallel dump workers don't share `fmtId` state. A consumer that
  never sets it gets the default single static buffer. `[inferred]`

## Cross-refs

- Implementation + the live issue rows: [[knowledge/files/src/fe_utils/string_utils.c]],
  `knowledge/issues/fe_utils.md` (§Notes "Identifier-quoting chokepoint").
- Proposed consolidation: `knowledge/idioms/safe-sql-identifiers.md` (would join
  `processSQLNamePattern` + `patternToSQLRegex` + backend `quoteOneName`).

## Potential issues

None new at the header level — the load-bearing invariants (`fmtId` buffer lifetime,
`appendShellString` allowlist) are already tracked against `string_utils.c` in
`knowledge/issues/fe_utils.md`. Cross-linked rather than re-filed.
