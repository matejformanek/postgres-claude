---
path: src/common/unicode/case_test.c
anchor_sha: e18b0cb7344
loc: 374
depth: read
---

# src/common/unicode/case_test.c

## Purpose

Stand-alone test program that validates PostgreSQL's built-in Unicode case
mapping (`unicode_lowercase_simple` / `unicode_titlecase_simple` /
`unicode_uppercase_simple` / `unicode_casefold_simple` plus the full-string
`unicode_strlower` / `unicode_strtitle` / `unicode_strupper` / `unicode_strfold`)
by exhaustively comparing every assigned Unicode codepoint against ICU's
case-mapping primitives. It also runs a fixed table of hand-written
`test_convert` cases covering tricky behavior (German `ß` → `SS`, Turkish
dotted/dotless I, Greek final-sigma `ς`, full-width digits, mid-word case
changes that grow the byte length). It is built and run only when the developer
opts in — the generated tables it tests live in `unicode_norm_table.h` /
`unicode_case_table.h` from `src/common/unicode/`. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int main(int argc, char **argv)` | `case_test.c:342` | Opens ICU `UCaseMap` (titlecase break-adjust disabled), runs `test_icu` if `USE_ICU`, then `test_convert_case` unconditionally |

## Internal landmarks

- `initcap_wbnext` (`:50-76`) — minimal word-boundary iterator copied from
  `pg_locale_builtin.c`; flips at alnum/non-alnum transitions. Used to drive
  `unicode_strtitle` for both POSIX (`isalnum` POSIX-flavor) and full
  (Unicode-flavor) modes.
- `icu_test_simple` (`:80-103`) — for one codepoint, compares
  `unicode_{lower,title,upper,casefold}_simple` to `u_tolower` / `u_totitle` /
  `u_toupper` / `u_foldCase(U_FOLD_CASE_DEFAULT)`. Aborts on any mismatch.
- `icu_test_full` (`:105-166`) — string-level: runs all four `unicode_str*`
  routines and `ucasemap_utf8To{Lower,Title,Upper}` / `ucasemap_utf8FoldCase`,
  diffing the UTF-8 outputs byte-for-byte. `[from-comment]`: titlecase
  comparison is what motivates the `U_TITLECASE_NO_BREAK_ADJUSTMENT` flag at
  `main:351` — ICU's default word breaker would otherwise disagree with PG's
  simple boundary iterator.
- `test_icu` (`:171-206`) — sweeps `0..0x10FFFF`. Skips codepoints where ICU
  thinks "unassigned" but PG doesn't (or vice versa) — a Unicode-version skew
  between PG's generated tables and the linked ICU.
- `test_convert` (`:209-257`) — runs a single `TestFunc` twice: once with a
  destination buffer that is NOT NUL-terminated (exactly `dst1len` bytes) and
  once with a NUL-terminated buffer (`dst1len + 1`). Both code paths must
  return the same `needed` and produce the same bytes; the buffer is
  pre-filled with `0x7F` to catch any non-write of trailing space.
- `test_convert_case` (`:296-339`) — hand-written corpus: identity strings,
  byte-length-changing `Ⱥ → ⱥ`, sharp-s up-mapping `ß → SS`, Turkish dotless
  I, Greek final-sigma at word boundaries (the famous `σςΣ ΣΣΣ` cases), and
  the full-width digit `U+FF11`. `[verified-by-code]`

## Invariants & gotchas

- **ICU not required.** `#ifdef USE_ICU` arms compile away; the
  `test_convert_case` fixed table still runs without ICU and is the floor of
  test coverage. `[verified-by-code]`
- **Unicode-version skew is expected.** When PG's bundled Unicode version and
  the linked ICU differ, both sides print a skip count (`pg_skipped_codepoints`
  / `icu_skipped_codepoints`) and continue. Reviewers updating
  `PG_UNICODE_VERSION` should expect these counts to swing.
- **Titlecase comparison demands `U_TITLECASE_NO_BREAK_ADJUSTMENT`.** Without
  it ICU's `ucasemap_utf8ToTitle` applies its own dictionary-aware word
  segmenter and diverges from PG's POSIX-style boundary scan. The test would
  emit false positives. `[from-comment]`
- **`test_convert` deliberately passes a non-NUL-terminated source** (`src1`
  is `malloc`+`memcpy`, no terminator). This exercises the `srclen`-counted
  contract of the `unicode_str*` API. A regression that started reading until
  NUL would walk past the buffer.
- **`test_convert` is destructive on first error**: it `exit(1)`s, so only the
  earliest failure is reported per run.

## Cross-refs

- `knowledge/files/src/common/unicode/category_test.c.md` — sibling
  category/property test runner.
- `knowledge/files/src/common/unicode/norm_test.c.md` — sibling normalization
  test runner.
- `source/src/common/unicode_case.c` and the generated
  `source/src/common/unicode_case_table.h` — the implementation under test.
