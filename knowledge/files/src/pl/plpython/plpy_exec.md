# plpy_exec

Covers `source/src/pl/plpython/plpy_exec.c` (1161 LOC) and `source/src/pl/plpython/plpy_exec.h` (14 LOC).

Source pin: `4b0bf0788b0`.

## One-line summary

Per-call execution machinery: builds Python arguments from PG `FunctionCallInfo`, calls `PyEval_EvalCode` on the cached function bytecode, coerces the result back to a Datum, and handles three call shapes (plain function/SRF, row-level trigger, event trigger) plus the recursive-call argument-stack discipline.

## Public API / entry points

| Symbol | Where | Purpose |
|---|---|---|
| `PLy_exec_function(fcinfo, proc)` | `plpy_exec.c:53-307` | Plain & SRF execution. Pushes recursive args, builds `args` list, evaluates code, iterates SRF, coerces output. |
| `PLy_exec_trigger(fcinfo, proc)` | `plpy_exec.c:320-430` | Row-level trigger: builds `TD` dict (relid/table_name/event/when/level/new/old/args), evaluates, decodes None/SKIP/MODIFY/OK return. |
| `PLy_exec_event_trigger(fcinfo, proc)` | `plpy_exec.c:435-471` | Event trigger: builds `TD` with `event` and `tag`, evaluates, no return value. |

Internal helpers (static):

| Symbol | Where | Purpose |
|---|---|---|
| `PLy_function_build_args` | `plpy_exec.c:475-527` | Convert PG `Datum`s to Python objects via `PLy_input_convert`; install in `proc->globals` by name and as ordered `args` list. |
| `PLy_function_save_args` / `restore_args` / `drop_args` | `plpy_exec.c:538-641` | Save/restore the `args`/`TD`/named-arg slots in `proc->globals` across recursive calls and across SRF iterator boundaries. |
| `PLy_global_args_push` / `pop` | `plpy_exec.c:654-714` | Maintain `proc->argstack` for recursive calls. |
| `PLy_trigger_build_args` | `plpy_exec.c:746-957` | Build the `TD` dict with all trigger context fields. |
| `PLy_modify_tuple` | `plpy_exec.c:963-1090` | Apply changes from `TD["new"]` dict back into a `HeapTuple` after a MODIFY return. |
| `PLy_procedure_call` | `plpy_exec.c:1103-1132` | The one-line `PyEval_EvalCode` invocation; wrapped in PG_TRY/PG_FINALLY to abort lingering plpy subtransactions. |
| `PLy_abort_open_subtransactions` | `plpy_exec.c:1138-1161` | If the user opened `plpy.subtransaction()` blocks and never closed them, force-rollback at exit with a WARNING. |

## Key invariants

- **`proc->calldepth` and `proc->argstack` are kept consistent across PG_TRY.** Comment at `:646-651`: "callers must ensure that PLy_global_args_pop gets invoked once, and only once, per successful completion of PLy_global_args_push. Otherwise we'll end up out-of-sync between the actual call stack and the contents of proc->argstack." Both functions are designed to not throw error after they've mutated `calldepth` or `argstack` [verified-by-code: `:665-672, :683-714`].
- **SRF iterator state is bound to `funcctx->multi_call_memory_ctx` via `MemoryContextRegisterResetCallback`.** If the SRF caller doesn't iterate to completion (e.g. `LIMIT 5` on a `SELECT * FROM srf()`), the callback `plpython_srf_cleanup_callback` fires when the multi-call context is reset, releasing the Python iterator refcount and any saved args [verified-by-code: `:83-87, :721-733`]. This is the elegant solution to "what if PG abandons our iterator mid-stream."
- **Trigger return must be None, "OK", "SKIP", or "MODIFY".** Any other string raises `ERRCODE_DATA_EXCEPTION` [verified-by-code: `:382-418`]. `MODIFY` on DELETE just emits a WARNING and ignores (the trigger row can't be modified for a DELETE) [verified-by-code: `:404-407`].
- **`PLy_modify_tuple` rejects generated columns and system attributes.** `attgenerated` → `ERRCODE_E_R_I_E_TRIGGER_PROTOCOL_VIOLATED` ("cannot set generated column"); attn ≤ 0 → `ERRCODE_FEATURE_NOT_SUPPORTED` ("cannot set system attribute"); unknown name → `ERRCODE_UNDEFINED_COLUMN` ("key not found") [verified-by-code: `:1027-1041`].
- **Subtransaction-cleanup runs in PG_FINALLY.** `PLy_procedure_call` records `save_subxact_level = list_length(explicit_subtransactions)` before `PyEval_EvalCode`, then `PLy_abort_open_subtransactions(save_subxact_level)` in PG_FINALLY [verified-by-code: `:1106-1125`]. This is what enforces "Python code that opens `plpy.subtransaction()` without `__exit__` gets force-rolled-back when control returns to PG." The comment at `:1115-1119` is explicit: "Since plpy will only let you close subtransactions that you started, you cannot *unnest* subtransactions, only *nest* them without closing." There's an `Assert(list_length(explicit_subtransactions) >= save_subxact_level)` to enforce this monotonicity.
- **SETOF-function null is special.** When `plrv == Py_None && srfstate->iter == NULL` (end of iteration), the result is `(Datum) 0` with `fcinfo->isnull = true` — but NOT passed through the type's input function. The comment at `:223-227` explains: "the iteration-ending null isn't a real value; don't pass it through the input function, which might complain."

## Notable internals

### Three call shapes, one handler dispatch

`plpython3_call_handler` (plpy_main.c) routes to one of three subhandlers based on `CALLED_AS_TRIGGER` / `CALLED_AS_EVENT_TRIGGER`. The subhandlers diverge in three ways:
1. **Argument construction**: `PLy_function_build_args` (list+named globals) vs `PLy_trigger_build_args` (TD dict for row trigger) vs ad-hoc TD dict for event trigger.
2. **Kwarg name**: `PyEval_EvalCode` is called with one of `"args"`, `"TD"`, `"TD"` as the `kargs` slot [verified-by-code: :103, :369, :461].
3. **Return decoding**: function uses `PLy_output_convert`; row trigger checks for `None`/`OK`/`SKIP`/`MODIFY` strings and may call `PLy_modify_tuple`; event trigger discards the return.

### SRF state machine

For a SETOF function:
1. **First call (`SRF_IS_FIRSTCALL`)**: alloc `PLySRFState` in `funcctx->multi_call_memory_ctx`, register cleanup callback, store in `funcctx->user_fctx`.
2. **First call body**: build args, `PyEval_EvalCode` to get the user function's return (expected to be an iterable), `PyObject_GetIter`. Verify caller supports `SFRM_ValuePerCall`.
3. **Each subsequent call (`SRF_PERCALL_SETUP`)**: restore saved args (`PLy_function_restore_args`), `PyIter_Next(srfstate->iter)` to fetch the next item.
4. **When iter exhausted**: `Py_None` is the result and `srfstate->iter` is NULL'd → next path through `PLy_exec_function` returns `SRF_RETURN_DONE`.

The saved-args dance (`:179-181`) exists because Python iterators might inspect their args via the `args` globals dict — and the user could call the same SRF recursively from another spot, overwriting `args`. Saving and restoring the dict slot per-call makes interleaved SRF calls safe.

### Recursive-call argument stack

Same function, called recursively:
1. Outer call: `calldepth=1`, `argstack=NULL`.
2. Outer call invokes itself → `PLy_global_args_push` saves outer's `args`/`TD`/named-args onto `proc->argstack`, increments `calldepth` to 2.
3. Inner call: `PLy_function_build_args` overwrites the same `proc->globals` slots with the inner's values.
4. Inner returns → `PLy_global_args_pop` restores outer's args from `argstack[0]`, decrements `calldepth`.

The comment at `:707-713` explains that exiting depth-1 no longer deletes the named-arg dict entries (a "pointless" optimization that was removed): "nothing can see the dict until the function is called again, at which time we'll overwrite those dict entries."

### `PLy_function_build_args`: PyList_New OUTSIDE PG_TRY

The list is allocated `PyList_New(proc->nargs)` BEFORE `PG_TRY` so a failure can be returned cleanly without unwinding [verified-by-code: `:483-489`, from-comment: `:482-485`]. The PG_CATCH at `:517-523` only handles errors from the per-arg `PLy_input_convert` loop. This is the canonical "alloc-then-PG_TRY" idiom in plpython.

### Trigger TD dict construction

`PLy_trigger_build_args` produces a Python dict with keys:
- `"name"` — `tg_trigger->tgname`.
- `"relid"` — OID as decimal string.
- `"table_name"` — unqualified name.
- `"table_schema"` — schema name.
- `"when"` — "BEFORE" / "AFTER" / "INSTEAD OF".
- `"level"` — "ROW" / "STATEMENT".
- `"event"` — "INSERT" / "UPDATE" / "DELETE" / "TRUNCATE".
- `"new"`, `"old"` — input tuples as Python dicts (or `None` for STATEMENT-level / wrong-event).
- `"args"` — list of `tg_trigger->tgargs` strings, or `None`.

For BEFORE row triggers, generated columns are NOT computed yet, so `PLy_input_from_tuple` is called with `include_generated=false` (the `!TRIGGER_FIRED_BEFORE(tdata->tg_event)` argument) [verified-by-code: `:844-845, :869-870`]. The comment at `:832-835` is explicit.

### `PLy_modify_tuple` validation chain

For each key in `TD["new"]`:
1. Key must be a `str` (PyUnicode_Check) — else `ERRCODE_DATATYPE_MISMATCH` "dictionary key at ordinal position N is not a string".
2. Name must resolve via `SPI_fnumber` — else `ERRCODE_UNDEFINED_COLUMN` "key not found as column".
3. `attn` must be > 0 — else `ERRCODE_FEATURE_NOT_SUPPORTED` "cannot set system attribute".
4. `attgenerated` must be false — else `ERRCODE_E_R_I_E_TRIGGER_PROTOCOL_VIOLATED` "cannot set generated column".
5. Value goes through `PLy_output_convert` with the cached per-column `PLyObToDatum`.

If `PyDict_GetItem(plntup, platt)` returns NULL after a successful `PyDict_Keys` enumeration, it's a `FATAL` "Python interpreter is probably corrupted" — Python invariant violation [verified-by-code: `:1043-1045`].

### `plpython_return_error_callback`

`errcontext("while creating return value")` — wraps any ereport during output coercion (`PLy_output_convert`). Registered just before the output conversion block, popped via `error_context_stack = plerrcontext.previous` at the end [verified-by-code: `:193-195, :283`]. Note: NOT popped in PG_CATCH because PG_CATCH unwinds the error_context_stack as part of PG_RE_THROW.

## Trust posture

N/A at this layer — execution machinery is identical for trusted/untrusted, and plpython has only the untrusted variant. See `plpython.h.md` and `plpy_main.md`.

One trust-relevant subtlety in `PLy_trigger_build_args`: the trigger dict exposes `tg_trigger->tgargs` (CREATE TRIGGER's literal arguments) verbatim into Python [verified-by-code: `:931-940`]. These come from the catalog (`pg_trigger.tgargs`) and are set by the trigger creator, which requires `CREATE` privilege on the table — not by the row's owner. So a SECURITY DEFINER plpython trigger created by a privileged user sees the trigger args set by that creator, never tampered by the SQL-level invoker. No injection vector here. [inferred from `:931-940` and standard PG trigger semantics.]

## Cross-references

- `plpy_main.md` — call-handler that dispatches into these three subhandlers.
- `plpy_procedure.md` — `PLyProcedure` struct definition; `proc->code`, `proc->globals`, `proc->argstack` are populated here.
- `plpy_typeio.c` (sibling sweep) — `PLy_input_convert`, `PLy_output_convert`, `PLy_input_from_tuple`, `PLy_output_setup_*` are defined there.
- `plpy_subxactobject.c` (sibling sweep) — `explicit_subtransactions` global walked by `PLy_abort_open_subtransactions`.
- `plpy_elog.md` — `PLy_elog(ERROR, ...)` is called from many failure sites here.
- A9 plpgsql `pl_exec.c` comparison: plpgsql's `exec_stmt_block` and friends are 5000+ LOC because plpgsql interprets bytecode directly; plpy_exec is ~1200 LOC because Python's interpreter does the heavy lifting and plpython just shuffles args. The complexity here is in the *boundaries* (PG↔Python type coercion, refcount discipline, recursive-args stack), not in the language semantics.
- A10-1 plperl comparison: plperl's `plperl_call_perl_func` does the analogous `args` setup as `@_`, the trigger TD setup as a `%TD` hash. plpython's TD as a Python `dict` is conceptually identical.

<!-- issues:auto:begin -->
- [Issue register — `plpython`](../../../../issues/plpython.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-correctness: NEW row in BEFORE trigger hides generated columns, but MODIFY rebuild via PLy_modify_tuple could resurface them (likely)] — `PLy_input_from_tuple(..., !TRIGGER_FIRED_BEFORE(...))` omits generated columns from `TD["new"]` in BEFORE triggers [verified-by-code: `:844-845`]. But `PLy_modify_tuple` only rejects writes to generated columns, not reads — and the heap_modify_tuple at `:1061` passes the OLD tuple as the base. If a user adds a `"gencol": x` key to `TD["new"]`, they get the "cannot set generated column" error correctly. But if they DON'T add it and the underlying OLD tuple has stale generated values, those flow through unchanged. This is correct heap-modify behavior, but the asymmetry between "hidden from NEW dict" and "preserved from OLD tuple" deserves a corpus note.

- [ISSUE-error-handling: SRF cleanup callback fires on memory context reset, but doesn't have access to Python exception state (maybe)] — `plpython_srf_cleanup_callback` at `:721-733` is called when `multi_call_memory_ctx` is reset. It DECREFs `iter` and drops saved args. But if the Python iterator's `__del__` raises a Python exception during the DECREF, that exception is silently discarded — there's no `PyErr_Clear` or `PLy_elog` call here. Probably fine because the callback runs in PG cleanup paths where the backend is already error-handling, but iterator destructors with side effects (e.g. closing a file) could fail silently.

- [ISSUE-security: trigger sees `tg_args` from catalog without any escaping (nit)] — `PLyUnicode_FromString(tdata->tg_trigger->tgargs[i])` at `:933`. `tgargs[i]` is a NUL-terminated C string from the catalog. If the trigger args contain a UTF-8 invalid sequence, `PLyUnicode_FromString` would error. Not a security issue (the trigger creator controls the args), but a robustness note: malformed catalog data would cause trigger fires to fail with a confusing error.

- [ISSUE-memory: PLySavedArgs FLEXIBLE_ARRAY_MEMBER allocation uses offsetof+nargs*sizeof (nit)] — `MemoryContextAllocZero(proc->mcxt, offsetof(PLySavedArgs, namedargs) + proc->nargs * sizeof(PyObject *))` at `:545-547`. This is the standard flexible-array idiom and is correct. But if `proc->nargs` is 0, this still allocates the offsetof header without the array — fine, but `result->nargs = proc->nargs = 0` means the `for (i = 0; i < result->nargs; ...)` loops are no-ops. No bug; documenting the edge case for completeness.

- [ISSUE-concurrency: SRF iterator persistence across PyEval_EvalCode in same backend (likely)] — `srfstate->iter` is a `PyObject *` rooted in `multi_call_memory_ctx`. While the SRF is mid-iteration, other plpython functions on the same backend (called via plpy.execute from a different SQL statement) share the same Python interpreter. If function B is called between two `SRF_PERCALL` invocations of function A, B's `PyEval_EvalCode` runs in the same interpreter as A's iterator. The iterator's `__next__` evaluation in A's continuation will see ANY global state B mutated. This is documented behavior (the Python interpreter is shared), but it means SRFs that depend on mutable globals can be corrupted by interleaved calls. Defense: write SRFs to not depend on `__main__` globals other than `args`/`SD`/`GD`.

- [ISSUE-audit-gap: plpython_return_error_callback uses PLy_current_execution_context which can elog(ERROR) (maybe)] — At `:735-743`, `plpython_return_error_callback` calls `PLy_current_execution_context()` which `elog(ERROR, ...)` if no plpython is executing. But this callback is registered while a plpython IS executing, so the path is unreachable in practice — except if a corrupted error_context_stack invokes the callback after the exec_ctx has been popped. The error_context_stack discipline is symmetric with PG_TRY so this is safe by construction; flagging as audit-gap for any future refactor that moves the pop earlier.

- [ISSUE-correctness: `SPI_finish() != SPI_OK_FINISH` always elog(ERROR), but SPI_OK_FINISH is the only success code (nit)] — At `:190-191, :376-377, :463-464`, every SPI_finish is wrapped in `if (... != SPI_OK_FINISH) elog(ERROR, "SPI_finish failed")`. Fine, but `SPI_finish()` only returns `SPI_OK_FINISH` or `SPI_ERROR_UNCONNECTED`. The error message is identical for both, which loses a useful distinction (unconnected = caller bug; other = SPI internal). Trivial nit.

## Synthesized by
<!-- backlinks:auto -->
- [idioms/fmgr.md](../../../../idioms/fmgr.md)
