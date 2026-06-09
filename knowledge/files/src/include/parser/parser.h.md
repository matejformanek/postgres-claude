# src/include/parser/parser.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 66 [verified-by-code]

## Role

External API for the **raw parser** (flex + bison) — the first
pipeline stage that turns a SQL string into `List *` of `RawStmt`
nodes. Pre-rewrite, pre-analyze.

## Public API

- `RawParseMode` enum (`:37-45`):
  - `RAW_PARSE_DEFAULT` — semicolon-separated statement list
    returning `List<RawStmt>`.
  - `RAW_PARSE_TYPE_NAME` — single `TypeName` (used by
    `format_type` and friends).
  - `RAW_PARSE_PLPGSQL_EXPR` — PL/pgSQL expression.
  - `RAW_PARSE_PLPGSQL_ASSIGN1/2/3` — PL/pgSQL assignment
    statement; `n` = number of dotted names in target.
- `BackslashQuoteType` enum: OFF / ON / SAFE_ENCODING (`:48-53`).
- `backslash_quote` GUC (extern int) (`:56`).
- `raw_parser(const char *str, RawParseMode mode) -> List *`
  (`:60`).
- `SystemFuncName(char *)`, `SystemTypeName(char *)` —
  utility constructors building `pg_catalog`-qualified
  references (`:63-64`).

## Invariants

- INV-PARSER-PRE-ANALYZE: raw_parser does NOT consult the catalog;
  output is pre-analyze and contains raw identifiers, not OIDs.
  Hence "raw" — running raw_parser on a hostile string is
  catalog-safe.
- INV-PARSER-NON-REENTRANT: flex/bison globals make a single
  raw_parser call non-reentrant per-process. Callers in
  recursive contexts (e.g. SQL-language functions being
  parsed during another parse) re-enter via fresh scanner
  state managed by `scanner_init`.
- INV-PARSER-MODE-DETERMINISTIC: each `RawParseMode` corresponds
  to a different start symbol in the bison grammar; choosing
  the wrong mode gives wrong errors but never wrong parse
  trees for valid input of the named kind.
- `backslash_quote=SAFE_ENCODING` (`:50-52`) — backslash quoting
  in string literals is permitted only in encodings where it's
  unambiguous (e.g. UTF-8). The setting is consulted at scan
  time, NOT parse time.

## Notable internals

- The auto-generated `parser/gram.c` from `gram.y` plus
  `parser/scan.c` from `scan.l` form the bulk; this header
  hides the YYSTYPE / YYLTYPE complexity behind a string
  function signature.
- `SystemFuncName("foo")` returns the List `("pg_catalog",
  "foo")` — used when emitting `cast` syntax or
  `RangeFunction` nodes for builtins.

## Trust boundary / Phase D surface

- **A11 echo — cross-cluster query trust.** `raw_parser` is the
  outer gate of EVERY query, including those from extensions
  that smuggle SQL via libpq replay (`pg_dump` restore,
  logical replication apply, `pg_cron`-style schedulers). All
  invariants downstream assume `raw_parser` produced the tree
  — but if an extension builds a RawStmt by hand and skips
  raw_parser, identifier conventions can be violated.
- **`standard_conforming_strings` interaction.** When OFF,
  string literals are treated as backslash-escaped (legacy
  pre-9.1 default). A query crafted under the assumption of
  one setting and executed under the other can parse
  differently — historical CVE vector. The setting is
  consulted at scan time (in `scan.l`); this header doesn't
  expose it but `backslash_quote` is the related GUC.
- **PL/pgSQL ASSIGN modes** (`:33-35`) — n parameter sets
  the number of dotted-name components; mis-set leads to
  silent re-binding of variable target. Caller must compute
  `n` correctly from the PL/pgSQL AST.
- **A14 echo — flex memory safety.** flex buffers are
  fixed-size; very long identifiers (> `MAX_PARSE_BUFFER`)
  trigger errors. flex re-entrancy state is in
  `core_yy_extra_type` (see `scanner.h`).

## Cross-references

- `parser/scanner.h` — flex state (`core_yy_extra_type`).
- `parser/scansup.h` — `downcase_truncate_identifier`,
  `truncate_identifier`.
- `parser/analyze.h` — `parse_analyze_*` next stage.
- `parser/kwlist.h` — keyword list.
- `pl/plpgsql/src/pl_comp.c` — uses PL/pgSQL parse modes.
- `tcop/postgres.c` — `exec_simple_query` calls `raw_parser`.

## Issues / drift

- `[ISSUE-TRUST: A11 echo — header doesn't mention standard_conforming_strings interaction with backslash_quote; both are scan-time GUCs with cross-cluster trust implications (medium)] — source/src/include/parser/parser.h:47-57`
- `[ISSUE-DOC: SystemFuncName/SystemTypeName comment "perhaps these should be elsewhere" — long-standing TODO (low)] — source/src/include/parser/parser.h:62`
- `[ISSUE-CODE: no API for "parse with a specific encoding override" — encoding is implicit in client_encoding GUC; cross-encoding query execution can give surprising scan results (low)] — source/src/include/parser/parser.h:60`
