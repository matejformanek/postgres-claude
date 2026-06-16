# plpy_spi (plpy_spi.c + plpy_spi.h)

Covers `source/src/pl/plpython/plpy_spi.c` (656 LOC) and `source/src/pl/plpython/plpy_spi.h` (29 LOC).

Source pin: `4b0bf0788b0`.

## One-line summary

The SPI bridge that backs Python-visible `plpy.execute`, `plpy.prepare`, `plpy.execute(plan, args, limit)`, `plpy.commit`, and `plpy.rollback`, plus the trio of `PLy_spi_subtransaction_{begin,commit,abort}` helpers that wrap every PG-throwing SPI call in `BeginInternalSubTransaction` so a thrown ereport becomes a catchable Python exception instead of a longjmp through the Python C stack.

## Public API / entry points

Module-level Python functions (called via the `plpy` module's PyMethodDef table in `plpy_plpymodule.c`):

- `PLy_spi_prepare(self, args)` — `plpy.prepare(query, [typelist])` [verified-by-code: `source/src/pl/plpython/plpy_spi.c:36-145`]
- `PLy_spi_execute(self, args)` — dispatch entry for `plpy.execute(query, [limit])` OR `plpy.execute(plan, [params], [limit])` [verified-by-code: `source/src/pl/plpython/plpy_spi.c:151-170`]
- `PLy_spi_execute_plan(ob, list, limit)` — the prepared-plan branch [verified-by-code: `source/src/pl/plpython/plpy_spi.c:172-293`]
- `PLy_commit(self, args)` — `plpy.commit()` [verified-by-code: `source/src/pl/plpython/plpy_spi.c:447-492`]
- `PLy_rollback(self, args)` — `plpy.rollback()` [verified-by-code: `source/src/pl/plpython/plpy_spi.c:494-539`]

Subxact helpers exposed in `plpy_spi.h` and used by sibling files (e.g. `plpy_cursorobject.c`):

- `PLy_spi_subtransaction_begin(oldcontext, oldowner)` [verified-by-code: `source/src/pl/plpython/plpy_spi.c:566-572`]
- `PLy_spi_subtransaction_commit(oldcontext, oldowner)` [verified-by-code: `source/src/pl/plpython/plpy_spi.c:574-581`]
- `PLy_spi_subtransaction_abort(oldcontext, oldowner)` [verified-by-code: `source/src/pl/plpython/plpy_spi.c:583-612`]

Type declared in the header:

- `PLyExceptionEntry { int sqlstate; PyObject *exc; }` — hash entry mapping SQLSTATE → Python exception subclass; populated by `plpy_plpymodule.c` and consumed by `PLy_spi_exception_set` here [verified-by-code: `source/src/pl/plpython/plpy_spi.h:18-22`].

## Key invariants

- **Every SPI call inside `plpy.*` runs in an internal subtransaction.** The pattern is the textbook example documented in the file's own comment block at `:541-565` [from-comment: `source/src/pl/plpython/plpy_spi.c:541-565`]. Without it, an `ereport(ERROR)` from inside SPI would longjmp directly through `PyObject_CallObject` frames, leaving Python's interpreter state corrupt; the subtransaction catches the longjmp, rolls back, and synthesizes a Python exception via `PLy_spi_exception_set`.
- **`PLyPlanObject->plan` is `SPI_keepplan`-protected after `PLy_spi_prepare` returns.** The plan is built in the SPI proc context, then explicitly transferred to TopMemoryContext via `SPI_keepplan` [verified-by-code: `source/src/pl/plpython/plpy_spi.c:127-129`]. If `SPI_keepplan` fails it `elog(ERROR)`s — but at that point the partial plan is still in SPI's procCxt, which the subtransaction abort will tear down cleanly.
- **`Assert(plan->plan != NULL)` post-condition for `PLy_spi_prepare`** [verified-by-code: `source/src/pl/plpython/plpy_spi.c:143`] — guarantees that a non-NULL `PLyPlanObject` returned from prepare has a usable saved plan. Any error path returns NULL via `PG_CATCH`.
- **Argument count must match plan's argcount.** `PLy_spi_execute_plan` raises `TypeError` with plural-aware message if not [verified-by-code: `source/src/pl/plpython/plpy_spi.c:196-212`].
- **Result row count must fit in `Py_ssize_t`.** Otherwise `ereport(ERROR, ERRCODE_PROGRAM_LIMIT_EXCEEDED)` [verified-by-code: `source/src/pl/plpython/plpy_spi.c:388-391`]. On 64-bit `Py_ssize_t` this is effectively unreachable; on 32-bit hosts a 2G+ row resultset would hit it.
- **`pg_verifymbstr(query, ...)` is called before every `SPI_prepare` and `SPI_execute` text path** [verified-by-code: `source/src/pl/plpython/plpy_spi.c:121, 312`]. Queries that came from `PLyUnicode_AsString` are already server-encoded, but `pg_verifymbstr(false)` re-validates as belt-and-suspenders.
- **Result tupdesc is copied into `TopMemoryContext`** so the `PLyResultObject` outlives the SPI context that produced it; the comment is explicit that `PLy_result_dealloc` is trusted to clean up [from-comment: `source/src/pl/plpython/plpy_spi.c:412-419`].
- **`exec_ctx->scratch_ctx = NULL` after every commit/rollback.** The comment says it "was cleared at transaction end" [from-comment: `source/src/pl/plpython/plpy_spi.c:457-458, 471-472, 504-505, 518-519`] — `SPI_commit`/`SPI_rollback` drops `CurTransactionContext` and everything in it; resetting the pointer prevents a later use-after-free.

## Notable internals

### The `volatile` keyword on locals near `PG_TRY` is required

Locals that span the `PG_TRY`/`PG_CATCH` boundary (e.g. `oldcontext`, `oldowner`, `optr`, `nargs`, `values`, `nulls`, `j`) are declared `volatile` to keep them stable across the `siglongjmp` that PG_CATCH performs [verified-by-code: `source/src/pl/plpython/plpy_spi.c:44-46, 178-179, 222-225`]. Compiler-optimizing them into registers would lose their pre-longjmp values. This is the standard PG idiom (see `idioms/error-handling`).

### Dual-path `PLy_spi_execute` parses with two `PyArg_ParseTuple` attempts

[verified-by-code: `source/src/pl/plpython/plpy_spi.c:151-170`] — first tries `"s|l"` (string query + optional long limit), clears the resulting Python error if that fails, then tries `"O|Ol"` (plan object + optional args + optional limit). The `is_PLyPlanObject(plan)` check gates the second branch.

This is **not** a parameterization decision: `plpy.execute("SELECT ... ")` accepts an arbitrary string and runs it via `SPI_execute` with no parameterization, just like A9 plpgsql's `EXECUTE` statement. A user-supplied query is a SQL-injection sink unless the user wraps it themselves with `plpy.quote_literal` / `plpy.quote_ident` (those live in `plpy_plpymodule.c`, not here).

### Plan argument types are resolved by `parseTypeString`, NOT by `OIDS`

[verified-by-code: `source/src/pl/plpython/plpy_spi.c:89-105`] — the user passes `plpy.prepare(query, ["text", "integer[]"])` and each string goes through `parseTypeString` (which calls `typenameTypeId`). That means the type list honors the **current `search_path`** at prepare-time. A function that does `plpy.prepare("…", ["my_type"])` will pick a different OID if invoked after `SET search_path = …, my_schema`.

This is the same posture as plpgsql `PREPARE` and is documented behavior, not a bug — but it's a Phase D audit hit: a SECURITY DEFINER function that calls `plpy.prepare` without locking down its search_path inherits whatever the caller set.

### `PLy_spi_execute_plan`: per-call tmpcontext

[verified-by-code: `source/src/pl/plpython/plpy_spi.c:231-234, 273`] — a `PL/Python temporary context` AllocSet is created under `CurTransactionContext`, all argument conversions happen inside it, and it's deleted on success. On `PG_CATCH`, the subtransaction abort tears down `CurTransactionContext` and everything under it, so the tmpcontext doesn't need explicit cleanup in the catch path [from-comment: `source/src/pl/plpython/plpy_spi.c:278`].

### `PG_TRY(2)` nested try in argument conversion

[verified-by-code: `source/src/pl/plpython/plpy_spi.c:253-264`] — uses the numbered-PG_TRY variant (level 2) to ensure `Py_DECREF(elem)` runs even if `PLy_output_convert` throws ereport. Without the level-2 try, a longjmp would leak the Python ref. The level-1 try around the whole loop catches the re-thrown error and runs `PLy_spi_subtransaction_abort`.

### `PLy_commit` and `PLy_rollback` do NOT use the subxact helpers

[verified-by-code: `source/src/pl/plpython/plpy_spi.c:447-539`] — they call `SPI_commit`/`SPI_rollback` directly inside `PG_TRY`, and on `PG_CATCH` they hand-roll the error-to-Python-exception conversion (the same code as `PLy_spi_subtransaction_abort` minus the `RollbackAndReleaseCurrentSubTransaction` call). This is because `SPI_commit` ends the outer transaction — there is no subtransaction to roll back; the whole subxact machinery assumes a containing transaction that the abort path can release back to.

### `PLy_spi_exception_set`: structured error attachment

[verified-by-code: `source/src/pl/plpython/plpy_spi.c:618-656`] — builds a Python `SPIError` subclass instance and attaches a `spidata` attribute that is a 10-tuple: `(sqlerrcode, detail, hint, internalquery, internalpos, schema_name, table_name, column_name, datatype_name, constraint_name)`. The format string `"(izzzizzzzz)"` means int + 4 strings + int + 5 strings, where lowercase `z` is "string or None." Failure to build any of these is itself fatal — `elog(ERROR, "could not convert SPI error to Python exception")`.

The fallback when no custom Python exception class matches the SQLSTATE is the generic `PLy_exc_spi_error`. Custom SQLSTATEs raised by user code (e.g. via `RAISE SQLSTATE 'XX001'`) hit this fallback.

### Subxact helper triplet semantics

`PLy_spi_subtransaction_begin` calls `BeginInternalSubTransaction(NULL)` then switches back to `oldcontext` so the body runs in the caller's memory context [verified-by-code: `source/src/pl/plpython/plpy_spi.c:566-572`]. `..._commit` calls `ReleaseCurrentSubTransaction()` and restores both context and resource owner [`:574-581`]. `..._abort` is the heaviest: copies the error data out, flushes elog state, rolls back the subxact, then constructs the Python exception via `PLy_spi_exception_set` [`:583-612`]. The error-data ownership transfer here is critical — `CopyErrorData` must happen in `oldcontext` (not the subxact's about-to-die context) and `FlushErrorState` must follow before `RollbackAndReleaseCurrentSubTransaction`.

## Cross-references

- `pg_language` entry for `plpython3u` — `lanpltrusted = false`; see `plpython.h.md` for the trust posture. plpython is **untrusted-only**, so no trusted/untrusted dispatch here.
- `source/src/backend/executor/spi.c` — `SPI_execute`, `SPI_prepare`, `SPI_execute_plan`, `SPI_keepplan`, `SPI_commit`, `SPI_rollback` are all called from here.
- `source/src/backend/access/transam/xact.c` — `BeginInternalSubTransaction`, `ReleaseCurrentSubTransaction`, `RollbackAndReleaseCurrentSubTransaction`.
- `plpy_planobject.c` — `PLyPlanObject` definition; this file fills `plan->plan`, `plan->nargs`, `plan->types`, `plan->args`.
- `plpy_resultobject.c` — `PLyResultObject` definition; this file fills `result->status`, `result->nrows`, `result->rows`, `result->tupdesc`.
- `plpy_plpymodule.c` — registers `PLy_spi_prepare`/`PLy_spi_execute`/etc. in the `plpy` module's method table; also owns the `PLy_spi_exceptions` HTAB hashtable.
- `plpy_cursorobject.c` (not in this slice) — uses the `PLy_spi_subtransaction_*` helpers exported from `plpy_spi.h` for the `plpy.cursor` interface.
- A9 baseline (plpgsql): `pl_exec.c`'s `exec_stmt_dynexecute` is the plpgsql analogue of `plpy.execute(text)` — same string-concatenation hazard, same lack of automatic parameterization.
- A10-1 (plperl): `spi_query`/`spi_prepare`/`spi_exec_prepared` in `plperl.c`; same subxact-wrap-every-SPI-call idiom.
- A10-2 (plpython core): `plpy_main.c`, `plpy_exec.c`, `plpy_elog.c`.

<!-- issues:auto:begin -->
- [Issue register — `plpython`](../../../../issues/plpython.md)
<!-- issues:auto:end -->

## Issues spotted

- **[ISSUE-security: `plpy.execute(text)` passes its argument straight to `SPI_execute` with no parameterization (likely)]** — `source/src/pl/plpython/plpy_spi.c:296-335`. Documented behavior, mirrors plpgsql `EXECUTE`. Cited here for the Phase D audit trail: every PL's text-execute path is a SQL-injection sink unless the user wraps with `plpy.quote_literal`/`plpy.quote_ident`. A SECURITY DEFINER plpython function that interpolates a parameter into a query string is the classic privesc.
- **[ISSUE-security: `plpy.prepare` resolves argument type names via `parseTypeString`, which honors the current `search_path` (likely)]** — `source/src/pl/plpython/plpy_spi.c:105`. A SECURITY DEFINER function whose `pg_proc.proconfig` does not pin `search_path` will resolve `"my_type"` to whatever the *caller's* search_path makes it resolve to. The plan object then carries that OID indefinitely. Same hazard exists for plpgsql DECLARE and plperl spi_prepare — system-wide pattern.
- **[ISSUE-correctness: 32-bit `Py_ssize_t` row-count overflow caught defensively (nit)]** — `source/src/pl/plpython/plpy_spi.c:388-391`. The check exists, but the `ereport(ERROR, ERRCODE_PROGRAM_LIMIT_EXCEEDED)` happens AFTER `result_new()` and BEFORE `PyList_New(rows)`, inside the `PG_TRY` block at `:375-431`. The catch path at `:424-431` does `Py_DECREF(result)`, so the partial result is freed correctly — no leak. Not actually a bug; logging because it's a defensive check worth confirming on 32-bit builds.
- **[ISSUE-error-handling: `PLy_spi_exception_set` failure mode is `elog(ERROR, …)` which then longjmps back up through the SAME PG_CATCH that called us (likely)]** — `source/src/pl/plpython/plpy_spi.c:651-655`. If, say, the `edata->message` contains a NUL byte that breaks `Py_BuildValue("(s)", ...)`, we jump to `failure:` and `elog(ERROR)`. That ereport then unwinds via the OUTER PG_TRY (whichever one called `..._subtransaction_abort`), which has already done `FlushErrorState`. The result is a second elog inside an aborted subxact. Hard to trigger but worth flagging.
- **[ISSUE-defense-in-depth: `pg_verifymbstr` called with `noError=false` for queries (nit)]** — `source/src/pl/plpython/plpy_spi.c:121, 312`. The query string is already server-encoded by `PLyUnicode_AsString`. The second verification is paranoid but adds CPU cost proportional to query length. Probably worth keeping; logged because a stricter language binding (e.g. one that guarantees server encoding by construction) could elide it.
- **[ISSUE-audit-gap: no logging of plan creation or text execute (audit-gap, maybe)]** — Every `plpy.execute(text)` and `plpy.prepare` hits SPI which has its own logging (`log_statement = all` will catch it), but at this layer there's no plpython-specific audit trail. If a function executes 10k dynamic queries per call, only `pg_stat_statements` (if installed) will surface the pattern. Phase D consideration if we ever want per-PL audit.
- **[ISSUE-documentation: the file-header block at :1-5 is one line of comment (nit)]** — `source/src/pl/plpython/plpy_spi.c:1-5`. Sibling plpy_main.c likely has the same; uniform across plpython. No fix needed, just noting the inconsistency with elsewhere in the tree.
