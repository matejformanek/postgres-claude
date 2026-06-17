---
path: src/tools/pg_bsd_indent/pr_comment.c
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
loc: 354
depth: deep
---

# `src/tools/pg_bsd_indent/pr_comment.c` — comment scanning and reflow

## Purpose

Handles everything between `/*` and `*/`. When the main switch in
[[knowledge/files/src/tools/pg_bsd_indent/indent.c]] sees a `comment` token, it
calls `pr_comment()`, which decides the comment's alignment column, whether it
is a "box"/"block" comment that must be preserved verbatim vs a text comment
that may be reflowed to fit `max_col`, copies it into the comment buffer
(`s_com`..`e_com`), and breaks long lines at blanks.

## Public symbols

| Symbol | Lines | Role |
|---|---|---|
| `pr_comment(void)` | 78-354 | Scan and format one comment into the `s_com`/`e_com` buffer. |

## Internal landmarks

- **Box-comment detection** (pr_comment.c:99-116): a comment starting in column 1
  with `-fc1` off, or whose first char after `/*` is `-`/`*`, or (with
  `-nfcb`) a newline, is a *box comment* — `ps.box_com=true`, alignment frozen,
  no reflow. The original indentation is captured into `ps.n_comment_delta`
  (pr_comment.c:152-166) so `dump_line` can reproduce it.
- **Column choice for non-box comments** (pr_comment.c:128-150): right-of-code
  comments go to `ps.com_ind` (or `ps.decl_com_ind` in declarations);
  `#else`/`#endif` trailing comments use `else_endif_com_ind`; `adj_max_col` is
  widened to at least `com_col+24` so a comment isn't squeezed to nothing.
- **Break-delimiter logic** (`break_delim`, pr_comment.c:181-202): with `-cdb`,
  a multi-line comment gets its `/*` and `*/` on their own lines — but only if
  it actually wraps (the scan at pr_comment.c:182-190 cancels it for one-liners).
- **The copy loop** (pr_comment.c:206-353): a `switch (*buf_ptr)` over form-feed,
  newline, `*` (possible end), and default chars. It tracks `last_bl` (last
  blank) so an over-long text comment can be broken there (pr_comment.c:321-350),
  emitting ` * ` continuation prefixes when `star_comment_cont` (`-sc`) is set.

## Invariants & gotchas

- **Box/block comments are never reflowed.** This is why a hand-drawn ASCII box
  or a deliberately-formatted block survives pgindent unchanged — and why a
  comment that *looks* like prose but starts with `*` on its first content line
  is treated as a box. Knowing this resolves most "pgindent reflowed/ didn't
  reflow my comment" surprises. `[verified-by-code]`
- **`CHECK_SIZE_COM` before each append.** Like the code buffer, the comment
  buffer grows via the macro from `indent_globs.h`; the loop calls it before
  multi-byte appends (e.g. pr_comment.c:210, 235, 285). A new append path that
  skips it can overflow `combuf`.
- **Unterminated comment at EOF** (pr_comment.c:228-233): prints
  `"Unterminated comment"` to stdout (not via `diag`) and dumps what it has —
  it does **not** set `found_err`, so an unterminated comment alone won't make
  `indent` exit nonzero.
- `ps.just_saw_decl` is saved/restored around the call (pr_comment.c:88,301) so
  a comment between a declaration and its blank-line bookkeeping doesn't reset
  the `-bad` state.

## Cross-refs

- [[knowledge/files/src/tools/pg_bsd_indent/indent.c]] — dispatches to `pr_comment`.
- [[knowledge/files/src/tools/pg_bsd_indent/io.c]] — `dump_line`/`count_spaces` it calls.
- [[idioms/coding-style]] — the multi-line `/* */` comment style this enforces.

## Potential issues

(none confirmed — the box-vs-text distinction and the no-`found_err`-on-EOF
behaviour are intentional; surfaced above as gotchas.)
