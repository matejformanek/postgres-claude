# parse_param.h

- **Source:** `source/src/include/parser/parse_param.h` (~25 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Hook-setup API for the two core-backend `$n` parameter cases.

```c
extern void setup_parse_fixed_parameters(ParseState *,
                                         const Oid *paramTypes, int n);
extern void setup_parse_variable_parameters(ParseState *,
                                            Oid **paramTypes, int *n);
extern void check_variable_parameters(ParseState *, Query *);
extern bool query_contains_extern_params(Query *);
```

The two `setup_*` functions install `ParamRef`-handling closures into
`pstate->p_paramref_hook` / `p_coerce_param_hook`. PL/pgSQL uses the same
hook surface with its own closures and does not include this header.
