---
path: src/tools/pg_bsd_indent/indent.h
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
loc: 53
depth: read
---

# `src/tools/pg_bsd_indent/indent.h` — function prototypes + `nitems`

## Purpose

The prototype header tying the directory together: declares the cross-file
functions (`lexi`, `parse`, `pr_comment`, `dump_line`, `fill_buffer`,
`lookahead`/`lookahead_reset`, the `compute_*_target`/`count_spaces*` column
helpers, the `diag2/3/4` reporters, `add_typename`/`alloc_typenames`, and the
option entry points `set_defaults`/`set_option`/`set_profile`). Also defines the
ubiquitous `nitems(x)` array-length macro (indent.h:31) and a forward
declaration of `struct parser_state` (indent.h:33).

## Declared symbols (by owning file)

| Owner | Symbols |
|---|---|
| [[knowledge/files/src/tools/pg_bsd_indent/lexi.c]] | `lexi`, `add_typename`, `alloc_typenames` |
| [[knowledge/files/src/tools/pg_bsd_indent/parse.c]] | `parse` |
| [[knowledge/files/src/tools/pg_bsd_indent/pr_comment.c]] | `pr_comment` |
| [[knowledge/files/src/tools/pg_bsd_indent/io.c]] | `dump_line`, `fill_buffer`, `lookahead`, `lookahead_reset`, `compute_code_target`, `compute_label_target`, `count_spaces`, `count_spaces_until`, `diag2`, `diag3`, `diag4` |
| [[knowledge/files/src/tools/pg_bsd_indent/args.c]] | `set_defaults`, `set_option`, `set_profile` |

## Gotchas

- It is BSD-licensed (Jens Schweikhardt, 2001) and carries the FreeBSD
  `$FreeBSD: head/usr.bin/indent/indent.h$` provenance line in a `#if 0` block
  (indent.h:27-29) — a marker that this whole directory is a vendored import,
  not PG-authored.
- `nitems(x)` is the same `sizeof(x)/sizeof(x[0])` idiom PG uses as `lengthof`
  elsewhere; here it is local to the indenter and applied to the parser's fixed
  arrays (`ps.paren_indents`, `ps.p_stack`, `di_stack`, …).

## Cross-refs

- [[knowledge/files/src/tools/pg_bsd_indent/README]] — directory overview.
- [[knowledge/files/src/tools/pg_bsd_indent/indent_globs.h]] — `struct parser_state` (forward-declared here).

## Potential issues

(none — a prototype header.)
