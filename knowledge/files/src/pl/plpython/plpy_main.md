# plpy_main

Covers `source/src/pl/plpython/plpy_main.c` (388 LOC) and `source/src/pl/plpython/plpy_main.h` (31 LOC).

Source pin: `4b0bf0788b0`.

## One-line summary

The PL/Python entry-point module: hosts `_PG_init` (one-shot interpreter bring-up), the three SQL-visible handlers (`plpython3_validator`, `plpython3_call_handler`, `plpython3_inline_handler`), and the `PLyExecutionContext` stack that tracks the currently-running plpython invocation for error callbacks and scratch memory.

## Public API / entry points

| Symbol | Where | Purpose |
|---|---|---|
| `_PG_init` | `plpy_main.c:57-111` | Module loader hook: `Py_Initialize()`, set up `__main__`, `GD`, import `plpy` builtin module, init procedure cache. Runs ONCE per backend, on first load of plpython3.so. |
| `plpython3_validator(funcoid)` | `plpy_main.c:114-141` | CREATE FUNCTION validator: gated by `check_function_bodies` GUC and `CheckFunctionValidatorAccess` ACL check; compiles the function body to catch syntax errors. |
| `plpython3_call_handler(fcinfo)` | `plpy_main.c:144-217` | Main dispatch: distinguishes plain function / row trigger / event trigger and routes to `PLy_exec_function` / `PLy_exec_trigger` / `PLy_exec_event_trigger`. |
| `plpython3_inline_handler(fcinfo)` | `plpy_main.c:220-290` | DO block handler: builds a transient `PLyProcedure` (no cache key), compiles, executes, and deletes. |
| `PLy_current_execution_context(void)` | `plpy_main.c:336-342` | Returns top of the execution-context stack; `elog(ERROR, ...)` if no plpython is running. Used by `plpython_error_callback`, `plpython_return_error_callback`, `plpython_trigger_error_callback`, `PLy_traceback`. |
| `PLy_get_scratch_context(ctx)` | `plpy_main.c:345-357` | Lazy-allocate a per-invocation `AllocSetContextCreate(TopTransactionContext, ...)` for type-I/O scratch space. |
| `PLy_interp_globals` | `plpy_main.c:50`, declared `plpy_main.h:11` | The interpreter's `__main__` dict (after GD and plpy module insertion). `PLy_procedure_compile` copies this dict as each procedure's globals. |
| `PLyExecutionContext` | `plpy_main.h:18-23` | Per-call frame: `curr_proc`, `scratch_ctx`, `next`. Singly-linked stack rooted at static `PLy_execution_contexts`. |

## Key invariants

- **One Python interpreter per PG backend.** `Py_Initialize()` runs once in `_PG_init` [verified-by-code: `plpy_main.c:70`]. There is NO `Py_Finalize` anywhere in plpython — the interpreter lives until the backend exits via process exit. This means: imported modules, monkey-patches, and arbitrary `GD`/`SD` state persist for the lifetime of the backend connection. A `plpython3u` function that does `import socket; socket.socket(...).connect(...)` leaves the socket descriptor open across subsequent invocations on the same backend, even from other unrelated functions.
- **Execution-context stack is LIFO, matched with `PG_TRY`/`PG_CATCH`.** Every `PLy_push_execution_context` pairs with exactly one `PLy_pop_execution_context`, and the pops are inside `PG_TRY` and `PG_CATCH` blocks to handle both clean exit and error rethrow [verified-by-code: `plpy_main.c:163-216` and `:256-289`]. The comment at `:160-163` and `:253-256` is explicit: "It is important that this get popped again, so avoid putting anything that could throw error between here and the PG_TRY."
- **`SPI_finish()` is NOT called in plpy_main** — it's deferred to `PLy_exec_function`/`PLy_exec_trigger` in plpy_exec.c. The plpy_main comment flags this: `/* Note: SPI_finish() happens in plpy_exec.c, which is dubious design */` [verified-by-code: `plpy_main.c:155, :229`]. This is a known wart — see Issues.
- **Validator never caches.** `plpython3_validator` calls `PLy_procedure_get(funcoid, InvalidOid, is_trigger)` [verified-by-code: `plpy_main.c:138`]. For trigger functions this means `fn_rel == InvalidOid`, which the cache layer in `plpy_procedure.c:80-83` detects and refuses to cache, so validation never poisons the cache with an entry that wouldn't match any future trigger call.
- **Inline blocks (`DO $$ ... $$ LANGUAGE plpython3u`) use a stack-allocated `PLyProcedure`.** No cache entry [verified-by-code: `plpy_main.c:238-243`]. The proc is `MemSet(0)`'d, given a private `mcxt` rooted under `TopMemoryContext`, compiled with `PLy_procedure_compile`, executed, then `PLy_procedure_delete`'d.

## Notable internals

### Interpreter bring-up sequence (`_PG_init`)

1. `pg_bindtextdomain(TEXTDOMAIN)` — register the gettext domain `plpython` [plpy_main.c:64].
2. `PyImport_AppendInittab("plpy", PyInit_plpy)` — register the plpy builtin module BEFORE `Py_Initialize` so it's available at interpreter startup [plpy_main.c:67]. `PyInit_plpy` lives in plpy_plpymodule.c (sibling sweep).
3. `Py_Initialize()` — actual interpreter bring-up [plpy_main.c:70].
4. `PyImport_AddModule("__main__")` — get the magic `__main__` module that hosts top-level execution [plpy_main.c:72].
5. Create empty `GD = PyDict_New()`, insert into `main_dict` as the user-facing global-shared-data dict [plpy_main.c:84-87].
6. `PyImport_ImportModule("plpy")` and insert into `main_dict` so `plpy.execute(...)` works without an explicit import [plpy_main.c:92-96].
7. `PLy_interp_globals = main_dict` [plpy_main.c:102]. Reference held forever (no matching DECREF anywhere).
8. `init_procedure_caches()` — initialize the function-OID hash table [plpy_main.c:106].
9. `explicit_subtransactions = NIL` — initialize the subxact stack used by plpy_subxactobject.c [plpy_main.c:108].

### Call-handler dispatch

`plpython3_call_handler` distinguishes call modes via `CALLED_AS_TRIGGER(fcinfo)` and `CALLED_AS_EVENT_TRIGGER(fcinfo)` [plpy_main.c:181, :191], and looks up the procedure via `PLy_procedure_get(funcoid, RelationGetRelid(tgrel) | InvalidOid, PLPY_xxx)`. For row triggers, the trigger relation OID is part of the cache key, so the same trigger function used on two tables gets two cache entries with separate compiled bodies — same source, but separate proc->result_in TupleDesc setup.

### Nonatomic SPI mode for procedures

`plpython3_call_handler` checks `fcinfo->context` for a `CallContext` node, and if its `atomic` flag is false, passes `SPI_OPT_NONATOMIC` to `SPI_connect_ext` [plpy_main.c:151-156]. This is the CALL-procedure-with-transaction-control entry point: when a CALL'd procedure uses `plpy.commit()` / `plpy.rollback()`, the SPI connection must be nonatomic so SPI doesn't error out. The `atomic_context` flag is also threaded into `PLy_push_execution_context`, which picks `TopTransactionContext` vs `PortalContext` for the execution-context allocation [plpy_main.c:166, :360-373] — procedures need `PortalContext` because they survive across `COMMIT` inside the proc.

### Error-callback wiring

`plpython_error_callback(exec_ctx)` adds `errcontext("PL/Python procedure/function \"%s\"", name)` to any ereport that fires while a plpython call is active [plpy_main.c:313-327]. Registered onto `error_context_stack` inside the `PG_TRY` and auto-popped by `PG_TRY`'s structural unwinding [plpy_main.c:176-179]. The comment is explicit: "the PG_TRY structure pops this for us again at exit, so we needn't do that explicitly, nor do we risk the callback getting called after we've destroyed the exec_ctx" [plpy_main.c:171-174].

### Memory-context choice for execution context

`PLy_push_execution_context` allocates the `PLyExecutionContext` struct in `TopTransactionContext` for atomic calls and `PortalContext` for nonatomic (procedure) calls [plpy_main.c:366]. The scratch context inside it is always rooted under `TopTransactionContext` regardless [plpy_main.c:353]. The asymmetry is intentional: the exec_ctx must survive across plpy commits when running under CALL, but the scratch context resets per top-level statement.

## Trust posture

Echoes `plpython.h.md`: plpython is **untrusted-only**. There is NO trust check in plpy_main.c. The `pg_language` catalog row created by `CREATE EXTENSION plpython3u` has `lanpltrusted = false`; the only gate is that CREATE EXTENSION itself requires superuser (from `superuser = true` in `plpython3u.control`).

Once `plpython3u` exists in a database, **any role with `USAGE` on the language can create functions** that run as the *invoking* user (or *definer* if SECURITY DEFINER). The "untrusted" label is exclusively about what the language can do (anything Python can do: open files, fork, dlopen via ctypes), not who can call it.

Notable absences in plpy_main.c that mirror this posture:
- **No `Safe.pm` analogue, no restricted `__builtins__`.** The `_PG_init` flow grabs the standard CPython interpreter's `__main__` namespace verbatim [plpy_main.c:72]. Nothing is removed; `os`, `subprocess`, `socket`, `ctypes`, `sys` are all accessible.
- **No separate `plpython3_trusted_call_handler` symbol.** Contrast: plperl exports both `plperl_call_handler` and `plperl_call_handler` (no — same handler, but the language has separate `pg_language` rows with `lanpltrusted=true` for plperl and `false` for plperlu, and Safe.pm is engaged inside the handler when invoked via the trusted language). plpython has a single handler set, no trust branch.
- **GIL acquisition is implicit.** Python's GIL is held whenever Python C-API functions are called. plpy_main never explicitly releases the GIL around PG calls (which are SPI-mediated), so the GIL is held continuously during a plpython call. For a single-backend, single-Python-interpreter design this is correct; but see Issues for the "long SPI op holds GIL" concern.

## Cross-references

- `plpy_exec.md` — where call/trigger/event-trigger execution actually happens.
- `plpy_procedure.md` — the cache and `PLyProcedure` lifecycle that handlers drive.
- `plpy_elog.md` — error bridging used by `_PG_init`'s `PLy_elog(ERROR, ...)` failures.
- `plpy_plpymodule.c` (sibling sweep) — `PyInit_plpy` and the plpy.* surface (execute, prepare, subtransaction, etc.).
- `plpy_subxactobject.c` (sibling sweep) — `explicit_subtransactions` list initialized here.
- A9 plpgsql comparison: `pl_handler.c` is plpgsql's analog. plpgsql has NO `_PG_init` interpreter bring-up because plpgsql has no interpreter — bytecode is interpreted by `pl_exec.c` directly. plpython's `_PG_init` is the cleanest example of "expensive one-time-per-backend init" in the source tree.
- A10-1 plperl comparison: plperl has dual-handler `plperl_call_handler` vs `plperlu_call_handler` (both routing to the same internal dispatch, with the trust flag taken from `fn_oid`'s pg_language row). plpython has only one.

## Issues spotted

- [ISSUE-api-shape: `SPI_finish()` lives in plpy_exec.c instead of plpy_main.c (maybe)] — Acknowledged in the source comment: `/* Note: SPI_finish() happens in plpy_exec.c, which is dubious design */` [verified-by-code: `plpy_main.c:155, :229`]. The push/connect happens here but the pop/disconnect lives two files away. If a new entry-point handler is added (e.g. a future inline-procedure handler) and forgets the SPI_finish in its dispatch arm, the SPI stack leaks. Not a current bug, but a foot-gun the maintainers have already flagged.

- [ISSUE-security: one Python interpreter per backend = persistent state across functions (likely)] — `Py_Initialize` runs once in `_PG_init`; `Py_Finalize` is never called [verified-by-code: `plpy_main.c:70`, and absence of any `Py_Finalize` in the file]. Threat model: a `plpython3u` function `f1` that does `import socket; sys.modules['evil'] = MyTrojan()` leaves `evil` importable by any subsequent plpython3u function on the same backend, including ones owned by other users (if invoked via SECURITY DEFINER on the trojan-installing user's function, or via PG connection reuse). This is documented behavior (the `GD` dict is explicitly the shared persistence mechanism), but the *non-`GD`* persistence (sys.modules patches, monkey-patched `os.open`, etc.) is rarely called out. Connection poolers that multiplex many user sessions onto one backend amplify this dramatically — pgbouncer in transaction-pooling mode + plpython3u is a known footgun.

- [ISSUE-concurrency: GIL held continuously during plpython invocation, including SPI calls (maybe)] — There is no `Py_BEGIN_ALLOW_THREADS` / `Py_END_ALLOW_THREADS` anywhere in plpy_main.c or plpy_exec.c [verified-by-code: grep would find none]. PG is per-backend single-threaded, so the GIL doesn't bottleneck other PG backends. But if a future patch threads Python (e.g. `import threading` to do parallel HTTP fetches inside a function), all those threads block on the GIL while the main thread is inside `SPI_execute` — and SPI calls don't release the GIL. This is the correct conservative default for plpython (Python threads + PG transactions = surprises), but it means plpython functions cannot productively use Python threads for I/O parallelism. Not a bug per se, but worth flagging as an "intentional limitation that's never documented."

- [ISSUE-error-handling: `_PG_init` calls `PLy_elog(FATAL, ...)` if `PyErr_Occurred()` after init (likely)] — At plpy_main.c:98-99, if any Python error remained latent through the init sequence, `PLy_elog(FATAL, ...)` kicks the entire backend (FATAL terminates the process). This is intentional ("untrapped error in initialization" means the interpreter is in an undefined state and the backend cannot proceed safely), but the user-visible effect is that a corrupted Python install — say, a broken `site.py` on the host — turns "CREATE EXTENSION plpython3u" or even "load on first call" into a backend crash. Not a bug, but the postcondition deserves a corpus mention because operators sometimes see "FATAL: untrapped error" without context.

- [ISSUE-audit-gap: `_PG_init` retains permanent refcount on `main_dict` with no DECREF (nit)] — `Py_INCREF(main_dict); PLy_interp_globals = main_dict;` at plpy_main.c:101-102 with no matching DECREF anywhere. This is deliberate (lifetime = backend), but if plpython ever grew an explicit teardown path, this leak would need to be paired. Documented for future-self.

- [ISSUE-defense-in-depth: validator runs full compile of user source under definer privs at CREATE FUNCTION time (maybe)] — `plpython3_validator` calls `PLy_procedure_get` which calls `PLy_procedure_create` which calls `PLy_procedure_compile` which calls `Py_CompileString` AND `PyEval_EvalCode` on the wrapping `def name(): ...` body [chain verified in plpy_procedure.c:345, :388-390]. The `PyEval_EvalCode` actually *executes* the function definition (not the body) to bind `name` in globals. This is normally safe — defining `def f(): malicious_thing()` doesn't execute `malicious_thing()`. BUT: a function source like `import os; os.system("...");\ndef f(): pass` *would* execute the import at compile time because `PLy_procedure_munge_source` wraps the user source as the *body* of a function (see `plpy_procedure.c:459` — `def %s():\n\t<src>`), making the import part of `f`'s body, not module-level. So this is fine in practice. But if a future patch ever changed the munge to allow module-level statements, CREATE FUNCTION would become arbitrary code execution gated only on `check_function_bodies`. Worth a note. (Currently safe.) [inferred from cross-reading plpy_procedure.c:445-487 and plpy_main.c:124-138.]
