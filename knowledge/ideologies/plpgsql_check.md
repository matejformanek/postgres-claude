# plpgsql_check — a static analyzer that borrows the real PL/pgSQL compiler via load_external_function + the PLpgSQL_plugin hook

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `okbob/plpgsql_check` @ branch `master`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> files fetched on 2026-06-10 (see Sources footer). Read alongside
> `[[knowledge/ideologies/plv8]]` (another PL-adjacent extension) and the core
> `src/pl/plpgsql` subsystem.

## Domain & purpose

plpgsql_check provides "enhanced checks for plpgsql functions"
(`src/plpgsql_check.c:5`) `[from-comment]` — a linter/static analyzer that
catches errors a normal PL/pgSQL function only surfaces at runtime (undefined
columns, type mismatches, unused variables, unclosed cursors, dead code), plus
an optional profiler and execution tracer. Its trick, and the reason it's worth
documenting, is that it does **not** reimplement the PL/pgSQL parser or
semantic analyzer: it reaches into the *already-loaded* `plpgsql` shared library
at runtime, reuses that compiler to build the same parse tree the executor
would, and then walks that tree in a *fake* execution environment that
type-checks every expression without running a single statement
(`src/plpgsql_check.c:11-23`) `[from-comment]`.

## How it hooks into PG

`plpgsql_check` (control `default_version` aside) supports the modern
`PG_MODULE_MAGIC_EXT(.name="plpgsql_check", .version="2.9.1")` form, falling
back to bare `PG_MODULE_MAGIC` on older PG (`src/plpgsql_check.c:45-56`)
`[verified-by-code]`. From `_PG_init` (`plpgsql_check.c:204-522`) it:

- **Dynamically resolves seven `plpgsql_*` symbols** out of `$libdir/plpgsql`
  via `load_external_function`, caching them in function pointers
  (`plpgsql_check__compile_p`, `__build_datatype_p`, `__parser_setup_p`,
  `__stmt_typename_p`, `__exec_get_datum_type_p`, `__recognize_err_condition_p`,
  `__ns_lookup_p`) (`plpgsql_check.c:117-123, 215-268`) `[verified-by-code]`.
- **Installs a `PLpgSQL_plugin`** through the global plugin variable pointer
  `plpgsql_check_plugin_var_ptr` (`plpgsql_check.c:58`, `plch_init_plugin()`
  call at `:506`) `[verified-by-code]` — this is the same `**plugin` rendezvous
  variable that the PL/pgSQL executor consults so debuggers/profilers can hook
  function entry/exit and per-statement callbacks.
- Defines **~30 `DefineCustom*Variable` GUCs** (`plpgsql_check.mode`,
  `…profiler`, `…enable_tracer`, `…cursors_leaks*`, warning toggles), several
  `PGC_SUSET`/`PGC_USERSET` enums (`plpgsql_check.c:270-467`) `[verified-by-code]`.
- **Conditionally reserves shmem** for the profiler when preloaded:
  `RequestNamedLWLockTranche("plpgsql_check profiler"/"… fstats")` and a
  `shmem_request_hook`/`shmem_startup_hook` pair, all gated on
  `process_shared_preload_libraries_in_progress` (`plpgsql_check.c:474-504`)
  `[verified-by-code]`. So it is dual-mode: useful lazily as a checker, richer
  (shared profiler stats) when preloaded.
- On PG ≥ 18, registers a **syscache invalidation callback** on `EXTENSIONOID`
  to recheck its own installed SQL-interface version
  (`pg_extension_cache_callback`, `plpgsql_check.c:127-135, 513-520`)
  `[verified-by-code]`.

Cross-ref `[[knowledge/idioms/fmgr]]`,
`.claude/skills/extension-development/SKILL.md`,
`.claude/skills/gucs-bgworker-parallel/SKILL.md`.

## Where it diverges from core idioms

### 1. It links to another extension's internals at runtime — `load_external_function("$libdir/plpgsql", …)`

Core extensions call *core* functions, which are exported from the postgres
backend binary. plpgsql_check instead does cross-`.so` symbol resolution: it
`dlsym`s seven non-API functions out of the `plpgsql` language handler library
(`LOAD_EXTERNAL_FUNCTION` macro = `load_external_function(file, funcname, true,
NULL)`, `plpgsql_check.c:141`, applied at `:217-266`) `[verified-by-code]`.
These are `plpgsql_compile`, `plpgsql_build_datatype`, `plpgsql_parser_setup`,
etc. — the compiler entry points PL/pgSQL never intended as a stable ABI. To
guard against signature drift, the code wraps each in `AssertVariableIsOfType`
(pre-19) or `StaticAssertVariableIsOfType` (PG ≥ 19) against the real symbol's
declared type (`plpgsql_check.c:185-195, 240-265`) `[verified-by-code]`, so a
core signature change breaks the build rather than crashing at runtime. This is
a deliberate, maintained dependency on a *sibling extension's* internal surface
— a divergence almost nothing else in the corpus does (most "reach into core"
cases copy a static function out; this one binds to the live symbol).

### 2. It drives the PL/pgSQL compiler/executor with a *fake* fcinfo and execstate, type-checking without executing

The README-of-the-source comment is explicit: "Reusing some plpgsql_xxx
functions requires full run-time environment. It is emulated by fake expression
context and fake fcinfo (these are created when active checking is used) — see:
setup_fake_fcinfo, setup_cstate" (`plpgsql_check.c:15-18`) `[from-comment]`.
`check_function.c` builds a `PLpgSQL_execstate` and `PLpgSQL_checkstate` by hand
(`setup_estate`, `setup_cstate`, `function_check`, `trigger_check`,
`check_function.c:67-87`) `[verified-by-code]` and walks the compiled function's
statement tree, asking the borrowed compiler to resolve every expression's type
— but the third comment warns the *real* cached plans must not be linked to the
fake environment, so all expressions created during checking are torn down with
`release_exprs(cstate.exprs)` (`plpgsql_check.c:19-23`) `[from-comment]`. This
is the corpus's purest example of **reusing the executor's front half (compile +
plan) while suppressing its back half (execute)**, an inversion of the normal
fmgr contract where `Datum f(PG_FUNCTION_ARGS)` actually runs.

### 3. Memoizing "already checked" by xmin+tid, like the PL handler's own compile cache

To avoid re-checking the same function body repeatedly, plpgsql_check keeps a
secondary hash table keyed the way PL/pgSQL keys its compile cache: on PG ≥ 18 a
`CachedFunctionHashKey`, earlier a `PLpgSQL_func_hashkey`, paired with the
function's `fn_xmin` + `fn_tid` and an `is_checked` flag
(`plpgsql_check_HashEnt`, `check_function.c:49-64`) `[verified-by-code]`. The
header comment calls this "protection against unwanted repeated check"
(`plpgsql_check.c:13-14`) `[from-comment]`. It is the same
"identify a pg_proc row version by (xmin, tid)" idiom core uses for plan-cache
invalidation, lifted into the extension.

### 4. Error *levels* are user-configurable policy, not fixed semantics

Whether an unclosed cursor is a `NOTICE`, `WARNING`, or hard `ERROR` is a GUC
(`plpgsql_check.cursors_leaks_errlevel`, enum mapping strings to elevels,
`plpgsql_check.c:88-93, 419-426`) `[verified-by-code]`; likewise tracer output
elevel and verbosity (`tracer_errlevel`, `tracer_verbosity` mapping to
`PGERROR_TERSE/DEFAULT/VERBOSE`, `:68-86, 383-408`). Core decides an ereport's
level at the call site; plpgsql_check turns *severity itself* into a runtime
knob, which means the same code path can emit anything from a debug note to a
transaction-aborting error depending on configuration. Cross-ref
`[[knowledge/idioms/error-handling]]`, `.claude/skills/error-handling/SKILL.md`.

## Notable design decisions (cited)

- **Idempotent `_PG_init`** with a `static bool inited` guard
  (`plpgsql_check.c:208-211`) `[verified-by-code]` — belt-and-suspenders against
  double initialization.
- **Version-gated plugin var typing**: PG ≥ 19 uses `StaticAssert*` (compile-time)
  while older uses `AssertVariableIsOfType` (`plpgsql_check.c:185-195`)
  `[verified-by-code]` — tracks the in-flight core changes to the plpgsql plugin
  ABI across versions in a single tree.
- **The installed SQL extension version is runtime-checked against an embedded
  `EXPECTED_EXTVERSION "2.9"`** (`plpgsql_check.c:143-183`): if the C library and
  the `pg_extension` row disagree it raises an error with an
  `ALTER EXTENSION … UPDATE` hint (`:172-176`) `[verified-by-code]`. The `.so`
  refuses to operate against a stale SQL half — stricter than core contrib, which
  typically tolerates version skew.
- **Profiler stats can live in shared memory** only when the module was preloaded
  (`plch_use_shared_stats_when_it_possible`, `plpgsql_check.c:453-459`); otherwise
  it falls back to backend-local hash tables (`plch_profiler_init_local_hash_tables`,
  `:472`) `[verified-by-code]` — graceful degradation between preload and lazy modes.

## Links into corpus

- `src/pl/plpgsql` (core) — plpgsql_check binds to its compiler symbols and its
  `PLpgSQL_plugin` rendezvous variable; the extension is meaningless without the
  exact internal layout of this subsystem.
- `[[knowledge/ideologies/plv8]]` — another PL-ecosystem extension; plv8 *is* a
  new PL, plpgsql_check *inspects* an existing one by borrowing its compiler.
- `[[knowledge/idioms/fmgr]]` — the fake-`fcinfo` construction inverts the
  normal `PG_FUNCTION_ARGS` execution contract (compile, don't run).
- `[[knowledge/idioms/error-handling]]` — severity-as-GUC (`cursors_leaks_errlevel`,
  tracer elevels) vs core's fixed call-site elevels.
- `.claude/skills/extension-development/SKILL.md` — dual lazy/preload module with a
  conditional `shmem_request_hook`; `load_external_function` cross-`.so` linking.

## Anthropology takeaway

plpgsql_check is the corpus's standout "**parasite on a sibling extension**"
case: where pg_squeeze and cstore_fdw copy a *static core* function into
themselves, plpgsql_check instead binds to the live `plpgsql.so` symbol table at
runtime and reuses the real compiler, guarding the unstable ABI with
compile-time type assertions. Two Phase-D / idiom-mining threads: (a) the
`load_external_function` + `(Static)AssertVariableIsOfType` pattern is a concrete
technique for depending on an *internal* symbol while failing loudly on drift —
worth a `knowledge/idioms` note as the safe form of "reach into another module".
(b) The "**compile but do not execute**" inversion — building a fake
`PLpgSQL_execstate` to type-check expressions — is a reusable static-analysis
idiom and the cleanest example in the set of separating the planner/compiler
front-half from the executor back-half. The `PLpgSQL_plugin` rendezvous variable
is itself the one *sanctioned* extension point here; everything else is
unsanctioned internal coupling, which makes plpgsql_check a good probe for how
stable PL/pgSQL's internals actually are across releases.

## Sources

Fetched 2026-06-10 (branch `master`):

- `https://api.github.com/repos/okbob/plpgsql_check/git/trees/master?recursive=1`
  @ 2026-06-10 → HTTP 200 (tree listing; manifest paths confirmed under `src/`).
- `https://raw.githubusercontent.com/okbob/plpgsql_check/master/README.md`
  @ 2026-06-10 → HTTP 200 (49771 bytes; skimmed for feature surface).
- `.../master/plpgsql_check.control` @ 2026-06-10 → HTTP 200 (182 bytes).
- `.../master/src/plpgsql_check.h` @ 2026-06-10 → HTTP 200 (26453 bytes; skimmed
  for plugin/typedef declarations).
- `.../master/src/plpgsql_check.c` @ 2026-06-10 → HTTP 200 (15732 bytes; deep-read
  — `_PG_init`, symbol resolution, plugin install, GUCs, version check).
- `.../master/src/check_function.c` @ 2026-06-10 → HTTP 200 (38205 bytes; first
  ~120 lines deep-read — hash-entry keying, `check_plugin`, setup_* declarations;
  the bulk of the checking walk skimmed).

All cites are `[verified-by-code]` against the fetched `.c`/`.h` except the
fake-environment rationale, the "secondary hash table" memoization purpose, and
the analyzer mission, which are `[from-comment]` (the file-header notes), and the
feature breadth, which is `[from-README]`. The full statement-walk in
`check_function.c` (`function_check`/`trigger_check` bodies), the profiler
(`profiler.c`), and tracer were not deep-read; claims about *how* expressions are
type-checked rest on the header comments + the visible setup scaffolding, tagged
accordingly.
