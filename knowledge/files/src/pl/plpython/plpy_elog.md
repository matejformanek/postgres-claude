# plpy_elog

Covers `source/src/pl/plpython/plpy_elog.c` (618 LOC) and `source/src/pl/plpython/plpy_elog.h` (46 LOC).

Source pin: `4b0bf0788b0`.

## One-line summary

The bidirectional error bridge: turns Python exceptions into PG `ereport()`s (via `PLy_elog_impl`), turns PG `ErrorData` into structured Python exception objects with rich attributes (`PLy_exception_set_with_details`), and synthesizes Python-style tracebacks that include the user's source line (`PLy_traceback`).

## Public API / entry points

| Symbol | Where | Purpose |
|---|---|---|
| `PLy_elog(elevel, fmt, ...)` macro | `plpy_elog.h:21-35` | Wraps `PLy_elog_impl` and adds `pg_unreachable()` after ERROR-level calls so the compiler knows control doesn't return. |
| `PLy_elog_impl(elevel, fmt, ...)` | `plpy_elog.c:44-156` | The Python→PG bridge. `PyErr_Fetch` the current Python exception, classify (SPIError / Error / Fatal / other), extract structured fields, then `ereport()` with full diag fields and traceback as errcontext. |
| `PLy_exception_set(exc, fmt, ...)` | `plpy_elog.c:489-500` | Thin wrapper over `PyErr_SetString` with vsnprintf + gettext translation. Used to raise typed Python exceptions from C. |
| `PLy_exception_set_plural(...)` | `plpy_elog.c:503-518` | Plural-aware variant using `dngettext`. |
| `PLy_exception_set_with_details(excclass, edata)` | `plpy_elog.c:521-576` | PG→Python bridge: build a Python exception object, attach `sqlstate`, `detail`, `hint`, `query`, `schema_name`, `table_name`, `column_name`, `datatype_name`, `constraint_name` as attributes, then `PyErr_SetObject`. Called from plpy_spi.c when an SPI call errors. |
| `PLy_exc_error`, `PLy_exc_fatal`, `PLy_exc_spi_error` | declared `plpy_elog.h:11-13`, defined `plpy_elog.c:15-17` | The three Python exception classes injected by plpy_plpymodule.c into the `plpy` module: `plpy.Error`, `plpy.Fatal`, `plpy.SPIError`. |

## Key invariants

- **Python exception state is fetched once and released in PG_FINALLY.** `PyErr_Fetch(&exc, &val, &tb)` runs OUTSIDE the `PG_TRY` (so the refcounts are owned before any longjmp risk), and `Py_XDECREF` of all three runs in `PG_FINALLY` so they're released on both normal exit and PG ereport longjmp [verified-by-code: `plpy_elog.c:59-62, :142-154`]. This is the canonical "PyObject lifecycle straddles a longjmp" pattern in plpython.
- **SPI errors carry a `spidata` tuple, plain Errors do not.** `plpy.SPIError` instances have an attribute `spidata` that is a 10-tuple `(sqlerrcode, detail, hint, query, position, schema_name, table_name, column_name, datatype_name, constraint_name)` packed by `PLy_exception_set_with_details` via `PyArg_ParseTuple(spidata, "izzzizzzzz", ...)` [verified-by-code: `plpy_elog.c:401-405`]. Plain `plpy.Error` instances have the same fields as direct attributes, no tuple — `PLy_get_error_data` walks them via `get_string_attr` [verified-by-code: `plpy_elog.c:429-442`].
- **`PLy_exc_fatal` raised from Python upgrades elevel to FATAL.** If the user does `raise plpy.Fatal(...)`, the elevel passed to `PLy_elog_impl` is overridden to `FATAL`, which terminates the backend [verified-by-code: `plpy_elog.c:89-90`]. This is the only level-mutation in the bridge.
- **First Python traceback frame is always skipped.** The "shouldn't happen" frame at index 0 represents the synthesized wrapper `def __plpython_procedure_foo_NNN():` and would just confuse users [verified-by-code: `plpy_elog.c:270-271`]. The frame-numbering offset (`plain_lineno - 1`) compensates for the wrapper line that munge_source prepends [verified-by-code: `plpy_elog.c:294-298`].
- **Traceback walks `tb_next` via `PyObject_GetAttrString` and explicitly DECREFs.** Each call to `PyObject_GetAttrString(tb, "tb_next")` returns a new reference; the code immediately `Py_DECREF(tb)` after stepping to avoid holding the chain [verified-by-code: `plpy_elog.c:336-348`]. The comment explains: "If we tried to hold this refcount longer, it would greatly complicate cleanup in the event of a failure in the above PG_TRY block."

## Notable internals

### `PLy_elog_impl` classification cascade

When called with a live Python exception:
1. `PyErr_NormalizeException(&exc, &val, &tb)` — turn the exception class + value pair into a fully-instantiated exception object [plpy_elog.c:78].
2. Match against `PLy_exc_spi_error` → extract rich diag via `PLy_get_spi_error_data` (sqlerrcode, detail, hint, query, position, schema/table/column/datatype/constraint names) [plpy_elog.c:80-84].
3. Else match against `PLy_exc_error` → extract subset via `PLy_get_error_data` (no query, no position) [plpy_elog.c:85-88].
4. Else match against `PLy_exc_fatal` → bump elevel to FATAL [plpy_elog.c:89-90].
5. Any other Python exception type (e.g. `ValueError`, `KeyError`, `ZeroDivisionError`) → no SQL-state extraction, `ereport` falls back to `ERRCODE_EXTERNAL_ROUTINE_EXCEPTION` [verified-by-code: `plpy_elog.c:123-124`].

### Source-line attachment in tracebacks

`PLy_traceback` examines `code.co_filename`; if it equals `<string>` (the filename `Py_CompileString` was called with in `plpy_procedure.c:388`), it appends the relevant line from `proc->src` (the munged source) to the traceback string [verified-by-code: `plpy_elog.c:304-322`]. `get_source_line` walks the source by counting `\n` characters and trims leading whitespace before emitting the line. This means user tracebacks include the actual source code of the function at the failing line, mimicking standard Python `traceback.py` output.

### `PLy_exception_set_with_details` failure mode

If any of the `Py_BuildValue`/`PyObject_CallObject`/`set_string_attr` calls fail (out-of-memory, or `excclass` has a broken `__init__`), the function `goto failure` and `elog(ERROR, "could not convert error to Python exception")` [verified-by-code: `plpy_elog.c:528-575`]. This converts the *attempt to translate a PG error into a Python exception* into a fresh PG ereport — which is fine because the caller (plpy_spi.c) is inside `PG_CATCH` cleanup and is about to rethrow anyway.

### Refcount discipline

`get_string_attr` returns a borrowed C-string pointer that lives only as long as the Python wrapper object's refcount [from-comment: `plpy_elog.c:383-385`]. The comment is explicit: "the returned string values are pointers into the given PyObject. They must not be free()'d, and are not guaranteed to be valid once we stop holding a reference on the PyObject." This is the canonical reason `PLy_elog_impl` does its `ereport()` *inside* the `PG_TRY` block where `val` is still refcounted, not after `Py_XDECREF(val)` in `PG_FINALLY`. Easy bug to introduce in a refactor.

## Trust posture

N/A at this layer — error bridging is identical for trusted and untrusted plpython, and plpython has only one variant. See `plpython.h.md`.

One trust-relevant subtlety: `PLy_traceback` will include lines from `proc->src` in the errcontext, which means a SECURITY DEFINER plpython function that fails will leak its source code line to the *invoker*'s error stream [verified-by-code: `plpy_elog.c:304-322`]. This is conventional behavior for PG functions (a plpgsql function in SECURITY DEFINER mode does the same via its own error context), but worth noting.

## Cross-references

- `plpy_main.md` — handlers register `plpython_error_callback` which surrounds the errcontext that `PLy_elog_impl`'s ereport is part of.
- `plpy_exec.md` — calls `PLy_elog(ERROR, ...)` at every Python-call failure site.
- `plpy_procedure.c:388` — `Py_CompileString(msrc, "<string>", Py_file_input)` sets `co_filename` to `<string>`, which `PLy_traceback` keys on.
- `plpy_spi.c` (sibling sweep) — where `PLy_exception_set_with_details` is called: the PG→Python translation point for `plpy.execute()` failures.
- `plpy_plpymodule.c` (sibling sweep) — defines `plpy.Error`, `plpy.Fatal`, `plpy.SPIError` classes that this file's globals reference.
- A9 plpgsql comparison: plpgsql's `exec_stmt_block` handles `EXCEPTION WHEN OTHERS THEN ...` via PG_TRY/PG_CATCH around subxact boundaries; the SQLSTATE matching is exact like here, but the exception "object" is just a `SQLERRM`/`SQLSTATE` pair, no nine-field detail. plpython's exposed attributes are strictly richer.
- A10-1 plperl: builds a Perl `$_TD` hash for errors with similar fields; plpython is structurally close.

## Issues spotted

- [ISSUE-correctness: `PLy_get_sqlerrcode` only validates alpha range up to F (likely)] — At `plpy_elog.c:371-376`, the SQLSTATE validator accepts `[0-9A-Z]` for all five positions and calls `MAKE_SQLSTATE`. But PG's actual SQLSTATE encoding uses `'0'-'9'` and `'A'-'Z'` for class/subclass identifiers, with a documented subset. The validator here accepts strings like `"ZZZZZ"` which is not a real SQLSTATE; it would be encoded into the errcode field and propagate to clients as a syntactically-valid-but-unknown SQLSTATE. Not a security issue, but a place where user-supplied SQLSTATE strings can construct arbitrary 5-char identifiers in error reports.

- [ISSUE-security: SECURITY DEFINER plpython function leaks source line to invoker via traceback (maybe)] — `PLy_traceback` appends the failing source line from `proc->src` to errcontext [verified-by-code: `plpy_elog.c:316-322`]. If a SECURITY DEFINER function runs as a privileged role and fails, the invoker sees the line of code that failed — including any literal strings/constants on that line. Comparable to plpgsql but worth a corpus mention. Mitigation: write SECURITY DEFINER functions to not embed secrets in source.

- [ISSUE-error-handling: `elog(ERROR, ...)` inside the traceback walk leaks per-frame Python refs (nit)] — At `plpy_elog.c:252-268`, each `PyObject_GetAttrString` is followed by `if (X == NULL) elog(ERROR, ...)` *inside* the `PG_TRY`. The `PG_FINALLY` block at :325-332 does `Py_XDECREF` on `frame, code, name, lineno, filename`, so this is actually fine — but only because the elog happens before subsequent fetches succeed. If a future refactor moved the elog calls *after* multiple successful fetches without resetting locals, refs could leak. Currently safe.

- [ISSUE-defense-in-depth: 1024-byte fixed buffer in `PLy_exception_set` truncates messages (nit)] — Both `PLy_exception_set` and `PLy_exception_set_plural` use a `char buf[1024]` stack buffer and `vsnprintf` [verified-by-code: `plpy_elog.c:492, :508`]. Messages longer than 1023 bytes are silently truncated. PG itself has no such limit on `errmsg`. In practice, the only callers are plpy_plpymodule/plpy_spi raising typed exceptions with short messages, but a future caller that formatted a SQL statement into the message could hit this.

- [ISSUE-correctness: `PyArg_ParseTuple(spidata, "izzzizzzzz", ...)` swallows TypeError silently (maybe)] — At `plpy_elog.c:401-405`, no return-value check on `PyArg_ParseTuple`. If a user code path mutates `SPIError.spidata` to a tuple of wrong shape (e.g. `e = plpy.SPIError("..."); e.spidata = ("garbage",)` then re-raises), PyArg_ParseTuple would set a Python error and return 0, but PLy_get_spi_error_data ignores the return. Subsequent `PyErr_Occurred` checks later in PLy_elog_impl might be confused, but the immediate effect is that some output parameters are unset and `sqlerrcode` stays 0. Probably benign because spidata is set only by plpy_spi.c, never by user code, but a hostile `__init__` override could break this assumption.

- [ISSUE-audit-gap: traceback frames after `elog(ERROR, ...)` continue the walk with `tb` already DECREF'd (audit-gap)] — Inspection at `plpy_elog.c:336-348` shows the `Py_DECREF(tb)` after the GetAttrString comes *after* the PG_TRY block returns successfully; but if the NEXT iteration's GetAttrString fails inside its PG_TRY, the outer `tb` pointer from the loop variable hasn't been re-assigned. The PG_FINALLY clears the per-frame XREFs but the loop's `tb` pointer is still the previous frame. Re-reading: actually `tb = PyObject_GetAttrString(tb, "tb_next")` reassigns `tb` BEFORE `Py_DECREF(tb)` — the DECREF is on the previous value via a temporary. Let me re-read... actually the code is `tb = PyObject_GetAttrString(tb, "tb_next"); if (tb == NULL) elog(ERROR, ...); Py_DECREF(tb);`. So `tb` is the NEW frame, and `Py_DECREF(tb)` immediately releases that new frame, relying on the parent frame's refcount to keep it alive. This is the comment at :340-347. Subtle but correct. Filing as audit-gap because future maintainers might trip on the inverted DECREF target.
