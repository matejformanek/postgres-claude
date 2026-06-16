# plpy_resultobject

Covers `source/src/pl/plpython/plpy_resultobject.c` (281 LOC) and
`source/src/pl/plpython/plpy_resultobject.h` (27 LOC).

Pinned to source `4b0bf0788b0`.

## One-line summary

`PLyResult` — the Python type returned by `plpy.execute(...)` and by
cursor `fetch()`. A list-like wrapper around the SPI result rows with
metadata accessors (`colnames`, `coltypes`, `coltypmods`, `nrows`,
`status`).

## Public API

### Struct layout (`plpy_resultobject.h:13-22`)

```
PLyResultObject {
    PyObject_HEAD
    PyObject   *nrows;    /* PyLong, returned by query */
    PyObject   *rows;     /* PyList of row dicts, empty when no data */
    PyObject   *status;   /* PyLong (SPI_OK_* / SPI_ERR_*) or Py_None */
    TupleDesc   tupdesc;  /* heap-copied; freed in dealloc */
}
```

### C entry points

| C symbol | Purpose | Cite |
|---|---|---|
| `PLy_result_init_type(void)` | Register the PyTypeObject via `PyType_FromSpec`. Called once from `PyInit_plpy`. | `plpy_resultobject.c:80-86` |
| `PLy_result_new(void)` | Construct a fresh empty `PLyResultObject` with `status=None, nrows=-1, rows=[]`. | `:88-114` |

### Python-visible methods (`PLy_result_methods`, `:27-34`)

| Python method | C function | Returns | Cite |
|---|---|---|---|
| `colnames()` | `PLy_result_colnames` | list of str | `:139-163` |
| `coltypes()` | `PLy_result_coltypes` | list of int (OIDs) | `:165-189` |
| `coltypmods()` | `PLy_result_coltypmods` | list of int | `:191-215` |
| `nrows()` | `PLy_result_nrows` | PyLong | `:217-224` |
| `status()` | `PLy_result_status` | PyLong | `:226-233` |

### PyType slots (`PLyResult_slots`, `:36-68`)

- `Py_tp_dealloc` → `PLy_result_dealloc` — refcount-DECREFs nrows/rows/
  status, calls `FreeTupleDesc` if non-NULL (`:116-137`).
- `Py_sq_length` / `Py_mp_length` → `PLy_result_length` —
  `PyList_Size(ob->rows)` (`:235-241`).
- `Py_sq_item` → `PLy_result_item` — `PyList_GetItem(ob->rows, idx)`
  with INCREF (`:243-253`).
- `Py_mp_subscript` → `PLy_result_subscript` —
  `PyObject_GetItem(ob->rows, item)` (`:267-273`). **This is what
  handles slices and dict-key lookups.**
- `Py_mp_ass_subscript` → `PLy_result_ass_subscript` —
  `PyObject_SetItem(ob->rows, item, value)` (`:275-281`). **Result
  rows are mutable from Python.**
- `Py_tp_str` → `PLy_result_str` — `<PLyResult status=… nrows=… rows=…>`
  (`:255-265`).
- `Py_tp_doc` — "Results of a PostgreSQL query".
- `Py_tp_methods` — see method table above.

### Spec flags (`:70-76`)

`Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE` — subclassable from Python.

## Key invariants

- **`tupdesc` is non-NULL only when the query produced columns.**
  `PLy_result_new` sets it to NULL (`:106`); `plpy_spi.c:_fetch_result`
  fills it in only when `status > 0 && tuptable != NULL`. The three
  `*colnames/coltypes/coltypmods` getters guard with
  `if (!ob->tupdesc) { PLy_exception_set(...,  "command did not produce
  a result set"); return NULL; }` (`:146-150`, `:172-176`, `:198-202`).
- **`rows` is always a list, never NULL after construction.**
  `PLy_result_new` aborts via `Py_DECREF(ob); return NULL` if
  `PyList_New(0)` fails (`:107-111`).
- **`dealloc` calls `FreeTupleDesc`** on the heap-copied tupdesc
  (`:127-130`). The tupdesc that lives here is the result of a copy in
  `plpy_spi.c`, not a typcache-shared one.
- **Py 3.8+ PyType refcount workaround** is applied (`:119-121`,
  `:133-136`) — Python issue 35810 says the type slot DECREF'd in
  dealloc must be paired with an INCREF at alloc time on older Pythons
  only; PG carries the workaround across the cutover.

## Notable internals

### Index / slice / assignment behavior

The map-protocol slots delegate straight to the underlying `rows`
list. So:

- `result[5]` → `PyObject_GetItem(rows, 5)` (`:267-273`).
- `result[2:8]` → same path, slice semantics inherited from list.
- `result[-1]` → standard Python negative-index semantics inherited
  from list.
- `result[5] = {...}` → `PyObject_SetItem(rows, 5, {...})` (`:275-281`)
  — **the SPI result can be mutated in-place from Python**. Doesn't
  affect anything in PG (no write-through), just the user's Python
  view.
- `result["colname"]` → `PyObject_GetItem(rows, "colname")` — **this
  fails** with `TypeError: list indices must be integers or slices`
  because rows is a plain Python list, not a dict-of-cols.
  Per-row access is `result[i]["colname"]` (each row IS a dict from
  `PLyDict_FromTuple`).

### `nrows` field — sentinel vs SPI result

`PLy_result_new` sets `nrows = -1` (`:104`). The actual value gets
overwritten by `plpy_spi.c` via:

```
Py_DECREF(result->nrows);
result->nrows = PyLong_FromUnsignedLongLong(rows);
```

So if you ever observe `result.nrows() == -1`, the construction code
path returned the result before `_fetch_result` could populate it —
which shouldn't happen in normal flow (it's an internal invariant).

### `status` field

`PLy_result_new` sets `status = Py_None` (`:102-103`). For successful
SPI executions, `plpy_spi.c` overwrites with
`PyLong_FromLong(status)` where `status` is one of the
`SPI_OK_*`/`SPI_ERR_*` constants.

## Type-confusion / value-conversion surface

This object is a passive container — almost no validation surface
beyond "tupdesc must be set for colnames/types/typmods". Notable:

- **`coltypes` returns OIDs as PyLongs** (`:185`). User code that
  treats them as ints and reverse-looks-up via SQL is fine; treating
  them as type names without a lookup is a footgun.
- **`coltypmods` returns raw typmods** (`:211`). For varchar(N), this
  encodes N + VARHDRSZ; for unbounded types it's -1. PG-side semantics
  not abstracted.
- **`rows` mutability** (`:275-281`) means user code can replace a row
  with arbitrary Python objects, then iterate; downstream code that
  expects a dict will crash with AttributeError. No surprise for PG —
  the data is already detached from SPI by the time the user sees it.
- **`PLy_result_item` returns a borrowed-ref-with-INCREF pattern**
  (`:249-252`). If `PyList_GetItem` returns NULL (out-of-bounds), the
  `if (rv != NULL) Py_INCREF(rv)` lets the NULL propagate as the
  IndexError that PyList already set. Clean.

## Cross-references

- **Siblings (A10):**
  - `plpy_plpymodule` — `PLy_result_init_type` called from `PyInit_plpy`.
  - `plpy_cursorobject` — `PLy_cursor_fetch` (in `plpy_cursorobject.c`)
    constructs a `PLyResultObject` and fills `status`, `nrows`, `rows`.
  - `plpy_planobject` — `PLy_spi_execute_plan` builds one of these.
  - `plpy_typeio` — each entry in `rows` is a dict built by
    `PLy_input_from_tuple` → `PLyDict_FromTuple`.
- **Sibling other-A10:**
  - `plpy_spi.c:_fetch_result` (`PLy_spi_execute_fetch_result`,
    `plpy_spi.c:337`) is the main producer — it sets `tupdesc` (via
    `CreateTupleDescCopy`), `status`, `nrows`, and fills `rows`.
- **Backend dependencies:**
  - `access/tupdesc.c` — `FreeTupleDesc`, `TupleDescAttr`.
  - `executor/spi.c` — `SPI_OK_*` constants are what `status` holds.

<!-- issues:auto:begin -->
- [Issue register — `plpython`](../../../../issues/plpython.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-api-shape: `result["colname"]` doesn't work; users must do
  `result[i]["colname"]` (documentation)] — counter-intuitive given
  the name. No code change implied; doc note.
- [ISSUE-correctness: `nrows` initialized to PyLong(-1) sentinel
  (`:104`) but never checked by callers (nit)] — relies on `_fetch_result`
  always overwriting before user sees it.
- [ISSUE-defense-in-depth: `Py_mp_ass_subscript` slot allows user to
  mutate `result.rows` (nit, by-design)] — harmless because the data
  is detached, but lets a buggy script silently corrupt its own result
  view.
- [ISSUE-memory: `tupdesc` is a heap-copy not refcounted via typcache
  (nit)] — `FreeTupleDesc` in dealloc is correct given how it's set
  up upstream. Worth confirming with the producer site in
  `plpy_spi.c:_fetch_result`.
