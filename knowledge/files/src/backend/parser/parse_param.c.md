# parse_param.c

- **Source:** `source/src/backend/parser/parse_param.c` (360 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Resolve `$n` `ParamRef` nodes for the two cases the core backend cares
about:

1. **Fixed parameter list** — types known up front (the `prepare ... as
   $1::int, $2::text` case after `PREPARE`).
2. **Variable parameter list** — types deduced from context (the legacy
   protocol form where the client doesn't pre-declare). The deduced array
   can be repalloc'd. [from-comment] `:6-12`

Other approaches (e.g. PL/pgSQL's variable refs) plug in via
`ParseState` hooks (`p_paramref_hook`) and don't use this file.

## Entries

- `setup_parse_fixed_parameters(pstate, types, nparams)` — wire the
  fixed-params resolver into the pstate. Called by
  `parse_analyze_fixedparams` in `analyze.c:140`.
- `setup_parse_variable_parameters(pstate, &types, &nparams)` — wire the
  variable-params resolver in. Called by `parse_analyze_varparams` in
  `analyze.c:179`.
- `check_variable_parameters(pstate, query)` — post-walk that errors if
  any `$n` ended up with type UNKNOWN.

## The hook mechanism

The two `setup_*` functions install a `ParamRef`-handling closure into
`pstate->p_paramref_hook` and stash their state in `pstate->p_ref_hook_state`.
`transformParamRef` in `parse_expr.c` then dispatches via the hook,
producing a `Param` node with the resolved type.

The same hook surface is what PL/pgSQL uses (with a different
implementation) to resolve `$N`-style references to PL/pgSQL variables.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
