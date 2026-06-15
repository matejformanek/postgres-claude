---
source_url: https://www.postgresql.org/docs/current/fdw-planning.html
chapter: "58.3 Foreign Data Wrapper Query Planning"
fetched_at: 2026-06-15
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
---

# FDW query planning — §58.3

Distilled from §58.3. Companion to
[[knowledge/docs-distilled/fdw-callbacks.md]]; this leaf explains *how the
three planning callbacks pass state forward* and *which `ForeignScan`
fields carry what to execution time*. The whole chapter is really about
two private channels (`fdw_private` at three levels) and the
correctness rule for pushed-down quals.

## Non-obvious claims

- **Three `fdw_private` channels, each untouched by core:**
  (1) `RelOptInfo.fdw_private` (a bare `void *`, init'd to NULL) carries
  state *between* `GetForeignRelSize` → `GetForeignPaths` →
  `GetForeignPlan`; (2) `ForeignPath.fdw_private` (a `List *`)
  distinguishes competing paths; (3) `ForeignScan.fdw_private` (a
  `List *`) reaches execution time. Only the last two must be
  `copyObject`-able. [from-docs §58.3]
- `GetForeignRelSize` must overwrite `baserel->rows` (post-filter row
  estimate); may improve `baserel->width` and `baserel->tuples`. These
  defaults are otherwise generic and usually wrong for a remote source.
  [from-docs §58.3]
- **`fdw_exprs` vs `fdw_private`:** `fdw_exprs` is the list of expression
  trees that the planner will *post-process into executable form* (so
  pushed-down parameters like `WHERE remote = $1` go here); `fdw_private`
  is opaque control data the backend never interprets. Both must survive
  `copyObject`; best practice is a `nodeToString`-dumpable representation
  for `ForeignPath.fdw_private` so debugging output works. [from-docs §58.3]
- **The READ COMMITTED recheck rule is the correctness landmine:** any
  qual you *remove* from the plan node's qual list (because you pushed it
  to the remote) must be re-added to `fdw_recheck_quals` OR rechecked in
  `RecheckForeignScan`. On a concurrent update to another table in the
  query, the executor re-evaluates original quals against possibly
  different parameter values; a pushed-down-and-forgotten qual yields
  wrong rows. [from-docs §58.3]
- Identify a pushdown-eligible clause during `GetForeignPaths` (it
  changes the cost estimate), stash a pointer to its `RestrictInfo` in
  the path's `fdw_private`, then in `GetForeignPlan` strip it from
  `scan_clauses` and move its sub-expression into `fdw_exprs`. The
  `scan_clauses` passed to `GetForeignPlan` are the same as
  `baserel->baserestrictinfo` but possibly reordered; simple FDWs just
  `extract_actual_clauses` and dump them all into the plan qual.
  [from-docs §58.3]
- **`fdw_scan_tlist` is optional for base scans (NIL ⇒ foreign-table row
  type) but MANDATORY for join paths** — a remote join has no single
  catalog row type, so `GetForeignJoinPaths`-derived plans must always
  describe their output columns explicitly. [from-docs §58.3]
- **Join clauses are not in `baserestrictinfo`.** A path may depend on a
  join clause `foreign_var = local_var`; such clauses live in the
  relation's join lists, and a path using one is a *parameterized path*
  whose `param_info` must be computed via `get_baserel_parampathinfo`.
  The FDW should always also build at least one path depending only on
  restriction clauses. For join rels, the relevant clauses arrive as
  `extra->restrictlist`, not `baserestrictinfo`. [from-docs §58.3]
- **Upper-rel pushdown** (grouping/aggregation/sort) goes through
  `GetForeignUpperPaths`, inserting paths into the matching upper rel
  (e.g. `UPPERREL_GROUP_AGG`) where they cost-compete with local
  processing. A whole remote `UPDATE`/`DELETE` can instead be inserted
  into `UPPERREL_FINAL`, but **a `UPPERREL_FINAL` path is responsible for
  the entire query's behavior**. [from-docs §58.3]
- In `INSERT` planning there is **no `RelOptInfo`** for the target (it's
  not scanned), so `PlanForeignModify`/`PlanDirectModify` can reuse
  `baserel->fdw_private` for UPDATE/DELETE but not for INSERT.
  Relatedly, `INSERT ... ON CONFLICT` cannot name a conflict target
  (remote constraints aren't locally known) ⇒ `ON CONFLICT DO UPDATE` is
  unsupported. [from-docs §58.3]
- All FDW private data should be `palloc`'d so it is reclaimed at end of
  planning. [from-docs §58.3]

## Links into corpus

- Callback catalog (this run): [[knowledge/docs-distilled/fdw-callbacks.md]].
- Parent chapter: [[knowledge/docs-distilled/fdwhandler.md]].
- Path/Plan machinery this hooks into: [[knowledge/subsystems/optimizer.md]]
  (`add_path`, RelOptInfo, parameterized paths, upper rels).
- Source struct: [[knowledge/files/src/include/foreign/fdwapi.h.md]].

## Caveats / verification

- All claims `[from-docs §58.3]`. The `UPPERREL_*` enum members and
  `ForeignScan` field names should be re-checked against
  `source/src/include/nodes/{pathnodes.h,plannodes.h}` at anchor
  `b78cd2bda5b1a306e2877059011933de1d0fb735` before citing line numbers.
