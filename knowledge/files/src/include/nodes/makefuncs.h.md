# makefuncs.h

- **Source:** `source/src/include/nodes/makefuncs.h` (128 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

Prototypes for the `makeFoo(...)` constructors in `makefuncs.c`. All
take a few "obvious" parameters and fill the remaining node fields
with sensible defaults (location = -1, etc.).

## Full prototype list

Parse-tree builders (call sites in parser/grammar):
- `makeA_Expr`, `makeSimpleA_Expr`
- `makeRangeVar`, `makeTypeName`, `makeTypeNameFromNameList`,
  `makeTypeNameFromOid`
- `makeColumnDef`, `makeAlias`
- `makeFuncCall`, `makeStringConst`
- `makeDefElem`, `makeDefElemExtended`
- `makeNotNullConstraint`
- `makeGroupingSet`
- `makeJsonFormat`, `makeJsonValueExpr`, `makeJsonBehavior`,
  `makeJsonKeyValue`, `makeJsonIsPredicate`, `makeJsonTablePath`,
  `makeJsonTablePathSpec`
- `makeVacuumRelation`

Analyzed/planner expression builders:
- `makeVar`, `makeVarFromTargetEntry`, `makeWholeRowVar`
- `makeTargetEntry`, `flatCopyTargetEntry`
- `makeFromExpr`
- `makeConst`, `makeNullConst`, `makeBoolConst`
- `makeBoolExpr`
- `makeRelabelType`
- `makeFuncExpr`
- `make_opclause`, `make_andclause`, `make_orclause`, `make_notclause`
- `make_and_qual` — qual-level AND (NULL = TRUE)
- `make_ands_explicit` / `make_ands_implicit` — convert between
  AND-list and BoolExpr form

Index machinery:
- `makeIndexInfo`

## Notes on dependencies

The header `#include`s `execnodes.h` and `parsenodes.h` (which
transitively pull in primnodes.h, pg_list.h, …). Including
`makefuncs.h` is thus a fairly heavy import; many files don't need
it directly.

## Cross-references

- Implementation: `source/src/backend/nodes/makefuncs.c`
