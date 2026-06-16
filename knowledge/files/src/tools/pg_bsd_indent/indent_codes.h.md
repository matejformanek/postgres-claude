---
path: src/tools/pg_bsd_indent/indent_codes.h
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
loc: 71
depth: read
---

# `src/tools/pg_bsd_indent/indent_codes.h` — token-type integer constants

## Purpose

A flat list of 37 `#define`s (`newline`=1 … `structure`=37) naming the integer
token/construct codes that flow between the three stages of `pg_bsd_indent`:
`lexi()` returns them, the `main()` switch in
[[knowledge/files/src/tools/pg_bsd_indent/indent.c]] branches on them, and
`parse()` pushes a subset onto its stack. There are no functions or types here —
it is pure shared vocabulary.

## The codes

`newline`(1), `lparen`(2), `rparen`(3), `unary_op`(4), `binary_op`(5),
`postop`(6), `question`(7), `casestmt`(8), `colon`(9), `semicolon`(10),
`lbrace`(11), `rbrace`(12), `ident`(13), `comma`(14), `comment`(15),
`swstmt`(16), `preesc`(17 — a `#` preprocessor line), `form_feed`(18),
`decl`(19), `sp_paren`(20 — if/while/for), `sp_nparen`(21 — else/do),
`ifstmt`(22), `whilestmt`(23), `forstmt`(24), `stmt`(25), `stmtl`(26),
`elselit`(27), `dolit`(28), `dohead`(29), `ifhead`(30), `elsehead`(31),
`period`(32), `strpfx`(33 — wide-string `L"..."` prefix), `storage`(34),
`funcname`(35), `type_def`(36), `structure`(37). (indent_codes.h:35-72)

## Gotchas

- **Code `0` is reserved for EOF** — `lexi` returns 0 when input is exhausted,
  and the main switch / `parse` treat 0 specially (e.g. indent.c:417,458). Do
  not assign a token to 0.
- The numeric values are positional in two distinct namespaces: some codes are
  *token types* from `lexi` (`ident`, `lparen`, …) and some are *construct
  types* pushed by `parse` (`ifhead`, `stmtl`, `dohead`, …). A few (`semicolon`,
  `decl`, `lbrace`, `rbrace`) appear in both roles. Renumbering requires a sweep
  of both `lexi.c` and `parse.c`.

## Cross-refs

- [[knowledge/files/src/tools/pg_bsd_indent/lexi.c]] — produces token codes.
- [[knowledge/files/src/tools/pg_bsd_indent/indent.c]] — switches on them.
- [[knowledge/files/src/tools/pg_bsd_indent/parse.c]] — pushes construct codes.

## Potential issues

(none — a constant table.)
