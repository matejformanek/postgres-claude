# parse_coerce.h

- **Source:** `source/src/include/parser/parse_coerce.h` (~110 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Public API of the coercion engine.

## Key types

- `CoercionContext` enum — `COERCION_IMPLICIT`, `COERCION_ASSIGNMENT`,
  `COERCION_EXPLICIT`. SQL spec's three coercion modes; controls which
  `pg_cast.castcontext` values are admissible.
- `CoercionForm` enum — `COERCE_EXPLICIT_CALL`, `COERCE_EXPLICIT_CAST`,
  `COERCE_IMPLICIT_CAST`, `COERCE_SQL_SYNTAX`. Used for ruleutils.c
  formatting (does the cast print as `x::int`, `CAST(x AS int)`, or
  nothing?).
- `CoercionPathType` enum — `COERCION_PATH_NONE`, `_RELABELTYPE`,
  `_FUNC`, `_ARRAYCOERCE`, `_COERCEVIAIO`.

## Major entries

- `coerce_to_target_type`, `coerce_type`, `coerce_to_boolean`,
  `coerce_to_specific_type`, `coerce_to_common_type`,
  `coerce_to_domain`.
- `select_common_type`, `select_common_typmod`, `select_common_collation`.
- `can_coerce_type` (predicate).
- `find_coercion_pathway`, `find_typmod_coercion_function` — for
  callers that need to introspect what a coercion would do.
- `IsBinaryCoercible`, `IsPreferredType` — type-system predicates used
  by overload resolution.
