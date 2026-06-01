# parse_relation.h

- **Source:** `source/src/include/parser/parse_relation.h` (~140 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Prototypes for `parse_relation.c`. The largest header in the parser dir
because it exposes the full RTE-construction API.

## Categories

1. **Namespace lookup**: `refnameNamespaceItem`, `scanNameSpaceForRefname`,
   `scanNameSpaceForRelid`, `scanNameSpaceForENR`, `scanNameSpaceForCTE`,
   `checkNameSpaceConflicts`.

2. **RTE construction** — one `addRangeTableEntry*` per RTE kind:
   - `addRangeTableEntry` (relation by RangeVar; takes lockmode + inFromCl)
   - `addRangeTableEntryForRelation` (by Relation already opened)
   - `addRangeTableEntryForSubquery`
   - `addRangeTableEntryForFunction`
   - `addRangeTableEntryForValues`
   - `addRangeTableEntryForTableFunc`
   - `addRangeTableEntryForJoin`
   - `addRangeTableEntryForCTE`
   - `addRangeTableEntryForENR`
   - `addRangeTableEntryForGraphTable`

3. **NSItem helpers**: `addNSItemToQuery`, `buildNSItemFromTupleDesc`,
   `buildNSItemFromLists`, `markNullableIfNeeded`.

4. **Column expansion / lookup**: `expandNSItemVars`, `expandNSItemAttrs`,
   `expandRTE`, `colNameToVar`, `searchRangeTableForCol`.

5. **Permission tracking**: `addRTEPermissionInfo`, `getRTEPermissionInfo`,
   `markVarForSelectPriv`.
