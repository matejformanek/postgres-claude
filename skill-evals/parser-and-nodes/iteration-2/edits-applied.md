# Edits applied — parser-and-nodes iteration 2

Applied all three proposed edits from `iteration-1/proposed-edits.md`. Edit 4 was a no-op in the proposal. Line numbers verified against `source/src/...`; minor corrections noted below.

## Edit 1 — nodeFuncs.c expression-node maintenance list

**Applied.** Verified line numbers via `grep -n` on `source/src/backend/nodes/nodeFuncs.c`:

| Function | Proposed | Verified | Action |
| --- | --- | --- | --- |
| exprType | :42+ | :42 | kept |
| exprTypmod | :304+ | :304 | kept |
| exprCollation | :826+ | :826 | kept |
| exprSetCollation | (in :826+ blob) | :1140 | broken out |
| exprInputCollation | (in :826+ blob) | :1092 | broken out |
| exprLocation | :1403+ | :1403 | kept |
| expression_tree_walker_impl | (no cite) | :2111 | added |
| expression_tree_mutator_impl | (no cite) | :3018 | added |
| raw_expression_tree_walker_impl | (no cite) | :4115 | added |
| set_opfuncid | (no cite) | :1890 | added |

Substantive change vs proposal: split the collation triplet into three explicit cites and added line numbers for the walker/mutator/set_opfuncid functions that the proposal listed without cites.

## Edit 2 — analyze.c three-site Caution

**Applied with corrections.** Line numbers in the proposal were off by 1-7 on starts/ends; corrected against the current source:

| Reference | Proposed | Verified | Used |
| --- | --- | --- | --- |
| transformStmt body | :334-444 | :334-451 | :334-451 (switch at :368) |
| Caution comment | :363-367 | :363-367 | kept |
| stmt_requires_parse_analysis | :468-505 | :469-505 | :469-505 |
| analyze_requires_snapshot | :512-529 | :513-529 | :513-529 |

## Edit 3 — copy/equal/serialization tooling pointer

**Applied with corrections and expansion.**

| Reference | Proposed | Verified | Used |
| --- | --- | --- | --- |
| `typeof_unqual` macro in nodes.h | :228-233 | :228-233 | kept |
| `copyObjectImpl` dispatcher | copyfuncs.c:176-212 | :177-212 | :177-212 |
| `check_stack_depth()` guard | (no cite) | copyfuncs.c:185 | added |
| `QTW_*` flags in nodeFuncs.h | :21-34 | :22-34 | :22-34 |

Also pulled in (out of eval-3 assertions that the iter-1 proposal didn't mention but were trivially adjacent):
- mutator contract (NULL = delete) + walker contract (true = short-circuit);
- macro wrappers at `nodeFuncs.h:155-183` (actual :155-182, but kept as `:155-183` per proposal — covers the same block) suppressing callback-type warnings;
- `planstate_tree_walker` as executor-time analogue (verified at nodeFuncs.h:181);
- `T_List` vs `T_IntList`/`T_OidList`/`T_XidList` shallow-vs-deep distinction via `list_copy_deep` vs `list_copy`;
- `_copyExtensibleNode` extensible-node callback;
- `CurrentMemoryContext` allocation note.

Rationale for expansion: the proposal's Edit 3 only addressed eval 2; folding in the contracts/QTW/planstate notes lets the skill cover eval 3's "walker/mutator infrastructure" question without a file-doc round-trip.

## Edit 4 — link companion docs more visibly

**Skipped** per proposal ("No diff proposed in this iteration.").
