# `contrib/hstore_plpython/hstore_plpython.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~194
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
- `plpython_to_hstore(PG_FUNCTION_ARGS)` (line 123) — guards
  against sequences masquerading as mappings: `PySequence_Check(dict)
  || !PyMapping_Check(dict)` ereports `ERRCODE_WRONG_OBJECT_TYPE`.
  `PyMapping_Items(dict)` returns a Python list of `(key, value)`
  tuples; loop fills `Pairs[]`; `PG_FINALLY` drops the items ref.
  [verified-by-code]

## Notable invariants / details

- Trusted-vs-untrusted: Python plug-ins are **all untrusted**
  post-PG-9.0; there is only `plpython3u`. So there is no
  trusted/untrusted parallel-extension split for the
  `*_plpython` family. The single transform is registered against
  `plpython3u`. [inferred from PG history]
- Lines 138-140 comment explicitly calls out the Python-3.10
  `PyMapping_Check`-reliable threshold: prior to 3.10
  `PyMapping_Check` returns true for sequences. The fallback is to
  check `PySequence_Check` first. Once PG drops support for Python
  < 3.10 this guard can be deleted. [verified-by-code]
  [ISSUE-stale-todo: future cleanup once `python_requires >= 3.10`
  (nit)].
- `PG_FINALLY` (line 187) ensures `Py_DECREF(items)` runs even if
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
- Line 166: `pairs[i].key = PLyObject_AsString(key)` — note
  `needfree = true` (line 168). `PLyObject_AsString` palloc's; the
  pfree responsibility transfers to `hstoreUniquePairs` which
  takes `needfree` as ownership transfer. [verified-by-code]
- Line 145: `PyMapping_Size(dict)` is called before
  `PyMapping_Items(dict)`. If the mapping's `__len__` and
  `__iter__` disagree (custom Python class) the loop bounds and
  the `items` list size could mismatch. The code uses `pcount`
  for both, so `PyList_GetItem` past the end returns NULL → crash
  in `PyTuple_GetItem(NULL, 0)`. [ISSUE-security: malicious
  Python class with mismatched `__len__` / `__iter__` could
  reach NULL deref (maybe — only reachable from plpython3u code,
  which is already untrusted superuser-only)].
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
