# `src/include/regex/regerrs.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~84
- **Source:** `source/src/include/regex/regerrs.h`

Static table of `{ errcode, "REG_NAME", "human description" }`
triples used by `pg_regerror` to turn an int errcode into a string.
Designed to be `#include`d inside an array initializer in
`backend/regex/regerror.c`. The comment in `regex.h` notes "the
table used by regerror() is generated automatically from this file."
[from-comment]

## API / declarations

Pure data file — no extern declarations. Entries are anonymous
struct initializers wrapped in braces, one per `REG_*` errcode from
`regex.h`:

- 20 main codes from `REG_OKAY=0` through `REG_ECOLORS=20`.
- Two skipped numbers between `REG_BADRPT=13` and `REG_ASSERT=15`
  (the `14` slot is intentionally absent in `regex.h`).

[verified-by-code]

## Notable invariants / details

- Order is positional — the table is indexed by errcode in the
  consumer (regerror.c). Inserting a code in the middle of `regex.h`
  without inserting the matching row here breaks the mapping.
  [from-comment]
- "REG_BADPAT" description literally contains the version string
  `"(reg version 0.8)"` — a Spencer-era artifact PG inherited.
  [verified-by-code]
- Debug codes `REG_ATOI=101`, `REG_ITOA=102` and `pg_regprefix`
  return codes (`REG_PREFIX=-1`, `REG_EXACT=-2`) are intentionally
  NOT in the table — they are not error conditions.

## Potential issues

- Numbering jumps from 13 to 15 (no `REG_*=14`); historical hole
  preserved for ABI stability. [ISSUE-doc-drift: 14 gap unexplained
  in this file (nit)]
- "(reg version 0.8)" in REG_BADPAT message is a hard-coded
  Spencer-era version that no longer matches anything meaningful.
  [ISSUE-stale-todo: REG_BADPAT version string is stale (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-regex`](../../../../issues/include-regex.md)
<!-- issues:auto:end -->
