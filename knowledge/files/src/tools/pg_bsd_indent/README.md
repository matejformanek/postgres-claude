---
path: src/tools/pg_bsd_indent
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
depth: read
---

# `src/tools/pg_bsd_indent/` — the C indenter behind `pgindent`

## What this is

`pg_bsd_indent` is PostgreSQL's lightly-patched fork of the **BSD `indent`(1)**
program (FreeBSD `usr.bin/indent`, version string `2.1.3`, see
[[knowledge/files/src/tools/pg_bsd_indent/args.c]] `INDENT_VERSION`). It is the
low-level formatter that `pgindent` (the perl wrapper in `src/tools/pgindent/`)
invokes on every `.c`/`.h` file to enforce the project's [[idioms/coding-style]]
(hard tabs, BSD braces, ~78-col lines). Historically PG depended on a separately
distributed `pg_bsd_indent`; since PG 16 it lives **in-tree** here so the whole
toolchain builds with meson/`ninja`.

It is a freestanding command-line program (`main()` in
[[knowledge/files/src/tools/pg_bsd_indent/indent.c]]), not a backend module — it
links against `src/port`/`src/common` only for `c.h`, `pg_noreturn`,
`pg_attribute_printf`, and `MAXPGPATH`, and provides its own cut-down `err`/`errx`
([[knowledge/files/src/tools/pg_bsd_indent/err.c]]).

## The pipeline (one pass, character-streamed)

```
fill_buffer()  →  lexi()        →  parse()/reduce()  →  dump_line()
(io.c: read     (lexi.c: tokenize  (parse.c: shift-     (io.c: emit the
 one line into   one token, return   reduce stack of      label+code+comment
 in_buffer)      a code from         statement shapes,    sections at the
                 indent_codes.h)     compute indent       computed columns)
                                     levels)
main() (indent.c) is the giant switch over token codes that drives all four.
pr_comment() (pr_comment.c) is the comment sub-formatter dump_line defers to.
```

Global mutable state (the buffers `s_code/e_code/l_code` etc. and the
`struct parser_state ps`) lives in
[[knowledge/files/src/tools/pg_bsd_indent/indent_globs.h]]; token-type integer
codes are in
[[knowledge/files/src/tools/pg_bsd_indent/indent_codes.h]]; the function
prototypes are in [[knowledge/files/src/tools/pg_bsd_indent/indent.h]].

## PostgreSQL-specific patches (vs upstream FreeBSD indent)

Two options were added for PG house style, both visible in
[[knowledge/files/src/tools/pg_bsd_indent/args.c]] `pro[]`:

- **`-tpg` / `-ntpg`** → `postgres_tab_rules`. Changes the tab-vs-space math in
  `indent_declaration()` (indent.c:1262-1265) and `pad_output()`
  (io.c:484-486) so a single space (not a tab) is emitted when a tab would land
  exactly one column past the target — PG's "don't let a tab eat the gap after
  a one-space-short stop" rule.
- The `is_func_definition()` lookahead (lexi.c:159-213) and the multi-line
  `lookahead()`/`lookahead_reset()` machinery (io.c:274-326) are PG additions
  so the indenter can tell a function *definition* from a *declaration* by
  scanning ahead for the first unparenthesised `{` vs `;`/`,`.

## Files in this directory

| File | LOC | Role | Doc |
|---|---|---|---|
| `indent.c` | 1278 | `main()` driver + token switch + `bakcopy` + `indent_declaration` | [[knowledge/files/src/tools/pg_bsd_indent/indent.c]] |
| `lexi.c` | 721 | Tokenizer (`lexi`), keyword table, typedef tracking | [[knowledge/files/src/tools/pg_bsd_indent/lexi.c]] |
| `io.c` | 605 | `dump_line`, `fill_buffer`, `pad_output`, lookahead buffer, `diag*` | [[knowledge/files/src/tools/pg_bsd_indent/io.c]] |
| `pr_comment.c` | 354 | Comment scanning/reflow | [[knowledge/files/src/tools/pg_bsd_indent/pr_comment.c]] |
| `args.c` | 350 | Option/profile parsing, `pro[]` table, defaults | [[knowledge/files/src/tools/pg_bsd_indent/args.c]] |
| `parse.c` | 338 | Shift-reduce statement parser (`parse`/`reduce`) | [[knowledge/files/src/tools/pg_bsd_indent/parse.c]] |
| `indent_globs.h` | 339 | Global buffers + `struct parser_state` + `CHECK_SIZE_*` | [[knowledge/files/src/tools/pg_bsd_indent/indent_globs.h]] |
| `indent_codes.h` | 71 | Token-type integer constants | [[knowledge/files/src/tools/pg_bsd_indent/indent_codes.h]] |
| `indent.h` | 53 | Function prototypes + `nitems` | [[knowledge/files/src/tools/pg_bsd_indent/indent.h]] |
| `err.h` / `err.c` | 45/67 | Cut-down `err`/`errx` | [[knowledge/files/src/tools/pg_bsd_indent/err.c]] |

## Why an agent cares

When `pgindent` mangles a patch in a surprising way (splits a function pointer
declaration oddly, mis-aligns a boxed comment, eats a blank line around
`#ifdef`), the behaviour is governed by the heuristics in these files — almost
all of them are *guesses* about C structure made from a single forward pass with
limited lookahead. The `is_func_definition` K&R caveat (lexi.c:150-157), the
`typedefs.list` mechanism (`add_typename`, lexi.c:687-721), and the
`/* INDENT OFF */` escape (io.c:389-437) are the three knobs that most often
explain "why did pgindent do *that*."

## Issue register

`knowledge/issues/tools.md` (shared with other `src/tools/` entries).
