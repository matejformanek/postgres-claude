# Issues — `contrib/ltree_plpython`

Per-subsystem issue register for **ltree_plpython**, the one-way ltree
→ Python list-of-strings transform extension. Single-file extension,
~62 LOC.

**Parent docs:** `knowledge/files/contrib/ltree_plpython/ltree_plpython.c.md`

**Source:** sweep A21-D, 2026-06-11.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | ltree_plpython.c (whole file) | undocumented-invariant | nit | Only ltree → Python direction exists; no `plpython_to_ltree`. No comment explains the asymmetry | open | files/contrib/ltree_plpython/ltree_plpython.c.md |
| 2026-06-11 | ltree_plpython.c:53-57 | correctness | nit | `PLyUnicode_FromStringAndSize` NULL return not checked before `PyList_SetItem`; silently substitutes None for the level | open | files/contrib/ltree_plpython/ltree_plpython.c.md |
| 2026-06-11 | ltree_plpython.c:48-50 | error-handling | nit | `errcode(ERRCODE_OUT_OF_MEMORY)` on `PyList_New` failure swallows actual Python error | open | files/contrib/ltree_plpython/ltree_plpython.c.md |
| 2026-06-11 | ltree_plpython.c:53-57 | style | nit | Tight conversion loop with no `CHECK_FOR_INTERRUPTS`; mitigated by ltree's own 65k-level cap | open | files/contrib/ltree_plpython/ltree_plpython.c.md |

## Notes

The asymmetry (only one direction) is the most notable thing about
this bridge. Comparison with the symmetric pairs in `hstore_plpython`
and `jsonb_plpython` suggests the omission was intentional: ltree
has strict per-level validation that doesn't trivially round-trip
from a list of strings. Users wanting Python → ltree can `'.'.join`
and let the text-cast handle it.

Trusted/untrusted: doesn't apply for plpython3u (untrusted only).

`PyList_SetItem` steals the reference returned by
`PLyUnicode_FromStringAndSize`, so no Py_DECREF is needed in the loop
— correct API usage.
