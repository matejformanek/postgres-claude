---
scenario: add-new-node-type
when_to_use: Adding a new tagged Node (parse, plan, or primitive expression) and need the full sweep of headers + generated copy/equal/out/read/jumble + nodeFuncs.c walker/mutator/exprType edits.
companion_skills: ["parser-and-nodes"]
related_scenarios: ["add-new-plan-node","add-new-utility-statement"]
canonical_commit: 964d01ae90c
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new Node type

## Scope — what's in / out

**In scope:**
- Declaring a new `typedef struct Foo { ... } Foo;` in
  `primnodes.h` / `parsenodes.h` / `plannodes.h` and getting the
  generated `T_Foo` enum + `_copyFoo` / `_equalFoo` / `_outFoo` /
  `_readFoo` / `_jumbleFoo` to land via `gen_node_support.pl`.
- Picking the right `pg_node_attr(...)` annotations (abstract,
  custom_copy_equal, custom_read_write, custom_query_jumble, no_copy,
  no_equal, no_read, no_query_jumble, nodetag_only, …) so the
  generator emits what you need and skips what you don't.
- Wiring `nodeFuncs.c` if the Node is an Expr subtype (the
  walker/mutator switches, `exprType` / `exprTypmod` / `exprCollation`
  / `exprLocation`, and `raw_expression_tree_walker` if it can appear
  in raw parse trees).
- Catversion bump iff the Node's external representation can land in
  a catalog (stored rewrite rules, SQL function bodies, view defs,
  default expressions, partition bounds — anything serialised via
  `nodeToString`).

**Out of scope:**
- A whole new Plan node with executor support — that's
  [add-new-plan-node](add-new-plan-node.md). This scenario stops at
  the Node-machinery layer; it doesn't cover `ExecInitFoo` / `nodeFoo.c`.
- A new utility statement struct — covered by
  [add-new-utility-statement](add-new-utility-statement.md) (the
  `XxxStmt` Node *plus* ProcessUtility dispatch + tab-completion).
- Extension-defined nodes via `ExtensibleNode` — `extensible.[ch]`
  has its own registry and doesn't touch `gen_node_support.pl`.

## Pre-flight

- **Companion skills:** load `parser-and-nodes`. It names the
  procedural rules for `gen_node_support.pl`, the `Expr` inheritance
  pattern, and the round-trip discipline.
- **Canonical commit:** `964d01ae90c` — *Automatically generate node
  support functions*. The watershed commit that replaced the
  hand-maintained copy/equal/out/read files with the Perl generator.
  Read it before starting — it documents the annotation language. The
  follow-ups `ca187d7455f` (nodetag_only), `5d29d525ffe` (comment
  format), and `5ac462e2b7a` (custom_query_jumble as a field attr)
  refine the model. TODO: a more recent "added one new Node"
  representative — `80feb727c86` (OLD/NEW RETURNING — added
  `ReturningExpr`) is a tight example. [verified-by-code](source/src/backend/nodes/README:1-114)
- **Common pitfalls (one-line each):**
  - Forgetting that `expression_tree_walker_impl` switch in
    `nodeFuncs.c` needs a manual `case T_Foo:` for Expr subtypes — the
    .funcs.c generator does NOT touch it [verified-by-code](source/src/backend/nodes/nodeFuncs.c:2111-2170).
  - Forgetting `exprType` / `exprTypmod` / `exprCollation` /
    `exprLocation` updates — they're hand-written switches over
    NodeTag and will silently return `InvalidOid` / `-1` for your new
    Expr [verified-by-code](source/src/backend/nodes/nodeFuncs.c:42-296,304-396,1403-1700).
  - Putting a varlena-ish field on a Node intended for `nodeToString`
    storage without thinking about read-back: `pg_node_tree`
    serialisation roundtrip must equal the original under
    `debug_write_read_parse_plan_trees=on` [verified-by-code](source/src/backend/utils/misc/guc_parameters.dat:743).
  - Forgetting that adding ANY Node renumbers the `NodeTag` enum, so
    extensions compiled against the old tags will misread tagged
    structs — never backport a new Node to a released branch
    [from-comment](source/src/include/nodes/nodes.h:18-24).

## File checklist (the FULL sweep)

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/include/nodes/primnodes.h` OR `parsenodes.h` OR `plannodes.h` | Declare the `typedef struct Foo { ... } Foo;` with `pg_node_attr(...)` annotations. Pick file by Node category (primitive expression / SQL parse tree / Plan-tree). [verified-by-code](source/src/include/nodes/primnodes.h:652-737) | [primnodes.h.md](../files/src/include/nodes/primnodes.h.md) / [parsenodes.h.md](../files/src/include/nodes/parsenodes.h.md) / [plannodes.h.md](../files/src/include/nodes/plannodes.h.md) | parser-and-nodes |
| 2 | `src/include/nodes/nodes.h` | No edit usually — `T_Foo` is appended to the generated `nodetags.h` automatically. Touch only if the new type wants a manually-assigned NodeTag number (rare) [verified-by-code](source/src/include/nodes/nodes.h:25-31). | [nodes.h.md](../files/src/include/nodes/nodes.h.md) | parser-and-nodes |
| 3 | `src/backend/nodes/gen_node_support.pl` | No edit for a normal Node — the generator reads the header you edited in #1 (already listed in `@all_input_files`) and emits copy/equal/out/read/jumble cases. Edit ONLY if you need a new top-level `pg_node_attr` keyword [verified-by-code](source/src/backend/nodes/gen_node_support.pl:53-79). | — | parser-and-nodes |
| 4 | `src/backend/nodes/copyfuncs.funcs.c` (generated) | Auto-regenerated; verify the emitted `_copyFoo` actually copies every field correctly. If a field needs custom treatment, add a field-level `pg_node_attr(copy_as(...))` or `pg_node_attr(copy_as_scalar)` rather than hand-editing [verified-by-code](source/src/backend/nodes/copyfuncs.c:42). | [copyfuncs.c.md](../files/src/backend/nodes/copyfuncs.c.md) | parser-and-nodes |
| 5 | `src/backend/nodes/equalfuncs.funcs.c` (generated) | Auto-regenerated; verify `_equalFoo`. Field-level `pg_node_attr(equal_ignore)` if a field must be skipped (e.g. location). Equality intentionally ignores parse-location fields [from-comment](source/src/backend/nodes/equalfuncs.c:4-8). | [equalfuncs.c.md](../files/src/backend/nodes/equalfuncs.c.md) | parser-and-nodes |
| 6 | `src/backend/nodes/outfuncs.funcs.c` (generated) | Auto-regenerated; emits `_outFoo` writing `{FOO :field1 ... :fieldN}`. If a field needs a hand-rolled writer use `pg_node_attr(write_as(...))` or mark the whole Node `custom_read_write` and hand-write in `outfuncs.c` proper. | [outfuncs.c.md](../files/src/backend/nodes/outfuncs.c.md) | parser-and-nodes |
| 7 | `src/backend/nodes/readfuncs.funcs.c` (generated) | Auto-regenerated; emits `_readFoo`. Skipped entirely if the Node has `no_read` (most Plan-tree nodes — they never enter the catalog) [verified-by-code](source/src/backend/nodes/gen_node_support.pl:106-113). | [readfuncs.c.md](../files/src/backend/nodes/readfuncs.c.md) | parser-and-nodes |
| 8 | `src/backend/nodes/queryjumblefuncs.funcs.c` (generated) | Auto-regenerated; emits the jumble case used by `pg_stat_statements`. Field-level `pg_node_attr(query_jumble_ignore)` or `query_jumble_location` for location fields [verified-by-code](source/src/backend/nodes/queryjumblefuncs.c:1-30). | [queryjumblefuncs.c.md](../files/src/backend/nodes/queryjumblefuncs.c.md) | parser-and-nodes |
| 9 | `src/backend/nodes/copyfuncs.c` | Edit ONLY if the Node is `custom_copy_equal` — then write `_copyFoo` here by hand. Otherwise leave alone; the `#include "copyfuncs.funcs.c"` at line 41 pulls in the generated one [verified-by-code](source/src/backend/nodes/copyfuncs.c:41). | [copyfuncs.c.md](../files/src/backend/nodes/copyfuncs.c.md) | parser-and-nodes |
| 10 | `src/backend/nodes/equalfuncs.c` | Same — only if `custom_copy_equal`. Generated body comes in via `#include "equalfuncs.funcs.c"` at line 40 [verified-by-code](source/src/backend/nodes/equalfuncs.c:40). | [equalfuncs.c.md](../files/src/backend/nodes/equalfuncs.c.md) | parser-and-nodes |
| 11 | `src/backend/nodes/outfuncs.c` | Hand-rolled `_outFoo` here if `custom_read_write`. Body otherwise comes from the generated `outfuncs.funcs.c` (no explicit #include — gen_node_support emits the include line into the generated file network) [verified-by-code](source/src/backend/nodes/outfuncs.c:1-30). | [outfuncs.c.md](../files/src/backend/nodes/outfuncs.c.md) | parser-and-nodes |
| 12 | `src/backend/nodes/readfuncs.c` | Hand-rolled `_readFoo` here if `custom_read_write`. Pulls in `readfuncs.funcs.c` at line 38 [verified-by-code](source/src/backend/nodes/readfuncs.c:38). | [readfuncs.c.md](../files/src/backend/nodes/readfuncs.c.md) | parser-and-nodes |
| 13 | `src/backend/nodes/nodeFuncs.c` — `expression_tree_walker_impl` | **Hand edit.** Add `case T_Foo:` in the big switch at line 2135 if Foo is an Expr subtype with sub-Nodes to walk. Forgetting this breaks every pass that uses the walker (eval_const_expressions, fix_opfuncids, plan_tree_walker, ...) [verified-by-code](source/src/backend/nodes/nodeFuncs.c:2111,2135). | [nodeFuncs.c.md](../files/src/backend/nodes/nodeFuncs.c.md) | parser-and-nodes |
| 14 | `src/backend/nodes/nodeFuncs.c` — `expression_tree_mutator_impl` | **Hand edit.** Mirror of #13: every walker case needs a mutator case that rebuilds the Node with mutated children [verified-by-code](source/src/backend/nodes/nodeFuncs.c:3018). | [nodeFuncs.c.md](../files/src/backend/nodes/nodeFuncs.c.md) | parser-and-nodes |
| 15 | `src/backend/nodes/nodeFuncs.c` — `exprType` / `exprTypmod` / `exprCollation` / `exprSetCollation` / `exprLocation` | **Hand edit.** Five separate switches over NodeTag — every Expr subtype must answer all of them. Missing a case silently returns `InvalidOid` (type) / `-1` (typmod) / `0` (location) [verified-by-code](source/src/backend/nodes/nodeFuncs.c:42-296,304-396,1403-1700). | [nodeFuncs.c.md](../files/src/backend/nodes/nodeFuncs.c.md) | parser-and-nodes |
| 16 | `src/backend/nodes/nodeFuncs.c` — `raw_expression_tree_walker_impl` | **Hand edit IFF** the Node can appear in a *raw* parse tree (output of `gram.y`, before `parse_analyze`). Most primnodes are post-analysis; only raw parse-tree nodes need this [verified-by-code](source/src/backend/nodes/nodeFuncs.c:4115). | [nodeFuncs.c.md](../files/src/backend/nodes/nodeFuncs.c.md) | parser-and-nodes |
| 17 | `src/backend/nodes/nodeFuncs.c` — `planstate_tree_walker_impl` | **Hand edit IFF** the new Node is a Plan node (has a PlanState mirror) — coordinate with [add-new-plan-node](add-new-plan-node.md) [verified-by-code](source/src/backend/nodes/nodeFuncs.c:4872). | [nodeFuncs.c.md](../files/src/backend/nodes/nodeFuncs.c.md) | parser-and-nodes |
| 18 | `src/backend/nodes/makefuncs.c` / `makefuncs.h` | Optional — add a `makeFoo(...)` constructor if Foo is created in many call-sites with a common argument shape. README says skip for infrequent nodes [from-readme](source/src/backend/nodes/README:99-101). | [makefuncs.c.md](../files/src/backend/nodes/makefuncs.c.md) | parser-and-nodes |
| 19 | `src/backend/nodes/Makefile` and `src/include/nodes/meson.build` | Edit ONLY if the new Node lives in a brand-new header — both build systems carry a copy of `@all_input_files` that must stay in lockstep with `gen_node_support.pl` [verified-by-code](source/src/backend/nodes/gen_node_support.pl:46-53), [verified-by-code](source/src/include/nodes/meson.build:3-27), [verified-by-code](source/src/backend/nodes/Makefile:74-94). | — | build-and-run |
| 20 | `src/include/catalog/catversion.h` | Bump `CATALOG_VERSION_NO` IFF the new Node can appear in a serialised parse/expression tree stored in a catalog (pg_rewrite, pg_proc.prosrc-as-tree, pg_attrdef.adbin, pg_constraint.conbin, pg_partitioned_table.partexprs, etc.). Plan-tree-only nodes do not require a bump [from-comment](source/src/include/catalog/catversion.h:26-38), [from-readme](source/src/backend/nodes/README:108-114). | [catversion.h.md](../files/src/include/catalog/catversion.h.md) | catalog-conventions |
| 21 | `src/test/regress/sql/<area>.sql` + `expected/*.out` | New regression coverage that exercises a query path which constructs / serialises / round-trips the new Node. Without coverage, the round-trip GUCs below have nothing to check [verified-by-code](source/src/backend/utils/misc/guc_parameters.dat:644,743). | — | testing |

Total: 21 sites — only ~5-7 are usually *hand* edits; the rest are
either auto-regenerated or "verify but don't touch".

## Phases — suggested split for `pg-feature-plan`

1. **Phase 1 — Declare + auto-regen.** Files: [1, 2, 3, 4-8]. Edit
   the header (#1), pick the right `pg_node_attr` set, run a full
   meson rebuild to trigger `gen_node_support.pl`, then read the
   generated `*.funcs.c` files (#4-8) and confirm the emitted bodies
   look right. Phase-end check: `meson compile -C dev/build-debug`
   green; `git diff src/backend/nodes/*.funcs.c` shows your new Node's
   functions.
2. **Phase 2 — Hand-edit `nodeFuncs.c`.** Files: [13, 14, 15, 16, 17].
   Add the walker / mutator / exprType / exprTypmod / exprCollation /
   exprSetCollation / exprLocation switch arms; add
   `raw_expression_tree_walker` and `planstate_tree_walker` cases iff
   applicable. Phase-end check: clean rebuild, run
   `meson test -C dev/build-debug --suite regress` at least to smoke
   that nothing regressed on existing queries.
3. **Phase 3 — Custom support (only if needed).** Files: [9-12, 18].
   Hand-write `_copyFoo` / `_equalFoo` / `_outFoo` / `_readFoo` if you
   marked the Node `custom_copy_equal` or `custom_read_write`; add
   `makeFoo` constructor if call-sites benefit. Phase-end check:
   round-trip test with `PG_TEST_INITDB_EXTRA_OPTS='-c
   debug_copy_parse_plan_trees=on -c
   debug_write_read_parse_plan_trees=on -c
   debug_raw_expression_coverage_test=on'`
   [from-readme](source/src/backend/nodes/README:103-108).
4. **Phase 4 — Catversion + tests + docs.** Files: [20, 21, 19 if a
   new header]. Bump catversion iff catalog-stored; add regression
   tests that exercise the new Node end-to-end (parse → analyze →
   plan → out → read for round-trip). Phase-end check: full
   `meson test -C dev/build-debug` green with round-trip GUCs on.


## Likely reviewers
<!-- persona-reviewers:auto -->

*Personas whose Domain-ownership paths overlap this scenario's §Files. Reflect who might catch this on hackers-list.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

| Persona | Overlapping path(s) |
|---|---|
| [`heikki-linnakangas`](../personas/heikki-linnakangas.md) | `src/include`, `src/backend/utils` |
| [`nathan-bossart`](../personas/nathan-bossart.md) | `src/include`, `src/backend/utils` |
| [`peter-eisentraut`](../personas/peter-eisentraut.md) | `src/include`, `src/backend/nodes` |
| [`michael-paquier`](../personas/michael-paquier.md) | `src/backend/utils` |
| [`tom-lane`](../personas/tom-lane.md) | `src/backend/utils` |

<!-- /persona-reviewers:auto -->

## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`aggregate-partial-finalize`](../idioms/aggregate-partial-finalize.md) | shares files: `src/include/nodes/nodes.h` |
| [`catalog-conventions`](../idioms/catalog-conventions.md) | shares files: `src/include/catalog/catversion.h` |
| [`node-types`](../idioms/node-types.md) | shares files: `src/backend/nodes/gen_node_support.pl`, `src/include/nodes/primnodes.h` |
| [`portable-identifiers`](../idioms/portable-identifiers.md) | shares files: `src/include/nodes/primnodes.h` |
| [`query-tree-walkers`](../idioms/query-tree-walkers.md) | shares files: `src/backend/nodes/nodeFuncs.c` |
| [`subplan-and-initplan`](../idioms/subplan-and-initplan.md) | shares files: `src/include/nodes/primnodes.h` |

<!-- /idioms-invoked:auto -->
## Pitfalls

- **Trap 1 — Adding an Expr subtype but forgetting `nodeFuncs.c`.**
  The generator does not touch `expression_tree_walker_impl`,
  `expression_tree_mutator_impl`, or the five `expr*` switches. The
  build will succeed; passes that traverse expressions (const-fold,
  qual pushdown, EXPLAIN var resolution) will silently skip your
  Node's children. Symptom: incorrect plans / lost references / hard
  crash on `InvalidOid` returned from `exprType`
  [verified-by-code](source/src/backend/nodes/nodeFuncs.c:2069-2105).
- **Trap 2 — Catversion bump forgotten on a catalog-bound Node.**
  Your local cluster (initdb'd against the new binary) keeps working;
  any pre-existing cluster mysteriously won't start, or worse, loads
  stored rules / view defs that misparse because the `NodeTag` enum
  shifted underneath them. The README is explicit
  [from-readme](source/src/backend/nodes/README:108-114); the
  catversion.h header carries the policy
  [from-comment](source/src/include/catalog/catversion.h:35-38).
- **Trap 3 — Picking `custom_read_write` for a Node that doesn't need
  it.** You inherit perpetual maintenance burden — every new field
  needs hand-extension of both `_outFoo` and `_readFoo`. Prefer the
  generator unless you genuinely need a non-symmetric representation
  (e.g. computing a field on read-back) [verified-by-code](source/src/backend/nodes/gen_node_support.pl:116-119).
- **Trap 4 — Raw parse node missing from `raw_expression_tree_walker`.**
  If the Node can appear in the output of `gram.y` *before*
  `parse_analyze`, you must add a case to the raw walker too. Most
  primnodes are post-analysis-only and do *not* need this; statement
  helpers (`SelectStmt` children, `A_Expr`, raw column refs) do
  [verified-by-code](source/src/backend/nodes/nodeFuncs.c:4115).
- **Trap 5 — Putting a Plan-only Node into a header processed for
  read support.** Plan nodes are tagged `no_read` (no `_readFoo`
  emitted) because they never enter the catalog. If you forget the
  attribute the generator emits read code that pulls in PlanState
  pointers it can't resolve [verified-by-code](source/src/backend/nodes/gen_node_support.pl:71-77).
- **Synchronization traps** (sibling files that must change together):
  - `src/backend/nodes/Makefile` ↔ `src/include/nodes/meson.build` ↔
    `gen_node_support.pl`'s `@all_input_files` — the three lists must
    contain the same header set in the same order [verified-by-code](source/src/backend/nodes/gen_node_support.pl:44-53).
  - `expression_tree_walker_impl` ↔ `expression_tree_mutator_impl` —
    every walker case needs a mirroring mutator case.
  - Five-way `exprType` / `exprTypmod` / `exprCollation` /
    `exprSetCollation` / `exprLocation` — adding an Expr to one
    without the others guarantees a half-broken Node.

## Verification (exact test invocations)

```bash
# Build with full regeneration — confirms gen_node_support.pl ran.
meson compile -C dev/build-debug

# Inspect the auto-generated bodies for your Node before testing.
grep -n "_copyFoo\|_equalFoo\|_outFoo\|_readFoo\|_jumbleFoo" \
  dev/build-debug/src/include/nodes/*.funcs.c

# Run the full regression suite with the three round-trip / coverage
# GUCs enabled — this is the canonical "did I wire it everywhere"
# check per README:103-108.
PG_TEST_INITDB_EXTRA_OPTS='-c debug_copy_parse_plan_trees=on \
  -c debug_write_read_parse_plan_trees=on \
  -c debug_raw_expression_coverage_test=on' \
  meson test -C dev/build-debug --suite regress

# Isolation + recovery only if your Node affects on-disk state.
meson test -C dev/build-debug --suite isolation
meson test -C dev/build-debug --suite recovery
```

A new test for the Node itself usually lives in
`src/test/regress/sql/<closest-existing-area>.sql` — e.g. a new Expr
subtype used by a SQL/JSON path joins `sql/jsonb_sqljson.sql`;
there's no dedicated `nodes.sql` test.

## Cross-refs

- Companion skills: `.claude/skills/parser-and-nodes/SKILL.md`
  (procedural rules for `gen_node_support.pl`, the Expr inheritance
  pattern, the round-trip discipline).
- Related scenarios: [add-new-plan-node](add-new-plan-node.md) (Plan
  + PlanState + executor) and
  [add-new-utility-statement](add-new-utility-statement.md) (XxxStmt
  + ProcessUtility dispatch). A new utility statement *is* a new Node
  type plus a dispatch row — that scenario unions this one.
- Idioms: [node-types-and-lists](../idioms/node-types-and-lists.md)
  (Node inheritance, NodeTag tagging, List patterns),
  [catalog-conventions](../idioms/catalog-conventions.md) (catversion
  bump rule for serialised parse trees).
- Subsystems: [parser-and-rewrite](../subsystems/parser-and-rewrite.md)
  (where parse-tree Nodes live), [optimizer](../subsystems/optimizer.md)
  (Plan-tree Node consumers).
- Issues: none registered yet for `src/backend/nodes/` —
  `knowledge/issues/` has no `nodes.md` row [unverified, no listing
  in issues/ at write time].
- Reference patch (canonical_commit): `git -C source show 964d01ae90c`
  — the watershed "generate node support" rework. Also instructive:
  `git -C source show 80feb727c86` (OLD/NEW RETURNING — added
  `ReturningExpr` end-to-end, a clean single-Node addition).
