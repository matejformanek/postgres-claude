---
path: src/tools/pg_bsd_indent/io.c
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
loc: 605
depth: deep
---

# `src/tools/pg_bsd_indent/io.c` — line emission, input buffering, lookahead, diagnostics

## Purpose

The I/O and column-arithmetic layer of `pg_bsd_indent`. It owns: `dump_line()`
(actually writes one formatted source line from the label/code/comment buffers),
`fill_buffer()` (reads one input line into `in_buffer`), the multi-line
`lookahead()` buffer that lets `lexi`/`is_func_definition` peek past the current
line, the `compute_*_target()` column calculators, `pad_output()` (tabs/spaces
to reach a target column), and the `diag2/3/4()` warning/error reporters.
Consumed by [[knowledge/files/src/tools/pg_bsd_indent/indent.c]].

## Public symbols

| Symbol | Lines | Role |
|---|---|---|
| `dump_line` | 60-220 | Emit the pending label + code + comment at their computed columns; reset buffers. |
| `compute_code_target` | 222-249 | Target column for the code section (handles paren line-up, continuation indent). |
| `compute_label_target` | 251-258 | Target column for labels / `case` / `#` lines. |
| `lookahead` | 274-313 | Read further ahead than `in_buffer`; grows a malloc'd buffer. |
| `lookahead_reset` | 319-326 | Rescan from just past `in_buffer`. |
| `fill_buffer` | 345-437 | Read the next input line; handle `/* INDENT ON/OFF */`. |
| `pad_output` | 467-494 | Write tabs/blanks to advance from `current` to `target` column. |
| `count_spaces_until` / `count_spaces` | 516-553 | Compute the column after printing a string (tab/backspace/FF aware). |
| `diag2` / `diag3` / `diag4` | 555-604 | Emit a warning/error (sets `found_err` on level≠0). |

File-scope globals: `comment_open`, `paren_target`, and the `lookahead_*`
buffer pointers (io.c:48-56).

## Internal landmarks

- **`dump_line`** is where the three buffers become one physical line. It emits
  pending blank lines (`n_real_blanklines`, governed by the `-bad`/`-bap`/`-sob`
  family), prints the label section (with special handling to append the macro
  name after `#else`/`#endif`, io.c:117-128), then the code at
  `compute_code_target()`, then any same-line comment at `ps.com_col`. It
  finally resets `e_lab/e_code/e_com` and rolls `ind_level = i_l_follow`.
- **`fill_buffer`** (io.c:345-437) also implements the `/* INDENT OFF */` …
  `/* INDENT ON */` escape: it pattern-matches the magic comment (io.c:389-427)
  and toggles `inhibit_formatting`, in which case it echoes input lines through
  verbatim. It also drops a leading `/**INDENT**` line (the indenter's own error
  marker) to avoid feedback.
- **`lookahead`** (io.c:274-313): first drains any `bp_save` region, then reads
  fresh chars from `input` into a doubling malloc'd buffer; `errx("too much
  lookahead required")` only on OOM. Reset semantics are documented at
  io.c:260-273.
- **`postgres_tab_rules` patch** lives in `pad_output` (io.c:484-486): emit a
  space instead of a tab when a tab would overshoot the target by exactly one
  column — the PG `-tpg` behaviour, mirrored in `indent_declaration`.

## Invariants & gotchas

- **Buffers are not NUL-terminated by `fill_buffer`.** The header comment
  (io.c:334-339) notes `buf_ptr`/`buf_end` bracket the line but no NUL is
  appended; consumers must respect `buf_end`. A loop that scans for `\0` instead
  of checking `buf_end` will run off the end.
- **`fill_buffer` always appends `' ' '\n'` at EOF** (io.c:376-378) and sets
  `had_eof` — downstream code distinguishes the synthetic trailing newline from
  real ones via `had_eof` (see `lexi` newline case).
- **Lookahead auto-resets** whenever `fill_buffer` consumes past it
  (io.c:371-374) — you cannot use it for "look behind." `[from-comment]`
- `diag*` route to **stdout as `/**INDENT** …*/` comments** when output is
  stdout, else to stderr (io.c:560-566). This is why piping through indent can
  inject `/**INDENT**` markers into the stream — and why `fill_buffer` filters
  them back out on a subsequent run.
- The `(char) 0200` sentinel handling in `dump_line` (io.c:153-155) prints
  `target_col * 7` — a legacy troff-mode magic byte; irrelevant to normal C
  formatting but don't remove it without understanding `-troff`.

## Cross-refs

- [[knowledge/files/src/tools/pg_bsd_indent/indent.c]] — calls `dump_line`/`fill_buffer`.
- [[knowledge/files/src/tools/pg_bsd_indent/lexi.c]] — uses `lookahead`.
- [[knowledge/files/src/tools/pg_bsd_indent/indent_globs.h]] — the buffer pointers + `CHECK_SIZE_*`.

## Potential issues

(none confirmed — the non-NUL-terminated buffer and lookahead-reset semantics
are documented invariants, surfaced above so a future editor doesn't trip on
them.)
