# plpy_subxactobject (plpy_subxactobject.c + plpy_subxactobject.h)

Covers `source/src/pl/plpython/plpy_subxactobject.c` (196 LOC) and `source/src/pl/plpython/plpy_subxactobject.h` (33 LOC).

Source pin: `4b0bf0788b0`.

## One-line summary

Implements `PLySubtransactionObject` — the Python type that backs `with plpy.subtransaction():`. `__enter__` calls `BeginInternalSubTransaction`, `__exit__` commits or rolls back based on whether Python is exiting cleanly (`exc_type is None`) or unwinding an exception. Tracks the LIFO stack of explicit subtransactions in the module-global `explicit_subtransactions` list.

## Public API / entry points

Exported via `plpy_subxactobject.h`:

- `List *explicit_subtransactions` — module-global LIFO stack of `PLySubtransactionData` entries [verified-by-code: `source/src/pl/plpython/plpy_subxactobject.c:15`].
- `PLy_subtransaction_init_type(void)` — registers `PLySubtransaction` Python type spec; called once from `_PG_init` via plpy_main [verified-by-code: `source/src/pl/plpython/plpy_subxactobject.c:57-63`].
- `PLy_subtransaction_new(self, unused) -> PyObject *` — Python-facing factory; backs `plpy.subtransaction()` [verified-by-code: `source/src/pl/plpython/plpy_subxactobject.c:66-83`].

Types declared in the header:

- `PLySubtransactionObject { PyObject_HEAD; bool started; bool exited; }` — per-instance Python state [verified-by-code: `source/src/pl/plpython/plpy_subxactobject.h:16-21`].
- `PLySubtransactionData { MemoryContext oldcontext; ResourceOwner oldowner; }` — entry stored in `explicit_subtransactions`, allocated in `TopTransactionContext` [verified-by-code: `source/src/pl/plpython/plpy_subxactobject.h:24-28`].

Python-facing methods (in `PLy_subtransaction_methods` at `:24-31`):

- `__enter__` / `enter` → `PLy_subtransaction_enter` [verified-by-code: `source/src/pl/plpython/plpy_subxactobject.c:93-133`].
- `__exit__` / `exit` → `PLy_subtransaction_exit` [verified-by-code: `source/src/pl/plpython/plpy_subxactobject.c:146-196`].

## Key invariants

- **State machine: `started` and `exited` bits are one-way latches.** Re-entering an already-entered subxact raises `ValueError "this subtransaction has already been entered"` [verified-by-code: `source/src/pl/plpython/plpy_subxactobject.c:100-104`]; re-exiting raises `"this subtransaction has already been exited"` [`:106-110, 164-168`]; exiting without entering raises `"this subtransaction has not been entered"` [`:158-162`].
- **The `explicit_subtransactions` list is the source of truth for "is there a subxact to pop?"** `__exit__` cross-checks `explicit_subtransactions == NIL` and raises `"there is no subtransaction to exit from"` [verified-by-code: `source/src/pl/plpython/plpy_subxactobject.c:170-174`]. This guards against a `__exit__` being called when the subxact has already been torn down by an outer abort.
- **LIFO ordering.** `__enter__` uses `lcons` to prepend; `__exit__` uses `linitial` + `list_delete_first` to pop the head [verified-by-code: `source/src/pl/plpython/plpy_subxactobject.c:126, 188-189`]. Nested `with` blocks therefore unwind in strict LIFO, which matches PG subxact semantics.
- **List cells live in `TopTransactionContext`.** The explicit `MemoryContextSwitchTo(TopTransactionContext)` before `lcons` [verified-by-code: `source/src/pl/plpython/plpy_subxactobject.c:124-126`] guarantees the list survives any short-lived context the caller might be in. `TopTransactionContext` is dropped at top-level COMMIT/ROLLBACK, which matches when explicit subxacts must all be resolved.
- **`PLySubtransactionData` is `pfree`'d on every successful `__exit__`** [verified-by-code: `source/src/pl/plpython/plpy_subxactobject.c:193`]. Forgotten subxacts (process exits with a started, non-exited subxact) leak this struct until `TopTransactionContext` resets, which is harmless.
- **`exc_type is None` ⇒ commit; anything else ⇒ rollback.** [verified-by-code: `source/src/pl/plpython/plpy_subxactobject.c:178-186`]. Python's context-manager protocol guarantees that `exc_type` is None iff the `with` block exited normally. If the user `try/except`s inside the `with`, exits normally, the subxact commits — even though an exception was raised and handled internally. This matches plpgsql's "exception handler commits the inner block" semantics.
- **Bool-as-Oid padding-elimination trick is NOT used here** (that's the pltcl proc_key trick). `PLySubtransactionObject` is plain `bool started; bool exited;` because it's a Python type object, not a hash key.

## Notable internals

### The `subxact.exited` latch prevents double-rollback

If `__exit__` raised before flipping `exited = true`, a `finally` block in user Python code that called `subxact.exit(*sys.exc_info())` could re-enter `__exit__`, which would call `RollbackAndReleaseCurrentSubTransaction` a second time on a subxact that no longer exists. The `exited` check at `:164-168` blocks that.

### Memory-context discipline at `__enter__`

[verified-by-code: `source/src/pl/plpython/plpy_subxactobject.c:113-129`]:

1. Save `CurrentMemoryContext` as `oldcontext`.
2. Allocate `PLySubtransactionData` directly in `TopTransactionContext` via `MemoryContextAlloc` (NOT `palloc` — different target context).
3. Stash `oldcontext` and `CurrentResourceOwner` in the data.
4. `BeginInternalSubTransaction(NULL)` — this switches `CurrentMemoryContext` to the subxact's context and `CurrentResourceOwner` to a new ResourceOwner.
5. Switch to `TopTransactionContext` for the `lcons` (list cells must outlive the subxact).
6. Switch back to `oldcontext` so the caller's Python code runs in the same memory context it was in before the `with` block.

The comment at `:128` makes the contract explicit: "Caller wants to stay in original memory context."

### `__exit__`'s ordering: release subxact BEFORE popping the list

[verified-by-code: `source/src/pl/plpython/plpy_subxactobject.c:178-193`] — `RollbackAndReleaseCurrentSubTransaction()` or `ReleaseCurrentSubTransaction()` runs first, THEN the list pop, THEN restoring `oldcontext` and `oldowner` from `subxactdata`. This is the only valid order: releasing the subxact uses internal PG state that doesn't depend on our list, and our list pop frees `subxactdata`, so we must read `oldcontext`/`oldowner` from it before `pfree`.

### Python 3.8 refcount workaround

[verified-by-code: `source/src/pl/plpython/plpy_subxactobject.c:74-77`] — `#if PY_VERSION_HEX < 0x03080000` does an extra `Py_INCREF(PLy_SubtransactionType)`. References Python issue 35810 (heap-type instances didn't INCREF their type before 3.8). The plpython3 minimum is well above 3.2 (`Py_LIMITED_API` pin) so this branch is dead in any supported configuration; kept for safety.

## Cross-references

- `source/src/backend/access/transam/xact.c` — `BeginInternalSubTransaction`, `ReleaseCurrentSubTransaction`, `RollbackAndReleaseCurrentSubTransaction`.
- `plpy_main.c` — calls `PLy_subtransaction_init_type` from `_PG_init`.
- `plpy_plpymodule.c` — wires `plpy.subtransaction` to `PLy_subtransaction_new`.
- `plpy_spi.c.md` (this sweep) — uses `PLy_spi_subtransaction_*` (lowercase, no Python type) for implicit per-SPI-call subxacts. The two systems are intentionally separate: implicit subxacts are invisible to Python; explicit subxacts via `with` give the user control.
- A9 baseline (plpgsql): `BEGIN ... EXCEPTION WHEN ... END` block in pl_exec.c. Same primitives (`BeginInternalSubTransaction` + commit/rollback) but the dispatch is on SQLSTATE match, not on Python's exception-type.
- A10-1 plperl: subxact-via-die / eval block; comparable shape.
- A10-4 pltcl (this sweep): the `subtransaction` Tcl command in pltcl.c (`pltcl_subtransaction` at `:2976`) plays the same role as plpy.subtransaction, but uses a *block of Tcl code as argument* rather than a context manager.

## Issues spotted

- **[ISSUE-correctness: Python's `try/except` inside `with` swallows exceptions; subxact COMMITS in that case (likely, by design)]** — `source/src/pl/plpython/plpy_subxactobject.c:178-186`. Different from plpgsql's `BEGIN ... EXCEPTION WHEN ... END` which always rolls back the inner block when an exception is caught. A plpython function that does `with plpy.subtransaction(): try: bad_sql() except plpy.SPIError: pass` will commit the (empty) subxact — but the user already saw the exception happen and probably expected rollback. Worth a doc note; not a bug.
- **[ISSUE-error-handling: `__enter__` does NOT wrap `BeginInternalSubTransaction` in `PG_TRY` (likely)]** — `source/src/pl/plpython/plpy_subxactobject.c:122`. If `BeginInternalSubTransaction` ereports (e.g. xact-state machine refuses; very unlikely from a function context), the longjmp unwinds through the Python C frame. The `subxactdata` allocated at `:115-117` leaks into `TopTransactionContext` (cleaned on xact-end, so bounded). The Python `subxact` object has `started=true` but no real subxact backing it — a subsequent `__exit__` will then try to release a non-existent subxact. Hard to trigger but worth flagging.
- **[ISSUE-error-handling: similarly `__exit__` does NOT wrap the `Release` / `Rollback` calls in `PG_TRY` (likely)]** — `source/src/pl/plpython/plpy_subxactobject.c:181-186`. If `RollbackAndReleaseCurrentSubTransaction` itself fails (theoretically possible — buffer pin leak, etc.), the longjmp leaves the Python `subxact` object with `exited=false`, the list entry still in place, and `subxactdata` un-freed. The catch-up happens at outer-xact teardown. Compare with `plpy_spi.c`'s `..._subtransaction_abort` which DOES wrap. The asymmetry is intentional: this is explicit user code, so any error here propagates naturally to user-visible behavior.
- **[ISSUE-audit-gap: `explicit_subtransactions` is process-wide / backend-wide, not per-function (audit-gap, nit)]** — `source/src/pl/plpython/plpy_subxactobject.c:15`. A function that spawns a `with` block, calls another plpython function (which may itself open a subxact), and unwinds, all share the same global list. Correct given LIFO discipline, but a static-analysis tool can't easily see the invariant "Python's `with` matches `BeginInternalSubTransaction` 1:1" across function boundaries.
- **[ISSUE-concurrency: not relevant — plpython runs on the single backend thread (n/a)]** — flagged for completeness. Backend per-connection fork model means no thread-safety concerns for the global list.
