# plpy_planobject

Covers `source/src/pl/plpython/plpy_planobject.c` (151 LOC) and
`source/src/pl/plpython/plpy_planobject.h` (26 LOC).

Pinned to source `4b0bf0788b0`.

## One-line summary

`PLyPlan` — the Python type returned by `plpy.prepare(...)`. Wraps an
`SPIPlanPtr` plus the per-arg `PLyObToDatum` conversion records and
exposes three Python methods: `execute(args, [limit])`,
`cursor([args])`, `status()`.

## Public API

### Struct layout (`plpy_planobject.h:12-20`)

```
PLyPlanObject {
    PyObject_HEAD
    SPIPlanPtr     plan;     /* SPI prepared plan, SPI_keepplan'd */
    int            nargs;    /* arg count from plpy.prepare */
    Oid           *types;    /* per-arg target OIDs */
    PLyObToDatum  *args;     /* per-arg conversion records */
    MemoryContext  mcxt;     /* owns types/args/plan; deleted in dealloc */
}
```

### C entry points

| C symbol | Purpose | Cite |
|---|---|---|
| `PLy_plan_init_type(void)` | Register PyTypeObject via `PyType_FromSpec`. Called once from `PyInit_plpy`. | `plpy_planobject.c:55-61` |
| `PLy_plan_new(void)` | Allocate an empty `PLyPlanObject` with all fields zero/NULL. | `:63-82` |
| `is_PLyPlanObject(PyObject*)` | Type-tag check via `ob->ob_type == PLy_PlanType`. | `:84-88` |

### Python-visible methods (`PLy_plan_methods`, `:22-27`)

| Python method | C function | Delegates to | Cite |
|---|---|---|---|
| `execute(args, [limit])` | `PLy_plan_execute` | `PLy_spi_execute_plan` in `plpy_spi.c` | `:128-138` |
| `cursor([args])` | `PLy_plan_cursor` | `PLy_cursor_plan` in `plpy_cursorobject.c` | `:116-125` |
| `status()` | `PLy_plan_status` | Just returns `Py_True` (TODO note inline) | `:141-151` |

### PyType slots (`PLyPlan_slots`, `:29-43`)

Only `Py_tp_dealloc`, `Py_tp_doc`, `Py_tp_methods`. **No `Py_tp_str`,
no `Py_tp_repr`, no map / sequence protocols** — it's a pure handle
object.

## Key invariants

- **`mcxt` owns everything.** `PLy_plan_new` leaves `mcxt = NULL`
  (`:79`); `PLy_spi_prepare` then creates it as
  `AllocSetContextCreate(TopMemoryContext, "PL/Python plan context",
  ALLOCSET_DEFAULT_SIZES)` (`plpy_spi.c:61-63`). `types[]` and
  `args[]` are palloc'd inside that context.
- **`plan` is `SPI_keepplan`'d** into TopMemoryContext-ish lifetime
  (`plpy_spi.c:128-129`). Dealloc must call `SPI_freeplan` (`:99`)
  before deleting the mcxt — order matters because `SPI_freeplan`
  manipulates its own catcache state.
- **`is_PLyPlanObject` is the type-tag guard** for `PLy_spi_execute`
  to detect "is this the plan form or the text form?" — see
  `plpy_spi.c:164-166`. Type-confusion here would let the user pass
  arbitrary Python objects in place of a plan; the guard catches it.
- **`nargs` is fixed at prepare time** — `args[]` and `types[]` are
  sized at `plpy.prepare` and never resized. The plan's bound SQL is
  fixed; only the values supplied to `execute(args)` vary.

## Notable internals

### Dealloc order (`PLy_plan_dealloc`, `:90-113`)

```
1. SPI_freeplan(self->plan)        if plan != NULL
2. MemoryContextDelete(self->mcxt) if mcxt != NULL
3. PyObject_Free(self)
4. (Py 3.8+) Py_DECREF(tp)
```

The SPI_freeplan-before-mcxt-delete order matters: `args[]` lives in
mcxt, but the plan itself was moved to its own SPI-managed context by
`SPI_keepplan`. Freeing the plan first lets SPI release its own catcache
references; freeing the mcxt then releases the conversion records.

### `PLy_plan_status` is a stub (`:141-151`)

The body is literally:

```
if (PyArg_ParseTuple(args, ":status"))
{
    Py_INCREF(Py_True);
    return Py_True;
    /* return PyLong_FromLong(self->status); */
}
return NULL;
```

There's no `status` field in the struct; the commented line is dead.
**The method exists as a forward-compat hook** but currently just
returns True if the user doesn't pass arguments. A user can't
distinguish a "good plan" from a "bad plan" via this; if `prepare`
returned a `PLyPlanObject`, the plan succeeded.

### `PLy_plan_execute` — delegation (`:128-138`)

```
PyArg_ParseTuple(args, "|Ol", &list, &limit)
return PLy_spi_execute_plan(self, list, limit);
```

The `|Ol` means args is optional. Note: `list` is type-checked inside
`PLy_spi_execute_plan` (`plpy_spi.c:182-188`), which rejects
`PyUnicode` (a str) explicitly because str is a sequence in Python
and would otherwise be iterated char-by-char.

### `PLy_plan_cursor` — delegation (`:116-125`)

Same shape, delegates to `PLy_cursor_plan` (in `plpy_cursorobject.c`).

## Type-confusion / value-conversion surface

- **`is_PLyPlanObject` is the only type tag.** Any C code that treats
  an arbitrary `PyObject*` as a `PLyPlanObject` must check this first.
  `PLy_spi_execute` does (`plpy_spi.c:165`); `PLy_cursor_plan` does
  *not* explicitly — it casts via `plan = (PLyPlanObject *) ob`
  (`plpy_cursorobject.c:185`). But the upstream caller is
  `PLy_plan_cursor` which is bound to `PLy_PlanType` via PyType
  dispatch, so `self` is guaranteed to be a `PLyPlanObject`. **Public
  reentry via `plpy.cursor(plan, args)` goes through `PLy_cursor`**
  which fall-through-attempts `"s"` parse first and then `"O|O"` parse
  — the `"O"` form does not validate; trying to pass a non-plan
  PyObject ends up in `PLy_cursor_plan` with `(PLyPlanObject *)` cast.
  **[ISSUE-correctness: `PLy_cursor` second branch accepts any
  PyObject as the "plan", no `is_PLyPlanObject` check before cast
  (likely)]** — see `plpy_cursorobject.c:88-89`. Result: a user can
  call `plpy.cursor(SomeOtherObject, args)` and the field reads on
  `plan->nargs`, `plan->plan` will dereference whatever's at those
  offsets in the foreign object. PyObject_New layouts guarantee
  `ob_refcnt`/`ob_type` at the start; everything after is per-type.
  Worth confirming whether `PLy_cursor_plan` adds the check.
- **`plan.execute(args)` validates arg-count match.** Inside
  `PLy_spi_execute_plan` (`plpy_spi.c:196-212`), `nargs != plan->nargs`
  → TypeError with the supplied args stringified into the message.
  So a mismatched-length sequence is rejected before any conversion
  runs.
- **Plan args run through the same `PLy_output_convert` path** as
  scalar returns (per-arg `PLyObToDatum` populated by
  `PLy_output_setup_func` in `plpy.prepare`). All the type-confusion
  notes from `plpy_typeio.md` apply equally to plan execution.
- **`status()` always succeeds** — no observable "this plan is bad"
  state from Python. A bad prepare raised at prepare time.

## Cross-references

- **Siblings (A10):**
  - `plpy_plpymodule` — `PLy_plan_init_type` called from `PyInit_plpy`;
    `plpy.prepare` (entry registered there) returns a `PLyPlanObject`.
  - `plpy_cursorobject` — `PLy_plan_cursor` → `PLy_cursor_plan`.
  - `plpy_typeio` — `PLyObToDatum` per-arg records, set up by
    `PLy_output_setup_func`.
- **Sibling other-A10:**
  - `plpy_spi.c` — `PLy_spi_prepare` (the constructor),
    `PLy_spi_execute_plan` (`plan.execute` body),
    `PLy_spi_subtransaction_begin/commit/abort` (wraps SPI calls).
- **Backend dependencies:**
  - `executor/spi.c` — `SPI_prepare`, `SPI_keepplan`, `SPI_freeplan`,
    `SPI_execute_plan`.
  - `utils/cache/typcache.c` — via `parseTypeString` resolving the
    declared arg types.
  - `parser/parse_type.c` — `parseTypeString` for the types[] list.

## Issues spotted

- [ISSUE-correctness: `PLy_cursor` text-vs-plan fallthrough at
  `plpy_cursorobject.c:88` accepts any PyObject as a "plan" without
  `is_PLyPlanObject` check before casting (likely)] — see the
  cursorobject doc for the matching note. May be safe because
  `PLy_cursor_plan` accesses fields that would segfault on a wrong
  type, but the type check should be explicit.
- [ISSUE-api-shape: `PLy_plan_status` is a no-op stub returning
  `Py_True` (nit, documentation)] — `plpy_planobject.c:141-151`. The
  commented-out `self->status` line suggests this was once richer;
  worth either deleting the dead code or wiring the field through.
- [ISSUE-defense-in-depth: no `Py_tp_str` / `Py_tp_repr` — `repr(plan)`
  yields the generic `<PLyPlan object at 0x…>` (nit)] —
  diagnostics-only; a custom repr printing the SQL text + arg types
  would help debugging. (Not exposed: information disclosure tradeoff
  is debatable.)
