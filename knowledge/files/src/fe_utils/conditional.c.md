# `src/fe_utils/conditional.c`

- **File:** `source/src/fe_utils/conditional.c` (189 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-04)

## Purpose

A stack of automaton states implementing nested `\if` / `\elif` / `\else` /
`\endif` conditional blocks. It is the data-structure half of psql's
client-side conditional execution (the policy — which `ifState` transition a
given meta-command triggers — lives in psql itself, e.g. `command.c`). Each
open `\if` block is one stack element carrying its current `ifState` plus two
saved scalars (query-buffer length and parenthesis depth) that psql uses to
restore the query buffer when a branch is skipped. Frontend memory rules:
elements are `pg_malloc_object`'d and released with `free`. [verified-by-code:
include + comment at `conditional.c:1-12`]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `conditional_stack_create` | :17 | Allocate an empty stack (`head = NULL`). |
| `conditional_stack_reset` | :29 | Pop and free every element; the stack struct itself survives. |
| `conditional_stack_destroy` | :43 | `reset` then `free` the stack struct. |
| `conditional_stack_push` | :53 | Push a new branch with a given initial `ifState`. |
| `conditional_stack_pop` | :69 | Pop+free the top element; false if the stack was empty. |
| `conditional_stack_depth` | :84 | Count elements (debugging); -1 if stack is NULL. |
| `conditional_stack_peek` | :106 | Return the top element's `ifState`, or `IFSTATE_NONE` if empty. |
| `conditional_stack_poke` | :118 | Overwrite the top element's `ifState`; false if empty. |
| `conditional_stack_empty` | :130 | True if `head == NULL`. |
| `conditional_active` | :140 | True if commands should currently execute (see below). |
| `conditional_stack_set_query_len` | :151 | Stash query-buffer length in the top element. |
| `conditional_stack_get_query_len` | :162 | Retrieve it; -1 if empty/unset. |
| `conditional_stack_set_paren_depth` | :173 | Stash parenthesis nesting depth in the top element. |
| `conditional_stack_get_paren_depth` | :184 | Retrieve it; -1 if empty/unset. |

## Internal landmarks

- `conditional_stack_push` (`:53`) initializes a fresh `IfStackElem` with `query_len = -1` and `paren_depth = -1` (`:58`–`:59`) — the sentinel "never saved" values that the `get_*` accessors return.
- `conditional_active` (`:140`) is the execution gate: it peeks the top state and returns true for exactly `IFSTATE_NONE` (no open `\if`), `IFSTATE_TRUE`, or `IFSTATE_ELSE_TRUE` (`:144`). All other states (false branches, an already-satisfied branch that has moved on, error/ignored states) mean commands are skipped.
- `conditional_stack_peek` returns `IFSTATE_NONE` for an empty stack (`:108`), so `conditional_active` on a never-`\if`'d session correctly reports "execute normally."
- The `query_len`/`paren_depth` accessors (`:151`–`:189`) tolerate an empty stack on the `get` side (returning -1) but `Assert(!conditional_stack_empty(cstack))` on the `set` side (`:153`, `:175`) — setting requires an open branch, getting does not.

## Invariants & gotchas

- **Two free idioms coexist.** `conditional_stack_create`/`push` allocate via `pg_malloc_object`, but `conditional_stack_pop` (`:76`) and `conditional_stack_destroy` (`:46`) release via plain `free()` rather than `pg_free`. This is harmless (`pg_malloc` is `malloc`-compatible) but is a minor inconsistency relative to the other fe_utils files. [verified-by-code] `:55`, `:76`, `:46`
- **`reset` keeps the stack, `destroy` frees it.** `conditional_stack_reset` (`:29`) empties the list but leaves a reusable stack; `conditional_stack_destroy` (`:43`) calls reset then frees the container. Don't use the stack after destroy. [verified-by-code]
- **NULL-tolerance is uneven by design.** `conditional_stack_reset` (`:32`), `conditional_stack_depth` (`:86`), and the `get_*`/`peek`/`empty` accessors guard against a NULL or empty stack, but `conditional_stack_push`/`pop`/`poke`/`empty` dereference `cstack` directly — passing a NULL stack to `push` will crash. [verified-by-code] `:60`, `:71`, `:132`
- **`query_len`/`paren_depth` sentinel is -1.** A return of -1 from `conditional_stack_get_query_len`/`get_paren_depth` means "no stack, or never saved," not a valid length/depth. Callers must distinguish. [from-comment] `:159`, `:182`
- **State transition policy is NOT here.** This file only stores/retrieves `ifState`; the rules mapping `\if`/`\elif`/`\else`/`\endif` to state changes live in the psql command layer. A correctness bug in branch evaluation is unlikely to be in this file. [inferred]

## Cross-references

- `source/src/include/fe_utils/conditional.h` — defines `ConditionalStack`, `ConditionalStackData`, `IfStackElem` (the `if_state`/`query_len`/`paren_depth`/`next` fields), and the `ifState` enum (`IFSTATE_NONE`, `IFSTATE_TRUE`, `IFSTATE_FALSE`, `IFSTATE_IGNORED`, `IFSTATE_ELSE_TRUE`, `IFSTATE_ELSE_FALSE`).
- `source/src/bin/psql/command.c` — implements `\if`/`\elif`/`\else`/`\endif`, driving `push`/`poke`/`pop` and the `set_query_len`/`set_paren_depth` save-restore around skipped branches.
- `source/src/bin/psql/mainloop.c` — consults `conditional_active` to decide whether to execute or discard each command.
- `source/src/bin/pgbench/pgbench.c` — also uses this conditional stack for its `\if` support.

## Confidence tag tally

- `[verified-by-code]` × 6
- `[from-comment]` × 1
- `[inferred]` × 1
