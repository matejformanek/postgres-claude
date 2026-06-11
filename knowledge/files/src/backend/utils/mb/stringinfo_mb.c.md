# `src/backend/utils/mb/stringinfo_mb.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~86
- **Source:** `source/src/backend/utils/mb/stringinfo_mb.c`

Multibyte-encoding-aware `StringInfo` helpers, kept separate from
`src/common/stringinfo.c` so frontend users of the common StringInfo
don't have to link against multibyte tables. Currently exports a
single function. [verified-by-code] [from-comment]

## API

- `appendStringInfoStringQuoted(StringInfo str, const char *s, int maxlen)`
  — appends `s` to `str` wrapped in single quotes, with embedded
  apostrophes doubled (SQL literal escape). If `maxlen >= 0` and
  `strlen(s) > maxlen`, the input is clipped to `pg_mbcliplen(s,
  slen, maxlen)` so we never split a multibyte character mid-byte,
  and an `...` ellipsis is appended before the closing quote. [verified-by-code]

## Notable invariants / details

- The clipping path makes a `pnstrdup` copy so that `strchr` searches
  over a NUL-terminated bounded buffer; the `pfree` at line 85
  releases it. If `maxlen < 0` no copy is made and we search the
  caller's storage directly. [verified-by-code]
- The doubling loop searches for `'`, copies up to and *including*
  the apostrophe, then rewinds `chunk_copy_start` to that same
  apostrophe so the next `appendStringInfo` re-emits it — net effect:
  one `'` becomes `''`. [verified-by-code]
- The ellipsis form is `%s...'` (`...` glued before the closing
  quote), giving outputs like `'abc...'`. [verified-by-code]
- Used by `ereport` error contexts and `pg_get_*def` callers that
  want a safe quoted preview of a user string. The "safe quoting"
  guarantee depends on `pg_mbcliplen` — see encnames allowlist
  (server-encoding-only). [inferred]
- The result of `appendStringInfo("...%s...", chunk_copy_start)` at
  line 80/82 passes the **mutated** (clipping) or **original** (no
  clipping) string through `%s` once more — meaning any caller
  feeding a string containing `%` chars is safe only because
  `%s` itself never re-interprets the argument. [verified-by-code]

## Potential issues

- File-line: stringinfo_mb.c:80-82. `appendStringInfo("%s...'", …)` and
  `appendStringInfo("%s'", …)` rely on the fact that `chunk_copy_start`
  still contains apostrophes that have **not yet been doubled** for the
  trailing chunk. The loop exits once `strchr` returns NULL (no more
  `'`), so the tail by construction has no `'` — correct, but subtle.
  Worth a comment. [ISSUE-undocumented-invariant: the "tail has no
  apostrophe" invariant is implicit (nit)]
- File-line: stringinfo_mb.c:45. `strlen(s)` is called unconditionally
  even when `maxlen >= 0`; for very long `s` with small `maxlen` this
  wastes work scanning past the eventual clip point. Minor. [ISSUE-style:
  avoidable `strlen` when caller is about to cap (nit)]
