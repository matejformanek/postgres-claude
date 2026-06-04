# pl_funcs.c

**Source pin:** `4b0bf0788b0`. Lines read: 1–1694 (complete).

## One-line summary

Lower-glamour utility module for plpgsql: owns the file-scope namespace
stack (`ns_top`), provides AST traversal (`plpgsql_statement_tree_walker`),
the `mark_local_assignment_targets` optimization pre-pass, the
function-memory release path (`plpgsql_free_function_memory` +
`plpgsql_delete_callback`), the assert-only debug printer
(`plpgsql_dumptree`), and a pair of string maps
(`plpgsql_stmt_typename`, `plpgsql_getdiag_kindname`) used in error
messages.

Notably **does NOT** contain the subxact callback. `plpgsql_subxact_cb`
lives in `source/src/pl/plpgsql/src/pl_exec.c:8853`
[verified-by-code via `grep "plpgsql_subxact_cb("`]; the brief was
incorrect on that point.

## Public API / entry points

All externally callable, declared in
`source/src/pl/plpgsql/src/plpgsql.h`; cites are
`source/src/pl/plpgsql/src/pl_funcs.c:<line>`:

- `plpgsql_ns_init(void)` — reset `ns_top` to `NULL` at the start of
  every fresh compile. Lines 42–46. [verified-by-code]
- `plpgsql_ns_push(const char *label, PLpgSQL_label_type label_type)`
  — open a new namespace block by appending a label item; empty string
  is substituted for `NULL`. Lines 53–59. [verified-by-code]
- `plpgsql_ns_pop(void)` — pop the chain back through (and including)
  the most recent `PLPGSQL_NSTYPE_LABEL`. Asserts `ns_top != NULL`.
  Lines 66–73. [verified-by-code]
- `plpgsql_ns_top(void)` — current chain head, snapshotted by every
  `PLpgSQL_expr` so that runtime variable resolution sees the correct
  block scope. Lines 80–84. [verified-by-code]
- `plpgsql_ns_additem(itemtype, itemno, name)` — generic add: palloc's
  `offsetof(nsitem, name) + strlen(name) + 1`, links via `prev`. Asserts
  that the first item ever added is a label. Lines 91–106.
  [verified-by-code]
- `plpgsql_ns_lookup(ns_cur, localmode, name1, name2, name3, names_used)`
  — recursive variable lookup; never matches labels. Two passes per
  level: unqualified by `name1`, then qualified `name1.name2`. See the
  invariants and "name shadowing" notes below. Lines 129–187.
  [verified-by-code]
- `plpgsql_ns_lookup_label(ns_cur, name)` — label-only walk back through
  the chain. Lines 194–206. [verified-by-code]
- `plpgsql_ns_find_nearest_loop(ns_cur)` — used by `EXIT`/`CONTINUE`
  without an explicit label; finds the closest `PLPGSQL_LABEL_LOOP`.
  Lines 213–225. [verified-by-code]
- `plpgsql_stmt_typename(PLpgSQL_stmt *)` — `cmd_type` → human-readable
  string (e.g. `"IF"`, `"statement block"`); used in `errcontext` and
  `errmsg`. Some strings are translated via `_()`, others are bare
  identifiers — see invariants. Lines 231–294. [verified-by-code]
- `plpgsql_getdiag_kindname(PLpgSQL_getdiag_kind)` — `kind` → label
  for `GET DIAGNOSTICS` items. All bare identifiers (untranslated).
  Lines 299–333. [verified-by-code]
- `plpgsql_mark_local_assignment_targets(PLpgSQL_function *)` — second
  pass after parsing, only useful when the function has exception
  blocks; refines the conservative `target_is_local=true` set by
  `mark_expr_as_assignment_source` (in `pl_gram.y`). Lines 672–683.
  [verified-by-code]
- `plpgsql_free_function_memory(PLpgSQL_function *)` — release SPI plans
  cached inside every `PLpgSQL_expr` in the function, then drop the
  function's permanent memory context. **Asserts `cfunc.use_count == 0`**.
  Lines 715–768. [verified-by-code]
- `plpgsql_delete_callback(CachedFunction *)` — deletion callback handed
  to `funccache.c`; just calls `plpgsql_free_function_memory`. Lines
  771–775. [verified-by-code]
- `plpgsql_dumptree(PLpgSQL_function *)` — debug printer to **stdout**,
  invoked only when `plpgsql_DumpExecTree` is set via the
  `#option dump` comp-option (see `pl_gram.y:385–388`). Lines 1600–1694.
  [verified-by-code]

## Key invariants

- **First item added must be a label.**
  `Assert(ns_top != NULL || itemtype == PLPGSQL_NSTYPE_LABEL)` at line
  98. Encoding a stack: every block prefix begins with a label so
  `plpgsql_ns_pop()` knows where to stop. [verified-by-code]
- **Namespace lookup never returns label items.**
  `plpgsql_ns_lookup` walks each block-level only over the run between
  `ns_cur` and the next label; once it hits the label it either descends
  to `nsitem->prev` (outer block) or breaks (`localmode`). Lines 140–142,
  177–180. [verified-by-code]
- **`names_used` is always written when caller passes a non-NULL
  pointer**, even on no-match (set to 0 at line 184–185). Avoids
  uninitialized-variable use in callers. [from-comment]
- **AST walker visits exactly the substatements the executor will run.**
  Every `cmd_type` arm of `plpgsql_statement_tree_walker_impl` either
  recurses through the right fields or has an explicit
  "no interesting sub-structure" comment. `default:` arm
  `elog(ERROR, "unrecognized cmd_type: %d", ...)` at line 595 makes
  silent omission of a new statement type impossible. [verified-by-code]
- **`plpgsql_free_function_memory` is single-shot.** After it runs,
  `func->ndatums = 0`, `func->action = NULL`, `func->fn_cxt = NULL`.
  Caller must ensure no live execution is in flight (`use_count == 0`
  assert at line 721). Lines 754, 758, 766–767. [verified-by-code]
- **`PLpgSQL_function` struct itself is NOT freed** by
  `plpgsql_free_function_memory`. Comment at lines 760–763:
  *"finally, release all memory except the PLpgSQL_function struct
  itself (which has to be kept around because there may be multiple
  fn_extra pointers to it)"*. The struct leaks until the caller's
  context dies. [from-comment]
- **`mark_stmt` resets `local_dnos` to NULL when entering a nested
  exception scope.** Lines 627–640: a `PLPGSQL_STMT_BLOCK` with
  `exceptions` invalidates everything outer (including the block's own
  DECLARE-section vars), so the recursion passes `NULL` as `local_dnos`.
  [from-comment + verified-by-code]
- **Function arguments are treated as local targets at the outermost
  level.** Lines 678–681: `local_dnos` is seeded with
  `func->fn_argvarnos[]` before walking `func->action`. This is the
  optimization handle that allows error-path elision of in-arg
  preservation in functions without exception blocks. [verified-by-code]

## Major functions

### Namespace stack

The model is a tree stored as singly-linked-list cells (`prev` only);
the "current chain" is whatever runs from `ns_top` back to NULL.
Block boundaries are `PLPGSQL_NSTYPE_LABEL` cells. During parsing,
`plpgsql_ns_push` opens a block and `plpgsql_ns_pop` closes it.
After parsing, every `PLpgSQL_expr` captured `ns_top` at parse time
(`expr->ns = plpgsql_ns_top()` at `pl_gram.y:2679`), and runtime
identifier lookup walks from that snapshot.

The double-pass structure of `plpgsql_ns_lookup` is subtle:

1. For each block level (between two labels), scan from `ns_cur` to the
   label looking for an unqualified `name1` match.
2. If no match at this level AND caller supplied `name2`, scan again
   looking for a label-matching `name1` then walk into that block for
   `name2`.

`name3` is never directly matched — it only forces the function to
disregard scalar-variable hits (because they can't have a third
component). Comment at lines 122–127. [from-comment]

### Statement-tree walker

`plpgsql_statement_tree_walker(stmt, stmt_cb, expr_cb, ctx)` (macro at
line 359) — generic visitor. The void-* cast macro is a deliberate
borrowing from `nodeFuncs.h` for the same readability reason
(comment lines 354–358).

`plpgsql_statement_tree_walker_impl` (lines 363–598) dispatches on
`cmd_type` and walks the right children. Cases for `GETDIAG`, `CLOSE`,
`COMMIT`, `ROLLBACK` are explicit no-ops. The `default:` `elog(ERROR)`
at line 595 is the "audit gap closer" — adding a new `cmd_type` without
a walker arm fails the next time the compiler tries to walk an example.

Currently used by:

- `mark_stmt` / `mark_expr` — the local-assignment-target pre-pass
  (lines 622–670).
- `free_stmt` / `free_expr` — releases SPI plans for every
  `PLpgSQL_expr->plan` (lines 697–713).

### Free path

`plpgsql_free_function_memory` (lines 715–768) is the **only** way a
compiled plpgsql function gets released. Sequence:

1. For each datum (VAR/PROMISE/REC), free SPI plans held in
   `default_val` and `cursor_explicit_expr` via `free_expr`. ROW and
   RECFIELD have no plans of their own. (Lines 724–753.)
2. Set `ndatums = 0` (line 754).
3. Walk the action tree calling `free_expr` on every embedded
   `PLpgSQL_expr` — this is what releases each statement's SPI plan
   (lines 706–713, dispatched via the walker).
4. `MemoryContextDelete(func->fn_cxt)` releases the per-function
   long-lived arena that owns the parse-tree itself (line 766).

[ISSUE-correctness: free_stmt swallows NULL but free_expr does not
guard expr being NULL before dereferencing expr->plan (likely)] —
actually it does — `if (expr && expr->plan)` at line 708. OK,
defensive code is in place.

[ISSUE-memory: `plpgsql_free_function_memory` leaves the
`PLpgSQL_function` struct dangling forever (documentation)] —
`source/src/pl/plpgsql/src/pl_funcs.c:760-768` — by design, because
external `fn_extra` pointers may still reference it; the comment
acknowledges this. Worth surfacing because it's a slow leak vector
under heavy function churn (rare, but real).

### `mark_stmt` / `mark_expr` optimization

The 2-step idea: `mark_expr_as_assignment_source` (`pl_gram.y:2688`)
optimistically sets `expr->target_is_local = true` for every
`DTYPE_VAR` assignment target. After full parse,
`plpgsql_mark_local_assignment_targets` walks the tree carrying a
Bitmapset of variables actually local-to-the-current-exception-scope
and overwrites `target_is_local` to the truth.

Why bother: a non-local target whose source expression errors out
inside an exception-protected sub-block must be preserved (the
exception handler can read it), so executor cannot reuse its storage.
A local target can be clobbered freely since the exception
unwind kills it anyway. Comment at lines 601–618.

### Dump tree

`plpgsql_dumptree` (line 1600) and the 20-some `dump_*` static
helpers — straightforward indented printout to `stdout`, gated on
`plpgsql_DumpExecTree`. The `#option dump` comp-option (pl_gram.y:385)
is the only switch; there is no GUC. Indent state lives in the
file-scope static `dump_indent` (line 784).

[ISSUE-audit-gap: dump output goes to raw stdout, not the elog stream
(maybe)] — `source/src/pl/plpgsql/src/pl_funcs.c:1606,1689,1693` use
`printf` + `fflush(stdout)`. On a server backend, stdout is generally
the postmaster log fd, so this lands in the server log — but bypasses
`ereport`'s structured-fields/translation/severity machinery and
client-side `RAISE LEVEL` settings. Acceptable for a developer-only
`#option dump`, but a sharp edge if user code ever enables it on a
hot path.

### Subtransaction callback (NOT here)

Worth recording for the next reader: `plpgsql_subxact_cb` is defined in
`source/src/pl/plpgsql/src/pl_exec.c:8853` and prototyped in
`source/src/pl/plpgsql/src/plpgsql.h:1270`. It is **not** in pl_funcs.c
despite the brief's hint. Its registration site is in pl_handler.c at
line 390. The skill `plpgsql.h` definition is the right starting point
for a future "subxact lifecycle" doc.

## Statement-type and diag-kind string maps

`plpgsql_stmt_typename` (lines 231–294) and `plpgsql_getdiag_kindname`
(lines 299–333) are exhaustive switch statements over their enum's full
range. Both fall through to `return "unknown"` if the value is out of
range — note this is a quiet failure, not an `elog`, because callers
use these to build error messages and an `elog` from inside an error
path would be catastrophic. [inferred]

[ISSUE-documentation: `plpgsql_stmt_typename` mixes translated and
untranslated entries (nit)] —
`source/src/pl/plpgsql/src/pl_funcs.c:237,239,249,251,253,255,269,273`
wrap their string with `_()`, but lines 241–247, 257–267, 271,
277–290 do not. The pattern appears to be: marker strings (token-like:
`"IF"`, `"LOOP"`, `"RAISE"`) are bare; descriptive phrases
(`"statement block"`, `"assignment"`, `"FOR with integer loop variable"`)
are translatable. Probably intentional but worth a comment.

## Cross-references

- Sibling files in `src/pl/plpgsql/src/`:
  - `pl_gram.y` — producer of every AST node that `plpgsql_*` here
    walks/frees/dumps. Calls `plpgsql_ns_push/pop` and
    `plpgsql_ns_lookup` directly during parse.
  - `pl_comp.c` — calls `plpgsql_ns_init` at compile start, builds
    `func->datums[]` that `plpgsql_free_function_memory` later releases.
  - `pl_exec.c` — the **only** consumer of
    `plpgsql_statement_tree_walker` (transitive: via the executor's
    statement dispatch — actually no, executor has its own switch; the
    walker is only used by the two callers in this file). Owns
    `plpgsql_subxact_cb` (line 8853).
  - `pl_handler.c` — registers `plpgsql_delete_callback` with funccache
    machinery and `plpgsql_subxact_cb` with `RegisterSubXactCallback`.
  - `plpgsql.h` — externs for every public symbol in this file
    (lines 1244–1330 approx).
- Backend:
  - `source/src/include/nodes/bitmapset.h` — `bms_*` ops in the
    mark-local pre-pass.
  - `source/src/backend/utils/cache/funccache.c` — calls
    `plpgsql_delete_callback` via the deletion-callback hook
    on `CachedFunction`.
  - `source/src/backend/executor/spi.c` — `SPI_freeplan` consumer.

## Issues spotted

- [ISSUE-memory: `PLpgSQL_function` struct intentionally leaks after
  `plpgsql_free_function_memory` (documentation)] —
  `source/src/pl/plpgsql/src/pl_funcs.c:760-768` — by-design per the
  comment; surface for "long-running backend with high function
  churn" auditors.
- [ISSUE-audit-gap: `plpgsql_dumptree` writes to raw stdout/printf
  rather than elog (nit)] —
  `source/src/pl/plpgsql/src/pl_funcs.c:1606,1689,1693` — bypasses
  client `RAISE LEVEL`, translation, and structured-error fields.
  Only triggered by the dev-only `#option dump`; impact bounded.
- [ISSUE-documentation: `plpgsql_stmt_typename` inconsistent
  translation of switch arms (nit)] —
  `source/src/pl/plpgsql/src/pl_funcs.c:231-294` — mixing `_()`-wrapped
  and bare strings; pattern is consistent (markers bare, phrases
  translatable) but undocumented in the file.
- [ISSUE-defense-in-depth: `plpgsql_dumptree` exposes the full compiled
  AST + variable defaults + cursor queries to whatever reads stdout
  (maybe)] — `source/src/pl/plpgsql/src/pl_funcs.c:1600-1694` — only
  triggered by `#option dump` written into the function source itself,
  so user must already have CREATE FUNCTION privilege. Not a leak
  vector, but worth noting: a SECURITY DEFINER function with
  `#option dump` would dump its body to the server log on every call.
- [ISSUE-correctness: array overflow check in
  `read_into_scalar_list` lives across the file boundary in `pl_gram.y`
  (nit)] — N/A here; relevant to the gram file.
