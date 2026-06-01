# params.h

- **Source:** `source/src/include/nodes/params.h` (~170 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

Carrier types for **parameter values** flowing into the executor.
Two parameter modes: PARAM_EXTERN (statically known up-front,
`ParamExternData`) and PARAM_EXEC (computed during execution,
`ParamExecData`). `:23-40` `[from-comment]`

## Key structs

### `ParamExternData` `:89`

```c
typedef struct ParamExternData {
    ParamFetchHook  fetchfn;   /* lazy fetch, optional */
    void           *paramfetch_arg;
    int             pflags;    /* bit field; PARAM_FLAG_CONST = treat as constant */
    Oid             ptype;     /* InvalidOid for unused slot */
    bool            pisnull;
    int16           plen;
    bool            pbyval;
    Datum           pvalue;
} ParamExternData;
```

### `ParamListInfoData` `:109`

The container the parser/planner/executor passes around. Either:
- **Static** mode: array of `numParams` ParamExternData entries
  appended to the struct (FLEXIBLE_ARRAY_MEMBER pattern).
- **Dynamic** mode: a `paramFetch` callback resolves params on
  demand; useful for SPI / cursor / PL-level callers.

Top-level fields: `paramFetch`, `paramFetchArg`,
`paramCompile`, `paramCompileArg`, `parserSetup`, `parserSetupArg`,
`paramValuesStr`, `numParams`, `params[]`.

### `ParamExecData` `:145`

Per-PARAM_EXEC slot: `execPlan` (the SubPlan/InitPlan being
evaluated), `value`, `isnull`. Stored in `EState.es_param_exec_vals`.

### `ParamsErrorCbData` `:153`

Per-query error callback context for printing params in error
messages.

## PARAM_FLAG_CONST `:40+`

Tells the planner the runtime value is permissible to treat as a
constant for that one plan (allows custom-plan re-planning when the
value changes a lot).

## Cross-references

- Implementation: `source/src/backend/nodes/params.c`,
  `source/src/backend/executor/execMain.c`.
- Param nodes: `primnodes.h Param`.
- SPI / PL bridges: `src/backend/executor/spi.c`,
  `src/pl/plpgsql/src/pl_exec.c`.
