# `src/backend/nodes/params.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~420
- **Source:** `source/src/backend/nodes/params.c`

`ParamListInfo` is the runtime carrier for `$N` parameter values. This
file holds the allocator, copy, serialize/restore, log-format, and
error-callback helpers for it. The data structure itself is defined in
`include/nodes/params.h`. Used by SPI, libpq's extended-query protocol,
plpgsql (extensively), PREPARE/EXECUTE, and parallel-worker
transmission. [verified-by-code]

## API / entry points

- `ParamListInfo makeParamList(int numParams)` — allocates the trailing
  `ParamExternData[numParams]` flex array via `offsetof + N * size`.
  Sets `parserSetup = paramlist_parser_setup` so the parser knows how
  to resolve `$N` references when a query is parsed with this
  ParamListInfo. [verified-by-code §params.c:43-63]
- `ParamListInfo copyParamList(ParamListInfo from)` — deep copy of
  values; **deliberately does NOT copy `paramFetch`/`paramCompile`
  hooks** — the copy is meant to be a static snapshot. Calls
  `from->paramFetch()` for each dynamic param to materialize it
  first, then `datumCopy()` for pass-by-ref types.
  [verified-by-code §params.c:77-112, from-comment §params.c:65-76]
- `EstimateParamListSpace` / `SerializeParamList` / `RestoreParamList`
  — for parallel-worker transmission via DSM. Wire format:
  `int4 nparams` then per-param `{ Oid typeOid; uint16 pflags;
  serialized-datum }`. Mirrors `copyParamList` in that hooks aren't
  preserved — the worker gets a static snapshot.
  [verified-by-code §params.c:166-317]
- `char *BuildParamLogString(params, knownTextValues, maxlen)` —
  produces the `$1 = 'foo', $2 = 42` style string for
  `log_parameter_max_length`. **Returns NULL if `paramFetch != NULL`
  or `IsAbortedTransactionBlockState()`** — can't run output
  functions during abort, can't safely invoke a fetch hook.
  [verified-by-code §params.c:332-396, from-comment §params.c:344-352]
- `void ParamsErrorCallback(void *arg)` — `errcontext` callback. Uses
  `data->params->paramValuesStr` which is set by the caller (typically
  to the result of `BuildParamLogString`). No-op if not preset.
  [verified-by-code §params.c:404-420]

## Notable invariants / details

- **`!OidIsValid(prm->ptype)`** treats the param as undefined / not
  bound; copies/serializes pass `typLen = sizeof(Datum), typByVal =
  true` as a placeholder. Used by plpgsql for params that haven't been
  filled in yet. [verified-by-code §params.c:104-108, 196-201, 269-273]
- **`paramFetch` is consulted for every read** — `copyParamList`,
  `EstimateParamListSpace`, and `SerializeParamList` all do
  `from->paramFetch(from, i+1, false, &prmdata)` rather than reading
  `from->params[i]` directly. Without this, dynamic params (like
  plpgsql's DECLARE state) wouldn't materialise.
  [verified-by-code §params.c:96-98, 184-186, 250-252]
- **`paramValuesStr` is NOT copied** by `copyParamList` — the comment
  says it may have been generated with a different `maxlen`, and is
  redundant given `BuildParamLogString` exists. [from-comment §params.c:75-76]
- **`paramlist_param_ref`** (the static parser hook) sets
  `paramtypmod = -1`, `paramcollid` from `get_typcollation`,
  `paramkind = PARAM_EXTERN`. Returns NULL if param number is out of
  range or ptype is invalid — letting the parser raise its usual
  "there is no parameter $N" error. [verified-by-code §params.c:130-161]
- **`tmpCxt` inside `BuildParamLogString`** — output functions run in a
  short-lived `AllocSetContext` named "BuildParamLogString" so that
  the type output palloc'd strings don't leak into the caller's
  context. The resulting StringInfo lives in caller's context though
  (initialized before the switch). [verified-by-code §params.c:354-396]

## Potential issues

- **File-line `params.c:104-108`.** When `ptype` is invalid, the
  copy/serialize code uses `(typLen, typByVal) = (sizeof(Datum), true)`.
  This assumes the source `value` is small enough to fit — but a
  poorly-initialised `ParamExternData` could have a varlena pointer
  here, which would then be copied/serialised as a Datum-sized int.
  The contract is "if `!OidIsValid(ptype)` the value is meaningless",
  but it's not asserted. [ISSUE-undocumented-invariant: invalid-ptype implies value-is-junk (maybe)]
