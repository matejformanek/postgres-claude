# src/include/parser/kwlist.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 538 [verified-by-code]

## Role

The **X-macro file** listing every SQL keyword: name, token symbol,
category, bare-label status. Auto-generated tooling (`gen_keywordlist.pl`)
reads this to produce sorted lookup tables for `scan.l`. The file is
intentionally INCLUDED MULTIPLE TIMES with different `PG_KEYWORD`
definitions; that's why there is **no include guard** (`:19`
[from-comment]).

## Public API

- Single macro `PG_KEYWORD(name, value, category, is_bare_label)`
  expanded once per entry. The macro is **not defined here** —
  each consumer (parser, scanner, autocomplete, psql tab-complete,
  pgindent's keyword list) defines its own expansion before
  `#include "kwlist.h"`.
- Categories: `UNRESERVED_KEYWORD`, `COL_NAME_KEYWORD`,
  `TYPE_FUNC_NAME_KEYWORD`, `RESERVED_KEYWORD`.
- Bare-label status: `BARE_LABEL` (can be used as `SELECT x AS
  keyword`) or `AS_LABEL` (needs explicit AS).

## Invariants

- INV-KWLIST-ASCII-SORT: header comment `:25` [from-comment] —
  entries MUST appear in ASCII order (`gen_keywordlist.pl`
  requires bsearch later). Manual sort errors break keyword
  lookup silently (a keyword would be treated as identifier).
- INV-KWLIST-NO-GUARD: deliberately no `#ifndef KWLIST_H` (`:19`
  [from-comment]) — re-inclusion is the design.
- INV-KWLIST-TOKEN-NAMES: token symbols ending in `_P` are
  alphabetic suffixes used when the bare name would clash with
  a C keyword or with another token (e.g. `ABORT_P` since
  `ABORT` is reserved in `<stdlib.h>` on some platforms).

## Notable internals

- Total: ~500 keyword entries (`:28-538`).
- Adding a keyword: append in ASCII order, regenerate via
  `gen_keywordlist.pl`, bump catversion if the keyword reservation
  changes parse semantics.
- A keyword's category (RESERVED vs UNRESERVED etc.) affects
  whether existing user code breaks; SQL standard committee
  occasionally promotes keywords (e.g. `ATOMIC` reserved in
  newer SQL).

## Trust boundary / Phase D surface

- Not a trust boundary directly. But:
- **Catalog upgrade.** Promoting a previously-unreserved keyword
  to RESERVED breaks existing catalog entries that used the
  word as an identifier (e.g. column name, role name, table
  name). PG release notes flag this; pg_upgrade may have to
  rewrite catalogs.
- **Encoding & truncation.** Keyword matching happens AFTER
  `downcase_truncate_identifier` (`scansup.h`) — identifiers
  longer than `NAMEDATALEN-1` get truncated; a keyword would
  never collide because keywords are ASCII and short, but a
  pathological identifier (e.g. `"select x"`) bypasses
  keyword treatment via quoting.
- **`bare_label` flag** (`:28-…`) governs SQL backward-
  compatibility for `SELECT 1 AS keyword`. Mistakenly setting
  BARE_LABEL on a true reserved keyword would create a parse
  ambiguity.

## Cross-references

- `common/keywords.h` — `ScanKeywordList`,
  `ScanKeywordLookup`.
- `parser/gram.y` — token names referenced from grammar.
- `parser/scan.l` — flex rule matching identifiers against
  keyword list.
- `tools/gen_keywordlist.pl` (in source/src/tools).
- `tcop/cmdtaglist.h` — parallel X-macro pattern (this slice).

## Issues / drift

- `[ISSUE-DOC: header comment notes "no include guard" but doesn't list the multiple consumers — readers grepping for #include "kwlist.h" find ~7 sites, surprising on first encounter (low)] — source/src/include/parser/kwlist.h:19`
- `[ISSUE-CODE: ASCII-sort is checked at code-gen time (gen_keywordlist.pl asserts) but not in C build; manual edits can silently break ordering (low)] — source/src/include/parser/kwlist.h:25`
