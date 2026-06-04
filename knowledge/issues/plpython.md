# Issues — `pl/python` (src/pl/plpython/)

Per-subsystem issue register for the **PL/Python procedural language**
— **untrusted-only by design** (`plpython3u`); there is no trusted
variant because Python's stdlib is too dynamically reflective to
safely subset (no Safe.pm analogue). The defense is `superuser = true`
at `CREATE EXTENSION plpython3u`.

**Parent docs:** `knowledge/files/src/pl/plpython/*` (14 docs covering
26 source files: most .c/.h module pairs combined into a single
module-named doc per A9's `pl_kwlists.md` precedent).

**Source:** 51 entries (combined from A10-2 + A10-3 + A10-4 partial)
surfaced 2026-06-04 by the A10 foreground sweep. Mirrored in the
per-file doc's `## Issues spotted` block.

## The headlines (vs A9 plpgsql + A10 plperl baselines)

1. **PL/Python is the ASYMMETRIC OUTLIER — untrusted only.** plpgsql
   (A9) is trusted because the language literally cannot do I/O
   (no file, socket, shell — just SQL via SPI). plperl (A10-1) is
   dual-posture (opcode-mask sandbox for plperl; superuser-only
   plperlu). plpython has no `plpython3` trusted variant because
   Python's `import`-based stdlib, `__builtins__`, getattr, and
   ctypes escape vectors make a Safe.pm analogue effectively
   impossible. The design choice was "no trusted Python, ever;
   gate everything on `superuser = true` in `plpython3u.control`
   at CREATE EXTENSION time". After that gate, any role with USAGE
   on `plpython3u` can write functions that have full filesystem +
   network access at the backend's UID.

2. **One Python interpreter per backend, never finalized.**
   `_PG_init` calls `Py_Initialize` once and `Py_Finalize` never
   (`plpy_main.c:70`). `sys.modules` mutations, monkey-patches, and
   `ctypes` loads persist across every plpython call on that backend
   for its entire lifetime. **Dramatically amplified by transaction-
   pooling connection multiplexers** — a function on connection A
   monkey-patches `os.open`; connection B (pooled to same backend)
   inherits the patch. plperl mitigates this somewhat with per-UID
   interpreter cache; plpython does not.

3. **GIL held continuously across SPI calls.** No
   `Py_BEGIN_ALLOW_THREADS` anywhere in plpy_main / plpy_exec / plpy_spi
   — the GIL is acquired at function entry and held through every
   `SPI_execute`, `SPI_cursor_open`, `SPI_prepare`. Python threads
   inside a function cannot productively run during SPI. Backend-
   wide latency hit if a plpython function spawns threads.

4. **`plpy.execute(text)` injection surface = plpgsql injection ∪
   every PG type's `_in()` function.** The text-form `plpy.execute`
   (`plpy_spi.c:296-335`) is structurally identical to plpgsql
   `exec_stmt_dynexecute` — no parameterization, straight to
   `SPI_execute`. PLUS the entire scalar-return path means every PG
   type's `_in()` is reachable from a Python return value via
   `PLyObject_ToScalar` (`plpy_typeio.c:1077-1096`). Combined attack
   surface is broader than plpgsql.

5. **`PLy_cursor_plan` is missing the `is_PLyPlanObject` check**
   that `PLy_spi_execute` has (`plpy_cursorobject.c:88-89, :185`
   vs `plpy_spi.c:165`). The text-fallback `"O|O"` parse accepts
   any PyObject as a "plan." Worth a focused trace to verify
   reachability — if reachable, this is a confused-pointer-
   dereference bug. **The most concrete Phase D finding from A10.**

6. **`plpy.subtransaction()` differs from plpgsql `EXCEPTION` in
   error-swallowing semantics** — Python `try/except` inside `with
   plpy.subtransaction():` swallows the exception → **subxact
   COMMITS** (`plpy_subxactobject.c:178-186`). plpgsql `WHEN OTHERS`
   forces rollback. Documented behavior, but a real cross-PL footgun
   for users porting code.

7. **`PLy_get_sqlerrcode` accepts non-real SQLSTATEs** like "ZZZZZZ"
   (`plpy_elog.c:371-376`) — validator checks char range only, not
   the SQLSTATE registry. SECURITY DEFINER functions can propagate
   nonsense SQLSTATEs to clients.

8. **Validator gap is real on plpython.** `_PG_init` calls
   `PLy_elog(FATAL, ...)` if `PyErr_Occurred()` after init
   (`plpy_main.c:98-99`) — a corrupted Python install turns
   `CREATE EXTENSION` into backend FATAL with opaque "untrapped
   error in initialization". And validator runs full
   `Py_CompileString + PyEval_EvalCode` on user source under definer
   privs (`plpy_main.c:124-138`, via `PLy_procedure_compile`) —
   currently safe because munge wraps user source as function body;
   a future patch allowing module-level statements would turn
   CREATE FUNCTION into RCE gated only on `check_function_bodies`.

## Cross-sweep references

- **Per-PL trust-gate ranking**: plpgsql (nothing) < plpython
  (superuser-only CREATE EXTENSION) < plperl (opcode-mask, drift-
  prone) < pltcl (Tcl Safe slave interp at C-dispatch level).
- **NAME-vs-OID cluster**: `plpy.prepare` resolves argument types via
  `parseTypeString` honoring current `search_path`
  (`plpy_spi.c:105`) — joins A3+A6+A7+A8+A9. SECURITY DEFINER
  without pinned search_path picks caller-controlled type OIDs.
- **Session-cache-staleness cluster (from A9)** — plpython procedure
  cache (`plpy_procedure.c:430-442`) uses xmin/tid invalidation only;
  ignores `pg_proc.proconfig` and role-setting changes. Same posture
  as plpgsql.

---

## Entries (51 total, grouped by file/module)

### plpython.h (41 LOC)

(no issues — pure scaffolding header)

### plpython_system.h (55 LOC)

- [ISSUE-documentation: `system_header` pragma only fires on
  GCC/clang, not MSVC (nit)] —
  `source/src/pl/plpython/plpython_system.h:26-28` — MSVC plpython
  builds get no Python-header warning suppression.

### plpy_main.c + plpy_main.h (388 + 31 LOC)

- [ISSUE-api-shape: `SPI_finish()` lives in plpy_exec.c instead of
  plpy_main.c (maybe)] —
  `source/src/pl/plpython/plpy_main.c:155,229` — flagged in-source
  as "dubious design"; split SPI lifecycle across files is a foot-
  gun for new handler arms.
- [ISSUE-security: one Python interpreter per backend = persistent
  state across functions (likely)] —
  `source/src/pl/plpython/plpy_main.c:70` — no `Py_Finalize`;
  `sys.modules` patches, monkey-patched `os.open`, ctypes loads
  persist for the backend's lifetime; amplified by transaction-
  poolers.
- [ISSUE-concurrency: GIL held continuously during plpython
  invocation, including SPI calls (maybe)] —
  `source/src/pl/plpython/plpy_main.c` — no
  `Py_BEGIN_ALLOW_THREADS` anywhere; Python threads inside a
  function cannot productively run during SPI.
- [ISSUE-error-handling: `_PG_init` calls `PLy_elog(FATAL, ...)` if
  `PyErr_Occurred()` after init (likely)] —
  `source/src/pl/plpython/plpy_main.c:98-99` — corrupted Python
  install turns `CREATE EXTENSION` into backend FATAL with opaque
  "untrapped error in initialization".
- [ISSUE-audit-gap: `_PG_init` retains permanent refcount on
  `main_dict` with no DECREF (nit)] —
  `source/src/pl/plpython/plpy_main.c:101-102` — intentional
  (lifetime = backend) but a future teardown path would need to
  pair this.
- [ISSUE-defense-in-depth: validator runs full Py_CompileString +
  PyEval_EvalCode on user source under definer privs (maybe)] —
  `source/src/pl/plpython/plpy_main.c:124-138` (via
  `PLy_procedure_compile`) — currently safe because munge wraps user
  source as function body; a future patch allowing module-level
  statements would turn CREATE FUNCTION into RCE gated only on
  `check_function_bodies`.

### plpy_elog.c + plpy_elog.h (618 + 46 LOC)

- [ISSUE-correctness: `PLy_get_sqlerrcode` accepts non-real SQLSTATE
  strings like "ZZZZZ" (likely)] —
  `source/src/pl/plpython/plpy_elog.c:371-376` — validator only
  checks char range, not real SQLSTATE registry; user-supplied
  SQLSTATEs propagate to clients.
- [ISSUE-security: SECURITY DEFINER plpython function leaks source
  line to invoker via traceback (maybe)] —
  `source/src/pl/plpython/plpy_elog.c:316-322` — `get_source_line`
  from `proc->src` appended to errcontext; comparable to plpgsql
  but worth a corpus call-out.
- [ISSUE-error-handling: `elog(ERROR, ...)` inside the traceback
  walk; refcount discipline depends on order (nit)] —
  `source/src/pl/plpython/plpy_elog.c:252-268` — current code is
  safe but a refactor that moves the elog after multiple successful
  GetAttrString calls could leak per-frame Python refs.
- [ISSUE-defense-in-depth: 1024-byte fixed buffer truncates
  exception messages (nit)] —
  `source/src/pl/plpython/plpy_elog.c:492,508` —
  `PLy_exception_set{,_plural}` use stack `char buf[1024]`; long
  messages truncated silently.
- [ISSUE-correctness: `PyArg_ParseTuple(spidata, "izzzizzzzz",
  ...)` return value unchecked (maybe)] —
  `source/src/pl/plpython/plpy_elog.c:401-405` — a corrupted
  `spidata` tuple leaves outputs partially set with no error
  propagation.
- [ISSUE-audit-gap: traceback walk reassigns `tb` before DECREF;
  relies on parent-frame refcount (audit-gap)] —
  `source/src/pl/plpython/plpy_elog.c:336-348` — correct but subtle;
  flagged for future refactors.

### plpy_exec.c + plpy_exec.h (1161 + 14 LOC)

- [ISSUE-correctness: NEW row in BEFORE trigger hides generated
  columns, but MODIFY rebuild via PLy_modify_tuple preserves OLD
  generated values (likely)] —
  `source/src/pl/plpython/plpy_exec.c:844-845,1061` — asymmetry
  between hidden-from-NEW-dict and preserved-from-OLD-tuple.
- [ISSUE-error-handling: SRF cleanup callback fires on memory
  context reset without Python error-state handling (maybe)] —
  `source/src/pl/plpython/plpy_exec.c:721-733` — iterator `__del__`
  exceptions silently discarded.
- [ISSUE-security: trigger `tg_args` from catalog interpolated into
  Python without escaping (nit)] —
  `source/src/pl/plpython/plpy_exec.c:931-940` — catalog data is
  creator-controlled; not a security vector, but malformed UTF-8 in
  tgargs fails the trigger.
- [ISSUE-memory: PLySavedArgs FLEXIBLE_ARRAY_MEMBER allocation with
  nargs=0 still allocates header (nit)] —
  `source/src/pl/plpython/plpy_exec.c:545-547` — correct flexible-
  array idiom; documented edge case.
- [ISSUE-concurrency: SRF iterator persistence across interleaved
  plpython calls in same backend (likely)] —
  `source/src/pl/plpython/plpy_exec.c:83-181` — single Python
  interpreter means another function's globals mutations are
  visible to a mid-iteration SRF's next call.
- [ISSUE-audit-gap: `plpython_return_error_callback` calls
  `PLy_current_execution_context()` which can elog(ERROR) (maybe)] —
  `source/src/pl/plpython/plpy_exec.c:735-743` — unreachable in
  practice; flagged for any future refactor that moves the exec_ctx
  pop earlier.
- [ISSUE-correctness: `SPI_finish() != SPI_OK_FINISH` collapses two
  failure modes into one message (nit)] —
  `source/src/pl/plpython/plpy_exec.c:190,376,463` — loses caller-
  bug-vs-internal distinction.

### plpy_procedure.c + plpy_procedure.h (487 + 82 LOC)

- [ISSUE-defense-in-depth: source mangling assumes NUL-terminated
  source; embedded `'\0'` truncates (likely)] —
  `source/src/pl/plpython/plpy_procedure.c:465-478` — relies on
  catalog (scan.l) rejecting nulls upstream.
- [ISSUE-correctness: source-line numbers off by 1 due to munge
  prefix; compensated cross-file in plpy_elog.c (confirmed)] —
  `source/src/pl/plpython/plpy_procedure.c:459` (prefix),
  `plpy_elog.c:294-298` (`plain_lineno - 1`) — coupling tripwire if
  munge prefix grows.
- [ISSUE-memory: `MemoryContextSetIdentifier(cxt, proc->proname)`
  borrows pointer into the context it describes (nit)] —
  `source/src/pl/plpython/plpy_procedure.c:192` — safe but no copy.
- [ISSUE-audit-gap: cache validity ignores `pg_proc.proconfig` and
  rolesetting changes (maybe)] —
  `source/src/pl/plpython/plpy_procedure.c:430-442` — only xmin/tid;
  correct but commonly surprising.
- [ISSUE-correctness: `procName[NAMEDATALEN + 256]` overflow check
  unreachable under catalog constraints (nit)] —
  `source/src/pl/plpython/plpy_procedure.c:157-162` — defense-in-
  depth.
- [ISSUE-api-shape: `init_procedure_caches` not idempotent against
  re-entry (nit)] —
  `source/src/pl/plpython/plpy_procedure.c:30-38` — no guard, but
  `_PG_init` invariant means re-entry should never happen.
- [ISSUE-concurrency: cache is per-backend; cross-backend
  invalidation works only via syscache (maybe)] —
  `source/src/pl/plpython/plpy_procedure.c` — relies on
  CacheInvalidateHeapTuple flowing through syscache; not obvious
  from this file alone.

### plpy_typeio.c + plpy_typeio.h (1561 + 175 LOC)

- [ISSUE-defense-in-depth: bytea length comes straight from
  `PyBytes_Size` with no explicit MaxAllocSize pre-check (nit)] —
  `source/src/pl/plpython/plpy_typeio.c:921` — palloc throws if too
  big, but error site is generic palloc not domain-appropriate
  ereport.
- [ISSUE-correctness: transform-function return reinterpret-cast
  with no type-tag verification (maybe)] —
  `source/src/pl/plpython/plpy_typeio.c:660`, `:1129` —
  `(PyObject *) DatumGetPointer(t)` accepts any pointer; mitigated
  by superuser-only CREATE TRANSFORM.
- [ISSUE-audit-gap: no plpython-specific JSON/JSONB handling; whole
  JSON path inherits jsonb_in stack-guard recursion (maybe)] —
  `source/src/pl/plpython/plpy_typeio.c:535-540` — default scalar
  fallthrough; cross-cite with jsonb_in CVE history.
- [ISSUE-documentation: cdecimal fallback unreachable under Python 3
  (nit)] — `source/src/pl/plpython/plpy_typeio.c:577-586`.
- [ISSUE-memory: `decimal_constructor` cached in static PyObject*
  with no shutdown decref (nit)] —
  `source/src/pl/plpython/plpy_typeio.c:572`.
- [ISSUE-api-shape: `PLy_input_setup_func` silently strips domain
  identity on input but preserves it on output (documentation)] —
  `source/src/pl/plpython/plpy_typeio.c:465-471`. Comment
  acknowledges "somewhat historical" asymmetry.
- [ISSUE-error-handling: `PLyObject_AsString` `slen > plen` branch
  uses `elog` not `ereport` (nit)] —
  `source/src/pl/plpython/plpy_typeio.c:1066` — "can't happen" path
  so consistent with style.

### plpy_plpymodule.c + plpy_plpymodule.h (532 + 17 LOC)

- [ISSUE-security: `plpy.execute(text)` runs arbitrary SQL with
  caller privileges and current search_path; no parameterization on
  text form (confirmed, by-design)] —
  `source/src/pl/plpython/plpy_plpymodule.c:75` →
  `source/src/pl/plpython/plpy_spi.c:296-335` — structurally
  identical to A9 plpgsql `exec_stmt_dynexecute`.
- [ISSUE-defense-in-depth: `plpy.prepare` resolves type names
  against current search_path with no allowlist (maybe)] —
  `source/src/pl/plpython/plpy_spi.c:105` — NAME-vs-OID pattern;
  consistent with rest of system.
- [ISSUE-correctness: `PLy_output` passes user-supplied message via
  `errmsg_internal` (no gettext) — intentional but undocumented
  (likely)] — `source/src/pl/plpython/plpy_plpymodule.c:499`.
- [ISSUE-error-handling: SQLSTATE "00000" syntactically passes
  validation but means "successful completion" — odd at ERROR
  level (nit)] —
  `source/src/pl/plpython/plpy_plpymodule.c:458-468`.
- [ISSUE-audit-gap: no size limit on `PLy_output` arguments;
  `plpy.error("x"*10**9)` hits palloc deep (nit)] —
  `source/src/pl/plpython/plpy_plpymodule.c:407`.

### plpy_resultobject.c + plpy_resultobject.h (281 + 27 LOC)

- [ISSUE-api-shape: `result["colname"]` doesn't work; users must
  do `result[i]["colname"]` (documentation)] —
  `source/src/pl/plpython/plpy_resultobject.c:267-273` — counter-
  intuitive given the name.
- [ISSUE-correctness: `nrows` initialized to PyLong(-1) sentinel
  but never checked by callers (nit)] —
  `source/src/pl/plpython/plpy_resultobject.c:104` — relies on
  `_fetch_result` always overwriting.
- [ISSUE-defense-in-depth: `Py_mp_ass_subscript` slot allows
  mutating `result.rows` from Python (nit, by-design)] —
  `source/src/pl/plpython/plpy_resultobject.c:275-281`.

### plpy_planobject.c + plpy_planobject.h (151 + 26 LOC)

- [ISSUE-correctness: `PLy_cursor` text-vs-plan fallback at cursor
  entry accepts any PyObject as a "plan" without
  `is_PLyPlanObject` check before cast (likely)] —
  `source/src/pl/plpython/plpy_cursorobject.c:88-89, :185` —
  `PLy_spi_execute` guards with `is_PLyPlanObject` at
  `source/src/pl/plpython/plpy_spi.c:165`; asymmetric.
- [ISSUE-api-shape: `PLy_plan_status` is a no-op stub returning
  `Py_True` (nit, documentation)] —
  `source/src/pl/plpython/plpy_planobject.c:141-151` — commented-
  out `self->status` line is dead code.
- [ISSUE-defense-in-depth: no `Py_tp_str`/`Py_tp_repr` slot —
  `repr(plan)` is the generic Python default (nit)] —
  `source/src/pl/plpython/plpy_planobject.c:29-43`.

### plpy_cursorobject.c + plpy_cursorobject.h (520 + 24 LOC)

- [ISSUE-correctness: `PLy_cursor_plan` casts `ob` to
  `PLyPlanObject*` without `is_PLyPlanObject(ob)` check;
  reachable via `PLy_cursor` `"O|O"` fallback (likely)] —
  `source/src/pl/plpython/plpy_cursorobject.c:88-89, :185` — same
  finding as the planobject ISSUE; flagged in both for cross-
  reference. **Most concrete Phase D candidate from A10.**
- [ISSUE-documentation: cursor-after-commit yields "aborted
  subtransaction" error wording even on explicit `plpy.commit()`
  (nit)] —
  `source/src/pl/plpython/plpy_cursorobject.c:357, :423, :510` —
  misleading.
- [ISSUE-defense-in-depth: text-form `plpy.cursor(text)` is
  unparameterized (`SPI_prepare(query, 0, NULL)`); user must
  `quote_*` (by-design)] —
  `source/src/pl/plpython/plpy_cursorobject.c:133` — identical
  posture to `plpy.execute(text)`.
- [ISSUE-defense-in-depth: cursor portals not `WITH HOLD`; survive
  subxact rollback only via name-based detection (by-design)] —
  affects procedures mixing `plpy.commit()` with open cursors.
- [ISSUE-memory: cursor mcxt under `TopMemoryContext` released only
  on Python dealloc; reference cycles can delay (nit)] —
  `source/src/pl/plpython/plpy_cursorobject.c:112-114, :213-215`.
- [ISSUE-error-handling: `PLy_cursor_query` calls `SPI_freeplan`
  *after* `SPI_cursor_open`; if open longjmps, freeplan never runs
  (nit)] —
  `source/src/pl/plpython/plpy_cursorobject.c:138-140` — harmless
  because subxact abort cleans up, but the shape is unusual.

### plpy_spi.c + plpy_spi.h (656 + 29 LOC)

- [ISSUE-security: `plpy.execute(text)` passes its argument straight
  to `SPI_execute` with no parameterization (likely)] —
  `source/src/pl/plpython/plpy_spi.c:296-335` — text-execute path is
  a SQLi sink unless caller wraps with `plpy.quote_literal`; mirrors
  plpgsql `EXECUTE`.
- [ISSUE-security: `plpy.prepare` resolves argument types via
  `parseTypeString` honoring current `search_path` (likely)] —
  `source/src/pl/plpython/plpy_spi.c:105` — SECURITY DEFINER without
  pinned search_path picks caller-controlled type OIDs.
- [ISSUE-correctness: 32-bit `Py_ssize_t` row-count overflow caught
  defensively (nit)] —
  `source/src/pl/plpython/plpy_spi.c:388-391` — guarded by
  `ereport(ERROR)` inside PG_TRY; cleanup correct, just noting.
- [ISSUE-error-handling: `PLy_spi_exception_set` failure path
  `elog(ERROR)`s after the outer subxact has flushed error state
  (likely)] — `source/src/pl/plpython/plpy_spi.c:651-655` — second
  elog inside already-aborted subxact; hard to trigger.
- [ISSUE-defense-in-depth: `pg_verifymbstr(false)` re-validates
  already-encoded query strings (nit)] —
  `source/src/pl/plpython/plpy_spi.c:121, 312` — paranoid but adds
  linear cost.
- [ISSUE-audit-gap: no plpython-specific audit trail for
  execute/prepare beyond what SPI logs (audit-gap, maybe)] —
  `source/src/pl/plpython/plpy_spi.c:296-335` — Phase D
  consideration.

### plpy_util.c + plpy_util.h (119 + 17 LOC)

- [ISSUE-memory: `PLyUnicode_AsString` doubles allocator pressure
  (nit)] — `source/src/pl/plpython/plpy_util.c:80-88` —
  PyUnicode→bytes→pstrdup; measurable on hot loops with large
  values.
- [ISSUE-correctness: embedded NUL handling silently truncates at
  strlen boundary (likely)] —
  `source/src/pl/plpython/plpy_util.c:65, 84` — `strlen(encoded)`
  ignores bytes past first NUL; benign for normal TEXT but data
  loss for Python str containing `\x00`.
- [ISSUE-defense-in-depth: no length cap on input — multi-GB strings
  hit backend OOM (audit-gap, maybe)] —
  `source/src/pl/plpython/plpy_util.c:18-73` — only natural limit is
  MaxAllocSize.
- [ISSUE-api-shape: `PLyUnicode_Bytes` returns bytes that most
  callers immediately stringify (nit)] —
  `source/src/pl/plpython/plpy_util.c:18-73` — bytes intermediate
  could be elided in `_AsString` micro-fast-path.

### plpy_subxactobject.c + plpy_subxactobject.h (196 + 33 LOC)

- [ISSUE-correctness: Python `try/except` inside `with` swallows
  exception → subxact COMMITS (likely, by design)] —
  `source/src/pl/plpython/plpy_subxactobject.c:178-186` — differs
  from plpgsql `EXCEPTION` which forces rollback; documented
  behavior worth a guide note.
- [ISSUE-error-handling: `__enter__` does NOT wrap
  `BeginInternalSubTransaction` in PG_TRY (likely)] —
  `source/src/pl/plpython/plpy_subxactobject.c:122` — extremely
  unlikely failure mode; leaves `subxactdata` leaked in
  `TopTransactionContext` (bounded).
- [ISSUE-error-handling: `__exit__` does NOT wrap `Release`/`Rollback`
  calls in PG_TRY (likely)] —
  `source/src/pl/plpython/plpy_subxactobject.c:181-186` —
  asymmetric vs `plpy_spi.c`'s subxact_abort helper; intentional but
  worth flagging.
- [ISSUE-audit-gap: `explicit_subtransactions` is backend-global,
  not per-function (nit)] —
  `source/src/pl/plpython/plpy_subxactobject.c:15` — static analysis
  can't prove `with`-vs-`BeginInternalSubTransaction` 1:1 across
  function boundaries.
