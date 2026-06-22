---
path: src/tools/pg_bsd_indent/indent.c
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
loc: 1278
depth: deep
---

# `src/tools/pg_bsd_indent/indent.c` — the indenter driver and token switch

## Purpose

The program entry point and main loop of `pg_bsd_indent`. It (1) initialises
all the global buffers and `struct parser_state ps`, (2) scans argv + profile
files for options, then (3) runs the central `while (1)` loop that pulls one
token at a time from `lexi()`, threads it through a giant `switch` on token
type, accumulates formatted output into the label/code/comment buffers, and
flushes lines via `dump_line()`. It also owns the `DECLARE_INDENT_GLOBALS`
definition so that all the `extern` globals in `indent_globs.h` get their single
real definition here (indent.c:50). See the cluster overview in
[[knowledge/files/src/tools/pg_bsd_indent/README]].

## Public symbols

| Symbol | Lines | Notes |
|---|---|---|
| `main` | 65-1198 | Init + option scan + the token-processing main loop. |
| `in_name` / `out_name` / `bakfile` | 59-63 | File-name globals (definitions). |

## Internal landmarks

- **Initialisation block** (indent.c:90-147): mallocs the four working buffers
  (`combuf`/`labbuf`/`codebuf`/`tokenbuf`, each `bufsize`=200 to start), seeds
  `ps.p_stack[0]=stmt`, sets `ps.last_token=semicolon`. Buffers grow on demand
  via the `CHECK_SIZE_*` macros from `indent_globs.h`.
- **Option scan** (indent.c:182-219): a first pass looks for `-npro`/`-P` to
  decide whether to read `.indent.pro`; then `set_defaults()` + `set_profile()`
  + per-arg `set_option()` (all in [[knowledge/files/src/tools/pg_bsd_indent/args.c]]).
  If no output file is named and input is a real file, `bakcopy()` renames the
  input to `<base>.BAK` and writes formatting back to the original name.
- **The `search_brace` buffering loop** (indent.c:280-455): the trickiest part.
  After `if (...)`/`while (...)`/`else`, newlines and comments up to the start
  of the following statement are buffered into `sc_buf`/`save_com` so that brace
  style (`-br`/`-bl`) and `-ce` "cuddle else" can be applied uniformly. The big
  comment at indent.c:418-436 flags a known wart: `lexi()` is called here purely
  to *categorise* the next token, but it has side effects (mutates parser state,
  eats whitespace), so the code calls it on a `transient_state` copy and only
  commits the copy back if it turns out not to be a mere lookahead.
- **The token switch** (indent.c:519-1192): one `case` per code from
  `indent_codes.h` (`lparen`, `rparen`, `unary_op`, `binary_op`, `semicolon`,
  `lbrace`, `rbrace`, `sp_paren`=if/while/for, `sp_nparen`=else/do, `decl`,
  `ident`/`funcname`, `comma`, `preesc`=`#`, `comment`, …). Each appends to
  `e_code`/`e_lab` and calls `parse()` to update indent levels.
- **`#if`/`#else`/`#endif` state stack** (indent.c:1135-1156): saves/restores
  `ps` across conditional-compilation so each arm is indented as if the others
  weren't there — `state_stack[]`/`match_state[]` from `indent_globs.h`.
- **`bakcopy`** (indent.c:1205-1243): copies input to `<base>.BAK`, reopens the
  backup as input and the original name as output (the in-place edit path).
- **`indent_declaration`** (indent.c:1245-1278): emits the tabs/spaces that
  align a declared identifier to `decl_indent`/`local_decl_indent`. This is
  where the PG `postgres_tab_rules` (`-tpg`) patch lives (indent.c:1263-1265):
  emit a space instead of a tab when a tab would land exactly one column past
  the target.

## Invariants & gotchas

- **Single forward pass, heuristic structure recovery.** `indent` is not a real
  C parser; it reconstructs statement shape from a token stream with limited
  lookahead. Most "pgindent did something weird" reports trace to a heuristic
  in this switch or in `lexi()` guessing wrong.
- **`CHECK_SIZE_CODE(3)` before the switch** (indent.c:515-518): the code relies
  on the documented invariant that no `case` increments `e_code` more than twice
  before the next `CHECK_SIZE_*`/`dump_line`, plus one for the NUL. Adding a new
  case that writes more than that without its own `CHECK_SIZE_CODE` would
  overflow the code buffer. `[verified-by-code]`
- **`ps.paren_indents[20]` / `di_stack[20]` / `il[64]` are fixed caps.** Hitting
  them is handled gracefully (`diag3 "Reached internal limit"`,
  indent.c:538-542, 811-815) rather than overflowing — but deeply-nested input
  silently loses alignment fidelity past the cap.
- `pg_fallthrough` markers (indent.c:356, 926) are deliberate switch
  fall-throughs; don't "fix" them.

## Cross-refs

- [[knowledge/files/src/tools/pg_bsd_indent/lexi.c]] — `lexi()` token source.
- [[knowledge/files/src/tools/pg_bsd_indent/parse.c]] — `parse()`/`reduce()` indent stack.
- [[knowledge/files/src/tools/pg_bsd_indent/io.c]] — `dump_line()`, `fill_buffer()`.
- [[knowledge/files/src/tools/pg_bsd_indent/indent_globs.h]] — buffers + `struct parser_state`.
- [[idioms/coding-style]] — the house style this enforces.

## Potential issues

- **[ISSUE-correctness: fixed-size `bakfile` filled with unbounded `sprintf`]**
  `indent.c:1219` — `bakcopy()` does `sprintf(bakfile, "%s.BAK", p)` into
  `char bakfile[MAXPGPATH]` (indent.c:63) where `p` is the basename of the input
  path. A basename within ~4 bytes of `MAXPGPATH` overflows the buffer. Only
  reachable on the in-place-edit path (input file named, no output file). Very
  low severity for a dev tool driven by `pgindent` (which passes short temp
  names), but it is an unchecked `sprintf` into a fixed buffer. See
  `knowledge/issues/tools.md`.
