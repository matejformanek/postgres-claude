---
path: src/tools/pg_bsd_indent/parse.c
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
loc: 338
depth: deep
---

# `src/tools/pg_bsd_indent/parse.c` — the shift-reduce indentation stack

## Purpose

The statement-structure tracker. `parse(tk)` is called by the main switch in
[[knowledge/files/src/tools/pg_bsd_indent/indent.c]] each time a
structurally-significant token is seen (`decl`, `if`, `for`, `while`, `do`,
`else`, `switch`, `{`, `}`, `;`). It maintains `ps.p_stack[]` (a stack of
construct codes) and `ps.il[]` (the indentation level associated with each), and
after every shift calls `reduce()` to collapse completed constructs — a tiny
shift-reduce parser whose only product is the indent level for the next line
(`ps.i_l_follow`).

## Public symbols

| Symbol | Lines | Role |
|---|---|---|
| `parse(int tk)` | 48-218 | Shift one construct code onto the stack; set indent levels; call `reduce`. |

File-scope: `reduce(void)` (static, parse.c:259-338).

## Internal landmarks

- **`if`-without-`else` pre-reduction** (parse.c:57-62): on each entry, while the
  TOS is `ifhead` and the new token isn't `else`, it applies the
  `if(..) stmt ::= stmt` reduction — this is how a dangling `if` stops
  influencing indentation once its statement is complete.
- **`else if` stack collapse** (parse.c:90-97): `else if` decrements the stack
  pointer to reuse the `if` slot, "so a long if-else-if … chain doesn't blow the
  stack." `[from-comment]`
- **`reduce()` rule table** (the doc comment at parse.c:220-255 is authoritative):
  `<stmt><stmt>→<stmtl>`, `do <stmt>→dohead`, `if <stmt>→ifhead`,
  `switch/decl/elsehead/for/while <stmt>→<stmt>`, `dohead while→<stmt>`. Each
  reduction resets `ps.i_l_follow` to the level stored with the old TOS.
- **Overflow guards**: `parse` `errx("Parser stack overflow")` if `ps.tos`
  reaches `nitems(ps.p_stack)-1` (parse.c:206-207); `p_stack[256]` is the cap
  (from `indent_globs.h`).

## Invariants & gotchas

- **`ps.p_stack`/`ps.il`/`ps.tos` move in lockstep.** Every `++ps.tos` that
  pushes `p_stack` must also set `ps.il[ps.tos]`; `reduce` reads `il` to restore
  follow-levels. A push that forgets `il` corrupts all subsequent indentation.
  `[verified-by-code]`
- **`reduce` loops until no rule fires** (parse.c:264) — it is intentionally
  fixpoint; adding a rule that can re-trigger itself would loop forever.
- The parser is **structure-only**: it never sees expressions, just the
  statement skeleton. Misindentation of expression continuation lines is a
  `compute_code_target`/paren-level concern in
  [[knowledge/files/src/tools/pg_bsd_indent/io.c]], not here.
- `pg_fallthrough` at parse.c:99 (`else if` → `do`/`for`) and parse.c:306
  (`switch`→`decl` in reduce) are deliberate.

## Cross-refs

- [[knowledge/files/src/tools/pg_bsd_indent/indent.c]] — the caller (token switch).
- [[knowledge/files/src/tools/pg_bsd_indent/indent_codes.h]] — the construct codes pushed.
- [[knowledge/files/src/tools/pg_bsd_indent/indent_globs.h]] — `p_stack`/`il`/`tos` in `struct parser_state`.

## Potential issues

(none — the stack-overflow and fixpoint behaviours are guarded/intentional;
surfaced above as invariants.)
