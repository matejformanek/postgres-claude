---
path: src/include/fe_utils/conditional.h
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 102
depth: read
---

# `src/include/fe_utils/conditional.h`

- **File:** `source/src/include/fe_utils/conditional.h` (102 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-05)

## Purpose

Defines the stack-of-automaton-states that implements nested `\if … \elif … \else … \endif`
conditionals. Shared by psql's interpreter, pgbench's interpreter, and pgbench's syntax
checker. The stack records, per nesting level, whether we are in a true/false/ignored branch
and whether a true branch has already been seen — so the interpreter knows whether to execute
code and whether to keep evaluating conditions. Implementation in `src/fe_utils/conditional.c`.
`[from-comment]` (:1-21)

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `ifState` | :29 | 6-state enum: NONE / TRUE / FALSE / IGNORED / ELSE_TRUE / ELSE_FALSE. |
| `IfStackElem` | :58 | One stack frame: `if_state` + `query_len` + `paren_depth` + `next`. |
| `ConditionalStackData` / `ConditionalStack` | :66-71 | Stack head wrapper + opaque pointer typedef. |
| `conditional_stack_create` | :74 | Allocate an empty stack. |
| `conditional_stack_reset` / `_destroy` | :76-78 | Pop-all / free. |
| `conditional_stack_depth` | :80 | Current nesting depth. |
| `conditional_stack_push` / `_pop` | :82-84 | Enter/leave a nesting level. |
| `conditional_stack_peek` / `_poke` | :86-88 | Read / overwrite top state (e.g. TRUE→IGNORED on `\elif`). |
| `conditional_stack_empty` | :90 | Is the stack empty? |
| `conditional_active` | :92 | Are we in an executing branch (top is TRUE/ELSE_TRUE)? |
| `conditional_stack_{set,get}_query_len` | :94-96 | Save/restore query-buffer length for branch rollback. |
| `conditional_stack_{set,get}_paren_depth` | :98-100 | Save/restore lexer paren depth for branch rollback. |

## Internal landmarks

- The **6-state machine** (`:29-44`) distinguishes "false but still eligible for a later true
  branch" (`IFSTATE_FALSE`) from "a true branch already happened or parent is false, so ignore
  the rest" (`IFSTATE_IGNORED`) — this is what makes `\elif` chains evaluate exactly one branch. `[from-comment]` (:31-43)
- `query_len` + `paren_depth` per frame (`:60-62`) exist so that on leaving an *inactive*
  branch the interpreter can throw away the SQL text accumulated inside it and restore the
  lexer's parenthesis nesting. The comment explains why text isn't simply suppressed at lex
  time: "that would be very invasive." `[from-comment]` (:49-56)

## Invariants & gotchas

- Only `query_len` and `paren_depth` are saved/restored across an inactive branch —
  deliberately **not** comment-nesting or string-literal state, because "a backslash command
  could never appear inside a comment or SQL literal." `[from-comment]` (:53-56)
- `conditional_active` returning false means the interpreter must skip execution but still
  track nesting (to find the matching `\endif`); it is not the same as `conditional_stack_empty`. `[verified-by-code]`

## Cross-refs

- Implementation: `src/fe_utils/conditional.c` (not yet documented per-file).
- Consumers: psql `\if` machinery, pgbench script interpreter.

## Potential issues

None — small, self-contained state-machine header with documented rationale for every field.
