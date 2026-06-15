---
path: src/common/unicode/norm_test.c
anchor_sha: e18b0cb7344
loc: 86
depth: read
---

# src/common/unicode/norm_test.c

## Purpose

Drives PostgreSQL's `unicode_normalize()` against the Unicode Consortium's
official `NormalizationTest.txt` fixtures. The fixture file is converted into
a C table (`UnicodeNormalizationTests` in the generated header
`norm_test_table.h`) by the build step in `src/common/unicode/Makefile`; this
program loops the table and asserts that PG's NFC/NFD/NFKC/NFKD output matches
the expected per-form output, exit-on-first-failure with the original
`linenum` so a regression points back at the source file. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int main(int argc, char **argv)` | `norm_test.c:59` | Iterates `UnicodeNormalizationTests` for all four NF forms (0..3) |

## Internal landmarks

- `print_wchar_str` (`:22-41`) — formats a `char32_t *` as `U+XXXX U+XXXX …`
  for diagnostic output. Static 50-codepoint buffer (`BUF_DIGITS`) is enough
  for any single line of the official fixture.
- `pg_wcscmp` (`:43-57`) — in-tree `wcscmp` over `char32_t` because libc's
  `wcscmp` operates on `wchar_t` which may be 16-bit on some platforms.
- `main` (`:59-86`) — walks `test->input[0] != 0` (the terminating sentinel),
  calls `unicode_normalize(form, test->input)` for `form` 0..3, and runs the
  result through `pg_wcscmp` against `test->output[form]`. On mismatch:
  `linenum`, form id, input/expected/got triple, `exit(1)`.

## Invariants & gotchas

- **Generated table is the contract.** `norm_test_table.h` is produced by
  parsing `NormalizationTest.txt`; bumping the Unicode version requires
  regenerating both that header and the case/category tables in lockstep.
  Running this binary against a stale generated header gives meaningless
  results.
- **Four forms in fixed order.** The `for (int form = 0; form < 4; form++)`
  loop assumes the same ordering as `unicode_norm.h`'s enum (`NFC`, `NFD`,
  `NFKC`, `NFKD`). If a future patch reorders the enum, this loop silently
  tests the wrong form.
- **No ICU dependency.** Unlike `case_test.c` / `category_test.c`, the
  fixture itself is authoritative — there is nothing to compare against.
- **First failure aborts.** No aggregate count; if N codepoints regress, only
  the first one is reported per run.

## Cross-refs

- `knowledge/files/src/common/unicode/case_test.c.md`
- `knowledge/files/src/common/unicode/category_test.c.md`
- `source/src/common/unicode_norm.c` — implementation under test.
