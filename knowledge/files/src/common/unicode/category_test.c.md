---
path: src/common/unicode/category_test.c
anchor_sha: e18b0cb7344
loc: 237
depth: read
---

# src/common/unicode/category_test.c

## Purpose

Stand-alone validator for PostgreSQL's generated Unicode **general-category**
and **binary-property** tables. Walks every codepoint `0..0x10FFFF` and
compares PG's `unicode_category(code)` plus a dozen `pg_u_*` predicates
(`pg_u_isalpha`, `pg_u_isspace`, `pg_u_prop_alphabetic`, `pg_u_prop_cased`, …)
against the equivalent ICU calls (`u_charType`, `u_hasBinaryProperty`,
`u_isUAlphabetic`, …). Built only when explicitly requested; protects the
hand-rolled tables in `unicode_category_table.h` from silent regressions when
the Unicode data files are re-generated. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int main(int argc, char **argv)` | `category_test.c:223` | Parses `PG_UNICODE_VERSION` and `U_UNICODE_VERSION`, runs `icu_test()` when `USE_ICU` is defined |

## Internal landmarks

- `parse_unicode_version` (`:35-48`) — turns a `"MAJOR.MINOR"` string into
  `MAJOR * 100 + MINOR` for ordered comparison; `Assert(n == 2)` and
  `Assert(minor < 100)` are the contract. Used to decide which side of a skew
  is older.
- `icu_test` (`:56-220`) — the workhorse. For each codepoint it gathers eight
  binary properties and twelve POSIX-style class predicates on both the PG
  and ICU side, then runs three diff checks:
  1. **General-category agreement** (`:151-162`) — must match exactly, otherwise
     print both categories and `exit(1)`.
  2. **Binary-property agreement** (`:164-184`) — `alphabetic`, `lowercase`,
     `uppercase`, `cased`, `case_ignorable`, `white_space`, `hex_digit`,
     `join_control`.
  3. **Class-predicate agreement** (`:186-206`) — `alpha`, `lower`, `upper`,
     `punct`, `digit`, `xdigit`, `alnum`, `space`, `blank`, `cntrl`, `graph`,
     `print`. `pg_u_iscntrl` is compared against `icu_category == PG_U_CONTROL`
     rather than `u_iscntrl` because the two libraries disagree on the
     definition. `[from-comment]`

## Invariants & gotchas

- **Version-skew skip is one-directional.** If PG marks a codepoint
  `PG_U_UNASSIGNED` but ICU doesn't AND `pg_unicode_version < icu_unicode_version`,
  the codepoint is skipped (`:135-141`) and counted in
  `pg_skipped_codepoints`. The reverse skip lives at `:143-149`. The test
  ceases to be exhaustive in that range — reviewers must check the skip count
  is plausible (small) after a Unicode bump.
- **POSIX class mapping is documented but subtle.** `[from-comment]` at
  `:86-98`: the comment warns that ICU's `UCHAR_POSIX_ALNUM` etc. are *not*
  "POSIX-compatible character classes" — they're ICU's flavor that PG happens
  to match. Don't reinterpret these as POSIX-required behavior.
- **`pg_u_ispunct(code, false)` / `pg_u_isdigit(code, false)` etc. pass `false`
  for the `posix` flag** (`:99-110`) — i.e., the comparison is against
  full-Unicode semantics, not POSIX-restricted semantics. The POSIX flavor is
  separately exercised by callers in `pg_locale_builtin.c`.
- **`PG_USED_FOR_ASSERTS_ONLY` on `n`** (`:38`) — the `sscanf` return is only
  asserted, so a non-assert build must not warn about an unused variable.
- **Exits on first mismatch**: no aggregate report, just the first failing
  codepoint and its diff.

## Cross-refs

- `knowledge/files/src/common/unicode/case_test.c.md` — sibling case-mapping
  test.
- `knowledge/files/src/common/unicode/norm_test.c.md` — sibling normalization
  test.
- `source/src/common/unicode_category.c` and generated
  `unicode_category_table.h` — the tables under test.
