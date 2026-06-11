# `src/pl/plpgsql/src/pl_reserved_kwlist.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** 50
- **Source:** `source/src/pl/plpgsql/src/pl_reserved_kwlist.h`

X-macro keyword list of the 22 PL/pgSQL **reserved** keywords. Each
entry is `PG_KEYWORD("name", K_TOKEN)`; the macro is intentionally not
defined here — callers (`gen_keywordlist.pl` at build time,
`pl_scanner.c` at compile time) define it before #including. Reserved
keywords are handed to the **core SQL scanner** as its keyword table,
so they are recognised before identifier rules and CANNOT be used as
PL/pgSQL variable names. [verified-by-code]

## API / role

- **Build-time consumer:** `src/tools/gen_keywordlist.pl` reads this
  file and emits `pl_reserved_kwlist_d.h` containing a packed string
  table, a `ScanKeywordList` struct, and a perfect-hash function.
  [from-comment]
- **Compile-time consumers (in `pl_scanner.c`):**
  - `#include "pl_reserved_kwlist_d.h"` (`source/src/pl/plpgsql/src/pl_scanner.c:60`)
    pulls in `ReservedPLKeywords` (the `ScanKeywordList`).
  - The file is re-included raw with `#define PG_KEYWORD(kwname, value) value,`
    (`source/src/pl/plpgsql/src/pl_scanner.c:64-67`) to build the
    parallel `static const uint16 ReservedPLKeywordTokens[]` array
    indexed by the same `kwnum` the scanner returns.
- **Scanner wiring:** `scanner_init(..., &ReservedPLKeywords,
  ReservedPLKeywordTokens)` (`source/src/pl/plpgsql/src/pl_scanner.c:627-628`)
  hands the table to the core SQL flex scanner so reserved words tokenise
  before identifier matching. [verified-by-code]

## Keyword roster

22 entries (`pl_reserved_kwlist.h:29-50`), ASCII-sorted:

`all`, `begin`, `by`, `case`, `declare`, `else`, `end`, `for`,
`foreach`, `from`, `if`, `in`, `into`, `loop`, `not`, `null`, `or`,
`then`, `to`, `using`, `when`, `while`.

The header at `pl_scanner.c:53-57` notes that `BEGIN`, `BY`, `DECLARE`,
`FOREACH`, `IF`, `LOOP`, `WHILE` are reserved in PL/pgSQL but NOT in
core SQL — they are reserved here to disambiguate block-label and
control-flow syntax inside PL/pgSQL bodies. [from-comment]

## Notable invariants / details

- **ASCII-sorted, gen_keywordlist.pl enforced.** Comment at line 25:
  "Note: gen_keywordlist.pl requires the entries to appear in ASCII
  order." The generated perfect-hash assumes sorted input; an
  out-of-order entry would silently break lookup. [from-comment]
  [ISSUE-correctness: ASCII-order requirement is comment-only;
  out-of-order entry produces a silent lookup failure (maybe)]
- **Deliberately no `#ifndef PL_RESERVED_KWLIST_H`** (line 18). The
  file is included multiple times with different `PG_KEYWORD` macro
  definitions; an include guard would defeat the pattern.
  [from-comment]
  [ISSUE-documentation: the "deliberately no #ifndef" comment doesn't
  explain WHY (nit)]
- **No overlap with `pl_unreserved_kwlist.h`.** Comment at line 23:
  "Be careful not to put the same word into pl_unreserved_kwlist.h."
  A duplicate would be semantically a bug but would still resolve
  consistently because each list has its OWN token-code array.
  [from-comment]
- **Token codes (`K_*`) defined by `pl_gram.y`.** The token-code array
  in `pl_scanner.c` resolves these symbols at compile time; if a
  token name in this file were removed from `pl_gram.y` the build
  fails. [verified-by-code]

## Potential issues

- `pl_reserved_kwlist.h:25` — Sort-order invariant is enforced only by
  comment + Perl-side check; no in-tree static assertion. [ISSUE-correctness:
  ASCII-order is comment-only; out-of-order entry → silent lookup failure
  (maybe)]
- `pl_reserved_kwlist.h:18` — No-include-guard rationale is opaque to a
  first-time reader. [ISSUE-documentation: deliberately-no-ifndef comment
  lacks pointer to `pl_scanner.c:64-72` where the multi-include trick is
  realised (nit)]

## Cross-references

- `source/src/pl/plpgsql/src/pl_scanner.c:60-72` — consumes the list
  twice.
- `source/src/pl/plpgsql/src/pl_gram.y` — defines `K_*` token IDs.
- `source/src/pl/plpgsql/src/pl_unreserved_kwlist.h` — the sibling list
  (84 entries) handled by `plpgsql_yylex` after namespace lookup.
- `source/src/tools/gen_keywordlist.pl` — emits `*_d.h`.
- `source/src/include/common/kwlookup.h` — `ScanKeywordList` /
  `ScanKeywordLookup` API.
