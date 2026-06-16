# `src/include/mb/stringinfo_mb.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~24
- **Source:** `source/src/include/mb/stringinfo_mb.h`

Single-function header — declares the multibyte-aware StringInfo
appender. The implementation in
`backend/utils/mb/stringinfo_mb.c` walks the input as multibyte and
escapes only valid lead/trail bytes (avoids splitting a multibyte
character with an embedded quote-escape). [verified-by-code]

## API / declarations

- `appendStringInfoStringQuoted(StringInfo str, const char *s,
  int maxlen)` — append `s` to `str` with SQL-quoting (double the
  embedded `'`); if `maxlen > 0`, truncate at that many CHARACTERS
  (not bytes) and append an ellipsis.

## Notable invariants / details

- Counterpart to the generic `appendStringInfoString` in
  `lib/stringinfo.h`, but encoding-aware — required when the input
  might be a multibyte string whose byte stream contains a value
  that *looks* like `'` (0x27) but is actually the trail of a
  multibyte character. Especially relevant for SJIS family.
  [inferred]
- Truncation is character-aware to avoid splitting mid-character.
  [inferred]

## Potential issues

- `maxlen` semantics (chars vs bytes) is not documented in the
  header; only conventional. [ISSUE-doc-drift: maxlen unit
  unspecified (nit)]
- Header is tiny and easy to overlook; callers default to the
  byte-level appender and silently corrupt SJIS output.
  [ISSUE-question: should the byte-level appender ereport on
  multibyte database encoding? (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-misc`](../../../../issues/include-misc.md)
<!-- issues:auto:end -->
