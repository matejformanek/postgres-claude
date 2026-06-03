# src/common/unicode_case.c

## Purpose

Implements the Unicode Default Case Conversion algorithm
(per UAX #21 / Unicode Standard §3.13) on UTF-8 strings — lower,
upper, title, casefold — for both single-codepoint and full-string
operation. The string path supports "full" Unicode case mappings
(one codepoint to many) and the Final_Sigma context-sensitive
mapping.

## Role in PG

Shared **frontend + backend**. Backend's "builtin" Unicode locale
provider (collprovider 'b') calls these for `lower()/upper()/initcap()`
without going through ICU. Backed by the generated
`unicode_case_table.h`.

## Key functions

- Codepoint-level: `unicode_lowercase_simple`,
  `unicode_titlecase_simple`, `unicode_uppercase_simple`,
  `unicode_casefold_simple`. (`unicode_case.c:49-79`)
- String-level: `unicode_strlower`, `unicode_strtitle`,
  `unicode_strupper`, `unicode_strfold`. All take
  `(dst, dstsize, src, srclen, bool full[, wbnext, wbstate])`,
  return required output size (callers may pass `dstsize=0` to
  size first then alloc and call again). `full=true` permits
  multi-codepoint expansion. (`unicode_case.c:99-190`)
- Internal `convert_case` — the workhorse loop: walks src by
  `utf8_to_unicode` + `unicode_utf8len`, calls `casemap()` per
  codepoint, dispatches on `CASEMAP_SELF` (raw copy), `CASEMAP_SIMPLE`
  (1→1), `CASEMAP_SPECIAL` (1→N up to `MAX_CASE_EXPANSION`).
  Title-casing toggles per-character casekind at word boundaries
  reported by the `WordBoundaryNext` callback.
  (`unicode_case.c:208-297`)
- `check_final_sigma` static — implements Unicode Table 3-17
  Final_Sigma condition by scanning backwards then forwards through
  the UTF-8 byte stream, skipping case-ignorable codepoints, until
  it finds a Cased character. (`unicode_case.c:307-359`)
- `check_special_conditions` — currently only supports
  `PG_U_FINAL_SIGMA`. (`unicode_case.c:365-377`)
- `casemap` static — the per-codepoint lookup. Fast-path for
  codepoints < 0x80 indexes directly into the case map array
  (offset by 1, since index 0 is a sentinel). Otherwise calls
  `case_index(u1)` from the generated table, then optionally walks
  the special-case array. (`unicode_case.c:392-427`)
- `find_case_map` static — the simple-only variant of `casemap`.
  (`unicode_case.c:433-441`)

## State / globals

- `casekind_map[NCaseKind]` static — maps the `CaseKind` enum to
  the generated tables `case_map_lower/title/upper/fold`.
  (`unicode_case.c:33-39`)

## Phase D notes

- **Input must be valid UTF-8.** The byte-walk in `check_final_sigma`
  has `Assert(false)` for "invalid UTF-8" cases (lines 331, 355).
  In a non-cassert build, invalid UTF-8 would cause the function to
  return wrong results but not crash; correctness depends on
  upstream validation by `pg_utf8_verifystr`.
  `[verified-by-code]`
- **Truncation is allowed.** All `unicode_str*` functions return
  the required-output length but write nothing past `dstsize`. The
  caller is responsible for checking `result <= dstsize` before
  treating the dst as complete. This is a documented two-pass
  pattern, but a single-pass caller that ignores the return value
  gets silently truncated output.
- **`full=false` swaps title for upper.** The comment at
  `unicode_case.c:122-124` notes that in non-full mode,
  `unicode_strtitle` uses uppercase rather than titlecase — this
  matches INITCAP()'s historical behaviour and ICU's default. Worth
  knowing when reading tests.
- **No Cased adjustment.** The function comment at `:200-204` is
  explicit: "does not currently implement the Unicode behavior in
  which the word boundary is adjusted to the next Cased character".
  Matches ICU and INITCAP() docs, but differs from some other DBs.

## Potential issues

`[ISSUE-correctness: invalid-UTF-8 input falls through Assert in
check_final_sigma; non-cassert build silently returns wrong case
folding. Caller MUST validate upstream. (maybe)]`

`[ISSUE-undocumented-invariant: full=false's title→upper swap is
documented only in convert_case's comment, not in the header. A
caller using titlecase for SCRAM-style "first letter caps" would
get different results in full vs non-full mode. (low)]`
