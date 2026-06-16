# plpy_plpymodule

Covers `source/src/pl/plpython/plpy_plpymodule.c` (532 LOC) and
`source/src/pl/plpython/plpy_plpymodule.h` (17 LOC).

Pinned to source `4b0bf0788b0`.

## One-line summary

The `plpy` Python module that PL/Python user code does `import plpy` on —
exposes `plpy.execute`, `plpy.prepare`, `plpy.cursor`, the
`plpy.notice/info/warning/error/fatal/debug/log` family, `plpy.quote_*`,
`plpy.subtransaction`, `plpy.commit`/`rollback`, and the dynamic
`plpy.spiexceptions.*` exception classes. This is the chief
**attack-surface entry point** for PL/Python user code.

## Public API

### Top-level `plpy` methods (`plpy_plpymodule.c:55-101`)

| Python name | C function | flags | Notes |
|---|---|---|---|
| `debug`, `log`, `info`, `notice`, `warning`, `error`, `fatal` | `PLy_debug`/`_log`/`_info`/…/`_fatal` | METH_VARARGS \| METH_KEYWORDS | Each is a thin wrapper around `PLy_output(level, …)` (`:251-291`). |
| `prepare(query, [types])` | `PLy_spi_prepare` (in `plpy_spi.c`) | METH_VARARGS | Returns a `PLyPlanObject`. |
| `execute(query_or_plan, [args], [limit])` | `PLy_spi_execute` (in `plpy_spi.c`) | METH_VARARGS | Returns a `PLyResultObject`. Two-form arg parse. |
| `quote_literal(str)` | `PLy_quote_literal` | METH_VARARGS | `:293-308` — wraps `quote_literal_cstr`. NULL → TypeError (`PyArg_ParseTuple "s"` rejects None). |
| `quote_nullable(str_or_None)` | `PLy_quote_nullable` | METH_VARARGS | `:310-328` — accepts None via `"z"` parse; returns the literal string `"NULL"`. |
| `quote_ident(str)` | `PLy_quote_ident` | METH_VARARGS | `:330-344` — wraps `quote_identifier`. |
| `subtransaction()` | `PLy_subtransaction_new` (in `plpy_subxactobject.c`) | METH_NOARGS | Returns a context manager. |
| `cursor(query_or_plan, [args])` | `PLy_cursor` (in `plpy_cursorobject.c`) | METH_VARARGS | Returns a `PLyCursorObject`. |
| `commit()` / `rollback()` | `PLy_commit` / `PLy_rollback` (in `plpy_spi.c`) | METH_NOARGS | DO/PROCEDURE-only; raises if inside an atomic context. |

### Exception classes (`:144-241`)

`PLy_add_exceptions` (`:144-173`) registers:

- `plpy.Error` — base exception (`:150-151`).
- `plpy.Fatal` — for FATAL-level reports (`:152-153`).
- `plpy.SPIError` — base for all SPI errors (`:154-155`).
- `plpy.spiexceptions` submodule — a Python module containing **one
  exception class per SQLSTATE** auto-generated from `errcodes.txt` via
  the `spiexceptions.h` X-macro include (`:50-53`, `:107-119`,
  `:210-241`). Each class has a `.sqlstate` attribute set to the 5-char
  `unpack_sql_state` form (`:226-230`).

A `PLy_spi_exceptions` HTAB (declared `plpy_plpymodule.h:12`,
initialized `:161-164`) maps `int sqlstate → PyObject* exc` so that
`PLy_spi_exception_set` can map a backend ErrorData to the most specific
class.

### Module init (`:125-142`)

`PyInit_plpy(void)` creates the `plpy` module (`PyModule_Create`),
calls `PLy_add_exceptions`, then **initializes the four PG-defined
PyTypes** via `PLy_plan_init_type`, `PLy_result_init_type`,
`PLy_subtransaction_init_type`, `PLy_cursor_init_type`. This is the
single place those PyTypeObjects come to life. Called from
`PyImport_AppendInittab("plpy", PyInit_plpy)` early in plpython startup
(in `plpy_main.c`).

## Key invariants

- **`PyModuleDef.m_size = -1`** (`:110`, `:117`) — module has no
  per-interpreter state; PG runs at most one Python interpreter per
  process anyway.
- **Exception map is fully populated at init.** No exception class is
  created on-demand. `Assert(!found)` at `:238` guarantees no SQLSTATE
  duplicates.
- **Every message before `ereport` is `pg_verifymbstr`'d**
  (`:480-495`). The eight stringly-typed errdata fields (`message`,
  `detail`, `hint`, `column_name`, `constraint_name`, `datatype_name`,
  `table_name`, `schema_name`) are all encoding-validated before
  reaching the ereport.
- **SQLSTATE must be 5 chars from `[0-9A-Z]`** (`:458-468`). Anything
  else raises a Python `ValueError` *before* the ereport — the only
  client-supplied control vector that gates the SQLSTATE the backend
  reports.
- **`PLy_output` uses `errmsg_internal`** (`:499`) — the user-supplied
  message string is treated as opaque and not run through
  `gettext()`. Same for detail (`errdetail_internal`).
- **`PLy_create_exception` adds an extra Py_INCREF** after
  `PyErr_NewException` because `PyModule_AddObject` steals the ref
  (`:191-196`). Without this incref, the returned exception would be
  freed when the module ref drops.

## Notable internals

### `PLy_output` — the elog bridge (`:368-532`)

Handles all seven log levels. The single most complex function in this
file. Key behaviors:

1. **Single-arg vs multi-arg formatting** (`:387-400`). With one arg,
   the value is stringified via `PyObject_Str` directly to avoid
   `('tuple',)` decoration; with N args, the full args tuple is
   stringified, which yields tuple-with-parens output.
2. **Keyword args parsed** (`:411-454`): message, detail, hint,
   sqlstate, schema_name, table_name, column_name, datatype_name,
   constraint_name. Anything else is rejected with `TypeError`
   "'%s' is an invalid keyword argument" (`:447-451`).
3. **`message` passed both positionally and as keyword** is rejected
   with `TypeError` (`:420-424`) — protects against silent override.
4. **SQLSTATE syntax check** at `:458-468` — strict 5-char,
   alphanumeric-uppercase only.
5. **`PG_TRY / PG_CATCH` wraps the `ereport`** (`:478-526`) so that a
   PG longjmp doesn't leave the Python interpreter in a bad state. On
   catch, `CopyErrorData` then `FlushErrorState`, then
   `PLy_exception_set_with_details` turns the errdata into a Python
   exception. `ereport(ERROR, ...)` calls land here.

### `PLy_quote_*` — passthrough wrappers

- `PLy_quote_literal` (`:293-308`): rejects None (`"s"` format), wraps
  `quote_literal_cstr`.
- `PLy_quote_nullable` (`:310-328`): accepts None (`"z"` format), returns
  the literal `"NULL"` for None, else `quote_literal_cstr`.
- `PLy_quote_ident` (`:330-344`): wraps `quote_identifier` (does not
  always quote — only if needed for SQL safety).

These are the documented Python-side mitigations for the
`plpy.execute(text)` SQL-injection surface. The user is expected to do
`plpy.execute("SELECT * FROM " + plpy.quote_ident(table))`. The
preferred safe path is `plpy.prepare` + `plan.execute(args)`.

### Exception generation (`:210-241`)

`spiexceptions.h` is a generated X-macro list of
`{ name, classname, sqlstate }` tuples derived from
`backend/utils/errcodes.txt`. The loop:
1. Creates a Python dict, sets `dict["sqlstate"] = "<5 char code>"`.
2. Calls `PLy_create_exception` with the SPIError base + the dict.
3. Inserts `(sqlstate → exc)` into the `PLy_spi_exceptions` HTAB.

Result: user code can do
`except plpy.spiexceptions.UndefinedTable: ...` and PG looks up the
right class by SQLSTATE on the C side.

## SQL-injection / attack surface

### `plpy.execute(text)` — string injection vector

The text-form path is `PLy_spi_execute → PLy_spi_execute_query` at
`plpy_spi.c:152-170` (sibling file, but the entry point is registered
here at `plpy_plpymodule.c:75`). The text version:

```
PyArg_ParseTuple(args, "s|l", &query, &limit)
…
SPI_execute(query, exec_ctx->curr_proc->fn_readonly, limit)
```

(`plpy_spi.c:159-160`, `:313`)

**Behaviors:**
- The text is `pg_verifymbstr`'d at `plpy_spi.c:312` before being
  handed to SPI.
- Runs under whatever search_path is active for the calling function.
  No injection-specific defenses beyond user calling `quote_ident`/
  `quote_literal`.
- `fn_readonly` is the procedure's volatility — STABLE/IMMUTABLE
  functions get a read-only SPI execute; VOLATILE doesn't.

This is structurally **identical to plpgsql's `exec_stmt_dynexecute`**
(see A9's `pl_exec.md` for the cross-file comparison). The
text-string SQL injection surface exists in both PLs; both expose
quote_ident / quote_literal as the documented mitigation; both also
offer a parameterized alternative (plpgsql `EXECUTE ... USING`,
plpython `plpy.prepare` + `plan.execute(args)`).

### `plpy.prepare(text, [types])` — type-name lookup vector

In `plpy_spi.c:37-145`. The `types[]` list is iterated and each entry
must be a Python str; then `parseTypeString(sptr, &typeId, &typmod, NULL)`
runs (`plpy_spi.c:105`). `parseTypeString` calls the SQL grammar
fragment for typename — supports any syntactic typename, including
schema-qualified ones. Search_path applies. **No allowlist** —
`plpy.prepare("SELECT $1", ["pg_catalog.regclass"])` is fine.

This is a NAME-vs-OID pattern: callers supply a string, server
resolves to OID. A function-creator-defined `search_path` could shadow
a builtin type — but that's the standard plpgsql/SQL gotcha, not
specific to plpython.

### `plpy.notice` / `info` / `warning` / `error` — format-string surface

**No %-substitution.** The arg(s) are `PyObject_Str`'d as opaque
strings (`:397-401`). User-supplied content goes into `errmsg_internal`
as `%s` (`:499`) — never as a format string. So
`plpy.notice("100% off")` is safe; the `%` is harmless.

### `plpy.commit` / `plpy.rollback`

Available only at procedure top level / DO-block. The atomic-context
check lives in `plpy_spi.c`'s `PLy_commit` / `PLy_rollback`; not in
this file.

## Cross-references

- **Siblings (A10):**
  - `plpy_planobject` — `PLyPlanObject` returned by `plpy.prepare`.
  - `plpy_resultobject` — `PLyResultObject` returned by `plpy.execute`.
  - `plpy_cursorobject` — `PLyCursorObject` returned by `plpy.cursor`.
  - `plpy_typeio` — used inside `plpy.prepare` to set up `PLyObToDatum`
    arrays for each declared arg type.
- **Sibling other-A10:**
  - `plpy_spi.c` — defines `PLy_spi_prepare`, `PLy_spi_execute`,
    `PLy_spi_execute_plan`, `PLy_commit`, `PLy_rollback`, and the
    subxact begin/commit/abort helpers used by every SPI entry here.
  - `plpy_subxactobject.c` — `PLy_subtransaction_new`,
    `PLy_subtransaction_init_type`.
  - `plpy_elog.c` — `PLy_elog`, `PLy_exception_set`,
    `PLy_exception_set_plural`, `PLy_exception_set_with_details`.
  - `plpy_main.c` — calls `PyImport_AppendInittab("plpy",
    PyInit_plpy)` so `import plpy` works.
- **Backend dependencies:**
  - `utils/adt/quote.c` — `quote_literal_cstr`, `quote_identifier`.
  - `utils/errcodes.txt` → `spiexceptions.h` (generated).
  - `utils/elog.c` — ereport, errcode, errmsg_internal,
    errdetail_internal, err_generic_string, MAKE_SQLSTATE.
  - `mb/pg_wchar.c` — `pg_verifymbstr`.
  - `utils/hash/dynahash.c` — `hash_create`, `hash_search`.

<!-- issues:auto:begin -->
- [Issue register — `plpython`](../../../../issues/plpython.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-security: `plpy.execute(text)` runs arbitrary SQL with the
  caller's privileges and current search_path; no parameterization on
  the text-form path (confirmed, by-design)] — `plpy_plpymodule.c:75`,
  `plpy_spi.c:296-335`. This is documented behavior and matches
  plpgsql `EXECUTE format(...)`. Mitigations are `quote_ident`/
  `quote_literal` / `plpy.prepare`. Worth flagging in the A10
  cross-file review because it's structurally identical to A9's
  `exec_stmt_dynexecute` surface.
- [ISSUE-defense-in-depth: `plpy.prepare` resolves type names against
  current search_path with no allowlist (maybe)] — `plpy_spi.c:105`.
  Same posture as SQL `DECLARE x %TYPE` and plpgsql `EXECUTE … USING`;
  consistent with the rest of the system.
- [ISSUE-correctness: `PLy_output` passes user-supplied message via
  `errmsg_internal` not `errmsg` (likely intentional)] —
  `plpy_plpymodule.c:499`. Means no translation lookup; arguably right
  because the message comes from user Python code. But the docs are
  silent on this.
- [ISSUE-error-handling: SQLSTATE "00000" passes the syntactic check
  at `:458-468` and would be sent through `MAKE_SQLSTATE` (nit)] —
  Result is `errcode(0)` which is "successful completion" — odd for an
  `ERROR`-level ereport. Probably caught downstream by elog assertions
  but no explicit reject.
- [ISSUE-audit-gap: no rate-limit / size-limit on `PLy_output`
  arguments (nit)] — A malicious function could `plpy.error("x" *
  10**9)`. Hits palloc MaxAllocSize eventually, but no early reject.
- [ISSUE-documentation: `decimal_constructor` import precedence is
  documented in `plpy_typeio.c` but not surfaced here (nit, doc)] —
  cross-file detail.
