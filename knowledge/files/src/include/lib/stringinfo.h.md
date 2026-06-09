# `src/include/lib/stringinfo.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 270

## Role

**The canonical text-construction sink in the backend.** Extensible
palloc-backed string buffer with sprintf-style append, binary
append, read-only views, and reset semantics. Every text-building
hot path in the backend uses this: `elog`/`ereport` message
formatters, `ruleutils` (catalog deparse), wire-protocol
formatters in `printtup`/`pqformat`, COPY input/output formatters,
SQL builders in contrib/dblink/postgres_fdw, JSON builder,
backup label builder, archive-recovery command formatters.
[from-comment] `source/src/include/lib/stringinfo.h:6-9`

## Public API (5 ways to create, ~12 append flavours)

[verified-by-code] header walks all creation forms in lines 58-100.

- Creation: `makeStringInfo()`, `makeStringInfoExt(initsize)`,
  `initStringInfo(&local)`, `initStringInfoExt(&local, initsize)`,
  `initReadOnlyStringInfo(&local, data, len)`,
  `initStringInfoFromString(&local, palloced_buf, len)`
- Append: `appendStringInfo(fmt, …)` (printf-style),
  `appendStringInfoVA(fmt, va_list)`, `appendStringInfoString`,
  `appendStringInfoChar`, `appendStringInfoCharMacro` (warning:
  multi-eval), `appendStringInfoSpaces`, `appendBinaryStringInfo`,
  `appendBinaryStringInfoNT` (no trailing NUL)
- Lifecycle: `resetStringInfo`, `enlargeStringInfo`,
  `destroyStringInfo`

`STRINGINFO_DEFAULT_SIZE = 1024` (line 112).

## Invariants

- INV-1: For non-read-only strings, `maxlen > len` always; there's
  a NUL terminator at `data[len]`. [from-comment]
  `source/src/include/lib/stringinfo.h:25-31`
- INV-2: Read-only mode = `maxlen == 0`. Read-only buffers may
  not be appended to or reset — runtime check in
  `enlargeStringInfo`/`resetStringInfo`.
- INV-3: 1 GB hard limit (`MaxAllocSize`). Beyond that,
  `enlargeStringInfo` raises `ereport(ERROR, …)`.
- INV-4: `appendStringInfoCharMacro` evaluates `str` multiple
  times — caller must pass a side-effect-free expression.
  [from-comment] line 229.

## Trust boundary (Phase D)

This is the **central text-construction sink for the entire
A13/A14 injection cluster**. The fundamental hazard:

- `appendStringInfo(s, "%s", untrusted_str)` produces a literal
  copy with NO quoting/escaping — caller must apply
  context-specific quoting (`quote_identifier`,
  `quote_literal_cstr`, JSON-escape, shell-escape) BEFORE the
  append.

Demonstrated abuses already in the corpus:

- A13 `contrib/tablefunc/tablefunc.c` — built SQL via
  `appendStringInfo` without `quote_identifier` for category
  values, leading to SQL injection in `crosstab`.
- A14 `src/backend/backup/basebackup_to_shell.c` — built a shell
  command via `appendStringInfo` without proper shell-quoting,
  leading to command injection.
- A7 `to_char` formatter — escape-sequence parsing builds a
  StringInfo from `cache_locale_time()` output trusted to be
  safe.

**Phase-D candidates** (not present in tree):

1. A `appendStringInfoQuotedIdentifier(s, ident)` helper that
   always emits SQL-quoted identifier with embedded
   double-quotes doubled, paralleling `quote_identifier`.
2. A `appendStringInfoShellQuoted(s, arg)` helper for arbitrary
   shell-arg cases (basebackup_to_shell, archive_command).
3. A taint-tracking wrapper that flags a StringInfo as
   "tainted" if any append takes untrusted input, asserting in
   debug builds when fed to a SQL/shell sink.

[unverified] None of these exist in tree.

## Cross-refs

- `knowledge/files/contrib/tablefunc/tablefunc.c.md` (A13)
- `knowledge/files/src/backend/backup/basebackup_to_shell.c.md` (A14)
- `knowledge/files/src/backend/utils/adt/formatting.c.md` (A7
  to_char) — escape-sequence handling
- `knowledge/files/src/backend/utils/adt/ruleutils.c.md` — the
  largest in-tree consumer; uses `quote_identifier` correctly
  everywhere
- `knowledge/idioms/error-handling.md` (if exists) — ereport
  formatter uses StringInfo internally

## Issues

- ISSUE-DESIGN: header-level docs do not warn callers about the
  injection footgun of `appendStringInfo(s, "%s", untrusted)`.
  Adding a header comment block "Building SQL/shell strings:
  always pre-quote with `quote_identifier`/`quote_literal_cstr`/
  appropriate-escape-helper before passing to %s" would
  centralize the hard-learned A13/A14 lessons.
  Site: `source/src/include/lib/stringinfo.h:193-199` (the
  `appendStringInfo` doc block). (Medium — informational; the
  fixes happen in callers, but documenting at the API surface is
  cheap.)
- ISSUE-PHASE-D: no built-in quoting helpers in this API; callers
  reach for `quote_identifier` (in `utils/builtins.h`) or
  ad-hoc inline escaping. A future Phase-D might add typed
  `StringInfo` variants. (Informational.)
