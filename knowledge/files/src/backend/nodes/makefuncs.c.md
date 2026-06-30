# makefuncs.c

- **Source:** `source/src/backend/nodes/makefuncs.c` (1038 lines)
- **Last verified commit:** `b78cd2bda5b1` (re-verified 2026-06-16 by
  pg-quality-auditor AUDIT mode after anchor-bump
  `e18b0cb7344..da1eff08a5be`; only the two trailing JsonTablePath
  entries drifted +2, rest of the inventory held)
- **Depth:** read

## Purpose

Convenience constructors (`makeFoo(...)`) for the most frequently
created node types. The README explicitly says: don't add a creator
here unless the node is created often enough that the boilerplate at
call sites is a real readability cost. `[from-README:99-100]`

## Conventions

- All constructors are thin wrappers around `makeNode(T)`
  (palloc0 + tag) plus field assignment. `nodes.h:149-161`
  `[verified-by-code]`
- Most set `location = -1` ("unknown") if the caller doesn't supply
  one — the parser sets real locations.
- A few do meaningful work beyond field-fill: `makeConst` force-
  detoasts varlena values (`:365-366`); `makeWholeRowVar` switches on
  RTE kind to pick the right rowtype OID
  (`:136-282`); `make_ands_implicit` interprets NULL clause as TRUE
  and unwraps a top-level AND (`:809-827`).

## Constructor inventory

| Line | Function | Returns |
|---|---|---|
| 29 | `makeA_Expr` | `A_Expr *` |
| 47 | `makeSimpleA_Expr` | `A_Expr *` (single-name op) |
| 65 | `makeVar` | `Var *` (sets varnullingrels=NULL, varnosyn=varno, location=-1) |
| 106 | `makeVarFromTargetEntry` | `Var *` via `exprType/exprTypmod/exprCollation` |
| 136 | `makeWholeRowVar` | whole-row reference; switches on `rtekind` |
| 288 | `makeTargetEntry` | `TargetEntry *` |
| 321 | `flatCopyTargetEntry` | shallow memcpy |
| 335 | `makeFromExpr` | |
| 349 | `makeConst` | force-detoasts varlena |
| 387 | `makeNullConst` | looks up typlen/typbyval |
| 407 | `makeBoolConst` | hardwires `BOOLOID, len=1, byval=true` |
| 419 | `makeBoolExpr` | |
| 437 | `makeAlias` | `pstrdup`s the name |
| 452 | `makeRelabelType` | |
| 472 | `makeRangeVar` | defaults relpersistence=PERMANENT, inh=true |
| 492 | `makeNotNullConstraint` | |
| 518 | `makeTypeName` | unqualified |
| 530 | `makeTypeNameFromNameList` | qualified |
| 546 | `makeTypeNameFromOid` | post-resolution |
| 564 | `makeColumnDef` | |
| 593 | `makeFuncExpr` | non-set-returning, non-variadic only |
| 617 | `makeStringConst` | `A_Const` wrapping a `T_String` value |
| 636 | `makeDefElem` | simple |
| 654 | `makeDefElemExtended` | with namespace+action |
| 675 | `makeFuncCall` | parse-tree-level (not `FuncExpr`!) |
| 700 | `make_opclause` | `OpExpr *`; sets opfuncid=Invalid until set_opfuncid runs |
| 726 | `make_andclause` / `make_orclause` / `make_notclause` | `BoolExpr` wrappers |
| 779 | `make_and_qual` | qual-level AND that treats NULL as TRUE |
| 798 | `make_ands_explicit` | `[a,b,c] → AND(a,b,c)`; empty → TRUE constant |
| 809 | `make_ands_implicit` | inverse: AND(a,b) → [a,b]; NULL → NIL; const-true → NIL |
| 833 | `makeIndexInfo` | |
| 891 | `makeGroupingSet` | |
| 906 | `makeVacuumRelation` | |
| 921 | `makeJsonFormat` | |
| 937 | `makeJsonValueExpr` | |
| 954 | `makeJsonBehavior` | |
| 970 | `makeJsonKeyValue` | |
| 985 | `makeJsonIsPredicate` | |
| 1007 | `makeJsonTablePathSpec` | |
| 1028 | `makeJsonTablePath` | |

## Notes

- `make_opclause` leaves `opfuncid = InvalidOid`; planner calls
  `set_opfuncid` (`nodeFuncs.c`) to fill it in just before execution.
  `:700-719` `[verified-by-code]`
- `makeIndexInfo` initialises only the static portions; exclusion and
  uniqueness-check state are left NULL for `RelationGetIndexAttrBitmap`
  / `index_build` to fill in later. `:833-885` `[verified-by-code]`

## Cross-references

- Header: `source/src/include/nodes/makefuncs.h`
- Related: `value.c` for value-wrapper makers (`makeInteger`,
  `makeString`, ...).
- Most call sites: `src/backend/parser/`, `src/backend/optimizer/`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [data-structures/var-const-nodes.md](../../../../data-structures/var-const-nodes.md)

