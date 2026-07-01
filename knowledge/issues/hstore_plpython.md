# Issues — `contrib/hstore_plpython`

Per-subsystem issue register for **hstore_plpython**, the hstore ↔
Python dict transform extension. Single-file extension, ~194 LOC.

**Parent docs:** `knowledge/files/contrib/hstore_plpython/hstore_plpython.c.md`

**Source:** sweep A21-D, 2026-06-11.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | hstore_plpython.c:103-115 | correctness | maybe | `PLyUnicode_FromStringAndSize` NULL return on OOM/decode not checked before `PyDict_SetItem(dict, key, ...)`; NULL key is undefined behaviour | open | files/contrib/hstore_plpython/hstore_plpython.c.md |
| 2026-06-11 | hstore_plpython.c:174-177 | security | maybe | `PyMapping_Size` vs `PyMapping_Items` length mismatch for adversarial Python class with mismatched `__len__` / `__iter__` could reach `PyTuple_GetItem(NULL, 0)` | landed 8612f0b7ce09 (2026-06-29, triaged 2026-07-01) | files/contrib/hstore_plpython/hstore_plpython.c.md |
| 2026-06-11 | hstore_plpython.c:96 | error-handling | nit | `errmsg("out of memory")` for `PyDict_New` failure hides any non-OOM Python error | open | files/contrib/hstore_plpython/hstore_plpython.c.md |
| 2026-06-11 | hstore_plpython.c:138-140 | stale-todo | nit | `PyMapping_Check` 3.10-pre-reliable workaround can be removed when PG drops Python <3.10 support | open | files/contrib/hstore_plpython/hstore_plpython.c.md |

## Notes

Trusted/untrusted: doesn't apply for plpython. Since PG 9.0 only
`plpython3u` (untrusted) exists — all Python access requires
superuser. No parallel `hstore_plpythonu` extension.

`PG_FINALLY` block (line 203) correctly drops the items refcount
even when `PLyObject_AsString` / `hstoreCheckKeyLen` / `hstorePairs`
ereport. The `volatile` qualifier on `items` and `out` (lines 129,
131) protects against longjmp clobbering.

The 145-162 security row landed via 8612f0b7ce09 (2026-06-29, "plpython:
Fix NULL pointer dereferences for broken sequence and mapping"): the
tuple returned by `PyList_GetItem` is now validated
(`tuple == NULL || !PyTuple_Check(tuple) || PyTuple_Size(tuple) < 2`,
lines 174-177) before `PyTuple_GetItem`, and both `PyMapping_Size` /
`PyMapping_Items` NULL returns are checked (146-149, 152-155). The
remaining three open rows (103-115 correctness, :96 error-handling,
138-140 stale-todo) were untouched and still hold at b7e4e3e7fa73.
