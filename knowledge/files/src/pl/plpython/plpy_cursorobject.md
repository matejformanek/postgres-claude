# plpy_cursorobject

Covers `source/src/pl/plpython/plpy_cursorobject.c` (520 LOC) and
`source/src/pl/plpython/plpy_cursorobject.h` (24 LOC).

Pinned to source `4b0bf0788b0`.

## One-line summary

`PLyCursor` — the Python type returned by `plpy.cursor(...)` or
`plan.cursor(...)`. Wraps an SPI portal by name (not by pointer), supports
Python's iterator protocol (`for row in cursor: ...`), explicit `fetch(N)`,
and `close()`. Each cursor owns a subtransaction-bounded portal pinned for
its lifetime.

## Public API

### Struct layout (`plpy_cursorobject.h:11-18`)

```
PLyCursorObject {
    PyObject_HEAD
    char           *portalname;   /* SPI portal name (in mcxt) */
    PLyDatumToOb    result;       /* RECORD-typed input conversion */
    bool            closed;       /* user called close() or dealloc ran */
    MemoryContext   mcxt;         /* owns portalname; deleted in dealloc */
}
```

### C entry points

| C symbol | Purpose | Cite |
|---|---|---|
| `PLy_cursor_init_type(void)` | Register PyTypeObject. Called once from `PyInit_plpy`. | `plpy_cursorobject.c:68-74` |
| `PLy_cursor(self, args)` | Module-level entry for `plpy.cursor(...)`. Tries `"s"` (query) parse, falls back to `"O|O"` (plan, args). | `:76-93` |
| `PLy_cursor_plan(ob, args)` | Plan-form constructor; binds args via `PLy_output_convert` then `SPI_cursor_open`. | `:163-301` |

### Python-visible methods (`PLy_cursor_methods`, `:30-34`)

| Python method | C function | Cite |
|---|---|---|
| `fetch(N)` | `PLy_cursor_fetch` | `:397-496` |
| `close()` | `PLy_cursor_close` | `:498-520` |

### PyType slots (`PLyCursor_slots`, `:36-56`)

- `Py_tp_dealloc` → `PLy_cursor_dealloc` — auto-closes the portal if
  not closed, deletes mcxt (`:303-333`).
- `Py_tp_iter` → `PyObject_SelfIter` — cursor is its own iterator.
- `Py_tp_iternext` → `PLy_cursor_iternext` — single-row fetch
  (`:335-395`).
- `Py_tp_methods` — see method table.
- `Py_tp_doc` — "Wrapper around a PostgreSQL cursor".

## Key invariants

- **Portal is looked up by name on every access** via
  `GetPortalByName(self->portalname)` (`:313`, `:353`, `:419`, `:505`).
  This is the deliberate design: holding the `Portal*` directly across
  Python ↔ PG calls is unsafe because a subtransaction abort could
  invalidate it.
- **Portal is `PinPortal`'d at creation** (`:148`, `:285`) and
  `UnpinPortal`'d at close (`:317`, `:514`). The pin keeps the portal
  alive across the user-controlled iteration.
- **`closed` flag is one-way.** Once set true, all methods reject
  with `ValueError "iterating/fetch from/closing a closed cursor"`
  (`:347-351`, `:413-417`, `:507`).
- **Every SPI call runs inside a `PLy_spi_subtransaction_*` envelope**
  (`:124-157`, `:225-297`, `:364-392`, `:434-493`). This is the
  contract that lets a Python exception unwind without leaving a
  partial state — subxact abort rolls back the SPI side, exception
  propagates to Python.
- **Result tuples are converted as RECORDOID with typmod=-1** initially
  (`:117-119`, `:218-220`); the per-call tupdesc gets installed by
  `PLy_input_setup_tuple` once `SPI_tuptable->tupdesc` is known
  (`:376-377`, `:469-470`).

## Notable internals

### `PLy_cursor` — the two-form parse (`:76-93`)

```
if (PyArg_ParseTuple(args, "s", &query))
    return PLy_cursor_query(query);

PyErr_Clear();   /* swallow the failed parse */

if (PyArg_ParseTuple(args, "O|O", &plan, &planargs))
    return PLy_cursor_plan(plan, planargs);
```

**[ISSUE-correctness: `PLy_cursor_plan` does not call
`is_PLyPlanObject(ob)` before casting (likely)]** — the fallback at
`:88` parses `"O|O"` which accepts any PyObject, then passes to
`PLy_cursor_plan` which does `plan = (PLyPlanObject *) ob`
(`:185`). The first field read is `plan->nargs` (`:187`) and the next
is `plan->plan` for `SPI_cursor_open` (`:277`). Object layouts after
`PyObject_HEAD` differ per type, so a malicious or buggy caller
passing e.g. a `PLyResultObject` instead of a `PLyPlanObject` would
read whichever field happens to live at the `nargs` offset, then
hand whatever's at the `plan` offset to `SPI_cursor_open`. That's
not a stable crash; it's a memory-read-confusion path. Likely
exploitable for crash; less clear for info disclosure.

Compare to `PLy_spi_execute` (`plpy_spi.c:164-166`) which explicitly
guards with `is_PLyPlanObject` before delegating. The asymmetry is
suspect.

### `PLy_cursor_query` — text form (`:95-161`)

1. `PyObject_New(PLyCursorObject, PLy_CursorType)` (`:104`).
2. Create `mcxt` in `TopMemoryContext` (`:112-114`). **Top-level
   ownership is intentional**: the cursor outlives the subtransaction
   used to create it.
3. `PLy_input_setup_func(&cursor->result, mcxt, RECORDOID, -1,
   curr_proc)` (`:117-119`).
4. Inside subxact: `pg_verifymbstr(query, ...)` (`:131`),
   `SPI_prepare(query, 0, NULL)` (`:133`), `SPI_cursor_open(NULL,
   plan, NULL, NULL, fn_readonly)` (`:138`),
   `SPI_freeplan(plan)` (`:140`), `cursor->portalname =
   MemoryContextStrdup(mcxt, portal->name)` (`:146`), `PinPortal`
   (`:148`). All-or-nothing within the subxact.

`SPI_prepare` with `nargs=0` and `argtypes=NULL` means the query is
**parameterless**. The text version of cursor cannot bind args. To
parameterize, use `plan.cursor(args)`.

### `PLy_cursor_plan` — plan form (`:163-301`)

Same shape as query path, plus arg conversion:

1. Validate `args` is a non-string sequence (`:175-179`).
2. Compare `nargs != plan->nargs` → TypeError with stringified args
   (`:187-203`). Identical pattern to `PLy_spi_execute_plan`.
3. Inside subxact: build `tmpcontext` in
   `CurTransactionContext` (`:239-241`) for the converted values.
4. Per-arg: `PySequence_GetItem(args, j)` then `PLy_output_convert`
   (`:255-273`), wrapped in `PG_TRY(2) / PG_FINALLY(2)` (a nested PG_TRY
   level) to guarantee `Py_DECREF(elem)`.
5. `SPI_cursor_open(NULL, plan->plan, values, nulls, fn_readonly)`
   (`:277-278`).
6. `MemoryContextDelete(tmpcontext)` (`:287`).

### `PLy_cursor_iternext` — `for row in cursor` (`:335-395`)

- Rejects on closed cursor and on portal-vanished (subxact aborted)
  (`:347-359`).
- Each `next()` is `SPI_cursor_fetch(portal, true, 1)` (`:368`).
  Returns `PyExc_StopIteration` when SPI_processed == 0 (`:369-373`).
- For each row, calls `PLy_input_setup_tuple` to refresh the tupdesc
  (handles SET search_path or schema changes between fetches) then
  `PLy_input_from_tuple` (`:376-380`).
- `SPI_freetuptable(SPI_tuptable)` runs unconditionally in the success
  branch (`:383`). The PG_CATCH leg just unwinds the subxact (`:387-391`).

### `PLy_cursor_fetch` — batch fetch (`:397-496`)

- Rejects on closed / aborted-subxact same as iter (`:413-425`).
- Allocates a fresh `PLyResultObject` (`:427-429`).
- `SPI_cursor_fetch(portal, true, count)` (`:438`).
- Sets `ret->status = PyLong_FromLong(SPI_OK_FETCH)`, `ret->nrows =
  PyLong_FromUnsignedLongLong(SPI_processed)`.
- **`SPI_processed > PY_SSIZE_T_MAX` → ereport
  ERRCODE_PROGRAM_LIMIT_EXCEEDED** "query result has too many rows to
  fit in a Python list" (`:455-458`). The PyList API is bounded by
  `Py_ssize_t`.
- Allocates `PyList_New(SPI_processed)`, fills row-by-row via
  `PLy_input_from_tuple` (`:472-480`).

### `PLy_cursor_close` (`:498-520`)

If not already closed: `GetPortalByName`, validate, `UnpinPortal +
SPI_cursor_close`. If portal is gone (subxact aborted): raise
ValueError "closing a cursor in an aborted subtransaction".

### Dealloc (`:303-333`) — auto-close

If the user lets a cursor go out of scope without `close()`, dealloc
runs `GetPortalByName` and **silently** closes if the portal still
exists. If the portal is gone, no error — quietly skipped. This is
the GC-friendly path.

## Type-confusion / value-conversion surface

- **`PLy_cursor` text path is parameterless** — `SPI_prepare(query, 0,
  NULL)`. Any user-controlled value must be `quote_*`'d into the text
  manually. Same injection posture as `plpy.execute(text)`.
- **`PLy_cursor_plan` does not validate plan type** before cast — see
  the ISSUE block above.
- **Cursor lifetime across (sub)transactions:** the `mcxt` lives in
  `TopMemoryContext` (`:112-114`, `:213-215`), but the **portal** is
  pinned only within the SPI subxact stack. If a subxact aborts
  underneath the cursor, the portal goes away; the next access raises
  the "iterating a cursor in an aborted subtransaction" ValueError
  (`:355-358`, `:421-424`, `:509-510`). The cursor itself isn't
  invalidated — `closed` stays false, the Python object is still
  alive, but every method fails until close. **The cursor can leak
  past a Python try/except**: a user catches the ValueError, but the
  underlying mcxt is never freed until the Python object is GC'd.
  Eventually dealloc runs and frees mcxt; meanwhile the portal name
  is stale.
- **Cursor across `commit()`/`rollback()` in procedures:** explicit
  Python-side `commit()` invalidates portals not opened with
  `WITH HOLD` (which plpython doesn't use). So a cursor opened in a
  procedure that does `plpy.commit()` mid-way will start raising
  "iterating a cursor in an aborted subtransaction" — slightly
  misleading error wording (commit, not abort).
  **[ISSUE-documentation: cursor-after-commit error message says
  "aborted subtransaction" even for explicit commit (nit)]**.
- **`PySequence_GetItem` in the per-arg conversion loop** (`:260`)
  inside a `PG_TRY(2)` ensures Py_DECREF on the elem even if
  `PLy_output_convert` longjmps. Carefully written — the nested
  PG_TRY level is exactly to avoid the standard PG_TRY/PG_FINALLY
  reentrancy footgun.
- **Result-tuple conversion via RECORDOID** means **`include_generated
  = true`** is passed in both iternext (`:380`) and fetch (`:476`).
  Generated columns ARE included in cursor results. This matches
  `PLy_input_from_tuple`'s explicit `include_generated` flag in
  `plpy_typeio.c:134`.

### Cursor leak / GC surface

- A cursor opened inside a `plpy.subtransaction()` block that exits
  without close gets its portal cleaned up by the subxact rollback
  (portal removal is automatic), then dealloc later runs `GetPortalByName`
  which returns NULL, the `PortalIsValid` check skips the close, and
  `MemoryContextDelete(mcxt)` releases the cursor's mcxt. No leak.
- A cursor opened *outside* any subxact, never closed, never GC'd:
  the portal lives until the function/procedure ends; the mcxt
  releases only when Python deallocs the object. **In a long-running
  procedure with many `plpy.cursor()` calls and reference cycles
  preventing GC, portals could accumulate.** Bounded by
  `max_portals`/`max_locks_per_transaction`-style limits, so it's a
  resource-leak class issue, not memory-unsafe.

## Cross-references

- **Siblings (A10):**
  - `plpy_plpymodule` — `PLy_cursor` and `plpy.cursor` registered
    here; `PLy_cursor_init_type` from `PyInit_plpy`.
  - `plpy_planobject` — `PLy_plan_cursor` is a thin wrapper that
    calls into `PLy_cursor_plan` here.
  - `plpy_resultobject` — `PLy_cursor_fetch` constructs and returns
    one of these.
  - `plpy_typeio` — `PLy_input_setup_func` for RECORDOID-typed
    `cursor->result`; `PLy_input_setup_tuple` per fetch;
    `PLy_input_from_tuple` per row.
- **Sibling other-A10:**
  - `plpy_spi.c` — `PLy_spi_subtransaction_begin/commit/abort` is the
    transactional envelope around every SPI call here.
  - `plpy_main.c` — `PLy_current_execution_context()` provides the
    `curr_proc` and `fn_readonly`.
- **Backend dependencies:**
  - `executor/spi.c` — `SPI_prepare`, `SPI_cursor_open`,
    `SPI_cursor_fetch`, `SPI_cursor_close`, `SPI_freeplan`,
    `SPI_freetuptable`, `SPI_processed`.
  - `utils/mmgr/portalmem.c` — `GetPortalByName`, `PortalIsValid`,
    `PinPortal`, `UnpinPortal`.

<!-- issues:auto:begin -->
- [Issue register — `plpython`](../../../../issues/plpython.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-correctness: `PLy_cursor_plan` casts `ob` to
  `PLyPlanObject*` without `is_PLyPlanObject(ob)` check; reachable from
  `PLy_cursor` `"O|O"` fallback (likely)] —
  `plpy_cursorobject.c:88-89, :185`. Compare to `PLy_spi_execute`'s
  explicit guard at `plpy_spi.c:165`. Either reachable or already
  blocked by Python-side dispatch I'm missing — but the explicit
  check would be clearly safer.
- [ISSUE-documentation: cursor-after-commit yields "aborted
  subtransaction" error wording (nit)] — `plpy_cursorobject.c:357,
  423, 510`. Misleading because explicit `plpy.commit()` is the
  common cause, not abort.
- [ISSUE-defense-in-depth: text-form `plpy.cursor(text)` cannot
  parameterize args; user must `quote_*` or use plan form (by-design,
  documentation)] — `plpy_cursorobject.c:133`. Same posture as
  `plpy.execute(text)`. Compare A9 plpgsql `exec_stmt_dynexecute`.
- [ISSUE-defense-in-depth: cursor portals are not `WITH HOLD`; survive
  subxact rollback only by name-based detection, not by holdability
  (by-design)] — Discussed in the type-confusion section. Affects
  procedure code that mixes `plpy.commit()` with open cursors.
- [ISSUE-memory: cursor mcxt is allocated under `TopMemoryContext`
  (`:112-114`, `:213-215`); released only when the Python object
  deallocs. Reference cycles in user code can delay release until
  Python GC runs (nit)] — bounded by Python lifetime, not a leak in
  the strict sense.
- [ISSUE-error-handling: `PLy_cursor_query` calls
  `SPI_prepare(query, 0, NULL)` and then `SPI_freeplan(plan)` *after*
  `SPI_cursor_open` (`:138-140`). If `SPI_cursor_open` longjmps, the
  freeplan never runs (nit)] — the subxact abort cleans the SPI
  state, so this is harmless in practice but the code shape is
  unusual.
