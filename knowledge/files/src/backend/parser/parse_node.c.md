# parse_node.c

- **Source:** `source/src/backend/parser/parse_node.c` (480 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Lifecycle of `ParseState`, plus a grab-bag of small node-construction
helpers used across the parser.

## Key entries

- `make_parsestate(parent)` — allocate a `ParseState`, optionally
  inheriting param / column hooks from a parent for sub-statement
  recursion. Called from `analyze.c:parse_analyze_*` and
  `parse_sub_analyze`.
- `free_parsestate(pstate)` — release the pstate and reset
  `p_target_relation` (closes the held relation).
- `parser_errposition(pstate, location)` — translate a token-stream
  position into the `ERRPOSITION()` cursor used by `ereport`.
- `transformContainerType` — array vs. composite vs. domain-over-array
  dispatcher for subscripting.
- `transformContainerSubscripts` — build `SubscriptingRef` from
  `A_Indirection`.
- `make_var(pstate, nsitem, attrno, location)` — central place where the
  `Var.varlevelsup` and other fields get filled.
- `transformArrayType`, `coerce_to_specific_type` (wrapper),
  `make_const`, `make_andclause` — small node-makers.

## ParseState (`parse_node.h:91-…`)

A scratchpad threaded through every helper in `parser/`:

- `p_sourcetext` — original SQL for error-cursor display.
- `p_rtable` / `p_joinlist` / `p_namespace` / `p_nullingrels` — building
  blocks for the eventual `Query`.
- `p_parent_parsestate` + `p_locked_from_parent` + `p_resolve_unknowns` —
  for sub-statement recursion.
- `p_paramref_hook` / `p_coerce_param_hook` / `p_pre_columnref_hook` /
  `p_post_columnref_hook` — extension points used by PL/pgSQL and the
  fixed/variable-param helpers in `parse_param.c`.
- `p_expr_kind` — current `ParseExprKind` while inside an expression
  transform, used for context-specific error messages and feature gating.
- `p_target_relation` / `p_target_nsitem` — for UPDATE/INSERT/DELETE.
- `p_hasAggs` / `p_hasWindowFuncs` / `p_hasTargetSRFs` / `p_hasSubLinks` —
  feature bits eventually copied into the `Query`.

## Caveats

- `make_parsestate(NULL)` creates a top-level pstate; passing the parent
  pstate is mandatory for sub-statements so that column resolution can
  walk up `p_parent_parsestate` for outer-query Var refs (driving
  `Var.varlevelsup`).
- Closing the target relation happens in `free_parsestate`; forgetting
  to free can leak a relcache pin.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
