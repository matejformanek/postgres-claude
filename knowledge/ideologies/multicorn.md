# multicorn — an FDW that embeds a CPython interpreter into the backend and turns the entire `FdwRoutine` callback set into virtual-method dispatch on a user-authored Python `ForeignDataWrapper` subclass

> Ideology note produced by the `pg-extension-anthropologist` routine.
> Repo: `pgsql-io/multicorn2` @ branch `main` — Multicorn2, the maintained
> (PG12–18) fork of the archived `Kozea/Multicorn`. All `file:line` cites below
> point into `pgsql-io/multicorn2` (not `source/`), since this doc characterizes
> an *external* extension's divergence from core idioms. Cites verified against
> files fetched via `raw.githubusercontent.com` on 2026-07-16 (see Sources
> footer).
> Read alongside [[wrappers]] (the same idea in Rust/pgrx) and [[pgrx]].

## Domain & purpose

Multicorn2 is "a Python3 Foreign Data Wrapper (FDW) for PostgreSQL" that "allows
you to fetch foreign data in Python in your PostgreSQL server"
(`README.md:5`, `README.md:12`) `[from-README]`. It is a *framework*, not a
single data source: you subclass one Python base class,
`multicorn.ForeignDataWrapper` (`python/multicorn/__init__.py:147`), implement a
handful of methods (`execute`, `insert`, `update`, `delete`, `get_rel_size`,
`can_sort`, `can_limit`, …), name your class in a `CREATE SERVER … OPTIONS
(wrapper 'my.module.Class')`, and Multicorn's C shim routes every PostgreSQL FDW
callback into a method call on an instance of your class. `[verified-by-code]`

The distribution ships in two halves (`README.md:18-30`) `[from-README]`:

- a Python package (`python/multicorn/__init__.py`) providing the
  `ForeignDataWrapper` base class users subclass;
- **two** shared libraries — `multicorn.so`, "a generic Postgres FDW extension
  which interfaces between Postgres and your custom FDW", and `_utils.so`, a
  CPython extension supporting `utils.py` (`README.md:25-30`) `[from-README]`.

The control file marks the extension relocatable and points at
`$libdir/multicorn` (`multicorn.control:3-4`) `[verified-by-code]`.

This is the maintained fork. The original `Kozea/Multicorn` is archived; this
`pgsql-io/multicorn2` line adds PG14–18 support, Python 3.9–3.13 testing, and
LIMIT/OFFSET pushdown ("Our latest release is v3.2 and it supports basic
pushdown for offset/limit", `README.md:5-8`) `[from-README]`.

The direct analog in the corpus is [[wrappers]], which expresses the *same*
"write a data source without touching `FdwRoutine`" idea as a safe-Rust trait
compiled with [[pgrx]]. Multicorn's twist is that the guest language is
*interpreted CPython embedded in the backend process*, not compiled Rust. Where
[[oracle_fdw]], [[sqlite_fdw]], and [[steampipe_postgres_fdw]] are each one FDW
written in C/Go against a specific remote, Multicorn is a polyglot host: any
Python object that yields rows becomes a foreign table.

## How it hooks into PG

**Handler + validator.** The two SQL-facing entry points are declared with
`PG_FUNCTION_INFO_V1(multicorn_handler)` and
`PG_FUNCTION_INFO_V1(multicorn_validator)` (`src/multicorn.c:42-43`)
`[verified-by-code]`. `CREATE FOREIGN DATA WRAPPER multicorn HANDLER
multicorn_handler VALIDATOR multicorn_validator` wires them in. `multicorn_handler`
allocates an `FdwRoutine` node and fills every callback slot
(`src/multicorn.c:184-219`) `[verified-by-code]`:

- Plan phase: `GetForeignRelSize`, `GetForeignPaths`, `GetForeignUpperPaths`,
  `GetForeignPlan`, `ExplainForeignScan` (`src/multicorn.c:190-194`).
- Scan phase: `BeginForeignScan`, `IterateForeignScan`, `ReScanForeignScan`,
  `EndForeignScan` (`src/multicorn.c:197-200`).
- Writable API: `AddForeignUpdateTargets`, `PlanForeignModify`,
  `BeginForeignModify`, `ExecForeignInsert`, `ExecForeignDelete`,
  `ExecForeignUpdate`, `EndForeignModify` (`src/multicorn.c:202-209`).
- PG14+: `GetForeignModifyBatchSize` + `ExecForeignBatchInsert`
  (`src/multicorn.c:211-214`), and `ImportForeignSchema`
  (`src/multicorn.c:216`). `[verified-by-code]`

**The `wrapper` OPTION names the Python class.** The validator only accepts
`wrapper` on a *server* (or FDW), never on a table — "Only at server creation can
we set the wrapper, for security issues" (`src/multicorn.c:234-247`)
`[verified-by-code]`. At server creation it imports the class eagerly to
validate it: `getClassString(className)` then `errorCheck()`
(`src/multicorn.c:256-258`) `[verified-by-code]`. The class string is resolved on
the Python side by `get_class(module_path)`, which splits the dotted path,
imports the module, and `getattr`s the final component
(`python/multicorn/__init__.py:578-595`) `[verified-by-code]`; the C side calls
`multicorn.get_class` via `PyObject_CallMethod` in `getClass`
(`src/python.c:206-215`) `[verified-by-code]`.

**Interpreter init timing.** `Py_Initialize()` runs once per backend inside
`_PG_init` (`src/multicorn.c:160`); `_PG_fini` calls `Py_Finalize()`
(`src/multicorn.c:177-181`) `[verified-by-code]`. Because PG uses a
per-connection fork model, every backend that loads `multicorn.so` gets its own
fresh CPython interpreter. `_PG_init` also *tries* to bootstrap PL/Python's `plpy`
module via `load_external_function("plpython3", "PyInit_plpy", …)` inside a
`PG_TRY`/`PG_CATCH`, silently skipping it if plpython3 is absent
(`src/multicorn.c:149-162`) `[verified-by-code]`. It then registers transaction
and subtransaction callbacks (`RegisterXactCallback` /
`RegisterSubXactCallback`, `src/multicorn.c:163-164`) and creates the global
`InstancesHash` oid→instance hash table in `CacheMemoryContext`
(`src/multicorn.c:166-173`) `[verified-by-code]`.

**Per-table instance caching.** Each foreign table's Python object is
constructed once and cached in `InstancesHash` keyed by table oid. `getCacheEntry`
looks up the entry; on miss (or when OPTIONS/columns changed) it rebuilds the
instance by calling the class with `(options_dict, columns_dict)` via
`PyObject_CallFunction(p_class, "(O,O)", p_options, p_columns)`
(`src/python.c:620-649`) `[verified-by-code]`. The constructor's signature is
`__init__(self, fdw_options, fdw_columns)`
(`python/multicorn/__init__.py:156-169`) `[verified-by-code]`. `getInstance`
wraps `getCacheEntry` and `Py_INCREF`s before handing the borrowed reference out
(`src/python.c:672-678`) `[verified-by-code]`.

**Per-scan ExecState.** Plan state (`MulticornPlanState`) is built in
`GetForeignRelSize` (`src/multicorn.c:274-350`), serialized into a `List` of
`Const` nodes by `serializePlanState` (`src/multicorn.c:1338-1358`), carried
through `make_foreignscan`'s `fdw_private` (`src/multicorn.c:641-649`), and
rehydrated into a `MulticornExecState` by `initializeExecState` in
`BeginForeignScan` (`src/multicorn.c:1364-1386`, `src/multicorn.c:681-707`)
`[verified-by-code]`. The three state structs (`MulticornPlanState`,
`MulticornExecState`, `MulticornModifyState`) are defined in
`src/multicorn.h:72-133` `[verified-by-code]`.

## Where it diverges from core idioms

### 1. A CPython interpreter lives inside the backend

The single most un-Postgres thing here: `Py_Initialize()` embeds a full CPython
runtime in the backend address space (`src/multicorn.c:160`) `[verified-by-code]`.
`postgres_fdw` compiles its remote logic into the same `.so` as C; [[wrappers]]
compiles a Rust trait impl; Multicorn instead *interprets* user Python at query
time. Every row of every scan crosses the C↔Python boundary. The FDW author
writes no C at all — the divergence is that the "wrapper" is a runtime-loaded,
duck-typed Python class resolved from a string
(`python/multicorn/__init__.py:578-595`) `[verified-by-code]`.

### 2. No explicit GIL / thread-state management

Multicorn calls `Py_Initialize()` and thereafter uses the CPython API directly
(`PyObject_CallMethod`, `PyIter_Next`, `Py_DECREF`, …) with **no**
`PyGILState_Ensure`/`Release`, no `PyEval_SaveThread`, no sub-interpreters — a
grep of the C sources finds only the single `Py_Initialize` call and no GIL/thread
primitives `[verified-by-code]`. This is safe *only* because each PG backend is a
single OS thread that holds the GIL implicitly for the life of the process; it is
exactly why Multicorn is fundamentally one-interpreter-per-backend and cannot
coexist with PL/Python as of Python 3.12 (`README.md:123-127`, issue #60)
`[from-README]`. Contrast [[wrappers]], which has no interpreter and no GIL to
worry about.

### 3. Datum ⇄ PyObject conversion for every value, both directions

There is no shared representation: each column value is marshaled across the
boundary individually.

- **Datum → PyObject** goes through `datumToPython`, a per-type-OID switch
  (BYTEA, TEXT/VARCHAR, BPCHAR, NUMERIC, DATE, TIMESTAMP, INT4) with an array
  fallback and an "unknown" catch-all that routes through the type's output
  function (`src/python.c:1522-1561`) `[verified-by-code]`. Arrays iterate with
  `array_create_iterator`/`array_iterate` and recurse into `datumToPython` on the
  element type (`src/python.c:1472-1510`) `[verified-by-code]`.
- **PyObject → Datum** goes through `pyobjectToDatum`, which stringifies the
  Python object into a `StringInfo` and then calls the type's *input function*
  (`InputFunctionCall`), with a fast path for BYTEA/TEXT/VARCHAR
  (`src/python.c:1338-1368`) `[verified-by-code]`. Rows come back as either a
  sequence or a mapping: `pythonResultToTuple` dispatches on
  `PySequence_Check` vs `PyMapping_Check` and errors otherwise
  (`src/python.c:1314-1336`) `[verified-by-code]`; `pythonSequenceToTuple` walks
  attributes and fills `slot->tts_values`/`tts_isnull`
  (`src/python.c:1265-1313`) `[verified-by-code]`. The conversion metadata
  (`ConversionInfo`: in/out `FmgrInfo`, type oid, ioparam, typmod, is_array)
  lives per column (`src/multicorn.h:51-63`) `[verified-by-code]`.

`postgres_fdw` avoids all of this by shipping SQL text and binary tuples over
libpq; Multicorn pays a text-round-trip cost per value because the guest is an
arbitrary Python object graph, not a wire format.

### 4. Refcount management across a longjmp error model

Every C function juggles CPython refcounts by hand (`Py_INCREF`/`Py_DECREF`/
`Py_XDECREF`), e.g. `getInstance` (`src/python.c:676`), the scan iterator
(`src/multicorn.c:748`), `EndForeignScan` (`src/multicorn.c:780-783`). The hazard
is that PG's error handling is `ereport(ERROR)` → `longjmp`, which does **not**
run intervening C cleanup — so a `Py_DECREF` sitting after a call that raises
never executes and the object leaks. Multicorn's discipline is to interleave
`errorCheck()` immediately after most Python calls (e.g.
`src/multicorn.c:980,989,1018,1029`) so a Python exception is converted to
`ereport` at a known point; but any refs allocated before that point and not yet
adopted into a MemoryContext are leaked on the longjmp. The two lifetime regimes
(CPython refcounting vs PG `palloc`/MemoryContext) are reconciled only loosely:
cached instance state is parented into a dedicated `cacheContext`
(`src/python.c:635-641`) `[verified-by-code]`, and `CacheEntry` keeps its
`options`/`columns` in that context "to avoid leaks" (`src/multicorn.h:46-48`)
`[from-comment]`.

### 5. Quals, sort keys, and LIMIT/OFFSET pushed down as Python objects the class may honor optionally

The pushdown contract is advisory, not enforced. WHERE clauses are extracted into
`qual_list` (`extractRestrictions`, `src/multicorn.c:336-346`) and rendered as a
Python list of `Qual` objects for `execute` (`src/python.c:909-1031`)
`[verified-by-code]`. Crucially, "Multicorn makes no assumption about the
particular behavior of a ForeignDataWrapper, and will NOT remove any qualifiers
from the PostgreSQL quals list. That means the quals will be rechecked anyway"
(`python/multicorn/__init__.py:306-309`) `[from-comment]` — and in
`make_foreignscan` the scan_clauses are passed as both quals and recheck exprs,
"All quals are meant to be rechecked" (`src/multicorn.c:641-648`)
`[verified-by-code]`. So a Python class that ignores the quals is *correct*, just
slow. Sort pushdown asks the class via `can_sort(sortkeys)`
(`src/python.c:1659-1689`, `python/multicorn/__init__.py:189-213`); LIMIT/OFFSET
pushdown asks `can_limit(limit, offset)` (`src/python.c:1629-1647`,
`python/multicorn/__init__.py:215-232`), gated in the planner by
`add_foreign_final_paths` which only pushes constant, non-NULL, no-WHERE,
no-WITH-TIES SELECT limits (`src/multicorn.c:514-590`) `[verified-by-code]`.
Parameterized paths come from the class's `get_path_keys()`
(`src/python.c:1570-1624`, `python/multicorn/__init__.py:234-289`)
`[verified-by-code]`. The pushed-down `limit`/`offset`/`sortkeys` are handed to
`execute` as kwargs (`src/multicorn.c:983-992` and `src/python.c:980-992`)
`[verified-by-code]`.

### 6. Python exceptions mapped to `ereport` (errors.c)

`errorCheck()` fetches the pending Python error with `PyErr_Fetch` and, if any,
converts it (`src/errors.c:22-51`) `[verified-by-code]`. There are two paths:

- A "multicorn exception" — an object carrying `_is_multicorn_exception` truthy —
  is reported by `reportMulticornException`, which pulls `message`/`hint`/
  `detail`/`code` attributes and maps the numeric `code` to a severity
  (`3 → ERROR`, else `4 → FATAL`) before `errstart`/`errmsg`/`errhint`/`errdetail`
  (`src/errors.c:104-155`) `[verified-by-code]`. These originate in `utils.py` to
  intercept ERROR/FATAL log messages (`src/errors.c:32-35`) `[from-comment]`.
- Any other Python exception goes to `reportException`, which imports the
  `traceback` module, formats the exception + traceback into `errdetail`/
  `errdetail_log`, and — notably — downgrades severity to `WARNING` instead of
  `ERROR` when already inside an aborted transaction block
  (`IsAbortedTransactionBlockState()`) so it doesn't PANIC the cleanup
  (`src/errors.c:53-102`) `[verified-by-code]`. The message is always prefixed
  "Error in python: <ExcName>" (`src/errors.c:91`) `[verified-by-code]`.

Contrast the core error-handling idiom: a native FDW picks a SQLSTATE and
`ereport`s directly; Multicorn has to *translate an exception object* from
another runtime, losing the SQLSTATE (it reports without an errcode) but keeping
the Python traceback in the server log.

### 7. Transaction lifecycle proxied to the Python instance

Multicorn maps PG's xact machinery onto instance methods. `begin_remote_xact`
calls `begin(serializable)` on first touch and `sub_begin(level)` to catch up
nesting depth (`src/python.c:681-703`) `[verified-by-code]`; the registered
`multicorn_xact_callback` fans `pre_commit`/`commit`/`rollback` out over every
cached instance (`src/multicorn.c:1196-1228`), and `multicorn_subxact_callback`
does the same for `sub_commit`/`sub_rollback` (`src/multicorn.c:1157-1191`)
`[verified-by-code]`. The base class provides no-op defaults for all of these
(`python/multicorn/__init__.py:436-490`), and a
`TransactionAwareForeignDataWrapper` subclass buffers DML for replay
(`python/multicorn/__init__.py:512-533`) `[verified-by-code]`.

## Notable design decisions

- **Handler fills a fixed `FdwRoutine`; the *variance* lives entirely in Python.**
  The C side is a thin, unchanging dispatcher — every callback slot is wired once
  in `multicorn_handler` (`src/multicorn.c:190-216`) `[verified-by-code]`.
- **`wrapper` OPTION is server-only for security; validated eagerly at CREATE
  SERVER.** Setting it on a table is rejected outright
  (`src/multicorn.c:238-242`) `[verified-by-code]`.
- **One CPython interpreter per backend, torn down in `_PG_fini`** — no
  sub-interpreters, no GIL calls (`src/multicorn.c:160`, `src/multicorn.c:180`)
  `[verified-by-code]`; the direct consequence is incompatibility with PL/Python
  ≥ 3.12 (`README.md:123-127`) `[from-README]`.
- **Instances cached by table oid, invalidated on OPTIONS/columns change.**
  `getCacheEntry` compares stored vs current options and columns and rebuilds only
  on drift (`src/python.c:598-651`) `[verified-by-code]`.
- **DML dispatches to duck-typed methods with opaque rowids.** `ExecForeignInsert`
  → `insert(values)` (`src/multicorn.c:978`), `ExecForeignUpdate` →
  `update(rowid, values)` (`src/multicorn.c:1123-1124`), `ExecForeignDelete` →
  `delete(rowid)` (`src/multicorn.c:1017`), each via `PyObject_CallMethod`
  `[verified-by-code]`. The rowid column name comes from the instance's
  `rowid_column` property, which raises `NotImplementedError` for read-only FDWs
  (`src/python.c:1732-1746`, `python/multicorn/__init__.py:350-363`)
  `[verified-by-code]`.
- **PG14+ batch insert bridges to a single `bulk_insert(list)` call**, gated by
  the instance's `modify_batch_size` (default 1 = disabled)
  (`src/multicorn.c:1035-1094`, `src/python.c:1751-1767`,
  `python/multicorn/__init__.py:365-407`) `[verified-by-code]`.
- **Plan state is serialized as a `List` of `Const` nodes** so it survives the
  plan→exec boundary in `fdw_private` (`src/multicorn.c:1338-1358`)
  `[verified-by-code]`; note the header comment flagging a "very crude hack" to
  carry `width` across because `reltarget->width` mutates between GetForeignPaths
  and GetForeignPlan (`src/multicorn.h:83-90`) `[from-comment]`.
- **`IMPORT FOREIGN SCHEMA` delegates to a Python classmethod** —
  `import_schema(...)` returns `TableDefinition` objects whose `to_statement`
  emits the `CREATE FOREIGN TABLE` DDL (`src/multicorn.c:1230-1331`,
  `python/multicorn/__init__.py:492-509`, `652-683`) `[verified-by-code]`.

## Links into corpus

- [[wrappers]] — the direct analog: the FDW callback API repackaged as a
  safe-Rust trait (via pgrx) instead of a Python class. The single best contrast
  for this doc.
- [[pgrx]] — the Rust/PG framework [[wrappers]] is built on; the compiled-guest
  counterpoint to Multicorn's interpreted-guest model.
- [[oracle_fdw]] — a single hand-written C FDW against one remote; contrast the
  polyglot-host framing.
- [[sqlite_fdw]] — another single-purpose C FDW; useful for the pushdown-in-C vs
  pushdown-as-Python-object contrast.
- [[steampipe_postgres_fdw]] — an FDW whose "wrapper" logic lives in another
  runtime (Go plugins); the closest structural cousin to Multicorn's
  language-bridge model.

(Multicorn embeds CPython much like core PL/Python does, but the two cannot
share a backend as of Python 3.12; see `README.md:123-127`.)

## Sources

- https://raw.githubusercontent.com/pgsql-io/multicorn2/main/README.md @ 2026-07-16 → HTTP 200
- https://raw.githubusercontent.com/pgsql-io/multicorn2/main/multicorn.control @ 2026-07-16 → HTTP 200
- https://raw.githubusercontent.com/pgsql-io/multicorn2/main/src/multicorn.c @ 2026-07-16 → HTTP 200
- https://raw.githubusercontent.com/pgsql-io/multicorn2/main/src/multicorn.h @ 2026-07-16 → HTTP 200
- https://raw.githubusercontent.com/pgsql-io/multicorn2/main/src/python.c @ 2026-07-16 → HTTP 200
- https://raw.githubusercontent.com/pgsql-io/multicorn2/main/src/errors.c @ 2026-07-16 → HTTP 200
- https://raw.githubusercontent.com/pgsql-io/multicorn2/main/python/multicorn/__init__.py @ 2026-07-16 → HTTP 200
