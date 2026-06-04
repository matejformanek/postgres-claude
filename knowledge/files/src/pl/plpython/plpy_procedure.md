# plpy_procedure

Covers `source/src/pl/plpython/plpy_procedure.c` (487 LOC) and `source/src/pl/plpython/plpy_procedure.h` (82 LOC).

Source pin: `4b0bf0788b0`.

## One-line summary

The PLyProcedure cache and lifecycle: looks up `pg_proc` by OID, builds a Python `def` wrapper around the user's body via source mangling, compiles it with `Py_CompileString`, validates cache entries against the catalog tuple's `xmin`/`tid`, and tears down on invalidation.

## Public API / entry points

| Symbol | Where | Purpose |
|---|---|---|
| `init_procedure_caches(void)` | `plpy_procedure.c:30-38` | Create the `PLy_procedure_cache` HTAB. Called once from `_PG_init`. |
| `PLy_procedure_name(proc)` | `plpy_procedure.c:46-51` | Return SQL name (or `"<unknown procedure>"` if NULL). Used by error callbacks. |
| `PLy_procedure_get(fn_oid, fn_rel, is_trigger)` | `plpy_procedure.c:71-140` | Cache lookup with create-on-miss. Returns NULL for the validator's trigger-without-relation case. |
| `PLy_procedure_compile(proc, src)` | `plpy_procedure.c:365-416` | Mangle the source, `Py_CompileString` it as a `def`, `PyEval_EvalCode` to bind the function name in `proc->globals`, then `Py_CompileString` a call expression `name()` to store as `proc->code`. |
| `PLy_procedure_delete(proc)` | `plpy_procedure.c:419-425` | Release all PyObject refs and delete the per-procedure MemoryContext. |
| `PLyTrigType` enum | `plpy_procedure.h:17-22` | `PLPY_TRIGGER`, `PLPY_EVENT_TRIGGER`, `PLPY_NOT_TRIGGER`. |
| `PLySavedArgs` struct | `plpy_procedure.h:25-32` | Linked-list node for recursive-call argument saving (see plpy_exec.md). |
| `PLyProcedure` struct | `plpy_procedure.h:35-60` | The cached procedure: mcxt, proname, pyname, fn_xmin, fn_tid, is_setof, is_procedure, is_trigger, result/result_in conv info, src, argnames[], args[], nargs, langid, trftypes, code, statics, globals, calldepth, argstack. |
| `PLyProcedureKey` struct | `plpy_procedure.h:62-67` | Hash key: `{fn_oid, fn_rel}`. |
| `PLyProcedureEntry` struct | `plpy_procedure.h:69-74` | Hash entry: `{key, proc *}`. |

## Key invariants

- **Cache key is (fn_oid, fn_rel), NOT fn_oid alone.** [verified-by-code: `plpy_procedure.h:62-67, plpy_procedure.c:96-98`]. A trigger function used on two tables gets two cache entries because the per-relation TupleDesc is baked into `proc->result_in`. A plain function always has `fn_rel = InvalidOid`.

- **OID-based, not name-based.** Cache key is the function OID from `pg_proc`. Unlike plpgsql's `%TYPE` resolution (which is NAME-based — see A9 `pl_comp.md`), plpython's cache binds to the OID. DROP+CREATE with the same name gets a new OID and a new cache entry; the old one becomes invalidatable via the xmin/tid check.

- **Cache validity = (fn_xmin, fn_tid) of the pg_proc tuple.** `PLy_procedure_valid` compares `proc->fn_xmin == HeapTupleHeaderGetRawXmin(procTup->t_data)` AND `ItemPointerEquals(&proc->fn_tid, &procTup->t_self)` [verified-by-code: `plpy_procedure.c:430-442`]. Any update to the pg_proc row (CREATE OR REPLACE, ALTER FUNCTION, ALTER FUNCTION OWNER, etc.) changes either xmin (if it caused a new tuple) or tid (if HOT-update), invalidating the cache entry. The entry is reused (no rehash), just re-populated with the freshly created `PLyProcedure`.

- **Trigger validation skips caching.** When `is_trigger == PLPY_TRIGGER && fn_rel == InvalidOid` (the call shape used by `plpython3_validator`), `use_cache = false` and the constructed `PLyProcedure` is deleted before return [verified-by-code: `plpy_procedure.c:80-83, :110-115`]. The comment explains: "the only caller that would pass that set of values is plpython3_validator, which ignores our result anyway."

- **Pseudotype rejection at proc-creation time.** Pseudotype RETURNS is allowed only for `VOIDOID`, `RECORDOID`, `TRIGGEROID`, and `EVENT_TRIGGEROID`; any other pseudotype rejects with `ERRCODE_FEATURE_NOT_SUPPORTED` [verified-by-code: `plpy_procedure.c:231-245`]. Pseudotype arguments are universally rejected [verified-by-code: `:318-322`]. (Cf. plpgsql which accepts `anyelement`.)

- **OUT and TABLE arg modes are skipped.** `proc->nargs` counts only IN/INOUT; OUT and TABLE columns are popped from the input list and never appear in the Python `args` [verified-by-code: `:282-293, :304-306`].

- **`PLy_procedure_munge_source` cannot overflow buffer.** Sized at `mlen = (strlen(src) * 2) + strlen(name) + 16` [verified-by-code: `:456`]; the worst-case substitution doubles each character (newline → "\n\t"). Defense-in-depth assertion `if (mp > (mrc + mlen)) elog(FATAL, "buffer overrun")` at `:483-484`.

- **PG_CATCH removes the cache entry on creation failure.** If `PLy_procedure_create` throws (e.g. compile error), `hash_search(..., HASH_REMOVE, NULL)` is called inside PG_CATCH to undo the HASH_ENTER [verified-by-code: `:128-134`]. Otherwise a subsequent lookup would find a half-populated entry with `proc = NULL`.

## Notable internals

### `PLy_procedure_create` flow

1. Format Python-safe name: `__plpython_procedure_<proname>_<fn_oid>` into a `procName[NAMEDATALEN + 256]` buffer [plpy_procedure.c:157-160]. Snprintf return checked for truncation.
2. Sanitize: replace any non-`[A-Za-z0-9]` byte with `'_'` [plpy_procedure.c:165-171]. This is what tolerates SQL function names containing dots, hyphens, spaces, or Unicode (Python identifiers must be strict ASCII for the wrapper).
3. Create per-procedure MemoryContext under `TopMemoryContext` with `MemoryContextSetIdentifier(cxt, proc->proname)` so `MemoryContextStats` reports show "PL/Python function: my_func" [plpy_procedure.c:174-176, :192].
4. Switch into the new context; allocate `palloc0_object(PLyProcedure)`; fill in basics (proname, pyname, fn_xmin, fn_tid, fn_readonly, is_setof, is_procedure, is_trigger, langid, trftypes).
5. For non-trigger: SearchSysCache TYPEOID for prorettype, reject bad pseudotypes, call `PLy_output_setup_func`.
6. Walk argument array: `get_func_arg_info`; for each non-OUT/non-TABLE arg, reject pseudotype, call `PLy_input_setup_func`, copy argname.
7. Fetch `prosrc` via `SysCacheGetAttrNotNull(PROCOID, procTup, Anum_pg_proc_prosrc)`.
8. Call `PLy_procedure_compile(proc, procSource)`.
9. PG_CATCH: switch back to oldcxt, `PLy_procedure_delete(proc)`, rethrow.

### `PLy_procedure_compile` source mangling

The user's function body:
```python
x = args[0]
return x * 2
```
becomes (via `PLy_procedure_munge_source`):
```
def __plpython_procedure_myfunc_16384():
	x = args[0]
	return x * 2

```

Specifically [verified-by-code: `:444-487`]:
- Prepend `def <pyname>():\n\t`.
- Walk input chars: convert `\r\n` → `\n`, convert `\r` or `\n` → `\n\t` (continue indenting subsequent lines), pass all other chars through.
- Append `\n\n` for clean termination.

This means **EVERY line of user source is indented one tab**, making the whole body sit inside the `def`. A user `def helper(): ...` at column 0 in their source becomes a nested function inside the synthesized wrapper, which is fine for closure semantics but means the user can't define helpers at module scope.

### Compile → eval → recompile-call pattern

`PLy_procedure_compile` does three Python operations [plpy_procedure.c:385-408]:
1. `Py_CompileString(msrc, "<string>", Py_file_input)` — compile the wrapper as a *module* (Py_file_input allows top-level statements).
2. `PyEval_EvalCode(code0, proc->globals, NULL)` — execute the wrapper module, which binds `__plpython_procedure_xxx_NNN` in `proc->globals`.
3. `Py_CompileString("__plpython_procedure_xxx_NNN()", "<string>", Py_eval_input)` — compile a call expression, stored as `proc->code`.

Later, `PLy_procedure_call` in plpy_exec.c just does `PyEval_EvalCode(proc->code, proc->globals, proc->globals)` to fire the call. The two-step (compile-to-bind, then compile-to-call) is necessary because Py_eval_input rejects statements, so we can't compile the body and call in one pass.

### `proc->globals` setup

```python
proc->globals = PyDict_Copy(PLy_interp_globals)
proc->globals["SD"] = PyDict_New()  # private static
# proc->globals["GD"] inherited from PLy_interp_globals
```
[verified-by-code: `:371-380`]. Then `PLy_function_build_args` (plpy_exec.c) injects `args` and the named-arg slots.

The `PyDict_Copy` is shallow: changes to mutable values in GD persist across functions, but rebinding `globals["GD"]` in one function only affects that function's globals. (Standard Python semantics; called out because plpython users sometimes expect otherwise.)

## Trust posture

N/A at this layer. The cache and lifecycle code is identical for trusted/untrusted, and plpython only has untrusted. See `plpython.h.md`.

One trust-relevant subtlety: `PLy_procedure_munge_source` does not escape the **`pyname`** when interpolating it into `"def %s():\n\t"` [verified-by-code: `plpy_procedure.c:459`]. But `pyname` itself is the sanitized `__plpython_procedure_<name>_<oid>` form where every non-alphanumeric character has been replaced with `_` [verified-by-code: `:165-171`]. So the only Python tokens that can appear in the synthesized `def` line are `[A-Za-z0-9_]` — no quotes, no parens, no newlines from user input. **Source injection from the function name is impossible** even though `snprintf("%s", name)` is used without quoting [verified-by-code]. Documented because it's the kind of thing a security-conscious reviewer would worry about.

## Cross-references

- `plpy_main.md` — `init_procedure_caches` invoked from `_PG_init`; `PLy_procedure_get` invoked from `plpython3_call_handler`.
- `plpy_exec.md` — consumes `proc->code`, `proc->globals`, `proc->argstack`, `proc->args[]`.
- `plpy_typeio.c` (sibling sweep) — `PLy_output_setup_func`, `PLy_input_setup_func`, `PLyObToDatum`, `PLyDatumToOb` defined there.
- `source/src/backend/catalog/syscache.c` — `SysCacheGetAttrNotNull`, `SearchSysCache1` machinery used here.
- A9 plpgsql comparison: plpgsql caches by `pl_comp.c:plpgsql_compile`, which uses a `plpgsql_HashEnt` keyed by `(fn_oid, trigOid, eventOid)` and validated by the same `xmin/tid` pair pattern. Structurally near-identical to plpython's cache. The big divergence: plpgsql `%TYPE` is NAME-based resolution during compile, plpython has no `%TYPE`-equivalent and is purely OID-based.
- A10-1 plperl comparison: plperl caches by `plperl_proc_hash` with similar xmin/tid invalidation. Source mangling differs — plperl wraps as `sub { ... }` and stores a Perl coderef.

## Issues spotted

- [ISSUE-defense-in-depth: source mangling does not escape user source for backslashes (likely)] — `PLy_procedure_munge_source` walks user source byte-by-byte, transforming only `\r`, `\n`, and `\r\n` [verified-by-code: `:465-478`]. All other bytes pass through verbatim, including backslashes, quotes, and embedded null bytes. This is correct because Python source files don't have a quoting layer — the bytes ARE the source. But: an embedded `'\0'` byte truncates the source at that point (`while (*sp != '\0')`), and PG TEXT fields can contain `'\0'` if loaded via pg_proc.dat or via a TEXT array-of-bytes ingestion. Probably not exploitable (pg_proc.prosrc is the text of a CREATE FUNCTION body, which goes through scan.l and rejects nulls), but worth noting that the munge function assumes NUL-termination semantics that the catalog enforces upstream.

- [ISSUE-correctness: source line numbers in tracebacks are off by 1 due to munge prefix (confirmed)] — `PLy_procedure_munge_source` prepends `"def %s():\n\t"` which inserts ONE extra line before the user's source. `PLy_traceback` in plpy_elog.c compensates with `plain_lineno - 1` [verified-by-code: `plpy_elog.c:294-298`]. This is correct as-is, but is a coupling between two files: if a future patch changes the munge prefix to span multiple lines (e.g. to add `import` shims), the `- 1` becomes wrong. Filing because it's a tripwire.

- [ISSUE-memory: `MemoryContextSetIdentifier(cxt, proc->proname)` borrows the proname pointer (nit)] — At `:192`, the identifier string is set to `proc->proname` which is itself allocated in `cxt`. So `MemoryContextStats` reads from the same context being described. This is a known PG idiom and is safe (the context isn't deleted while it's reporting), but worth noting because `MemoryContextSetIdentifier` doesn't copy.

- [ISSUE-audit-gap: cache validity check ignores `pg_proc.proconfig` and rolesetting changes (maybe)] — `PLy_procedure_valid` only compares xmin/tid of the `pg_proc` tuple [verified-by-code: `:430-442`]. If the pg_proc tuple itself doesn't change but the function's effective environment changes (e.g. `ALTER ROLE ... SET ...` that affects search_path which the function depends on), the cached `PLyProcedure` is reused. This is actually CORRECT — plpython doesn't bake search_path into the compiled code — but a user might expect cache invalidation on environment changes. Documenting because it's a common source of confusion.

- [ISSUE-correctness: `procName[NAMEDATALEN + 256]` is checked for snprintf overflow but the input could be wider (nit)] — At `:157-162`, the format is `"__plpython_procedure_%s_%u"` with `NameStr(procStruct->proname)` (max NAMEDATALEN bytes including null = 64 bytes) and a uint OID (max 10 decimal digits). Total max = 22 (prefix) + 63 + 1 (_) + 10 = 96 bytes, well under NAMEDATALEN+256 = 320. The runtime `if (rv >= sizeof(procName))` check is defense-in-depth and will never fire under normal catalog constraints. Fine.

- [ISSUE-api-shape: `init_procedure_caches` is called from `_PG_init` but not idempotent (nit)] — If `_PG_init` is somehow re-entered (it shouldn't be, but plpython has no guard), `hash_create` would create a NEW hash and leak the old one. Defense-in-depth would be a static `bool inited = false` guard. Not a real risk — PG's module loader guarantees _PG_init runs once — but flagged for completeness.

- [ISSUE-concurrency: cache is per-backend, no shared cache invalidation (maybe)] — `PLy_procedure_cache` is a process-local HTAB. If backend A has cached function F (xmin=100) and backend B does `CREATE OR REPLACE FUNCTION F` (new xmin=200), backend A's next call to F will: SearchSysCache1 → get new tuple → `PLy_procedure_valid` returns false (xmin mismatch) → delete and rebuild. Correct, but requires the syscache to invalidate too. PG's catalog invalidation machinery (`CacheInvalidateHeapTuple` etc.) handles the syscache side. So the cross-backend invalidation works transitively. Documented because it's not obvious from this file alone.
