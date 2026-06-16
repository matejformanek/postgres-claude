---
path: src/tools/pg_bsd_indent/indent_globs.h
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
loc: 339
depth: deep
---

# `src/tools/pg_bsd_indent/indent_globs.h` — global buffers + `struct parser_state`

## Purpose

The shared-state header for `pg_bsd_indent`. It declares all the `extern` global
working buffers, the `CHECK_SIZE_*` buffer-growth macros, the ~80 formatting
option globals (one per `pro[]` row in
[[knowledge/files/src/tools/pg_bsd_indent/args.c]]), and the big
`struct parser_state` that carries per-position parser state. Every `.c` file in
the directory includes it; exactly one (`indent.c`, via
`#define DECLARE_INDENT_GLOBALS`) turns the `extern`s into real definitions.

## The single-definition trick

indent_globs.h:49-55 + 336-339: if `DECLARE_INDENT_GLOBALS` is defined,
`#define extern` (to nothing) so the declarations become definitions, then
`#undef extern` at the end. Only `indent.c` sets the macro (indent.c:50), so all
globals get exactly one definition there and are `extern` references everywhere
else. **Touching this without understanding it produces duplicate-symbol or
missing-symbol link errors.** `[verified-by-code]`

## Key declarations

- **The four output buffers**, each a `s_*`/`e_*`/`l_*` (start/end/limit) triple
  over a heap block: `labbuf`/`s_lab`/`e_lab`/`l_lab` (label),
  `codebuf`/`s_code`/`e_code`/`l_code` (code), `combuf`/`s_com`/`e_com`/`l_com`
  (comment), `tokenbuf`/`s_token`/`e_token`/`l_token` (current token; `token` is
  `#define`d to `s_token`, indent_globs.h:127). (indent_globs.h:112-131)
- **Input buffer**: `in_buffer`/`in_buffer_limit`/`buf_ptr`/`buf_end`
  (indent_globs.h:133-137) plus the `sc_buf[sc_size]`/`save_com`/`sc_end`
  save-comment region and `bp_save`/`be_save` (indent_globs.h:139-146).
- **`CHECK_SIZE_CODE/COM/LAB/TOKEN`** (indent_globs.h:60-110): the realloc-on-
  demand macros. Each checks `e_X + desired >= l_X`, grows the block by
  `+400+desired`, `err(1,NULL)` on OOM, and **re-derives `s_X`/`e_X`/`l_X`** into
  the new block. `CHECK_SIZE_COM` additionally preserves `last_bl`.
- **`struct parser_state`** (indent_globs.h:234-330): ~60 fields — the parser
  stack `p_stack[256]`/`il[64]`/`cstk[32]`, `tos`, indent levels (`ind_level`,
  `i_l_follow`, `ind_size`), paren bookkeeping (`p_l_follow`,
  `paren_indents[20]`, `cast_mask`/`not_cast_mask`), declaration state
  (`in_decl`, `dec_nest`, `decl_indent`), `procname[100]`, and the many
  `want_blank`/`last_*`/`search_brace` booleans. Three copies exist:
  `ps` (live), `state_stack[5]` and `match_state[5]` (for `#if`/`#else` save).

## Invariants & gotchas

- **After any `CHECK_SIZE_*`, the `s_/e_/l_` pointers may have moved** (realloc).
  Code that caches a raw pointer into one of these buffers across a
  `CHECK_SIZE_*` call must recompute it. `[verified-by-code]`
- **Fixed caps are load-bearing**: `p_stack[256]`, `il[64]`, `paren_indents[20]`,
  `state_stack[5]` (max `#if` nesting tracked), `procname[100]`. Exceeding them
  is guarded in callers (`diag`/`errx`), not here.
- `bufsize` is only 200 (the *initial* size, indent_globs.h:36); real files
  outgrow it immediately and rely on `CHECK_SIZE_*`.

## Cross-refs

- [[knowledge/files/src/tools/pg_bsd_indent/indent.c]] — the sole definer (`DECLARE_INDENT_GLOBALS`).
- [[knowledge/files/src/tools/pg_bsd_indent/args.c]] — `pro[]` targets every option global here.
- [[knowledge/files/src/tools/pg_bsd_indent/parse.c]] — operates on `p_stack`/`il`/`tos`.

## Potential issues

(none — the `#define extern` trick and realloc-invalidates-pointers rule are
deliberate; flagged above so an editor doesn't break them.)
