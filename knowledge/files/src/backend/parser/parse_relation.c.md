# parse_relation.c

- **Source:** `source/src/backend/parser/parse_relation.c` (4063 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (top + namespace + RTE-building entry points)

## Purpose

Support routines for the parser's view of relations and columns. Two
overlapping concerns:

1. **Namespace lookup** — given a refname or a `ColumnRef`, find the right
   `ParseNamespaceItem` / column in the current `ParseState`, producing a
   `Var` (with the right `varno` / `varattno` / `varlevelsup`) or a
   diagnostic with a fuzzy-match hint.
2. **Range table entry (RTE) construction** — the family of
   `addRangeTableEntry*` functions that materialize each kind of RTE
   (`RTE_RELATION`, `RTE_SUBQUERY`, `RTE_FUNCTION`, `RTE_VALUES`,
   `RTE_JOIN`, `RTE_CTE`, `RTE_NAMEDTUPLESTORE`, `RTE_RESULT`, `RTE_TABLEFUNC`,
   `RTE_GRAPH_TABLE`) and the matching `ParseNamespaceItem`.

## Fuzzy-match diagnostics

`FuzzyAttrMatchState` `:59-70` records up to two best non-exact matches +
two exact matches across all RTEs in scope, so that the
`column "foo" does not exist` error can hint "did you mean bar?". Cap is
`MAX_FUZZY_DISTANCE = 3` `:72`. `scanRTEForColumn` `:82-86` does the actual
per-RTE Levenshtein search.

## Namespace lookup

| Symbol | Role |
|---|---|
| `refnameNamespaceItem` `:105-…` | look up qualified-or-unqualified refname; ambiguous matches raise an error |
| `scanNameSpaceForRefname` `:75-77` | scan local namespace only |
| `scanNameSpaceForRelid` `:78-79` | by Oid |
| `check_lateral_ref_ok` `:80-81` | enforce that a LATERAL ref is only made from a marked-lateral position |
| `rte_visible_if_lateral` `:101` / `rte_visible_if_qualified` `:102` | visibility predicates used by the qualified-vs-unqualified rules |

The `markRTEForSelectPriv` helper `:87-88` is the place where column-level
SELECT privilege gets recorded for later check by the executor (via
`Query.rteperminfos`).

## RTE construction

The `addRangeTableEntry*` family (later in file) is the canonical way for
*every other parser file* to attach a relation to the current Query. Each
returns a `ParseNamespaceItem` and:

- allocates the `RangeTblEntry`,
- locks the underlying object at the appropriate `rellockmode` (recorded on
  the RTE for later re-acquisition by `AcquireRewriteLocks` and the planner),
- builds the `eref` alias and column-name list,
- registers the result into `pstate->p_rtable` and (if added to namespace)
  `pstate->p_namespace`.

The split between `addRangeTableEntry*` (build the RTE) and
`addNSItemToQuery` / `addRTEPermissionInfo` (attach to namespace) gives the
per-clause callers (`transformFromClauseItem` in `parse_clause.c`) the
flexibility to control visibility (LATERAL, USING merge columns, etc.).

## Column expansion

`expandRelation` `:89-93` / `expandTupleDesc` `:94-99` produce parallel
`colnames` + `colvars` lists that drive `SELECT *` expansion (called from
`parse_target.c`'s `ExpandSingleTable`/`ExpandColumnRefStar`). They honor
`include_dropped` (omit dropped columns from `*`) and `returning_type`
(used for `RETURNING OLD.*` / `NEW.*` semantics).

## specialAttNum

`specialAttNum` `:100` translates the system-column names (`ctid`, `xmin`,
`xmax`, `cmin`, `cmax`, `tableoid`) into their negative attribute numbers.

## Why this file is so big

A lot of repetition: each RTE-kind needs its own builder *and* its own
namespace materializer *and* its own column-list builder. The
`expandTupleDesc` path is the centralized escape valve for most of it, but
JOIN / subquery / VALUES / function-with-OUT-params / GRAPH_TABLE each have
enough variation to merit dedicated routines.

## Caveats

- Locks are taken **here**, on RTE creation; they must be re-acquired by
  the rewriter (`AcquireRewriteLocks` in `rewriteHandler.c:148`) for any
  Query that survives past the current command.
- `markRTEForSelectPriv` is called from many call sites; missing one is the
  bug pattern that leaks column-level privilege checking.
- The fuzzy match is purely UX — it never affects which column the query
  actually resolves to.
