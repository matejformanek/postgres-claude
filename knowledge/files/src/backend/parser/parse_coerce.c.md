# parse_coerce.c

- **Source:** `source/src/backend/parser/parse_coerce.c` (3407 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Type-coercion engine: when does an expression of type S need (and is
allowed) to be converted to type T, and what node tree implements the
conversion? Used pervasively by `parse_expr.c`, `parse_func.c`,
`parse_oper.c`, `parse_target.c` and the CTE / set-op type unifiers.

## Two-layer model

1. **Decide if coercion is legal** under a given `CoercionContext`
   (`COERCION_IMPLICIT`, `COERCION_ASSIGNMENT`, `COERCION_EXPLICIT`).
   `pg_cast` is the catalog; the algorithm is documented in the SQL spec
   chapter on type promotion.

2. **If legal, build a coercion node:** `RelabelType` (no-op recast),
   `CoerceViaIO` (typoutput→typinput), `ArrayCoerceExpr`, `FuncExpr`
   (via a cast function), `CoerceToDomain`, `ConvertRowtypeExpr`, etc.

## Key entries

- `coerce_to_target_type` — the typical assignment-side caller (UPDATE
  SET, INSERT VALUES).
- `coerce_type` — generic "give me an expression of type T".
- `can_coerce_type` — predicate only.
- `select_common_type` — used by UNION arms, CASE branches, COALESCE to
  find a result type all inputs can coerce to.
- `coerce_to_boolean` — WHERE/HAVING/ON helper.
- `coerce_to_specific_type` — helper for "this clause must produce
  type X" cases.
- `coerce_record_to_complex` — RowExpr → composite type.

## Domains

Domain types are unwrapped lazily here: the inner base type is what cast
lookups use, but the result is wrapped in `CoerceToDomain` so the runtime
CHECK constraints fire.

## "Unknown" type

String literals (`A_Const` of `Sconst`) are typed as `UNKNOWN` until
context determines what they should be. `parse_coerce` is where that
late-binding happens; that's why `select 'foo'` returns `text` but
`insert into t(intcol) values ('5')` ends up with an `int4` Const.

## Related

- `pg_cast` catalog — where casts are registered.
- `parse_type.c` — produces the `Oid` that this file's machinery routes
  through.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
