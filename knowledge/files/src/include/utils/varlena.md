# utils/varlena.h — text/string-comparison helpers (NOT the varlena header format)

Source: `source/src/include/utils/varlena.h` (56 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Misnomer: this header does NOT define the varlena on-disk format (that lives in `c.h` / `varatt.h`). It declares the public API for text comparisons, identifier splitting, Levenshtein distance, regex replacement, and "closest match" suggestion.

## Public API

- `varstr_cmp(arg1, len1, arg2, len2, collid)` (`varlena.h:19`) — collation-aware compare.
- `varstr_sortsupport` (`varlena.h:20`) — abbreviated-key + collation sortsupport.
- `varstr_levenshtein` / `varstr_levenshtein_less_equal` (`varlena.h:21-28`) — `trusted=true` allows arbitrary char costs; `false` rejects non-default insert/delete/sub costs (CVE-2017-7546-style? — see varlena.c).
- `textToQualifiedNameList`, `scan_quoted_identifier`, `scan_identifier`, `SplitIdentifierString`, `SplitDirectoriesString`, `SplitGUCList` (`varlena.h:29-38`) — identifier/list parsing.
- `replace_text_regexp` (`varlena.h:39-42`).
- `ClosestMatchState` + `initClosestMatch`/`updateClosestMatch`/`getClosestMatch` (`varlena.h:44-54`) — "did you mean" suggestion machinery.

## Invariants

- **INV-varstr-collation-required** [inferred]: `varstr_cmp` requires a valid `collid`; passing 0 / InvalidOid would assert in pg_locale lookup.
- **INV-levenshtein-trusted-flag** [verified-by-code, `varlena.h:24, 28`]: untrusted callers (i.e. SQL-level invocation) must pass `trusted=false`; the impl in varlena.c rejects non-default costs to bound work (DoS mitigation).
- **INV-ClosestMatchState-source-min-max-d** [verified-by-code, `varlena.h:44-50`]: caller sets `source`+`max_d` at init, `min_d` and `match` are updated as candidates are scored.

## Notable internals

- The header is unusually thin given the importance of `varstr_cmp` for sort + hash + ORDER BY collation correctness.
- `escape_json_with_len` and friends are NOT here — they live in `utils/json.h`.

## Trust-boundary / Phase-D surface

- **`varstr_levenshtein(... trusted=true ...)` should never be reached from SQL** (`varlena.h:24, 28`): the trust flag exists specifically to prevent users from supplying massive ins/del/sub costs to push the inner-loop work up. Any new caller must hardcode `trusted=false` unless it's an internal known-safe site.
- `SplitIdentifierString`, `SplitDirectoriesString`, `SplitGUCList` mutate the input buffer (write NULs in place); callers must not pass shared/const memory.

## Cross-refs

- `source/src/backend/utils/adt/varlena.c` — implementations.
- `c.h` / `varatt.h` — actual varlena header format (NOT this file despite the name).

## Issues

- `[ISSUE-DOC: filename is misleading (low)]` — readers expect varlena format here, get string-ops. A one-line header pointer to `varatt.h` would help.
- `[ISSUE-INVARIANT: trusted flag is foot-gun (medium)]` — `varstr_levenshtein(..., trusted=true)` should require a comment explaining why each callsite is safe; consider renaming to `_unbounded` or wrapping with a checked entry point.
