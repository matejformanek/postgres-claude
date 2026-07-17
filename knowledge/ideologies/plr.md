# plr — an R procedural language that shares Postgres' own C runtime and its longjmp

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `postgres-plr/plr` @ branch `master`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Cites verified against the files
> fetched on 2026-07-17 (see Sources footer). This entry extends the
> procedural-language sweep (`knowledge/ideologies/{plv8,pljava,pldotnet}.md`)
> with a fifth PL — the one that hosts no VM at all.

## Domain & purpose

PL/R lets you write SQL-callable functions, DO blocks, triggers, and window
functions in R and run them inside an embedded R interpreter: the language's
`plr.control` comment is literally "load R interpreter and execute R script from
within a database" (`plr.control:2`) `[from-README]`. It is Joe Conway's 2003
extension, explicitly "Based on pltcl by Jan Wieck and inspired by
REmbeddedPostgres" (`README.md:15-17`, `plr.c:10-13`) `[from-README]`, and it
links `libR` directly — `SHLIB_LINK += -lR` (`Makefile:24`) with R headers
required at build time (`Makefile:20-21`, `README.md:33-35`) `[verified-by-code]`.
Its analytical draw is that R's statistical libraries become available as
first-class SQL functions (`aggregate` / `data.frame` / model fitting), with
Postgres tuples marshalled to R `data.frame`s automatically.

**The one thing that makes PL/R structurally distinct.** plv8 embeds a V8
*isolate*, pljava a *JVM*, pldotnet a *CLR* — each a managed VM with its own
exception model, so each bridges *exceptions ↔ `ereport`/`longjmp`*. R is not a
VM. R is a C library that, like Postgres itself, does its own error handling with
`setjmp`/`longjmp` and manages memory with a mark-sweep GC guarded by a
`PROTECT`/`UNPROTECT` C stack. So PL/R's central problem is not exception-model
reconciliation but **two C libraries in one process that each own `setjmp`/
`longjmp` and each own a heap** — and PL/R bridges them with a *double-longjmp
trampoline* (§2) and a global mutable interpreter (§1) that, because R can neither
be re-initialized nor sandboxed, is a single process-wide singleton shared across
every user and every function in the backend. That is the signature of this PL:
no isolation boundary exists, because R never had one.

## How it hooks into PG

PL/R is a standard PL handler trio, each `PG_FUNCTION_INFO_V1`: the comment names
them outright — "There are three externally visible pieces to plr:
plr_call_handler, plr_inline_handler, and plr_validator" (`plr.c:226-228`)
`[verified-by-code]`.

- **Call handler** `plr_call_handler` (`plr.c:237-293`) `[verified-by-code]`
  saves the caller's `MemoryContext`, `SPI_connect`s (with `SPI_OPT_NONATOMIC`
  for procedures on PG ≥ 11, `plr.c:248-262`), lazily initializes R on first call
  (`plr.c:266-285`), then dispatches to `plr_trigger_handler` or
  `plr_func_handler` via `CALLED_AS_TRIGGER` (`plr.c:287-290`).
- **Inline handler** `plr_inline_handler` (`plr.c:295-321`) `[verified-by-code]`
  services `DO` blocks — it pulls `source_text` out of the `InlineCodeBlock` and
  `load_r_cmd`s it directly, with no compile/cache step.
- **Validator** `plr_validator` (`plr.c:323-366`) `[verified-by-code]` honors
  `check_function_bodies` and `CheckFunctionValidatorAccess` (`plr.c:335`), then
  wraps the body in `{…}` and parse-checks it via `plr_parse_func_body`.

It leans on the usual backend APIs: **fmgr** (`perm_fmgr_info` caches type I/O
functions per argument, `plr.c:1357`, `1398`; `FmgrInfo` arrays in the
`plr_function` cache, `plr.h:589-591`); **SPI** (`SPI_connect`/`SPI_finish`
bracket every call, `plr.c:258-262`, `972-973`); the **syscache** (`SearchSysCache`
on `PROCOID`/`LANGOID`/`TYPEOID` throughout `do_compile`); and **`on_proc_exit`**
for interpreter teardown (`plr.c:532`).

The embedded R interpreter itself is brought up in `plr_init` (`plr.c:463-546`)
`[verified-by-code]`: it calls `Rf_initEmbeddedR(rargc, rargv)` (`plr.c:524`) with
argv `{"PL/R", "--slave", "--silent", "--no-save", "--no-restore"}`
(`plr.c:468`), sets `R_SignalHandlers = 0` to stop R installing its own signal
handlers over Postgres' (`plr.c:517`), forces `R_Interactive = false`
(`plr.c:541`), and registers `on_proc_exit(plr_cleanup, 0)` (`plr.c:532`). GC of
R values is done the R way: `PROTECT`/`UNPROTECT` around every transient `SEXP`
(e.g. `plr.c:878-899` protects `fun`/`rargs`/`rvalue` then `UNPROTECT(3)`), and
`R_PreserveObject`/`R_ReleaseObject` for the long-lived compiled function
(`plr.c:1526`, `1063`).

Cross-ref `[[knowledge/idioms/fmgr]]`, `[[knowledge/idioms/spi]]`,
`[[knowledge/idioms/error-handling]]`, `[[knowledge/idioms/memory-contexts]]`,
`.claude/skills/plpgsql-internals/SKILL.md`.

## Where it diverges from core idioms

### 1. One process-global R interpreter per backend — no per-user isolation, ever

R's embedding API is a singleton: `Rf_initEmbeddedR` initializes process-global C
state (`R_GlobalEnv`, the GC heap, the device list) and cannot be run twice, which
PL/R encodes as two static one-shot latches, `plr_pm_init_done` and
`plr_be_init_done` (`plr.c:53-54`), with `plr_init` refusing to "init more than
once" (`plr.c:471-472`) `[verified-by-code]`. Every PL/R function in the backend
therefore shares **one** `R_GlobalEnv`; compiled functions are installed into it
under a synthesized name `PLR<oid>` (`plr.c:1137`, `1503-1524`) and referenced by
a preserved `SEXP fun` in the per-function cache (`plr.h:596`). Contrast the
sibling PLs: plv8 keeps a `ContextVector` with one V8 isolate *per `user_id`*, and
pljava/pldotnet can host isolated class-loaders/AppDomains. PL/R has no such axis
— there is exactly one R state, populated once per backend by `plr_init_all`
(`plr.c:716-748`), and every role that runs PL/R in that backend sees the same
global environment. `plr_load_builtins` seeds it once with the error-handler and
SPI shim functions (`plr.c:570-639`), and `plr_load_modules` optionally injects
rows from a user `plr_modules` table into that same shared namespace at backend
init (`plr.c:648-714`). Cross-ref `knowledge/ideologies/plv8.md` (per-user
isolate) and `[[knowledge/architecture/process-model]]`.

### 2. The double-longjmp error bridge: PG `ereport` → R `error()` → PG `ereport`

This is the load-bearing divergence. Both Postgres and R implement errors with
`setjmp`/`longjmp`, so a naive `SPI_exec` inside an R support function would
`longjmp` straight past R's C frames, corrupting R's `PROTECT` stack and GC. PL/R
instead traps the Postgres error and *re-throws it as an R error*:

- Every SPI shim wraps the backend call in `PG_TRY()`/`PLR_PG_CATCH()`
  (`pg_rsupport.c:155-161` for `plr_SPI_exec`, and identically for `prepare`,
  `execp`, cursor open/fetch/move) `[verified-by-code]`.
- `PLR_PG_CATCH()` (`plr.h:533-542`) `[verified-by-code]` switches into the SPI
  context, `CopyErrorData()`s the Postgres `ErrorData`, then calls R's own
  `error("error in SQL statement : %s", edata->message)` — i.e. it converts a PG
  `longjmp` into an **R `longjmp`**, unwinding cleanly back through R's frames.
- Symmetrically, PL/R installs an R error hook at bootstrap:
  `options(error = expression(pg.throwrerror(geterrmessage())))`
  (`plr.c:75-76`, `587`), and `pg.throwrerror` calls back into C via
  `.C("throw_r_error", …)` (`plr.c:67-74`). `throw_r_error`
  (`pg_rsupport.c:814-821`) simply stashes the message in the global
  `last_R_error_msg` `[verified-by-code]`.
- When control returns from `R_tryEval` in `call_r_func` with `errorOccurred`
  set, PL/R finally re-raises it as a Postgres `ereport(ERROR, …)` carrying
  `last_R_error_msg` as `errdetail` (`plr.c:1584-1612`) `[verified-by-code]`.

So a SQL error raised inside `pg.spi.exec` travels PG-`longjmp` → caught →
R-`error()` `longjmp` → R error option → `throw_r_error` → `R_tryEval` returns →
PG `ereport`. Two independent `longjmp` regimes handed the baton back and forth.
Non-SQL R errors (`stop()`, parse errors) ride the same `last_R_error_msg` channel
(`plr.c:378-407` in `load_r_cmd`, `plr.c:1559-1582` in `plr_parse_func_body`).
The reverse direction — R telling Postgres to log — is `throw_pg_log`
(`pg_rsupport.c:54-66`), reached from R via `pg.thrownotice`/`pg.throwwarning`/
`pg.throwlog` `.C` shims (`plr.c:77-85`), which `elog` at the requested elevel.
Cross-ref `[[knowledge/idioms/error-handling]]`, `knowledge/ideologies/plv8.md`
(§2 there bridges JS-exception ↔ C++-exception ↔ `ereport`; here it is
`longjmp` ↔ `longjmp`).

### 3. Parsing untrusted R input is fenced with `R_ToplevelExec`

Because a parse error in R `longjmp`s, PL/R cannot call `R_ParseVector` directly
inside a Postgres control-flow region. `plr_parse_func_body` runs the parse inside
`R_ToplevelExec(plr_protected_parse, &ppd)` (`plr.c:1552-1582`) `[verified-by-code]`
— R's own protected-execution trampoline that establishes a fresh top-level
context so a parse `longjmp` is contained and reported as `PARSE_OK`/error status
rather than escaping. This is a divergence with no core-PG analogue: core code has
`PG_TRY`, but here PL/R must reach for R's *own* unwind-protection primitive
because the failure originates on R's side of the boundary.

### 4. R's GC heap lives entirely outside Postgres MemoryContexts

Datums marshalled to/from R are `palloc`'d in Postgres contexts, but the R objects
themselves live in R's GC heap, which no `MemoryContext` owns or resets. PL/R
therefore runs a *parallel* memory discipline: `PROTECT`/`UNPROTECT` balancing on
every transient `SEXP` (e.g. `plr.c:1595-1597`, `1645-1798`), and
`R_PreserveObject` to pin the compiled function `SEXP` for the cache's lifetime
(`plr.c:1526`), released with `R_ReleaseObject` only when the cache entry is
invalidated (`plr.c:1063`). The long-lived `plr_function` C struct is itself
`palloc`'d in `TopMemoryContext` so it outlives the per-call context
(`plr.c:1148`, and `plr_init_all` switches to `TopMemoryContext` for all
one-time init, `plr.c:721-722`). PL/R keeps two named contexts across the SPI
boundary — `plr_caller_context` and `plr_SPI_context` (`plr.c:48-49`, set at
`plr.c:255`, `263`) — and shuttles between them with `SWITCHTO_PLR_SPI_CONTEXT`/
`CLEANUP_PLR_SPI_CONTEXT` macros (`plr.h:529-532`). A `DEBUGPROTECT` build even
overrides `PROTECT`/`UNPROTECT` to log every GC-stack push/pop with file:line
(`plr.h:271-279`, `plr.c:1915-1929`) `[verified-by-code]` — a measure of how
alien the second heap is to normal PG memory reasoning. Cross-ref
`[[knowledge/idioms/memory-contexts]]`.

### 5. Untrusted by construction — R can touch the filesystem, and PL/R hands it more

PL/R is an untrusted language: R has no safe subset (unlike pltcl's Safe slave
interpreter or plv8's binding-free V8), so trusting it is impossible. The handler
does record `lanpltrusted` per function (`plr.c:1184`, `plr.h:578`), but the
extension exposes SQL-callable functions that are frankly host-level:
`install_rcmd` loads *arbitrary* R source into the shared interpreter
(`pg_userfuncs.c:86-95`) `[verified-by-code]`; `plr_environ` dumps the entire
postmaster environment as a tuplestore (`pg_userfuncs.c:285-362`); `plr_set_rhome`
/ `plr_unset_rhome` / `plr_set_display` mutate process env vars via
`putenv`/`unsetenv` (`pg_userfuncs.c:453`, `469`, `498`); and `plr_get_raw`
serializes R objects to `bytea` (`pg_userfuncs.c:513`). The README is explicit
that R must be available with `--enable-R-shlib` and that `R_HOME` must be set in
the postmaster's environment or "PL/R will refuse to load"
(`README.md:33-38`) `[from-README]`. Cross-ref `knowledge/ideologies/plv8.md`,
`knowledge/ideologies/pljava.md` (trust-gate ranking; PL/R sits at the untrusted
floor with plpython).

### 6. Catalog & SPI conventions: an SQL-shim layer, not a C-native SPI API

Rather than expose SPI as C-callable R primitives directly, PL/R bootstraps a
*layer of R functions* into the interpreter that call C via `.Call`/`.C`:
`pg.spi.exec`, `pg.spi.prepare`, `pg.spi.execp`, the cursor family, and
`pg.quoteliteral`/`pg.quoteident` are all defined as R source strings in
`plr.c:91-129` and loaded by `plr_load_builtins` (`plr.c:589-598`)
`[verified-by-code]`. It even ships **DBI-compatible shims** — `dbDriver`,
`dbConnect`, `dbSendQuery`, `fetch`, `dbGetQuery`, `dbReadTable` (`plr.c:130-166`)
— so R code written against the DBI package runs against the in-process backend
unmodified. Module loading is catalog-driven the pltcl way: a user table
`plr_modules` (looked up by namespace via `getNamespaceOidFromLanguageOid`,
`plr.c:1834-1866`, `haveModulesTable`, `plr.c:1872-1891`) supplies R source
executed at backend init (`plr.c:648-714`). Version-conditional catalog awareness
shows up too: `pg.spi.lastoid` is only defined for `CATALOG_VERSION_NO < 201811201`
(`plr.c:117-121`, `599-601`), and `pg.spi.commit`/`pg.spi.rollback` only for
PG ≥ 11 (`plr.c:122-129`, `602-605`). Cross-ref `[[knowledge/idioms/spi]]`.

## Notable design decisions (cited)

- **`ERROR`/`WARNING` macro collision is resolved by undef-and-restore.** R and
  Postgres both `#define ERROR` and `WARNING` to *different* integer values, so
  `plr.h` `#undef`s them before including the R headers (`plr.h:94-100`) and
  restores the Postgres meanings afterward, re-`#define`ing `ERROR`→`PGERROR`
  (20) and `WARNING`→`PGWARNING` (19) (`plr.h:218-236`) `[verified-by-code]`.
  A tax paid by every file that must speak both APIs.
- **Compiled-function cache keyed on `fn_xmin`/`fn_tid`, pltcl-style.**
  `compile_plr_function` caches by a `plr_func_hashkey` (funcOid + trigrelOid +
  actual arg types, `plr.h:550-568`) and revalidates against
  `HeapTupleHeaderGetXmin` + `ItemPointerEquals` on the `pg_proc` tuple
  (`plr.c:1047-1067`); a stale entry is dropped and its `SEXP` `R_ReleaseObject`d
  (`plr.c:1059-1064`) `[verified-by-code]`. Polymorphic args are resolved with a
  copy of plpgsql's `resolve_polymorphic_argtypes`, defaulting to `int4` during
  validation (`plr.c:1939-1983`).
- **Postgres tuples become R `data.frame`s.** Composite/relation arguments are
  detected via `arg_is_rel` (`plr.c:1662-1665`) and converted with
  `CONVERT_TUPLE_TO_DATAFRAME` (`plr.h:493-510`) → `pg_tuple_get_r_frame`
  (`pg_conversion.c:574`); scalars go through `pg_scalar_get_r`
  (`pg_conversion.c:73`), arrays through `pg_array_get_r`
  (`pg_conversion.c:139`), and results back through `r_get_pg`
  (`pg_conversion.c:801`). `bytea` is special-cased to R `unserialize`
  (`pg_conversion.c:92-129`) `[verified-by-code]`, the mirror of `plr_get_raw`'s
  `serialize`.
- **Window functions get a per-frame R environment.** For `iswindow` functions
  PL/R creates a fresh R environment `window_env_<ptr>` on the first row and
  tears it down on the last (`plr.c:928-949`, `961-966`), passing whole-partition
  frame data as extra R args (`plr.c:1737-1793`); unbound-frame detection reaches
  into `WindowAggState` internals (`plr.c:552-564`) `[verified-by-code]`.
- **Interpreter teardown shells out to `rm -rf`.** `plr_cleanup` (the
  `on_proc_exit` callback, `plr.h:419-420`, `plr.c:415-441`) runs `R_dot_Last`,
  `R_RunExitFinalizers`, `KillAllDevices`, then deletes R's session tempdir with
  `system("rm -rf \"<R_SESSION_TMPDIR>\"")` `[verified-by-code]` — a shell-out
  no core PL would do, and a reminder that R owns process-level resources
  (temp dirs, graphics devices) outside Postgres' resource-owner discipline.
- **`plr_atexit` guards the R-suicide failure mode.** R's init "currently exits"
  on failure via `R_suicide`; PL/R registers a libc `atexit(plr_atexit)`
  (`plr.c:512`) that turns that silent process exit into an `ereport(ERROR)`
  pointing at a misconfigured `R_HOME` (`plr.c:443-455`, `499-503`)
  `[verified-by-code]`.

## Links into corpus

- `knowledge/ideologies/plv8.md`, `knowledge/ideologies/pljava.md`,
  `knowledge/ideologies/pldotnet.md` — the PL siblings. PL/R is the data point
  that breaks the "each PL bridges *exceptions* ↔ `ereport`" pattern: R brings no
  VM and no exception model, only a second `longjmp` regime and a second GC heap,
  so the bridge (§2) and the isolation story (§1) are categorically different.
- `[[knowledge/idioms/fmgr]]` — the `plr_call_handler`/`inline_handler`/
  `validator` trio and the cached `FmgrInfo` type-I/O arrays.
- `[[knowledge/idioms/spi]]` — the `pg.spi.*` R-shim layer and the DBI-compat
  functions built on `SPI_exec`/`SPI_prepare`/cursors.
- `[[knowledge/idioms/error-handling]]` — the double-longjmp trampoline
  (`PLR_PG_CATCH` → R `error()` → `throw_r_error` → `ereport`) and
  `throw_pg_log`.
- `[[knowledge/idioms/memory-contexts]]` — the R GC heap outside MemoryContexts,
  `PROTECT`/`UNPROTECT` + `R_PreserveObject`, and the two named PL/R contexts.
- `[[knowledge/idioms/error-context-callbacks]]` — `plr_error_callback` /
  `rsupport_error_callback` push "In PL/R function %s" onto `error_context_stack`.
- `.claude/skills/plpgsql-internals/SKILL.md`, `.claude/skills/error-handling/SKILL.md`,
  `.claude/skills/fmgr-and-spi/SKILL.md`, `.claude/skills/extension-development/SKILL.md`.

## Anthropology takeaway

PL/R is the PL that never had a sandbox to lose. Where plv8/pljava/pldotnet embed
a managed VM and spend their structural budget reconciling that VM's exception
model and heap with Postgres, PL/R embeds a *peer C library* — R, which owns its
own `setjmp`/`longjmp` error handling and its own mark-sweep GC, and which the
embedding API forbids you from running more than once per process. The two
consequences define the extension: (1) a single process-global interpreter shared
by every user and function in the backend, with no isolation axis to add; and
(2) a double-longjmp trampoline that hands control back and forth between two C
libraries that both think they own the stack. Everything else — the untrusted-only
posture (§5), the `ERROR`/`WARNING` undef dance, the `rm -rf` tempdir cleanup, the
`R_ToplevelExec` parse fence — falls out of hosting a full statistical language's
C runtime *inside* Postgres' C runtime rather than beside it in a VM.

## Sources

Fetched 2026-07-17 (branch `master`, via `raw.githubusercontent.com/postgres-plr/plr`):

- `plr.c` → HTTP 200 (53507 bytes; handler trio, `plr_init`/`Rf_initEmbeddedR`,
  `plr_load_builtins` R-bootstrap, `compile_plr_function`/`do_compile` cache,
  `load_r_cmd`/`plr_parse_func_body`/`call_r_func` error paths, window-function
  env, `plr_cleanup` — deep-read).
- `plr.h` → HTTP 200 (20790 bytes; `plr_function`/`plr_func_hashkey` structs,
  `PLR_PG_CATCH`/context macros, `ERROR`/`WARNING` undef-restore, `DEBUGPROTECT`,
  trigger-arg macros — deep-read).
- `pg_rsupport.c` → HTTP 200 (19593 bytes; `plr_SPI_exec`/`prepare`/`execp`,
  cursor family, `throw_pg_log`, `throw_r_error` — cited regions deep-read).
- `pg_userfuncs.c` → HTTP 200 (15321 bytes; `install_rcmd`, `plr_environ`,
  `plr_set_rhome`/`plr_unset_rhome`/`plr_set_display`, `plr_get_raw`, `plr_array*`
  — cited regions deep-read).
- `pg_conversion.c` → HTTP 200 (54741 bytes; `pg_scalar_get_r`/`pg_array_get_r`/
  `pg_tuple_get_r_frame`/`r_get_pg` signatures + `bytea` unserialize path —
  headers + cited regions read, bulk of marshalling skimmed).
- `plr.control` → HTTP 200 (170 bytes). `Makefile` → HTTP 200 (2962 bytes;
  `-lR` link, libR-shared gate, REGRESS list). `README.md` → HTTP 200 (2438
  bytes; provenance, `R_HOME`/`--enable-R-shlib` requirements).

404 gaps (probed, not present at these paths on `master`): `pg_backend_random.c`,
`README` (plain). `pg_backend_support.c` (named in `Makefile:22` SRCS) was not
fetched — `compute_function_hashkey`, `plr_HashTable*`, `perm_fmgr_info`, and
`get_load_self_ref_cmd` live there (declared `plr.h:666-675`) and are cited only
via their call sites, tagged accordingly.

All cites are `[verified-by-code]` against the fetched `.c`/`.h` except the
end-user feature narrative and R-library-availability claims, which are
`[from-README]`, and the "R owns process-global state / cannot re-init" framing,
which is `[inferred]` from the one-shot init latches (`plr.c:471-472`) and the
`Rf_initEmbeddedR` single call site.
