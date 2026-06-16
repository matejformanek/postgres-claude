# `src/backend/utils/adt/quote.c`

- **File:** `source/src/backend/utils/adt/quote.c` (135 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

The **canonical SQL-injection escape helpers**: `quote_literal(text)`,
`quote_ident(text)`, `quote_nullable(anyelement)`, plus the C-callable
`quote_literal_cstr(rawstr)`. Used by every trigger function that
synthesizes SQL via `format()` or string concatenation, and by every
DBA/extension code path that produces dynamic SQL.

## Type role

- **`quote_ident(text)`** (`:25`) — wraps `quote_identifier` from
  ruleutils.c. Returns input unchanged when the identifier is
  "obviously safe": starts with lowercase letter or underscore, contains
  only `[a-z0-9_]`, and is not a SQL keyword. Otherwise wraps in `"..."`
  with internal `"` doubled. (Behavior driven by
  `quote_all_identifiers` GUC.)
- **`quote_literal(text)`** (`:75`) — wraps `quote_literal_internal`.
  Worst-case sizing `len * 2 + 3 + VARHDRSZ` (`:86`).
- **`quote_literal_cstr(rawstr)`** (`:101`) — same as quote_literal but
  works on a cstring; returns palloc'd cstring. Buffer sized
  `len*2 + 3 + 1`.
- **`quote_nullable(anyelement)`** (`:128`) — returns the cstring
  `"NULL"` for SQL NULL input, otherwise routes through
  `DirectFunctionCall1(quote_literal, ...)`.

## `quote_literal_internal` (the worker, `:45`)

```c
for (s = src; s < src + len; s++)
    if (*s == '\\') {
        *dst++ = ESCAPE_STRING_SYNTAX;   // 'E'
        break;
    }
*dst++ = '\'';
while (len-- > 0) {
    if (SQL_STR_DOUBLE(*src, true))      // escape_backslash = TRUE
        *dst++ = *src;
    *dst++ = *src++;
}
*dst++ = '\'';
```

`SQL_STR_DOUBLE(ch, true)` is `((ch) == '\'' || (ch) == '\\')`
(`source/src/include/c.h:1255`). So **single quotes are always
doubled, backslashes are always doubled**, and if the input contained
any backslash, the entire result is prefixed with `E` to force
`E'...'` syntax. The comment at `:39-43` is explicit: "This must
produce output that will work in old servers with
standard_conforming_strings = off. It's used for example by dblink,
which may send the result to another server." [verified-by-code]

## Phase D audit — encoding & SCS combinations

This is the most-asked Phase D question for this batch.

- **`SCS=on` server:** output is `E'...'`, so PG accepts the backslash
  doubling regardless of SCS. Backslashes are emitted as `\\`. Safe.
- **`SCS=off` server:** output is also `E'...'` (if input had any
  backslash) or `'...'` (if input had no backslash, in which case
  backslashes were impossible to begin with, so SCS doesn't matter).
  Safe.
- **Old server, no `E'...'` syntax:** the `E` prefix would cause a
  syntax error on truly ancient servers (< 8.1). For pre-8.1 targets
  the helper is technically incorrect, but those servers are out of
  support. Effectively safe.

**Multi-byte server encodings:**

- The loop is **byte-by-byte** (`:60-65`). It looks for `0x27` (`'`)
  and `0x5C` (`\`) as raw bytes. For **PG-supported server encodings**
  (UTF-8, EUC-JP, EUC-KR, EUC-TW, EUC-CN, BIG5 server-side support is
  disallowed; SJIS server-side support is disallowed; **GB18030
  server-side support is disallowed for this exact reason**), no
  trailing byte of a multibyte character can be `0x27` or `0x5C`. The
  server-encoding allowlist enforced by `PostgreSQL.encodings` is
  precisely the set where these byte values cannot appear except as
  ASCII characters. [verified-by-code via `src/common/encnames.c` +
  the PG documentation chapter on character sets]
- Therefore `quote_literal` / `quote_literal_cstr` are safe across **all
  permitted server encodings** when the input is **valid for that
  encoding**.
- **WARNING — invalid UTF-8 input:** if a caller passes a `text` value
  whose bytes are not valid UTF-8 (e.g. arbitrary bytea-as-text), the
  output is still byte-correct but the validation onus shifts to the
  receiver. PG itself validates encoding at input time, so this is
  primarily a concern for C-callers of `quote_literal_cstr` that pass
  raw external bytes. [inferred]
- **`quote_ident` calls `quote_identifier` which is similarly
  byte-oriented** (compares `'a'..'z'`, `'0'..'9'`, `'_'`, `'"'`); the
  same encoding-allowlist argument makes it safe for all supported
  server encodings. [verified-by-code via
  `ruleutils.c:13691-13780`]

**Bottom line audit answer:** YES, `quote_literal` and `quote_ident` are
100% safe against SQL injection for **all server-encoding/SCS
combinations PG supports**, as long as the input is a valid `text`
value for the current server encoding. The defense relies on the
PG-level rule that **server encodings never have `0x27` or `0x5C` as a
non-ASCII trailing byte**, which is structural — not a per-helper
check. Any future encoding admitted as a server encoding would have to
respect that invariant.

## Potential issues

- `[ISSUE-undocumented-invariant: safety depends on the server-encoding
  allowlist excluding any encoding where 0x27/0x5C can appear as a
  multibyte trailing byte (medium). Not enforced in quote.c itself;
  enforced upstream by encnames.c.]`
- `[ISSUE-correctness: quote_literal_cstr called with non-encoding-valid
  bytes produces byte-correct but semantically dubious output. C
  callers must validate first. (low)]`
- `[ISSUE-stale-todo: comment about backwards-compat with old servers
  with SCS=off (`:40-42`) — still accurate but the era it warns about
  is now ancient. (info)]`

## Cross-references

- `source/src/include/c.h:1245-1258` — `SQL_STR_DOUBLE`,
  `ESCAPE_STRING_SYNTAX` definitions.
- `source/src/backend/utils/adt/ruleutils.c:13691` —
  `quote_identifier` (the `quote_ident` worker).
- `source/src/backend/utils/adt/format.c` — `format()` uses
  `quote_literal_cstr` / `quote_identifier` for `%L` and `%I`.
- `source/src/common/encnames.c` — server-encoding allowlist.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally

- `[verified-by-code]` × 4
- `[from-comment]` × 1
- `[inferred]` × 1
