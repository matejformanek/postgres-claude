# `contrib/jsonb_plpython/jsonb_plpython.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~518
- **Source:** `source/contrib/jsonb_plpython/jsonb_plpython.c`

Transform-extension bridging `jsonb` and Python objects for
`plpython3u` functions with `TRANSFORM FOR TYPE jsonb`. The largest
PL-bridge in contrib because it must dispatch over four jsonb scalar
types, two container types (object/array), plus four Python type
categories (None/bool/number/str + mapping/sequence). Lazily imports
`cdecimal` or `decimal` on first call to obtain the `Decimal` ctor.
Uses extensive `PG_TRY/PG_CATCH` blocks to keep PyObject refcounts
balanced when ereports interrupt traversal. [verified-by-code]

## API / entry points

- `_PG_init(void)` (line 45) — fetches `PLyObject_AsString`,
  `PLyUnicode_FromStringAndSize`, `PLy_elog_impl` from
  `$libdir/PLPYTHON_LIBNAME`. The `PLy_elog` macro is `#undef`'d
  and redefined to call the loaded function pointer (line 62).
  [verified-by-code]
- `plpython_to_jsonb(PG_FUNCTION_ARGS)` (line 472) — entry into
  `PLyObject_ToJsonbValue` with fresh `JsonbInState`, then
  `JsonbValueToJsonb`. [verified-by-code]
- `jsonb_to_plpython(PG_FUNCTION_ARGS)` (line 488) — lazy-init
  `decimal_constructor`: try `cdecimal` (faster C impl), fall back
  to `decimal`. Then `PLyObject_FromJsonbContainer`. [verified-by-code]

### Internal helpers

- `PLyUnicode_FromJsonbValue` (line 70) — jbvString → Python str.
- `PLyUnicode_ToJsonbValue` (line 83) — Python obj → jbvString via
  `PLyObject_AsString`.
- `PLyObject_FromJsonbValue` (line 96) — jbv scalar → PyObject:
  null→None, numeric→Decimal, string→str, bool→True/False.
- `PLyObject_FromJsonbContainer` (line 138) — recursive walk; the
  rawScalar case unwraps top-level scalars; array → `PyList_New(0)
  + PyList_Append`; object → `PyDict_New` + `PyDict_SetItem`.
- `PLyMapping_ToJsonbValue` (line 266) — Python dict → jsonb object.
- `PLySequence_ToJsonbValue` (line 320) — Python list → jsonb array.
- `PLyNumber_ToJsonbValue` (line 358) — Python number → jbvNumeric
  via `numeric_in`, rejects NaN/inf.
- `PLyObject_ToJsonbValue` (line 408) — top-level dispatcher.

## Notable invariants / details

- Decimal-import is one-shot per backend; `decimal_constructor` is
  a static, never freed, never re-imported. If the Python
  interpreter is reset (currently not done) the dangling pointer
  would crash. [verified-by-code]
- `cdecimal` was a separate package before Python 3.3 (where the C
  decimal landed in stdlib). The fallback path is therefore dead
  on all currently supported Python versions but still present.
  [ISSUE-dead-path: `cdecimal` import path is dead since
  Python 3.3 (nit)].
- The `bool` vs `number` ordering at line 437-438 is intentional:
  `PyNumber_Check(True)` returns true, so the bool branch must run
  first. The comment calls this out. [verified-by-code]
- `PLyMapping_ToJsonbValue` accepts `None` keys (line 289-294) and
  silently coerces to empty string `""`. **No deduplication**, so
  two `None`-keyed entries from a Python class with `__iter__`
  yielding multiple `None`s would create duplicate jsonb keys —
  which `JsonbValueToJsonb` collapses but in an order-dependent
  way (last wins). [verified-by-code] [ISSUE-correctness: None
  key → "" with no warning; collides silently with an actual
  "" string key (maybe)].
- Type-error message at line 449 uses `PLyObject_AsString` on the
  type object itself to produce the type name — clever but if the
  type's `__str__` raises, that exception is swallowed and the
  resulting string is "<error message from PLyObject_AsString>"
  (depends on plpython's stringifier). [verified-by-code]
- `PG_TRY/PG_CATCH` blocks (lines 171-191, 204-247, 275-311,
  331-348, 364-380) all follow the same pattern: declare PyObject
  pointers `volatile`, decref in catch arm, `PG_RE_THROW`. This is
  the standard idiom for Python-PG interop. [verified-by-code]
- `PLyNumber_ToJsonbValue` (line 358) wraps `numeric_in` in
  `PG_TRY` — but the `PG_CATCH` arm **re-ereports** with a fresh
  ERROR rather than re-throwing the original (lines 376-379).
  This **discards the original errcontext** and the original
  errcode. [ISSUE-error-handling: PLyNumber_ToJsonbValue
  swallows numeric_in's original error detail; user sees only
  "could not convert value \"X\" to jsonb" (nit)].

## Potential issues

- Lines 376-379: `PG_CATCH` → `ereport(ERROR, ...)` is the wrong
  pattern. The original error is lost; if `numeric_in` ereports
  due to OOM, the user sees a misleading
  ERRCODE_DATATYPE_MISMATCH. Should be `PG_RE_THROW()` or at
  least preserve original errcode/errmsg via `errcontext`.
  [ISSUE-error-handling: PG_CATCH re-ereport pattern (likely)].
- Line 388, 392: `numeric_is_nan` / `numeric_is_inf` are called
  **after** `numeric_in` may have already allocated; if the input
  is "NaN" they ereport, leaking the Numeric. Per-call context
  cleans up but in pathological loops this is measurable.
  [ISSUE-leak: Numeric leak on NaN/inf rejection (nit)].
- Line 217: `if (!result) return NULL;` on `PyList_New(0)` failure
  — the caller is `PLyObject_FromJsonbContainer` whose top-level
  `result` variable will be NULL, and `jsonb_to_plpython` then
  invokes `PLy_elog(ERROR, ...)`. Path is correct but the NULL-
  return convention is inconsistent with the rest of the
  function (some branches `elog(ERROR, ...)` directly).
  [ISSUE-style: NULL-return vs ereport inconsistency (nit)].
- Line 449: `errmsg("Python type \"%s\" cannot be transformed to
  jsonb", PLyObject_AsString((PyObject *) obj->ob_type))` — the
  `PLyObject_AsString` call allocates within the error path. If
  *it* throws (unlikely but possible), errcontext loops or
  truncated message results. [ISSUE-error-handling: allocation
  in errmsg argument (nit)].
- The trusted-vs-untrusted asymmetry doesn't apply: only
  `plpython3u` exists. The bridge does NOT verify the caller's
  language; it just registers the transform. A misuse via fake
  C-function call wouldn't go through transforms anyway.
  [inferred].

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `jsonb_plpython`](../../../issues/jsonb_plpython.md)
<!-- issues:auto:end -->
