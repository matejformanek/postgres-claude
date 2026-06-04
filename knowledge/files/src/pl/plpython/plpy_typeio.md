# plpy_typeio

Covers `source/src/pl/plpython/plpy_typeio.c` (1561 LOC) and `source/src/pl/plpython/plpy_typeio.h` (175 LOC).

Pinned to source `4b0bf0788b0`.

## One-line summary

Bi-directional Datum ↔ PyObject conversion plumbing for PL/Python — sets up
per-type conversion records once (`PLy_*_setup_func`) and then dispatches
through a function pointer for every value. This is **the** type-confusion
surface for PL/Python: every argument crossing the PG ↔ Python boundary
flows through this file.

## Public API

Header file `plpy_typeio.h:150-173` exports:

| Symbol | Direction | Purpose |
|---|---|---|
| `PLy_input_convert(PLyDatumToOb*, Datum)` → `PyObject*` | SQL → Py | Outer-level entry; resets per-call scratch context, dispatches via `arg->func` (`plpy_typeio.c:80-108`). |
| `PLy_output_convert(PLyObToDatum*, PyObject*, bool*)` → `Datum` | Py → SQL | Outer-level entry; just dispatches with `inarray=false` (`plpy_typeio.c:119-124`). |
| `PLy_input_from_tuple(PLyDatumToOb*, HeapTuple, TupleDesc, bool include_generated)` → `PyObject*` | SQL → Py | Tuple-to-dict shortcut used by `nodeFunctionscan`-style returns (`plpy_typeio.c:133-153`). |
| `PLy_input_setup_func` / `PLy_output_setup_func` | both | (Re)initialize a `PLyDatumToOb` / `PLyObToDatum` from `(typeOid, typmod, proc)` — does typcache lookup, domain unwrap, transform lookup, picks a `func` pointer (`plpy_typeio.c:295-408` for output, `:417-542` for input). |
| `PLy_input_setup_tuple` / `PLy_output_setup_tuple` | both | (Re)initialize composite per-column conversion arrays from an explicit `TupleDesc` (`plpy_typeio.c:164-203`, `:214-253`). |
| `PLy_output_setup_record` | Py → SQL | Special bless-the-tupdesc path for `RETURNS RECORD` functions (`plpy_typeio.c:260-286`). |
| `PLyObject_AsString(PyObject*)` → `char*` (palloc'd) | Py → cstring | Server-encoding-aware stringification, exported for transform modules (`plpy_typeio.c:1027-1070`). |

The conversion-state structs (`PLyDatumToOb`, `PLyObToDatum` and their tagged
unions for scalar/array/tuple/transform/domain) are declared in
`plpy_typeio.h:26-147`; the comment at `:22-25` says "the conversion data
structs should be regarded as private to plpy_typeio.c. We declare them here
only so that other modules can define structs containing them" — i.e. they're
embedded into `PLyCursorObject`, `PLyPlanObject`, and the per-arg/per-return
structs in `plpy_procedure.c`.

## Key invariants

- **`arg->func` is the discriminator.** All dispatch goes through it; once
  `PLy_*_setup_func` returns, the consumer never inspects `typoid` to choose
  a path. `PLy_input_setup_tuple` even asserts the func equals
  `PLyDict_FromComposite` (`plpy_typeio.c:170`); ditto
  `PLyObject_ToComposite` for output (`:220`).
- **Recursion is bounded by `check_stack_depth()`.** Both
  `PLy_output_setup_func` and `PLy_input_setup_func` call it on entry
  (`plpy_typeio.c:306`, `:429`). Domains, arrays-of-arrays, and arrays of
  composites all recurse; this is the only stack guard.
- **Output conversion must run even for `Py_None`** so that domain
  constraints fire. The header explicitly documents this contract
  (`plpy_typeio.h:80-83`). Every `PLyObject_To*` function checks
  `plrv == Py_None` first and sets `*isnull = true` before returning
  `(Datum) 0`.
- **Input conversion runs in a *scratch* memory context** reset before each
  call (`plpy_typeio.c:88-101`). The reset is *before* the conversion, not
  after — so a thrown error during reset can't strand a Python refcount.
- **Composite tupdesc is re-checked on every output.**
  `PLyObject_ToComposite` calls `lookup_rowtype_tupdesc` *every time* for
  named composites (`plpy_typeio.c:973`) and compares
  `tuple.tupdescid` against `typentry->tupDesc_identifier` to detect
  `ALTER TYPE` between calls (`:977-982`). RECORD types are cached because
  they can't change.
- **Composite output goes through one of four converters** depending on the
  Python type: string (record_in), sequence, mapping, or generic object via
  `__getattr__` (`plpy_typeio.c:1006-1014`).

## Notable internals

### Input dispatch (SQL → Python)

`PLy_input_setup_func` (`plpy_typeio.c:417-542`):
- Domains: tail-recurse into the base type. Note this means `PLyDatumToOb`
  for a domain ends up with the *base* type's func, completely losing
  domain identity on input (output preserves the domain). This is the
  asymmetric pattern called out in the comment at `:458-464`.
- Arrays (`IsTrueArrayType`): recurse for the element type, set
  `func = PLyList_FromArray`.
- Transform function (`get_transform_fromsql` returns valid OID): use
  `PLyObject_FromTransform`. The transform fmgr returns a `PyObject*`
  disguised as a `Datum` (`plpy_typeio.c:655-661`) — `DatumGetPointer` is
  reinterpret-cast and the contract is that the transform must return an
  owned reference. **No type check on what the transform returns.**
- Composite (`TYPTYPE_COMPOSITE` or RECORDOID): `PLyDict_FromComposite`.
- Scalars: hard-coded fast paths for bool, float4/8, numeric, int2/4/8,
  oid, bytea. Default falls through to `PLyUnicode_FromScalar`, which calls
  the type's *output* function (`OutputFunctionCall`) and wraps the C
  string in Python unicode (`:642-649`). This means **a custom scalar
  type's `_out` function defines its Python representation.**

### Output dispatch (Python → SQL)

`PLy_output_setup_func` (`plpy_typeio.c:295-408`):
- Domains: keep the domain identity; `PLyObject_ToDomain` recursively
  converts via the base, then calls `domain_check` (`:1103-1113`).
- Arrays: `PLySequence_ToArray` — uses `ArrayBuildState`.
- Transform: `PLyObject_ToTransform` calls the to-SQL transform with
  `PointerGetDatum(plrv)` (the PyObject pointer is the "Datum")
  (`:1119-1130`). The transform owns interpretation; we don't type-check.
- Composite: `PLyObject_ToComposite`. Special-cases `Py_None`, then
  PyUnicode (parses via `record_in`), PySequence (positional),
  PyMapping (by column name), else `PyObject_GetAttrString` per column.
- Scalars: hard-coded bool & bytea, else default `PLyObject_ToScalar`
  which stringifies via `PLyObject_AsString` then runs the type's
  *input* function (`InputFunctionCall`).

### Array recursion (`PLyList_FromArray` / `PLySequence_ToArray_recurse`)

Multi-dimensional iteration in physical (row-major) order
(`plpy_typeio.c:706-776`). Bitmap-NULL handling is hand-coded; `bitmap_p`
is advanced via `bitmask <<= 1` with the (1<<8) wrap idiom
(`:761-767`). MAXDIM enforced.

For Python → PG, `PLySequence_ToArray_recurse` (`:1196-1278`) enforces
that all inner lists have equal length per dimension; mixing scalars and
sub-arrays at the same level raises
`ERRCODE_INVALID_TEXT_REPRESENTATION` "multidimensional arrays must have
array expressions with matching dimensions" (`:1239-1241`,
`:1255-1257`). `MAXDIM` check at `:1228-1232`.

### Composite (SQL → Py): `PLyDict_FromTuple` (`:815-874`)

- Skips dropped columns (`attisdropped`).
- For `attgenerated`: skipped unless `include_generated`; **virtual
  generated columns always skipped** (`:849-850`) — newish (PG 18) behavior.
- Iterates with `PyDict_SetItemString(dict, key, value)`. Errors from
  `att->func` propagate through `PG_RE_THROW` with `Py_DECREF(dict)`
  cleanup (`:866-871`).

### Composite (Py → SQL): mapping / sequence / generic-object

- `PLyMapping_ToComposite` (`:1345-1407`): `PyMapping_GetItemString(key)`
  for each non-dropped attribute. **Missing key → ereport
  ERRCODE_UNDEFINED_COLUMN** "key not found in mapping" with a hint to
  set `None` for SQL NULL. Extra keys silently ignored.
- `PLySequence_ToComposite` (`:1410-1484`): length must equal the
  non-dropped column count; mismatch is `ERRCODE_DATATYPE_MISMATCH`
  "length of returned sequence did not match number of columns in row".
  Strict — too many or too few both fail.
- `PLyGenericObject_ToComposite` (`:1487-1561`):
  `PyObject_GetAttrString(object, key)` for each non-dropped column.
  Missing attribute → `ERRCODE_UNDEFINED_COLUMN` "attribute … does not
  exist in Python object" with a long PG-9→10 array-vs-record hint.
- `PLyUnicode_ToComposite` (`:1284-1342`): stringifies via
  `PLyObject_AsString`, then runs `record_in`. The `inarray` branch
  pre-validates that the string starts with `(` (after whitespace), and
  raises an explicit "malformed record literal … Missing left parenthesis"
  before `record_in` does, *only to give a better hint*
  (`:1323-1336`). Otherwise behavior matches `record_in`.

### `PLyObject_AsString` — the encoding gate (`:1027-1070`)

This is the textual `Py → SQL` chokepoint. Steps:
1. PyUnicode? → `PLyUnicode_Bytes` (encodes to server encoding).
2. PyFloat? → `repr()` then bytes (str() is lossy for floats).
3. Else `str()` then bytes.
4. `pstrdup` the C string.
5. Check `strlen(C string) < PyBytes_Size`: ERROR "Python string
   representation appears to contain null bytes" (`:1061-1064`).
6. `strlen > PyBytes_Size`: ERROR "longer than reported length" (assertion
   in disguise).
7. `pg_verifymbstr` (`:1067`) — final encoding validation against server
   encoding.

So **every Python text value entering PG is encoding-validated and
embedded-null-rejected** by this function before reaching any input
function.

## Type-confusion / value-conversion surface

This is the most security-relevant file in the bunch. The conversion
posture per case:

- **Scalars (default path, `PLyUnicode_FromScalar` + `PLyObject_ToScalar`):**
  PG calls the type's `out` function, hands the C string to Python; the
  reverse calls `PLyObject_AsString` (encoding-checked, null-byte-rejected)
  and then the type's `in` function. **Transitively this is exactly the
  attack surface of every scalar type's I/O pair**: a Python value entering
  PG is parsed by `Foo_in()`, so any flaw in a type's input function is
  reachable via plpython text return values. The pg_verifymbstr at
  `:1067` blocks the obvious encoding-confusion vector.
- **Bytea (`PLyObject_ToBytea`, `:900-936`):** `PyObject_Bytes(plrv)` then
  `memcpy` into a fresh `bytea`. Bypasses the cstring path on purpose
  precisely so embedded NULs survive (`:896-898`). Length is taken from
  `PyBytes_Size`; the size + VARHDRSZ palloc is unchecked for overflow but
  `PyBytes_Size` returns `Py_ssize_t` ≥ 0 and palloc caps at MaxAllocSize
  itself. **[ISSUE-defense-in-depth: bytea length comes straight from
  PyBytes_Size with no MaxAllocSize pre-check (likely)]** — palloc will
  throw if too big, but the error happens deep in palloc instead of with a
  domain-appropriate ereport.
- **Bool (`PLyObject_ToBool`):** `PyObject_IsTrue(plrv)`. Python truth is
  permissive (empty list = false, non-empty list = true, etc.). The
  comment at `:877-881` explicitly notes "Python attaches a Boolean value
  to everything, more things than the PostgreSQL bool type can parse."
  Intentional — but means an unexpected SQL boolean is reachable from any
  truthy/falsy Python value.
- **Transform functions** (`PLyObject_FromTransform`,
  `PLyObject_ToTransform`): The transform sees a raw `Datum`/`PyObject*`
  reinterpret-cast. **No validation that the transform's return type
  matches what we expected.** `(PyObject *) DatumGetPointer(t)` at
  `:660` will happily reinterpret any pointer. **[ISSUE-correctness:
  transform function return is untyped (maybe)]** — but transforms must be
  installed by superuser via CREATE TRANSFORM, so this is a privilege-gated
  surface.
- **Composite extra/missing columns:** Mapping: extra ignored, missing
  raises (with hint). Sequence: length must match exactly. Generic object:
  missing raises. Dropped columns always get `(Datum) 0` + null=true.
  **No surprise for the SQL side; the Python side does the validation
  per-call.**
- **Composite type-tag confusion:**  Named composites re-look-up the
  tupdesc per call (`:973`) and detect `ALTER TYPE` via
  `tupDesc_identifier` (`:977-982`). RECORD typmod uses
  `lookup_rowtype_tupdesc(typoid, typmod)` (`:989`) which is keyed on the
  blessed tuple registry. So a maliciously-altered composite between calls
  is detected.
- **Multidimensional arrays:** Strict per-dim length equality enforced
  (`:1237-1241`). Mixing scalars + sublists at the same level errors.
  `MAXDIM` enforced. Empty array → `construct_empty_array` (`:1178`).
- **JSON path:** plpy_typeio has **no special JSON handling**. JSON/JSONB
  values arrive as scalars through `PLyUnicode_FromScalar` → `jsonb_out`
  on input; the reverse calls `jsonb_in` via `PLyObject_ToScalar`. So
  jsonb_in's stack-guarded recursion is the actual safety net; plpython
  doesn't add its own. **[ISSUE-audit-gap: no plpython-specific JSON
  handling; entire JSON surface inherits jsonb_in's recursion limits]** —
  this is by design, but worth flagging when the cross-cite check looks
  at jsonb_in deep recursion CVE risk.
- **Numeric → Decimal (`PLyDecimal_FromNumeric`, `:569-601`):** Lazy
  import of `cdecimal` falling back to `decimal`. The `decimal_constructor`
  is cached in a `static PyObject *` and **never decremented or
  invalidated** — fine for the lifetime of an interpreter, but
  `cdecimal` (Python 2 vintage) hasn't been a thing in Python 3 for many
  years. **[ISSUE-documentation: cdecimal fallback is vestigial under
  Python 3 (nit)]** — `PyImport_ImportModule("cdecimal")` will always
  PyErr_Clear and fall through.

### Encoding for text

- Python → SQL: `PLyObject_AsString` calls `PLyUnicode_Bytes` which is
  `PyUnicode_AsEncodedString(plrv, server_encoding_name, "strict")` in
  `plpy_util.c` (used by `pg_verifymbstr` follow-up).
- SQL → Python: `PLyUnicode_FromString` (in `plpy_util.c`) decodes from
  server encoding to Python unicode.
- Embedded NUL: blocked by the `slen < plen` check at `:1061-1064`.
- Encoding mismatch: blocked by `pg_verifymbstr` at `:1067`.

## Cross-references

- **Siblings (A10 scope):**
  - `plpy_plpymodule` — registers the `plpy.*` API surface.
  - `plpy_resultobject` — `PLyResult`, returned by `plpy.execute`.
  - `plpy_planobject` — `PLyPlan`, returned by `plpy.prepare`.
  - `plpy_cursorobject` — `PLyCursor`, returned by `plpy.cursor`.
- **Siblings (other A10 agents):**
  - `plpy_spi.c` — uses `PLy_output_setup_func` to set up `PLyPlanObject->args`
    and `PLy_input_from_tuple` to wrap result tuples.
  - `plpy_exec.c` — uses `PLy_input_convert` for in-args and
    `PLy_output_convert` for the return value.
  - `plpy_procedure.c` — long-lived `PLyDatumToOb`/`PLyObToDatum` arrays
    live in the per-procedure memory context.
  - `plpy_elog.c` — `PLy_elog` used by transform error paths.
  - `plpy_util.c` — `PLyUnicode_Bytes`, `PLyUnicode_FromString`,
    `PLyUnicode_AsString`.
- **Backend dependencies:**
  - `utils/typcache.c` — `lookup_type_cache`, `TypeCacheEntry`,
    `tupDesc_identifier` invalidation.
  - `utils/cache/typcache.c` — `lookup_rowtype_tupdesc`.
  - `utils/fmgr.c` — `fmgr_info_cxt`, `OutputFunctionCall`,
    `InputFunctionCall`, `FunctionCall1` for transforms.
  - `utils/adt/domains.c` — `domain_check`.
  - `utils/adt/arrayfuncs.c` — `ArrayBuildState`, `accumArrayResult`,
    `makeMdArrayResult`, `construct_empty_array`.
  - `mb/pg_wchar.c` — `pg_verifymbstr` (encoding gate).

## Issues spotted

- [ISSUE-defense-in-depth: bytea length comes straight from `PyBytes_Size`
  with no explicit MaxAllocSize pre-check (nit)] — `plpy_typeio.c:921-923`.
  palloc will throw on huge sizes, but the error site is generic.
- [ISSUE-correctness: transform-function return is reinterpret-cast with
  no type tag verification (maybe)] — `plpy_typeio.c:660` (input),
  `:1129` (output). Mitigated by superuser-only CREATE TRANSFORM.
- [ISSUE-audit-gap: no plpython-specific JSON/JSONB validation; depends
  entirely on jsonb_in's recursion guards (maybe)] — affects the entire
  default-scalar path for json/jsonb.
- [ISSUE-documentation: cdecimal fallback at `:577-586` is unreachable
  under Python 3 (nit)] — module is Python-2-era; harmless but dead.
- [ISSUE-memory: `decimal_constructor` cached in a static `PyObject *`
  with no shutdown decref (nit)] — `:572`. Process-lifetime; matches PG
  per-backend lifecycle, so acceptable.
- [ISSUE-error-handling: `PLyObject_AsString` `slen > plen` path uses
  `elog(ERROR, ...)` rather than `ereport` with errcode (nit)] —
  `plpy_typeio.c:1066`. This is a "can't happen" branch, so the elog is
  consistent with PG style.
- [ISSUE-api-shape: `PLy_input_setup_func` silently discards domain
  identity on input (documentation)] — `plpy_typeio.c:465-471`. Asymmetric
  with output. Comment at `:458-464` acknowledges this is "somewhat
  historical." Means a Python receiving a domain-typed value never
  observes the domain constraint on the input path (output preserves it).
