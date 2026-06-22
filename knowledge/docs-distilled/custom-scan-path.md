---
source_url: https://www.postgresql.org/docs/current/custom-scan-path.html
chapter: "60.1 Creating Custom Scan Paths"
fetched_at: 2026-06-16
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
---

# Custom scan paths (`CustomPath`) — §60.1

The first of the three custom-scan-provider stages: how a provider injects a
`CustomPath` into the planner's path list via the two pathlist hooks. Path →
Plan is §60.2 ([[knowledge/docs-distilled/custom-scan-plan.md]]); execution is
§60.3 ([[knowledge/docs-distilled/custom-scan-execution.md]]). All three
structs live in [[knowledge/files/src/include/nodes/extensible.h.md]].

## Non-obvious claims

- **You register by hooking, not by catalog.** Unlike FDWs there is no
  `CREATE` statement: a provider sets `set_rel_pathlist_hook` (base rels) and
  /or `set_join_pathlist_hook` (joins) in its `_PG_init`, chaining any
  previous hook. [from-docs §60.1]
- **`set_rel_pathlist_hook` fires *after* core generates the normal access
  paths but *before* Gather/Gather-Merge paths are added** — so a custom
  path competes with seqscan/indexscan and can still be parallelized above.
  Signature: `(PlannerInfo *root, RelOptInfo *rel, Index rti,
  RangeTblEntry *rte)`. [from-docs §60.1]
- **`set_join_pathlist_hook` is called repeatedly for the *same* join** with
  different inner/outer relation combinations; the join clauses arrive via
  `extra->restrictlist` (a `JoinPathExtraData *`). It is **not** required to
  produce a path on any given call. [from-docs §60.1]
- **`CustomPath` fields beyond the embedded `Path`:**
  - `uint32 flags` — optional-capability bitmask (below).
  - `List *custom_paths` — child `Path` nodes the planner will turn into
    child `Plan`s for you.
  - `List *custom_restrictinfo` — join clauses for a join rel, else NIL.
  - `List *custom_private` — provider-private data; **must be
    `nodeToString`-compatible** (i.e. built from copyable nodes) so
    `EXPLAIN`/debug output and copy/out funcs don't choke.
  - `const CustomPathMethods *methods`.
  [from-docs §60.1]
- **The three capability flags are opt-in and have real teeth:**
  - `CUSTOMPATH_SUPPORT_BACKWARD_SCAN` — supports backward scan.
  - `CUSTOMPATH_SUPPORT_MARK_RESTORE` — supports mark/restore (needed under
    a merge join).
  - `CUSTOMPATH_SUPPORT_PROJECTION` — **if NOT set, the scan node may only
    emit Vars of the scanned relation**; if set, the provider must be able
    to evaluate arbitrary scalar expressions in its target list. Getting
    this wrong = either a missing-projection plan error or unhandled
    expressions. [from-docs §60.1]
- **`PlanCustomPath` (a `CustomPathMethods` callback) converts the path to a
  finished plan**, typically a `CustomScan`. Signature includes `tlist`,
  `clauses`, and `custom_plans` (the planned children of `custom_paths`):
  `Plan *(*PlanCustomPath)(root, rel, best_path, tlist, clauses,
  custom_plans)`. [from-docs §60.1]
- **`ReparameterizeCustomPathByChild`** rewrites expressions in
  `custom_private` when a path parameterized by a parent relation must be
  re-expressed against a child rel (partitionwise-join reparameterization).
  Optional, but required to participate in those plans. [from-docs §60.1]

## Links into corpus

- Struct home: [[knowledge/files/src/include/nodes/extensible.h.md]]
  (`CustomPath`, `CustomPathMethods`, `CustomScan`, `CustomScanState`).
- Next stages: [[knowledge/docs-distilled/custom-scan-plan.md]] (§60.2) +
  [[knowledge/docs-distilled/custom-scan-execution.md]] (§60.3).
- Parent: [[knowledge/docs-distilled/custom-scan.md]].
- Executor node: [[knowledge/files/src/backend/executor/nodeCustom.c.md]].
- Path/Plan machinery this plugs into: [[knowledge/subsystems/optimizer.md]]
  (add_path cost-dominance; Path → Plan via createplan.c).
- Pluggable-provider sibling (catalog-registered instead of hooked):
  [[knowledge/docs-distilled/fdwhandler.md]].

## Caveats / verification

- All claims `[from-docs §60.1]`. The hook typedefs, `CUSTOMPATH_SUPPORT_*`
  bit values, and the `CustomPathMethods` callback signatures are verifiable
  in `source/src/include/nodes/extensible.h` and the hook decls in
  `src/backend/optimizer/...` at anchor
  `b78cd2bda5b1a306e2877059011933de1d0fb735`.
