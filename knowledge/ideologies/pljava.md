# pljava — a Java PL that embeds a whole JVM in the backend process

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `tada/pljava` @ branch `master`. Version is build-substituted
> (`default_version = '${project.version}'`, control template)
> `[verified-by-code: pljava-packaging/src/main/resources/pljava.control:2]`.
> 269★, Java + C (a JNI native bridge in `pljava-so/src/main/c/`, the bulk of the
> runtime in Java under `org.postgresql.pljava`). All `file:line` cites below point
> into the **pljava** repo, NOT into PG `source/`, since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against files
> fetched on 2026-06-21 (see Sources footer).
> Confidence tags: `[verified-by-code]` `[from-README]` `[from-comment]`
> `[inferred]` `[unverified]`.
> **Sibling note:** pljava extends the procedural-language sweep alongside
> [[knowledge/ideologies/plv8]] (the V8-isolate JS PL) and core's `plperl` /
> `plpython` / `pltcl`. The recurring question across the sweep — *how does a PL
> host a foreign execution engine inside a single-threaded, longjmp-driven PG
> backend?* — gets its heaviest answer here: pljava embeds an entire **Java
> Virtual Machine** per backend. Read this against plv8: V8 isolate vs JVM, one
> sandbox-by-absence-of-bindings vs one sandbox-by-SecurityManager-policy.

## Domain & purpose

pljava "brings Java™ Stored Procedures, Triggers, and Functions to the PostgreSQL
backend" `[from-README: README.md:3-4]`. You write functions/triggers in Java,
compile them to a jar, `INSTALL_JAR` the jar into a catalog table, set a schema
classpath, and `CREATE FUNCTION ... LANGUAGE java` (trusted/sandboxed) or
`LANGUAGE javau` (untrusted). The Java side exposes a JDBC-shaped API
(`Connection`, `ResultSet`, `TriggerData`) over PG's SPI. It is the JVM analogue
of plv8's V8: where plv8 hosts a JS compute engine, pljava hosts the full Java
runtime — classloaders, threads, GC, a SecurityManager-based policy layer — all
living inside the PG backend process. Two distinct PG languages share one
implementation: `java` (trusted) and `javau` (untrusted), distinguished only by
which call handler PG dispatches to
`[verified-by-code: pljava-so/src/main/c/Backend.c:1895-1909]`.

## How it hooks into PG

- **The PL call-handler / validator contract, doubled for trusted + untrusted.**
  Four `PG_FUNCTION_INFO_V1` entry points: `java_call_handler` /
  `javau_call_handler` and `java_validator` / `javau_validator`
  `[verified-by-code: Backend.c:1890,1901,1951,1959]`. Both call handlers funnel
  into one `internalCallHandler(bool trusted, …)` that pushes an `Invocation`,
  runs `Function_invoke(funcoid, trusted, forTrigger, …)` inside `PG_TRY/PG_CATCH`,
  and pops the invocation on both paths
  `[verified-by-code: Backend.c:1911-1946]`. This is the standard PL handler seam
  (`pg_language.lanplcallfoid`), used exactly as core plperl/plpython/pltcl use it.

- **It installs itself by running DDL from inside the JVM.** Unusually, the
  `CREATE EXTENSION` SQL does almost nothing: it stashes the `.so` path in a
  sentinel table and issues `LOAD '${module.pathname}'`
  `[verified-by-code: pljava-packaging/src/main/resources/pljava--.sql:24-30]`,
  with a header comment stating "most of the work of setting up PL/Java is done
  within PL/Java itself, touched off by the LOAD command"
  `[from-comment: pljava--.sql:3-7]`. The C `_PG_init` runs the init sequencer,
  which (in the LOAD case) calls `InstallHelper_groundwork()`
  `[verified-by-code: Backend.c:810-815]`; that crosses into Java, where
  `InstallHelper.groundwork()` opens a JDBC default connection and executes the
  real DDL: `CREATE SCHEMA sqlj`, `CREATE OR REPLACE FUNCTION
  sqlj.java_call_handler() RETURNS language_handler … LANGUAGE C`, the validators,
  and the `CREATE LANGUAGE` entries
  `[verified-by-code: pljava/src/main/java/org/postgresql/pljava/internal/InstallHelper.java:392-414,512-530,553-602]`.
  The extension bootstraps its own catalog presence from Java code running in the
  embedded VM.

- **`_PG_init` → a multi-stage, resumable init sequencer.** `_PG_init`
  `[verified-by-code: Backend.c:953-980]` records the path separator and calls
  `initsequencer(initstage, tolerant)`, a `switch`-on-`initstage` state machine
  with fallthrough between stages: register GUCs → check `libjvm_location` →
  check `policy_urls` → check `pljava.enable` → `pg_dlopen(libjvm)` →
  `pg_dlsym("JNI_CreateJavaVM")` → build the JVM option list → start the VM →
  install signal handlers → load PL/Java classes → install the sqlj schema
  `[verified-by-code: Backend.c:577-819]`. It can be re-entered from the call
  handler, a GUC assign hook, or the validator, resuming where it left off — the
  header comment enumerates these four entry paths
  `[from-comment: Backend.c:533-575]`. GUC assign hooks for `libjvm_location`,
  `vmoptions`, `modulepath`, `policy_urls`, `enabled` re-drive the sequencer if a
  setting that was blocking init is fixed mid-session
  `[verified-by-code: Backend.c:451-523]`.

- **GUCs (`pljava.*`), mostly `PGC_SUSET` / `GUC_SUPERUSER_ONLY`.** Registered in
  `registerGUCOptions` `[verified-by-code: Backend.c:1709-1871]`:
  `pljava.libjvm_location`, `pljava.vmoptions` ("Options sent to the JVM when it
  is created"), `pljava.module_path`, `pljava.policy_urls` (Java security policy
  files), `pljava.allow_unenforced`, `pljava.debug`,
  `pljava.statement_cache_size`, and the threading-policy enum
  `pljava.java_thread_pg_entry` (see divergence #6)
  `[verified-by-code: Backend.c:1713-1871]`. The JVM-launch GUCs are
  `PGC_SUSET`/`GUC_SUPERUSER_ONLY` because they choose native code to dlopen and
  flags to hand the VM `[verified-by-code: Backend.c:1719-1720,1731-1732]`.

- **Load timing: on-demand `LOAD`, not necessarily `shared_preload_libraries`.**
  The JVM is started lazily on first need (first PL/Java call, or the LOAD during
  `CREATE EXTENSION`), not eagerly at postmaster start. `_PG_init` is documented
  as possibly called "very early" in a background worker before much is set up
  `[from-comment: Backend.c:234-243]`, so init is deferrable (`deferInit`) and the
  VM is only created when the sequencer reaches `IS_JAVAVM_OPTLIST`
  `[verified-by-code: Backend.c:710-738]`.

Cross-ref [[knowledge/idioms/fmgr]], [[knowledge/idioms/error-handling]],
[[knowledge/idioms/memory-contexts]],
`.claude/skills/extension-development/SKILL.md`,
`.claude/skills/gucs-config/SKILL.md`.

## Where it diverges from core idioms

### 1. A whole JVM embedded in the backend via the JNI Invocation API — one per backend, lazily started, at most once per session

The defining divergence. pljava `pg_dlopen`s `libjvm` and `pg_dlsym`s
`JNI_CreateJavaVM` `[verified-by-code: Backend.c:636-652]`, builds a `JVMOptList`
(user `vmoptions`, `--module-path`, redirected `abort`/`exit`/`vfprintf` hooks,
and `-Xrs` to keep the JVM from grabbing PG's signals)
`[verified-by-code: Backend.c:688-705]`, then `initializeJavaVM` calls
`JNI_createVM(&s_javaVM, &vm_args)` `[verified-by-code: Backend.c:1632-1659]`.
`s_javaVM` is a single static `JavaVM*` per backend
`[verified-by-code: Backend.c:106]`. An `on_proc_exit(_destroyJavaVM, 0)` handler
tears it down at backend exit `[verified-by-code: Backend.c:715,1420-1449]`.

The hard constraint that follows from JNI: **a process can create the JVM at most
once**. If creation fails after an earlier success in the same session, pljava
emits the hint that the runtime "does not support more than one VM creation per
session. You may need to exit this session and start a new one"
`[verified-by-code: Backend.c:728-733]`. This is far heavier than plv8's per-user
V8 isolate ([[knowledge/ideologies/plv8]] divergence #1): a V8 isolate can be
created, disposed, and recreated freely (`plv8_reset()`); a JVM is a
one-shot-per-process singleton. Under PG's one-process-per-backend fork model
this is tolerable — each forked backend gets its own fresh address space and thus
its own one JVM — but it means there is no in-session "restart Java" escape hatch
analogous to plv8's reset. Cross-ref [[knowledge/architecture/process-model]]
(per-connection fork), `.claude/skills/bgworker-and-extensions/SKILL.md`.

### 2. The exception bridge: PG `ereport`/`longjmp` ↔ Java `throw`, reconciled in *both* directions without letting either unwinder cross the other's frames

This is the load-bearing correctness story, and pljava solves it symmetrically.

**PG error → Java exception.** Every native method that calls into PG wraps the
call in `PG_TRY()`; the `PG_CATCH()` calls `Exception_throw_ERROR(...)`, which
captures the in-flight error via `pljava_ErrorData_getCurrentError()`, **calls
`FlushErrorState()`**, builds a Java `ServerException` from the captured
`ErrorData`, sets `currentInvocation->errorOccurred = true`, and `JNI_throw`s it
`[verified-by-code: pljava-so/src/main/c/Exception.c:188-211]`. Critically the PG
`longjmp` is *caught at the C frame nearest the JNI boundary* and converted to a
pending Java exception — the `siglongjmp` never propagates up through JVM-compiled
frames (which would corrupt the JVM). The SPI bridge shows the pattern in situ:
`SPI__1exec` does `BEGIN_NATIVE … PG_TRY { SPI_exec(...) } PG_CATCH {
Exception_throw_ERROR("SPI_exec") } PG_END_TRY … END_NATIVE`
`[verified-by-code: pljava-so/src/main/c/SPI.c:120-149]`.

**Java exception → PG error.** Symmetrically, when a PL/Java function returns
having left an unhandled exception, `Invocation_popInvocation` reads the static
`s_unhandled` SQLException field, and re-logs/re-raises it at the C level
`[verified-by-code: pljava-so/src/main/c/Invocation.c:195-239]`. A dedicated
`UnhandledPGException` marks the case where a PG error that was converted to Java
was *never handled* by the Java code and must resurface as the original PG error
(`Exception_isPGUnhandled`, `Exception_throw_unhandled`)
`[verified-by-code: Exception.c:52-55,172-186]`.

This is the same boundary problem [[knowledge/ideologies/pgrx]] solves with
`pg_guard_ffi_boundary` (sigsetjmp ↔ Rust panic) and
[[knowledge/ideologies/pgrouting]] solves with a catch-all C++ firewall — but
pljava's version is *bidirectional and stateful*: it does not merely stop one
unwinder from crossing into the other, it round-trips a PG `ErrorData` through a
Java `ServerException` and back, with `FlushErrorState()` marking the handoff
point. Contrast [[knowledge/ideologies/plv8]] divergence #2 (JS ↔ C++ ↔ ereport,
three error models): pljava has two error models but a richer error *object*
(full `ErrorData` with SQLSTATE) crossing the seam. The `Exception_throw` family
even round-trips the SQLSTATE by unpacking PG's `MAKE_SQLSTATE` 6-bit encoding
into the 5-char string a `java.sql.SQLException` expects
`[verified-by-code: Exception.c:112-127]`. Cross-ref
[[knowledge/idioms/error-handling]] (PG_TRY/PG_CATCH, ereport, SQLSTATE).

### 3. SPI exposed to Java as JDBC, via JNI native methods that re-establish PG's stack base

Java code talks to PG through what looks like JDBC, but underneath each JDBC call
is a `JNINativeMethod` registered on an internal class that calls the SPI C API.
`SPI_initialize` registers `_exec`, `_getProcessed`, `_getResult`, `_getTupTable`,
`_freeTupTable` and statically asserts that the Java-side copies of every
`SPI_OK_*`/`SPI_ERROR_*` constant match the C headers (`CONFIRMCONST`)
`[verified-by-code: SPI.c:31-110]`. The actual `SPI_connect` is lazy:
`Invocation_assertConnect()` connects on first use and registers trigger data if
present `[verified-by-code: Invocation.c:98-118]`, and `popInvocation` calls
`SPI_finish()` `[verified-by-code: Invocation.c:251-252]`. Because these native
methods may run on a JVM thread (not necessarily the original backend thread that
holds PG's real C stack), the SPI calls are bracketed by `STACK_BASE_PUSH(env)` /
`STACK_BASE_POP()` to give PG's stack-depth guard a valid base
`[verified-by-code: SPI.c:129-145]`. No core PL needs this — they run entirely on
the backend's own C stack. Cross-ref [[knowledge/idioms/spi]],
`.claude/skills/fmgr-and-spi/SKILL.md`.

### 4. Datum ↔ jobject marshalling through a per-type C "class" vtable

pljava reimplements a small object system in C to map PG types to Java types. A
`TypeClass` carries `coerceDatum` (Datum → `jvalue`) and `coerceObject` (jobject
→ Datum) function pointers; `Type_coerceDatum`/`Type_coerceObject` dispatch
through the instance's `typeClass`
`[verified-by-code: pljava-so/src/main/c/type/Type.c:286-312]`. `TypeClass_alloc`
allocates the vtable in `TopMemoryContext` and seeds the coercers with
"unimplemented" stubs `[verified-by-code: Type.c:1060-1092]`. Each scalar type is
a `.c` file under `pljava-so/src/main/c/type/` (`String.c`, `Integer.c`,
`Timestamp.c`, `Array.c`, `Composite.c`, …) supplying its own coercers — e.g.
`_String_coerceDatum` does server-encoding-aware conversion to a Java `String`
`[verified-by-code: pljava-so/src/main/c/type/String.c:52-60]`. This is the
analogue of plv8's `Converter` ([[knowledge/ideologies/plv8]]) and is the layer
that makes "a PG `text` becomes a Java `String`, a `timestamptz` becomes a
`java.time.OffsetDateTime`" work. The core analog is fmgr's input/output
functions plus the type cache; pljava builds a parallel, JNI-aware coercion table
on top. Cross-ref [[knowledge/idioms/fmgr]].

### 5. GC ↔ MemoryContext boundary handled by "DualState" + a ReferenceQueue, not finalizers

A Java object backed by a PG-allocated resource (a `TupleDesc`, an SPI plan, a
`MemoryContext`, a cursor) faces a lifetime mismatch: the JVM frees on GC, PG
frees on transaction/ResourceOwner end, and neither can safely call the other's
free routine at an arbitrary moment. pljava's answer is the **DualState**
mechanism. Rather than Java finalizers — "deprecated in recent Java anyway, which
can increase the number of threads needing to interact with PG" — DualState
objects are enqueued on a `ReferenceQueue` when their referent becomes
unreachable, and `pljava_DualState_cleanEnqueuedInstances()` is called from
"strategically-chosen points in native code so the thread already interacting
with PG will clean the enqueued items"
`[from-comment + verified-by-code: pljava-so/src/main/c/DualState.c:65-76]`. On
the PG side, a `ResourceRelease` callback (`resourceReleaseCB`) and
`pljava_DualState_nativeRelease(void *ro)` make the Java handles inaccessible when
the owning PG ResourceOwner/MemoryContext expires
`[verified-by-code: DualState.c:54-55,78-101]`. There is a family of single-shot
releasers — `SinglePfree`, `SingleMemContextDelete`, `SingleFreeTupleDesc`,
`SingleHeapFreeTuple`, `SingleFreeErrorData`, `SingleSPIfreeplan`,
`SingleSPIcursorClose` — each a JNI native that performs exactly one PG free
operation `[verified-by-code: DualState.c:108-209]`. `popInvocation` drives both
`nativeRelease` and `cleanEnqueuedInstances` on every invocation exit
`[verified-by-code: Invocation.c:241-249]`. This is a far more elaborate
GC↔context reconciliation than plv8's "second heap with its own memory cap"
([[knowledge/ideologies/plv8]] divergence #4): plv8 keeps the V8 heap entirely
separate from PG memory; pljava must instead make individual Java objects *own*
PG-context-scoped resources and release them deterministically at the right PG
lifetime boundary. Cross-ref [[knowledge/idioms/memory-contexts]] (ResourceOwner,
MemoryContextCallback).

### 6. Threads — a single-threaded backend hosting a multi-threaded VM, with a GUC-tunable entry policy

A JVM is inherently multithreaded (GC threads, JIT compiler threads, plus any
threads user code spawns), but a PG backend's C code is strictly single-threaded
and PG's `siglongjmp` error model assumes one thread of control. pljava's bridge
gives PG a serialized view: by default only the "main" thread enters PG while it
holds the JVM, and the GUC `pljava.java_thread_pg_entry` selects the policy for
other Java threads that try to enter PG —
`allow` / `error` / `block` / `throw`, encoded as a bitmask where bit 1 = "C code
refuses JNI calls on the wrong thread", bit 2 = "skip MonitorEnter/MonitorExit",
bit 4 = "Java code refuses wrong-thread calls before crossing JNI"
`[verified-by-code: Backend.c:441-449,525-530,1854-1871]`. `-Xrs` is passed to
the VM so it does not install its own handlers over PG's signals
`[verified-by-code: Backend.c:700]`, and (when `USE_PLJAVA_SIGHANDLERS`) pljava
installs its own `SIGINT`/`SIGTERM`/`SIGQUIT` handlers
`[verified-by-code: Backend.c:742-746]`. No core PL has a threading-entry policy
because none of them is multithreaded; this GUC is a pure consequence of putting
a thread-spawning runtime inside a single-threaded backend. Cross-ref
`.claude/skills/locking/SKILL.md` (PG's single-threaded-backend assumption).

### 7. Code lives in catalog tables (`sqlj.*`), loaded by a classloader-per-schema — not on the filesystem

Where core PLs store function source text in `pg_proc.prosrc`, pljava stores
**jars in catalog tables** and resolves classes from them at runtime. The install
SQL marks `sqlj.jar_repository`, `sqlj.jar_entry`, `sqlj.jar_descriptor`,
`sqlj.classpath_entry`, `sqlj.typemap_entry` for dump via
`pg_extension_config_dump`
`[verified-by-code: pljava-packaging/src/main/resources/pljava--.sql:54-67]`. The
`Loader` class (`extends ClassLoader`) loads "from jars installed in the database
with `SQLJ.INSTALL_JAR`" `[from-comment: Loader.java:87-92]`; it keys a
`ClassLoader` per schema (`s_schemaLoaders`), builds the classpath by querying
`sqlj.jar_repository` JOIN `sqlj.classpath_entry`, and fetches class bytes with
`SELECT entryImage FROM sqlj.jar_entry …`
`[verified-by-code: Loader.java:188-223,463]`. It deliberately forces SPI
`read_only => false` on these reads so that, mid-`install_jar`, the deployment
descriptor can see classes loaded earlier in the same transaction — a subtle
snapshot-visibility workaround documented at length
`[from-comment: Loader.java:60-85]`. This is a wholly different code-distribution
model from every core PL and from plv8 (which stores JS source in `prosrc`): the
unit of deployment is a jar in a table, versioned and dumped with the database,
with a per-schema classpath acting like a `search_path` for code. Cross-ref
[[knowledge/idioms/catalog-conventions]], [[knowledge/idioms/spi]].

### 8. Security: a real Java SecurityManager policy layer (now eroding under the JDK)

The trust split (`java` vs `javau`) is enforced not by an opcode mask (plperl) or
a Safe interpreter (pltcl) or absence-of-bindings (plv8), but by Java's
SecurityManager + a policy file named by `pljava.policy_urls`
`[verified-by-code: Backend.c:1749-1765]`. The headline fragility: upstream Java
disabled the SecurityManager (JEP 411/486), so on Java 24+ enforcement is gone.
pljava's validator now *refuses* to let a non-superuser create a `trusted`
(`java`) function when running with `-Djava.security.manager=disallow`, with a
long errdetail explaining that "this PL/Java version enforces security policy
using important Java features that upstream Java has disabled as of Java 24"
`[verified-by-code: Backend.c:1981-1996]`. The `pljava.allow_unenforced` GUC names
which languages may run without enforcement
`[verified-by-code: Backend.c:1767-1780]`. This is the corpus's clearest example
of a PL sandbox whose *foundation is being removed by its host runtime* —
contrast plv8, whose sandbox (V8 has no host bindings) cannot be taken away by a
JDK decision. Cross-ref `knowledge/issues/plperl.md`, `knowledge/issues/pltcl.md`
(the trust-gate ranking).

## Notable design decisions (with cites)

- **A resumable init state machine, re-entered from four call sites.** `initstage`
  is a module-global enum advanced by `initsequencer`'s fallthrough switch; assign
  hooks, the call handler, and the validator can all re-enter to resume after the
  user fixes a blocking GUC `[verified-by-code: Backend.c:533-575,577-590,1926-1929]`.
  This is why misconfiguration produces a `WARNING` ("Java virtual machine not yet
  loaded") plus a hint, rather than a hard failure
  `[verified-by-code: Backend.c:596-603]`.
- **`abort`/`exit`/`vfprintf` are redirected away from the JVM.** The option list
  hands the VM `my_abort`, `my_exit`, `my_vfprintf` so the JVM cannot directly
  call libc `abort()`/`exit()` and silently kill the backend
  `[verified-by-code: Backend.c:696-698]`; `_destroyJavaVM` even logs a
  "last-ditch message if the VM happens to rudely call exit()"
  `[from-comment: Backend.c:711-714]`.
- **Install-from-Java implies a chicken-and-egg sentinel.** Because the native lib
  cannot easily learn its own load path when invoked via `CREATE EXTENSION`
  (it sees the CREATE EXTENSION command, not a LOAD path), the SQL script saves
  the `module_pathname` into a sentinel table whose *name reads like an error
  message* ("see doc: do CREATE EXTENSION PLJAVA in new session") so a botched
  load surfaces a legible hint `[from-comment: pljava--.sql:9-22,32-47]`.
- **Handler functions are created with all privileges revoked from PUBLIC.**
  `InstallHelper.handlers` runs `REVOKE ALL PRIVILEGES ON FUNCTION
  sqlj.java_call_handler() FROM public` for each handler/validator
  `[verified-by-code: InstallHelper.java:561-562,582-583,603-604]`.
- **JNI lifetime hygiene is everywhere.** `JNI_pushLocalFrame(128)` /
  `JNI_popLocalFrame` bracket every invocation, and global refs are explicitly
  created/deleted (`NewGlobalRef`/`deleteGlobalRef`) to avoid JNI local-ref table
  overflow and ref leaks `[verified-by-code: Invocation.c:25,142-144,177,220-227,254]`.

## Links into corpus

- **PL siblings (the procedural-language sweep):** [[knowledge/ideologies/plv8]] —
  the closest structural twin. **Contrasts:** JVM (one-per-process, one-shot)
  vs V8 isolate (per-user, freely recreatable via `plv8_reset()`);
  bidirectional `ErrorData`↔`ServerException` round-trip vs JS↔C++↔ereport triple;
  SecurityManager-policy trust (erodible by the JDK) vs sandbox-by-absence (V8);
  jars-in-`sqlj.*`-tables + classloader-per-schema vs JS source in `prosrc`;
  DualState/ReferenceQueue GC reconciliation vs a separate capped V8 heap;
  a thread-entry-policy GUC vs single-threaded V8.
  Core analogs for the PL handler contract: `src/pl/plperl`, `src/pl/plpython`,
  `src/pl/tcl` — and the corpus PL notes `knowledge/issues/plperl.md`,
  `knowledge/issues/plpython.md`, `knowledge/issues/pltcl.md` for the trust-gate
  ranking pljava's SecurityManager story extends.
- **FFI-boundary exception-handling contrast:** [[knowledge/ideologies/pgrx]] —
  `pg_guard_ffi_boundary` bridges ereport-longjmp ↔ Rust unwind at every call;
  [[knowledge/ideologies/pgrouting]] — a catch-all C++ firewall funnels errors to
  out-params before the C side `ereport`s. pljava's bridge (#2) is the
  *bidirectional, stateful* member of this family.
- **Idioms / subsystems:**
  - [[knowledge/idioms/fmgr]] / [[knowledge/idioms/spi]] — the call-handler
    trio, the Datum↔jobject `TypeClass` vtable (#4), and the SPI-as-JDBC bridge (#3).
    Core analog: `src/backend/utils/fmgr/`, `src/backend/executor/spi.c`, the PL
    language-handler contract (`language_handler` return type, `pg_language`).
  - [[knowledge/idioms/error-handling]] — PG_TRY/PG_CATCH, `ereport`, SQLSTATE,
    `FlushErrorState` (#2). Core analog: `src/backend/utils/error/elog.c`.
  - [[knowledge/idioms/memory-contexts]] — the DualState/ResourceOwner/GC
    reconciliation (#5). Core analog: `src/backend/utils/mmgr/` (ResourceOwner,
    MemoryContextCallback).
  - [[knowledge/idioms/catalog-conventions]] — code-in-catalog (`sqlj.*` jar
    tables, `pg_extension_config_dump`) (#7).
  - [[knowledge/architecture/process-model]] — why one-JVM-per-process is
    survivable under PG's per-connection fork model (#1).
- `.claude/skills/extension-development/SKILL.md`,
  `.claude/skills/fmgr-and-spi/SKILL.md`,
  `.claude/skills/error-handling/SKILL.md`,
  `.claude/skills/gucs-config/SKILL.md`,
  `.claude/skills/bgworker-and-extensions/SKILL.md`.

## Anthropology takeaway

pljava is the maximal case of "host a foreign engine in a PG backend." Every tax
the corpus has catalogued for embedded engines shows up here at its heaviest: a
one-shot-per-process VM singleton (vs plv8's recreatable isolate), a bidirectional
stateful error bridge that round-trips a full `ErrorData` through a Java exception
and back, a GC↔ResourceOwner reconciliation built on weak references and a
deterministic clean-from-the-PG-thread discipline, a threading-entry policy for a
multithreaded runtime inside a single-threaded backend, code stored as jars in
catalog tables with a classloader-per-schema, and an extension that *installs
itself by running DDL from inside the very engine it is bootstrapping*. Its trust
model — a real SecurityManager policy — is also the corpus's clearest cautionary
tale: a PL sandbox whose foundation the host runtime (the JDK) is actively
removing, forcing pljava to fall back to "superuser-only trusted functions" on
Java 24+. The plv8 contrast is the sharpest in the sweep: same problem shape,
opposite answers at almost every axis.

## Sources

Fetched 2026-06-21 (branch `master`):

| URL | HTTP |
|---|---|
| https://api.github.com/repos/tada/pljava/git/trees/master?recursive=1 | 200 |
| https://raw.githubusercontent.com/tada/pljava/master/README.md | 200 |
| https://raw.githubusercontent.com/tada/pljava/master/pljava-packaging/src/main/resources/pljava.control | 200 |
| https://raw.githubusercontent.com/tada/pljava/master/pljava-packaging/src/main/resources/pljava--.sql | 200 |
| https://raw.githubusercontent.com/tada/pljava/master/pljava-packaging/src/main/resources/pljava.sql | 200 |
| https://raw.githubusercontent.com/tada/pljava/master/pljava-so/src/main/c/Backend.c | 200 |
| https://raw.githubusercontent.com/tada/pljava/master/pljava-so/src/main/c/Exception.c | 200 |
| https://raw.githubusercontent.com/tada/pljava/master/pljava-so/src/main/c/Invocation.c | 200 |
| https://raw.githubusercontent.com/tada/pljava/master/pljava-so/src/main/c/SPI.c | 200 |
| https://raw.githubusercontent.com/tada/pljava/master/pljava-so/src/main/c/DualState.c | 200 |
| https://raw.githubusercontent.com/tada/pljava/master/pljava-so/src/main/c/type/Type.c | 200 |
| https://raw.githubusercontent.com/tada/pljava/master/pljava-so/src/main/c/type/String.c | 200 |
| https://raw.githubusercontent.com/tada/pljava/master/pljava-so/src/main/c/InstallHelper.c | 200 |
| https://raw.githubusercontent.com/tada/pljava/master/pljava-so/src/main/include/pljava/JNICalls.h | 200 |
| https://raw.githubusercontent.com/tada/pljava/master/pljava/src/main/java/org/postgresql/pljava/sqlj/Loader.java | 200 |
| https://raw.githubusercontent.com/tada/pljava/master/pljava/src/main/java/org/postgresql/pljava/internal/InstallHelper.java | 200 |

**Fetch notes / substitutions:**
- No 404s. The manifest's guessed layout was correct: the JNI native bridge is
  under `pljava-so/src/main/c/` and the Java runtime under
  `pljava/src/main/java/org/postgresql/pljava/`.
- The `.control` file lives at `pljava-packaging/src/main/resources/pljava.control`
  (a template — `default_version = '${project.version}'`, `schema = sqlj`,
  `directory = 'pljava'`), not at the repo root.
- The real install logic is NOT in the `.sql` scripts (which only `LOAD` the lib);
  the sqlj-schema / `CREATE LANGUAGE` / handler-function DDL is executed from Java
  in `InstallHelper.java` (`groundwork`/`handlers`), driven by C `_PG_init` →
  `InstallHelper_groundwork` (`InstallHelper.c`).
- Files deep-read for cites: `Backend.c` (init sequencer, JVM bootstrap, GUCs,
  call handler, thread policy, security — ~lines 100-980, 1700-2000), `Exception.c`
  (full), `Invocation.c` (full), `SPI.c` (full), `DualState.c` (lines 1-209),
  `Type.c` (coercer dispatch + alloc), `String.c` (a concrete coercer),
  `Loader.java` (classloader/jar-table queries), `InstallHelper.java`
  (groundwork/handlers DDL).
- Skimmed / not deep-read (cited only structurally or not at all): the full
  `type/*.c` marshaller set beyond String, `JNICalls.c` body (only `JNICalls.h`
  macros read), `Function.c` (the per-function dispatch/cache — referenced via the
  call handler but not line-cited in depth), the annotation-processor /
  DDR-generation toolchain under `pljava-api` and `pljava-pgxs`, and the test
  surface. The Java-side SecurityManager policy implementation
  (`org.postgresql.pljava.policy`) was inferred from the C-side GUC + validator
  cites, not read directly — the Java-24 enforcement-erosion claim rests on
  `Backend.c:1981-1996` and the `policy_urls`/`allow_unenforced` GUC descriptions.
