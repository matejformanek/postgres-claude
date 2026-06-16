# `src/pl/plpgsql/src/pl_unreserved_kwlist.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** 114
- **Source:** `source/src/pl/plpgsql/src/pl_unreserved_kwlist.h`

X-macro keyword list of the 85 PL/pgSQL **unreserved** keywords (84
distinct token codes — `elseif` and `elsif` both map to `K_ELSIF`).
Each entry is `PG_KEYWORD("name", K_TOKEN)`. Unlike the reserved list,
these are NOT given to the core SQL scanner; instead `plpgsql_yylex`
checks them in `pl_scanner.c` **after** namespace/identifier lookup
fails (`source/src/pl/plpgsql/src/pl_scanner.c:247-253, 289-295`). A
user CAN declare a PL/pgSQL variable named e.g. `assert` or `commit`
and that variable will shadow the keyword in the body. [verified-by-code]

## API / role

- **Build-time consumer:** `src/tools/gen_keywordlist.pl` reads this
  file and emits `pl_unreserved_kwlist_d.h` with packed string blob,
  `ScanKeywordList` struct, and a perfect-hash function. [from-comment]
- **Compile-time consumers (in `pl_scanner.c`):**
  - `#include "pl_unreserved_kwlist_d.h"` (`pl_scanner.c:61`) pulls
    `UnreservedPLKeywords` (the `ScanKeywordList`).
  - The raw `.h` is re-included with
    `#define PG_KEYWORD(kwname, value) value,` (`pl_scanner.c:69-72`)
    to build the parallel `static const uint16
    UnreservedPLKeywordTokens[]` array indexed by `kwnum`.
- **Runtime lookup:** `plpgsql_yylex` uses
  `ScanKeywordLookup(ident, &UnreservedPLKeywords)` only after the
  namespace lookup misses, then indexes into
  `UnreservedPLKeywordTokens[kwnum]` for the bison token id.
  [verified-by-code]

## Keyword roster (84 distinct K_* codes from 85 entries)

ASCII-sorted (`pl_unreserved_kwlist.h:30-114`). Logical groupings:

- **Statement intros:** `assert`, `call`, `close`, `commit`,
  `continue`, `do`, `execute`, `exit`, `fetch`, `get`, `import`,
  `insert`, `merge`, `move`, `open`, `perform`, `raise`, `return`,
  `rollback`.
- **DECLARE-section nouns:** `alias`, `array`, `collate`, `constant`,
  `cursor`, `default`, `is`, `option`, `rowtype`, `type`.
- **Cursor flags / FETCH directions:** `absolute`, `backward`,
  `chain`, `current`, `first`, `forward`, `last`, `next`, `no`,
  `prior`, `relative`, `reverse`, `scroll`.
- **Diagnostics / GET STACKED DIAGNOSTICS items:** `column_name`,
  `constraint_name`, `datatype`, `diagnostics`, `errcode`,
  `message`, `message_text`, `pg_context`, `pg_datatype_name`,
  `pg_exception_context`, `pg_exception_detail`,
  `pg_exception_hint`, `pg_routine_oid`, `returned_sqlstate`,
  `row_count`, `schema_name`, `stacked`, `table_name`,
  `sqlstate`, `column`, `constraint`, `schema`, `table`.
- **RAISE option words / log levels:** `debug`, `log`, `info`,
  `notice`, `warning`, `error`, `exception`, `detail`, `hint`,
  `query`.
- **Configuration / variable_conflict:** `variable_conflict`,
  `use_column`, `use_variable`, `print_strict_params`.
- **Boolean / misc:** `and`, `dump`, `elseif` (alias of
  `elsif`), `slice`, `strict`.

## Notable invariants / details

- **ASCII-sorted, enforced by `gen_keywordlist.pl`.** Comment at
  line 26: "gen_keywordlist.pl requires the entries to appear in ASCII
  order." [from-comment]
  [ISSUE-correctness: ASCII-order requirement is comment-only;
  out-of-order entry would silently break perfect-hash lookup (maybe)]
- **`pl_gram.y`'s `unreserved_keyword` production must mirror this
  list.** Header comment line 23-24: "Also be sure that pl_gram.y's
  unreserved_keyword production agrees with this list." There is NO
  build-time check enforcing this; drift would manifest as a
  user-visible regression caught only by tests. [from-comment]
  [ISSUE-audit-gap: no automated check that this list matches
  `pl_gram.y`'s `unreserved_keyword` production (maybe)]
- **`elseif` and `elsif` both produce `K_ELSIF`** (lines 56-57). The
  only two-spellings-one-token entry in either file; both spellings
  occupy distinct `kwnum` slots but resolve to the same token id via
  the parallel `UnreservedPLKeywordTokens[]` array. [verified-by-code]
- **No overlap with `pl_reserved_kwlist.h`** (line 23 comment).
  Duplicating a word would shadow it: the core scanner would emit the
  reserved-keyword token first, and the unreserved check in
  `plpgsql_yylex` would never see it. [from-comment]
- **Deliberately no `#ifndef PL_UNRESERVED_KWLIST_H`** (line 18). The
  multi-include-with-different-PG_KEYWORD-macro pattern requires
  re-inclusion. [from-comment]
  [ISSUE-documentation: rationale opaque; could point to
  `pl_scanner.c:64-72` (nit)]
- **Variable-shadowing semantics.** Because the unreserved-keyword
  lookup runs AFTER `plpgsql_ns_lookup` (see `pl_scanner.c:247-253`),
  a DECLAREd variable wins. This means user functions can shadow PL
  control words like `commit`, `assert`, `merge` — a foot-gun if the
  user later forgets a local var shadows a statement-introducing
  word. [verified-by-code]
  [ISSUE-undocumented-invariant: shadowing is intentional but the
  user-visible surprise is undocumented in `plpgsql.sgml` (nit)]

## Potential issues

- `pl_unreserved_kwlist.h:24` — Header-comment-only enforcement of
  `pl_gram.y` agreement. [ISSUE-audit-gap: no automated cross-check
  with the bison grammar; drift caught only by tests (maybe)]
- `pl_unreserved_kwlist.h:26` — Sort-order invariant lacks an in-tree
  static assert. [ISSUE-correctness: ASCII-order is comment-only;
  out-of-order entry → silent lookup failure (maybe)]
- `pl_unreserved_kwlist.h:18` — Comment-only "no include guard"
  rationale. [ISSUE-documentation: deliberately-no-ifndef comment
  could point at `pl_scanner.c:64-72` (nit)]
- `pl_unreserved_kwlist.h:56-57` — `elseif`/`elsif` synonym is
  undocumented at this layer; user-visible behaviour only mentioned in
  `plpgsql.sgml`. [ISSUE-documentation: synonym pair lacks an
  in-comment cross-reference (nit)]

## Cross-references

- `source/src/pl/plpgsql/src/pl_scanner.c:61, 69-72, 247-253, 289-295`
  — primary consumer; the namespace-first lookup is what makes these
  "unreserved".
- `source/src/pl/plpgsql/src/pl_gram.y` — `unreserved_keyword`
  production that MUST mirror this list.
- `source/src/pl/plpgsql/src/pl_reserved_kwlist.h` — sibling 22-entry
  reserved list handed to the core SQL scanner.
- `source/src/tools/gen_keywordlist.pl` — emits `*_d.h`.
- `source/src/include/common/kwlookup.h` — `ScanKeywordList` /
  `ScanKeywordLookup` API.

<!-- issues:auto:begin -->
- [Issue register — `plpgsql`](../../../../../issues/plpgsql.md)
<!-- issues:auto:end -->
