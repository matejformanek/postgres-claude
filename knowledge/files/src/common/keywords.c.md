# src/common/keywords.c

## Purpose

Owner of the master SQL keyword arrays. Concrete definitions of
`ScanKeywordCategories[]` and `ScanKeywordBareLabel[]`, plus the
`ScanKeywords` blob included via the generated `kwlist_d.h`.

## Role in PG

Shared **frontend + backend**. The compile-time table assembly is
the entire point — at runtime nothing in this file executes.

## Key constructs

- `#include "kwlist_d.h"` — pulls in the generated
  `ScanKeywords` blob (string pool + offsets + hash function).
  (`keywords.c:23`)
- `ScanKeywordCategories[SCANKEYWORDS_NUM_KEYWORDS]` — assembled by
  redefining `PG_KEYWORD(kwname, value, category, collabel)` to
  emit just `category`, then `#include "parser/kwlist.h"`.
  (`keywords.c:27-33`)
- `ScanKeywordBareLabel[SCANKEYWORDS_NUM_KEYWORDS]` — same trick
  with `BARE_LABEL`/`AS_LABEL` macros expanding to `true`/`false`.
  (`keywords.c:39-44`)

## State / globals

Three `const` arrays exported via `PGDLLIMPORT` from
`common/keywords.h`. Read-only after link.

## Phase D notes

Inert. The kwlist contents come from `parser/kwlist.h` which is
hand-edited; the hash function and offsets come from
`gen_keywordlist.pl`. If those two get out of sync (mismatched
keyword count), build fails.

## Potential issues

None.
