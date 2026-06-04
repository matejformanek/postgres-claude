# pl_reserved_kwlist.h and pl_unreserved_kwlist.h

**Source pin:** `4b0bf0788b0`. Lines read: `pl_reserved_kwlist.h` 1–50 (complete),
`pl_unreserved_kwlist.h` 1–114 (complete).

## One-line summary

PG_KEYWORD-macro-driven keyword tables consumed at build time by
`gen_keywordlist.pl` to emit the `*_d.h` ScanKeywordList lookup data,
AND at compile time by `pl_scanner.c` to populate the parallel
`ReservedPLKeywordTokens[]` / `UnreservedPLKeywordTokens[]` arrays
indexed by `ScanKeywordLookup` return value.

## Why two files

From `pl_scanner.c:29-57` ("A word about keywords"):

- **Reserved** keywords are handed to the **core scanner** at
  `scanner_init` time (`pl_scanner.c:627-628`: passes `&ReservedPLKeywords`
  + `ReservedPLKeywordTokens` as the keyword table). The core scanner will
  return them as keyword tokens BEFORE it can return them as identifiers.
  A user cannot declare a PL/pgSQL variable named `BEGIN` or `IF`.
- **Unreserved** keywords are checked **separately** by `plpgsql_yylex`
  AFTER variable lookup fails (`pl_scanner.c:247-253, 289-295`). A user
  CAN declare a variable named `assert` or `commit` and it will shadow
  the keyword — the wrapper's namespace lookup runs first.

The header at `pl_scanner.c:53-57` also lists which words are reserved in
plpgsql but NOT in core SQL grammar: `BEGIN BY DECLARE FOREACH IF LOOP
WHILE`. These are reserved to disambiguate block-label syntax.

## Reserved keyword list

22 keywords (`pl_reserved_kwlist.h:29-50`):

`all`, `begin`, `by`, `case`, `declare`, `else`, `end`, `for`, `foreach`,
`from`, `if`, `in`, `into`, `loop`, `not`, `null`, `or`, `then`, `to`,
`using`, `when`, `while`.

## Unreserved keyword list

84 keywords (`pl_unreserved_kwlist.h:30-114`). Highlights:

- Statement intros: `assert`, `call`, `close`, `commit`, `continue`,
  `do`, `execute`, `exit`, `fetch`, `get`, `import`, `insert`, `merge`,
  `move`, `open`, `perform`, `raise`, `return`, `rollback`.
- DECLARE-section words: `alias`, `array`, `collate`, `constant`, `cursor`,
  `default`, `is`, `option`, `rowtype`, `type`.
- Cursor flags: `absolute`, `backward`, `chain`, `current`, `first`,
  `forward`, `last`, `next`, `no`, `prior`, `relative`, `reverse`, `scroll`.
- Diagnostics: `column_name`, `constraint_name`, `datatype`,
  `diagnostics`, `errcode`, `message`, `message_text`, `pg_context`,
  `pg_datatype_name`, `pg_exception_context`, `pg_exception_detail`,
  `pg_exception_hint`, `pg_routine_oid`, `returned_sqlstate`,
  `row_count`, `schema_name`, `stacked`, `table_name`.
- RAISE levels: `debug`, `log`, `info`, `notice`, `warning`, `error`,
  `exception`, `detail`, `hint`.
- Configuration: `variable_conflict`, `use_column`, `use_variable`,
  `print_strict_params`.
- Misc: `and`, `dump`, `elseif`/`elsif` (two spellings, same token
  `K_ELSIF`), `query`, `slice`, `strict`.

## Key invariants

- **ASCII-sorted.** Both files' header comment requires entries in ASCII
  order ("Note: gen_keywordlist.pl requires the entries to appear in ASCII
  order"). Out-of-order entries would break binary search in the generated
  ScanKeywordList. [from-comment]
- **No #ifndef guard.** Deliberate (line 18 in both files: "There is
  deliberately not an #ifndef PL_*_KWLIST_H here"). The same file is
  included multiple times with different `PG_KEYWORD` macro definitions —
  once to build the `ScanKeywordList` (via the generated `_d.h`), once to
  build the `uint16` token-code array (`pl_scanner.c:66-72`). [from-comment]
- **No overlap.** Both header comments warn: "Be careful not to put the
  same word into pl_unreserved_kwlist.h" / pl_reserved_kwlist.h. If a
  word were in both lists, the core scanner would emit the reserved token
  first and the unreserved-keyword check in `plpgsql_yylex` would never
  fire — but a token-code collision in the `*Tokens[]` arrays would still
  resolve consistently because each file has its OWN token-code array.
  Still, semantically a duplicate would be a bug. [from-comment]
- **The `pl_gram.y` `unreserved_keyword` production must mirror
  `pl_unreserved_kwlist.h`.** Header comment at
  `pl_unreserved_kwlist.h:24`: "Also be sure that pl_gram.y's
  unreserved_keyword production agrees with this list." There is NO
  build-time check that enforces this — drift is caught only by
  regression tests that exercise each keyword. [from-comment]
- **`elseif` and `elsif` share `K_ELSIF`.** Lines 56-57 of
  `pl_unreserved_kwlist.h` are the only two-spellings-one-token entry.
  ScanKeywordList lookup returns different `kwnum`s but both index into
  `UnreservedPLKeywordTokens[]` at the (different) `kwnum` positions that
  happen to hold the same `K_ELSIF` value.

## Notable internals

### `gen_keywordlist.pl` flow

The Perl script (in `src/tools/`) reads each `*_kwlist.h` and emits a
`*_kwlist_d.h` containing:

- A C string blob with all keyword names packed.
- A `ScanKeywordList` struct literal (offset table + count + max length).
- A pre-computed perfect-hash function for O(1) lookup.

Both `_d.h` files are included by `pl_scanner.c:60-61` and used via
`ScanKeywordLookup(ident, &ReservedPLKeywords)` /
`ScanKeywordLookup(ident, &UnreservedPLKeywords)`.

### Why parallel token-code array

`ScanKeywordLookup` returns an int index into the keyword table. To map
from index → token code (bison's `K_BEGIN`, `K_IF`, etc.), `pl_scanner.c`
includes the same `.h` file again with a different PG_KEYWORD definition
(`pl_scanner.c:64`: `#define PG_KEYWORD(kwname, value) value,`) building
a `uint16[]` parallel to the keyword list. Index `kwnum` in
`UnreservedPLKeywords` is the same as index `kwnum` in
`UnreservedPLKeywordTokens[]`. This pattern lets `gen_keywordlist.pl`
produce a generic-shape lookup table that doesn't need to know about
bison's specific token IDs.

## Cross-references

- `pl_scanner.c` — primary consumer. Includes the `_d.h` headers (lines
  60-61) and the raw `.h` files (lines 66-72) to build both lookup tables.
- `pl_gram.y` — defines the K_* token constants and the
  `unreserved_keyword` grammar production that must mirror the list.
- `src/tools/gen_keywordlist.pl` — generator script.
- `src/include/parser/kwlist.h`, `src/include/common/kwlookup.h` —
  the core-SQL equivalents and the `ScanKeywordList` /
  `ScanKeywordLookup` API.

## Issues spotted

- [ISSUE-audit-gap: no automated check that `pl_unreserved_kwlist.h`
  matches `pl_gram.y`'s `unreserved_keyword` production (maybe)] —
  `source/src/pl/plpgsql/src/pl_unreserved_kwlist.h:24` — Header
  comment is the only enforcement. Drift would manifest as a
  user-visible regression (a new unreserved keyword unusable as
  variable name, or vice versa) caught only by tests. Could be a
  Perl-side check in `gen_keywordlist.pl` or a Makefile rule.

- [ISSUE-documentation: the "deliberately no #ifndef" comment doesn't
  explain WHY (nit)] —
  `source/src/pl/plpgsql/src/pl_reserved_kwlist.h:18` (and the same in
  the unreserved file) — A reader new to PG keyword machinery has to dig
  to understand the multi-include-with-different-macro pattern. The
  comment could point to `pl_scanner.c:64-74` as the example. Cosmetic.

- [ISSUE-correctness: ASCII-order requirement is comment-only; an
  out-of-order entry would produce a SILENT lookup failure (the perfect
  hash is built assuming sorted input) — caught only at first runtime
  use of that keyword (maybe)] —
  `source/src/pl/plpgsql/src/pl_reserved_kwlist.h:25` — The Perl script
  presumably aborts on disorder, but a reviewer can't verify that from
  the header alone; worth a one-line cite to `gen_keywordlist.pl`'s
  enforcement.
