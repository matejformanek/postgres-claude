# `src/backend/utils/fmgr/funcapi.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~1980
- **Source:** `source/src/backend/utils/fmgr/funcapi.c`

Helpers for set-returning functions (SRFs), composite-returning
functions, and the `RECORD`/polymorphic resolution machinery used by
fmgr-callable C functions. Already covered in part by other docs.

## SRF call protocol

- `SRF_FIRSTCALL_INIT()` → allocates `FuncCallContext` in the per-call
  multi-call memory context.
- `SRF_PERCALL_SETUP()` → restores context.
- `SRF_RETURN_NEXT(funcctx, datum)` / `SRF_RETURN_DONE(funcctx)` —
  per-call return macros; deal with the `ReturnSetInfo` plumbing.
- `InitMaterializedSRF(fcinfo, flags)` — newer alternative for
  materialize-mode SRFs (e.g. tuplestore-based) used by most newly-
  written system views.

## Composite type plumbing

- `get_call_result_type` — derive `TypeFuncClass` + `TupleDesc` from
  fmgr context: handles plain composite, RECORD with a column-list
  call, polymorphic resolution from argument types.
- `resolve_polymorphic_argtypes` — figures out anyelement/anyarray/
  anyrange concretizations.
- `TupleDescGetAttInMetadata` / `BuildTupleFromCStrings` — common
  helper for SRFs that produce composite output from strings.

## Notable

- `get_func_result_name` lets `SELECT * FROM srf()` retrieve OUT-
  parameter column names.
- Heavy use by `pg_stat_*` functions, `pg_ls_*`, `unnest`,
  `generate_series` — anything returning SETOF or composite. [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
