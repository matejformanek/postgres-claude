# `contrib/hstore_plpython/hstore_plpython.c`

- **Last verified commit:** `b7e4e3e7fa73`
- **Lines:** 210
- **Source:** `source/contrib/hstore_plpython/hstore_plpython.c`

Transform-extension bridging `hstore` and Python dicts for `plpython3u`
functions with `TRANSFORM FOR TYPE hstore`. Mirrors `hstore_plperl`'s
shape: `_PG_init` loads function pointers from `$libdir/<plpython>`
and `$libdir/hstore`; the two transform functions build a `PyDict_New`
from an HStore or walk a Python mapping back into a `Pairs[]` /
`hstorePairs`. Uses `PG_TRY/PG_FINALLY` to keep `items` decref'd on
the Python side even if `PLyObject_AsString` ereports. [verified-by-code]

## API / entry points

- `_PG_init(void)` (line 44) — fetches `PLyObject_AsString`,
  `PLyUnicode_FromStringAndSize` from `$libdir/PLPYTHON_LIBNAME`
  and five hstore symbols. `PLPYTHON_LIBNAME` is a CPP define from
  `plpython` headers; only the Python-3 build ("plpython3") is
  ever present post-PG-13 (Python 2 support removed in commit
  `9d63ea7b`, PG 13). [verified-by-code] [inferred for Python-2
  removal]
- `hstore_to_plpython(PG_FUNCTION_ARGS)` (line 81) — `PyDict_New`,
  loop `PyDict_SetItem(dict, key, value)` for each pair (NULL value
  → `Py_None`). `Py_XDECREF` after each `SetItem` because
  `PyDict_SetItem` itself takes a ref. Returns `PointerGetDatum(dict)`.
  [verified-by-code]
- `plpython_to_hstore(PG_FUNCTION_ARGS)` (line 125) — guards
  against sequences masquerading as mappings: `PySequence_Check(dict)
  || !PyMapping_Check(dict)` ereports `ERRCODE_WRONG_OBJECT_TYPE`
  (`not a Python mapping`, line 140-143). `PyMapping_Size` is now
  NULL-checked (`pcount < 0`, 146-149) and `PyMapping_Items(dict)`
  is NULL-checked (152-155) — both hardened by 8612f0b7ce09. The
  returned Python list of `(key, value)` tuples fills `Pairs[]`;
  each tuple is validated (`tuple == NULL || !PyTuple_Check(tuple)
  || PyTuple_Size(tuple) < 2`, 174-177) before use; `PG_FINALLY`
  drops the items ref. [verified-by-code]

## Notable invariants / details

- Trusted-vs-untrusted: Python plug-ins are **all untrusted**
  post-PG-9.0; there is only `plpython3u`. So there is no
  trusted/untrusted parallel-extension split for the
  `*_plpython` family. The single transform is registered against
  `plpython3u`. [inferred from PG history]
- Lines 135-139 comment explicitly calls out the Python-3.10
  `PyMapping_Check`-reliable threshold: prior to 3.10
  `PyMapping_Check` returns true for sequences. The fallback is to
  check `PySequence_Check` first (line 140). Once PG drops support
  for Python < 3.10 this guard can be deleted. [verified-by-code]
  [ISSUE-stale-todo: future cleanup once `python_requires >= 3.10`
  (nit)].
- `PG_FINALLY` (line 203) ensures `Py_DECREF(items)` runs even if
  any `PLyObject_AsString` / `hstoreCheckKeyLen` / `hstorePairs`
  ereports. The `volatile` qualifier on `items` and `out` (lines
  129, 131) protects against longjmp clobbering across the
  PG_TRY. [verified-by-code]
- `Py_XDECREF` vs `Py_DECREF`: the loop uses `Py_XDECREF` because
  `PyUnicode_FromStringAndSize` returns NULL on OOM and dec on
  NULL is a crash. But the OOM is not propagated as an ereport —
  `PyDict_SetItem(dict, NULL, ...)` would later segfault. [ISSUE-
  correctness: PyUnicode_FromStringAndSize NULL return not checked
  before PyDict_SetItem; OOM → segfault rather than clean ereport
  (maybe — OOM under plpython is generally fatal anyway)].

## Potential issues

- Lines 103, 111: `PLyUnicode_FromStringAndSize` can fail (OOM,
  decoding error if HSTORE bytes are not valid UTF-8). Return
  value is **not checked** before `PyDict_SetItem(dict, key, …)`.
  `PyDict_SetItem` with `key=NULL` is undefined behaviour.
  [ISSUE-correctness: missing NULL-check on Py-side allocations
  (maybe)].
- Line 182: `pairs[i].key = PLyObject_AsString(key)` — note
  `needfree = true` (line 184). `PLyObject_AsString` palloc's; the
  pfree responsibility transfers to `hstoreUniquePairs` which
  takes `needfree` as ownership transfer. [verified-by-code]
- Line 145: `PyMapping_Size(dict)` is called before
  `PyMapping_Items(dict)`. If the mapping's `__len__` and
  `__iter__` disagree (custom Python class) the loop bounds and
  the `items` list size could mismatch. **RESOLVED upstream by
  8612f0b7ce09** ("plpython: Fix NULL pointer dereferences for
  broken sequence and mapping", 2026-06-29): `PyList_GetItem` past
  the end is now guarded — each `tuple` is checked for
  `NULL || !PyTuple_Check || PyTuple_Size < 2` (lines 174-177)
  before `PyTuple_GetItem`, and both `PyMapping_Size` and
  `PyMapping_Items` NULL returns are checked (146-149, 152-155).
  The former [ISSUE-security] NULL-deref from a malicious Python
  class with mismatched `__len__` / `__iter__` no longer reaches.
  [verified-by-code]
- Line 96: `errmsg("out of memory")` should typically use the
  PG_RE_THROW style — `PyDict_New` failure here would be a real
  Python interpreter error, not necessarily OOM. The error
  message swallows the actual cause. [ISSUE-error-handling:
  generic "out of memory" hides the Python-side error (nit)].

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `hstore_plpython`](../../../issues/hstore_plpython.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-hstore_plpython.md](../../../subsystems/contrib-hstore_plpython.md)
