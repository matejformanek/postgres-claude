# provsql — a planner_hook that rewrites every SELECT into a semiring-provenance circuit, stored in an mmap'd DAG behind a background worker

> Ideology note produced by the pg-extension-anthropologist cloud routine.
> Repo: `PierreSenellart/provsql` @ branch `master` (default_version `1.11.0-dev`),
> fetched 2026-07-05.
> Caveat: characterization based on the files actually fetched — `doc/provsql.md`
> (the README target), `Makefile` + `Makefile.internal` (the real PGXS build),
> `provsql.common.control`, the C core `src/provsql.c` (15,361 lines; the
> `_PG_init` + GUC block + hook wiring read in full, the 15k-line rewrite engine
> read at its structural markers not line-by-line), `src/provsql_shmem.{c,h}`,
> `src/provsql_mmap.c` (the bgworker + IPC glue + SQL-callable gate functions,
> read in full), `src/MMappedCircuit.{cpp read in full}`, `src/GenericCircuit.hpp`
> (the semiring `evaluate<S>()` template), `src/where_provenance.cpp`,
> `src/provsql_error.h`, `src/provsql_utils.h` (the `constants_t` OID cache),
> `src/provsql_shmem.h`. NOT fetched (probe → 404 for the guessed names, or not
> needed): `ProvenanceEvaluate.cpp` and `provsql_mmap.cpp` do not exist under
> those names (the worker glue is `provsql_mmap.c`, the store is
> `MMappedCircuit.cpp`); the `src/semiring/*.cpp` concrete semiring
> implementations (Counting, BooleanFormula, etc.), `src/BooleanCircuit.cpp`,
> `src/dDNNF*.cpp`, the tree-decomposition knowledge-compiler (`tdkc`), and the
> `circuit_cache.{c,h}` per-session cache body were not fetched — their call
> sites are cited instead. There is a `provsql.control`, but it is *generated* at
> build time from `provsql.common.control` (probe on `provsql.control` → 404;
> the `.common.control` source → 200).

## Domain & purpose

ProvSQL is a research-grade extension that adds **(m-)semiring provenance and
uncertainty/probabilistic-database management** to PostgreSQL: it computes
where-provenance, probabilities, Shapley values, and arbitrary semiring
evaluations over query results [from-README, doc/provsql.md:19-21]. The
mechanism: every base tuple in a tracked relation carries a `uuid` provenance
token; ProvSQL intercepts each `SELECT` at plan time and rewrites it so the
result tuples carry a *new* token wired into a **provenance circuit** — a DAG
of ⊕/⊗/⊖/δ/project/eq gates recording how each output was derived from inputs
[verified-by-code, provsql.c:5-18]. Answers to "how probable is this row",
"which source cells matter", "what does this row evaluate to in semiring S" are
then post-hoc traversals of that circuit under a chosen semiring, rather than
anything the base query computed. The provenance is thus a *shadow computation*
grafted onto the normal relational one.

## How it hooks into PG

Load model is `shared_preload_libraries = 'provsql'` (mandatory in the normal
multi-process build) followed by `CREATE EXTENSION provsql CASCADE`
[from-README, doc/provsql.md:36-49]; the control file declares
`requires = 'uuid-ossp'`, `relocatable = false`, `trusted = true`
[verified-by-code, provsql.common.control:1-7]. `_PG_init` hard-errors if it is
not being loaded from the postmaster (`!process_shared_preload_libraries_in_progress`)
in that build [verified-by-code, provsql.c:14863-14865].

Build is a **mixed C + C++17 shared object**, `MODULE_big = provsql`, whose
`OBJS` is `$(wildcard src/*.c)` plus `$(wildcard src/*.cpp src/semiring/*.cpp
src/distributions/*.cpp)` with the standalone-tool `.cpp` mains filtered out
[verified-by-code, Makefile.internal:OBJS]. It links `-lstdc++
-lboost_serialization` and forces `with_llvm = no` (JIT disabled due to LLVM
bugs) [verified-by-code, Makefile.internal].

`_PG_init` installs **five hooks** and defines a large GUC surface
[verified-by-code, provsql.c:15321-15349]:

- `planner_hook` → `provsql_planner` — the centerpiece: rewrites the `Query`
  tree of every tracked `SELECT` before planning [verified-by-code,
  provsql.c:14245, 15338].
- `ExecutorStart_hook` / `ExecutorEnd_hook` → `provsql_executor_start` /
  `provsql_executor_end` — maintain a re-entrancy/nesting depth used by the
  planner-side classifier [verified-by-code, provsql.c:14372, 14389, 15342-15343].
- `ProcessUtility_hook` → `provsql_ProcessUtility` — captures `CREATE TABLE AS`
  so derived tables inherit provenance lineage [verified-by-code,
  provsql.c:14425-14451, 15344].
- `shmem_startup_hook` (+ `shmem_request_hook` on PG ≥ 15) →
  `provsql_shmem_startup` / `provsql_shmem_request` — reserve the
  `provsqlSharedState` segment and a named LWLock tranche [verified-by-code,
  provsql.c:15322-15340; provsql_shmem.c:127-181].

It then registers **two background workers** — `RegisterProvSQLMMapWorker()`
(the circuit store) and `RegisterProvSQLKCMCPWorker()` (a knowledge-compiler
server supervisor) [verified-by-code, provsql.c:15347-15348;
provsql_mmap.c:102-125]. The MMap worker is `BgWorkerStart_PostmasterStart`,
`bgw_restart_time = 1`, `BGWORKER_SHMEM_ACCESS`, library `provsql`, entry
`provsql_mmap_worker` [verified-by-code, provsql_mmap.c:106-124].

The SQL surface is a set of `PG_FUNCTION_INFO_V1` C functions —
`create_gate`, `get_gate_type`, `get_children`, `set_prob`, `get_prob`,
`set_extra`, `set_table_info`, `set_ancestors`, … — that marshal a `pg_uuid_t`
token plus payload and round-trip it to the worker [verified-by-code,
provsql_mmap.c:129-1070]. The uses-the-hook `PG_MODULE_MAGIC;` is the plain
(no-args) form [verified-by-code, provsql.c:82].

### The core mechanism: two processes talking over anonymous pipes

The provenance circuit does not live in a heap table. It lives in five
**mmap'd files under `$PGDATA/base/<db_oid>/`** (`MAPPING`, `GATES`, `WIRES`,
`EXTRA`, `TABLE_INFO`) owned by the MMap background worker, one `MMappedCircuit`
per database, created lazily on first message [verified-by-code,
MMappedCircuit.cpp:41-53, 196-205]. Backends never touch these files; they
send single-byte-tagged messages (`'C'` create gate, `'t'` get type, `'c'` get
children, `'P'` set prob, `'g'` serialize whole sub-circuit, …) down an
**anonymous `pipe(2)`** whose four fds live in the shared segment, and read the
reply back [verified-by-code, provsql_shmem.c:156-163;
provsql_mmap.c:157-204]. The `provsqlSharedState` LWLock serialises pipe writes;
small writes (fitting in `PIPE_BUF`) take the lock `LW_SHARED` and rely on POSIX
pipe write atomicity, while oversized child lists escalate to `LW_EXCLUSIVE` and
a multi-write batch [verified-by-code, provsql_mmap.c:239-282;
provsql_shmem.c:183-196]. The worker's `provsql_mmap_main_loop` blocks on
`READM(c)` and dispatches forever [verified-by-code, MMappedCircuit.cpp:542-556].

## Where it diverges from core idioms

- **Provenance is stored outside the MVCC heap, in worker-owned mmap files.**
  Core's every-datum-in-a-heap-tuple model is bypassed for the circuit: the
  authoritative gate DAG is an append-only set of `mmap`'d vectors managed by a
  single background worker, indexed by UUID, with no transactional visibility,
  no WAL, and no rollback [verified-by-code, MMappedCircuit.cpp:41-107,
  558-565]. A tuple's heap row holds only the `uuid` token; its *meaning* is in
  the out-of-heap DAG. Crash consistency is claimed via a tombstone scheme that
  keeps each file "internally consistent without any extra recovery step" —
  explicitly *not* via WAL [from-comment, MMappedCircuit.cpp:567-584]. This is
  the single most distinctive divergence: provenance updates are **not part of
  the transaction that produces them** and survive/vanish independently of
  commit/abort.

- **`planner_hook` mutates the `Query` tree wholesale, not the plan.** Rather
  than adding a Path or a custom scan, `provsql_planner` rewrites the parse-tree:
  it discovers provenance columns in the range table, synthesizes `Var`s onto
  them (`make_provenance_attribute`, setting the PG16 `RTEPermissionInfo`
  `selectedCols` bitmap by hand), splices a provenance expression into the
  target list, maps SQL operators to semiring operations (⊗ for join, ⊕ for
  duplicate-elimination, ⊖ for `EXCEPT`), and even inlines CTEs and rewrites
  `DISTINCT` into `GROUP BY` before handing off to the standard planner
  [verified-by-code, provsql.c:5-18, 172-206, 6609-6712]. It calls back into
  SQL via `SPI_connect`/`SPI_execute` *from inside the planner hook* to lower
  recursive CTEs and plant reachability aggregations [verified-by-code,
  provsql.c:1311-1314, 1704-1707, 1923-1926] — an unusually deep rewrite for a
  planner hook (most hooks observe or swap the plan; this one re-authors the
  query).

- **C++/C boundary with an exception→`elog` firewall.** SQL-callable C++ entry
  points wrap their whole body in `try { … } catch(const std::exception &e) {
  provsql_error("…: %s", e.what()); } catch(...) { provsql_error("… Unknown
  exception"); }` [verified-by-code, where_provenance.cpp:180-187]. Since
  `provsql_error` is `elog(ERROR, "ProvSQL: " fmt, …)` [verified-by-code,
  provsql_error.h:38], the firewall converts a C++ exception into a PG
  `ERROR`/longjmp at the outermost C++ frame — the canonical pattern for a
  library that must not let a C++ exception unwind through PG's setjmp-based
  error stack. The C↔C++ seam is bridged with `extern "C"` blocks around PG
  headers [verified-by-code, MMappedCircuit.cpp:32-36].

- **`elog(ERROR)` longjmp *inside* deep C++ code skips destructors.** The same
  `provsql_error` macro is called from hundreds of sites deep inside the C++
  store and dispatch (`MMappedCircuit.cpp` alone has ~40) [verified-by-code,
  MMappedCircuit.cpp:237-537]. Each is an `elog(ERROR)` longjmp that unwinds
  *past* any live C++ automatic objects without running their destructors —
  the well-known hazard of mixing `ereport`/`elog` with C++ RAII. Here it is
  largely on IPC-failure paths in the worker (which then dies and is restarted
  by `bgw_restart_time = 1`), so the leaked C++ state is discarded with the
  process; but it is a genuine divergence from RAII-safe C++ and from PG's own
  `PG_TRY`/`PG_CATCH` discipline [inferred, from MMappedCircuit.cpp:225-556 +
  provsql_error.h:38].

- **A per-database singleton `std::map<Oid, MMappedCircuit*>` as process-global
  state.** The worker holds an ordinary C++ `std::map` of live circuits keyed by
  database OID, `new`'d lazily and `delete`d at shutdown — not a PG shmem hash,
  not a relcache entry [verified-by-code, MMappedCircuit.cpp:39, 60-65,
  196-205]. State lives in worker heap + mmap, orthogonal to PG's catalog and
  memory-context machinery.

- **Semiring soundness enforced at evaluation via provenance-class tagging.**
  The `provsql.provenance` enum GUC (`where`/`semiring`/`absorptive`/`boolean`)
  declares, per session, the most specific provenance class the circuit must
  stay faithful to; gates are *tagged* with the assumptions used to build them,
  and `GenericCircuit::evaluate<S>()` refuses to run a semiring `S` that "does
  not admit a homomorphism" from a tagged gate's class, raising rather than
  silently returning an unsound value [verified-by-code, provsql.c:113-139,
  14878-14908; GenericCircuit.hpp:35-92]. This is a type-soundness discipline
  the SQL type system has no notion of — enforced in template C++.

- **Custom `constants_t` OID cache instead of syscache lookups per call.** A
  large `constants_t` struct caches ~60 OIDs (types, functions, operators,
  aggregates for the `random_variable` machinery) fetched once via
  `get_constants(bool)` and threaded through the rewrite [verified-by-code,
  provsql_utils.h:155-231; provsql.c:1226, 14257]. This is a hand-rolled
  equivalent of the fmgroids/syscache pattern, sized to the extension's own
  schema.

- **Spawns external solver binaries from the backend.** The
  `provsql.tool_search_path` (PGC_SUSET) and `provsql.kcmcp_server` (PGC_SIGHUP)
  GUCs configure directories/commands for external knowledge compilers (`d4`,
  `c2d`, `minic2d`, `dsharp`, `weightmc`, `graph-easy`) that ProvSQL execs to
  compile Boolean circuits to d-DNNF for exact probability [verified-by-code,
  provsql.c:95-97, 14947-14998]. Both are deliberately *not* `PGC_USERSET` — the
  comments note a non-privileged role must not redirect them to an
  attacker-controlled binary [from-comment, provsql.c:95, 14990-14991].

## Notable design decisions

- **A second, process-collapsed build (`PROVSQL_INPROCESS_STORE`) for WASM /
  PGlite.** The whole pipe-and-worker architecture is `#ifdef`'d out for a
  single-process target: shared memory, the worker, and the LWLocks become
  no-ops; the pipes are replaced by two growable in-memory byte FIFOs
  (`provsql_fifo`); and the backend calls `provsql_inproc_generic_circuit`
  directly instead of serialising a Boost archive across the (now absent)
  process boundary — which is also what lets the WASM build drop the compiled
  `libboost_serialization` dependency [verified-by-code, provsql_shmem.c:31-123;
  provsql_shmem.h:76-108; MMappedCircuit.cpp:207-223, 385-401]. In this build the
  planner hook is installed at `CREATE EXTENSION`/dlopen time and no
  `shared_preload_libraries` is required [verified-by-code, provsql.c:14855-14866].

- **Cross-process circuit transfer by Boost binary serialization over the
  pipe.** For whole-sub-circuit reads (message `'g'`/`'j'`), the worker
  `boost::archive::binary_oarchive`-serialises a `GenericCircuit` into a
  `stringstream` and ships the bytes back to the backend, which deserialises it
  [verified-by-code, MMappedCircuit.cpp:390-399, 522-531]. The DAG is thus
  marshalled through a third-party serializer, not PG's own I/O funcs.

- **Concurrency hazard handled by placeholder-upgrade in `createGate`.** Under
  concurrent backends, a child gate can be lazy-added as a default `gate_input`
  by an earlier-arriving parent before its own real `createGate` arrives; the
  code detects the placeholder and upgrades it in place rather than dropping the
  real gate [from-comment + verified-by-code, MMappedCircuit.cpp:67-107]. The
  per-session `circuit_cache` is likewise deliberately *not* trusted to short-
  circuit the worker IPC, because a cache hit only proves "seen this session",
  not "worker has the gate" [from-comment, provsql_mmap.c:206-225].

- **Relcache invalidation broadcast by hand from DML paths.** `set_table_info` /
  `remove_table_info` / `set_ancestors` call `CacheInvalidateRelcacheByRelid`
  themselves — guarded by a `SearchSysCacheExists1(RELOID, …)` existence check —
  because they are invoked from DML and upgrade-backfill paths that, unlike DDL,
  do not already emit an invalidation [verified-by-code, provsql_mmap.c:694-707,
  898-899].

- **`trusted = true` but the control file is generated per major version.** The
  build strips the `trusted` line from the generated `provsql.control` on PG < 13
  (which predates trusted extensions) [verified-by-code, Makefile.internal:
  `$(EXTENSION).control` rule]. The SQL install script itself is assembled from
  version-gated fragments (`provsql.common.sql` + `provsql.14.sql`) and a frozen
  `provsql--1.0.0.sql` fixture drives the `ALTER EXTENSION … UPDATE` chain test
  [verified-by-code, Makefile.internal: `sql/provsql.sql`, `BASE_INSTALL`].

- **A `provsql.provenance = 'boolean'` fast lane routes #P-hard UCQs through
  tractable exact compilers.** When the session declares Boolean provenance, the
  planner recognises unsafe/`#P`-hard UCQs and reroutes their existence
  provenance through a Möbius-inversion route (guaranteed-PTIME for its class)
  or a joint-width tree-decomposition compiler, each gated by data/treewidth
  caps (`provsql.mobius_max_gates`, `provsql.joint_max_treewidth`,
  `provsql.joint_max_states`) [verified-by-code, provsql.c:103-111,
  15202-15316]. This is a whole probabilistic-inference planner living inside a
  Postgres extension's GUC-configured hook.

## Links into corpus

- [[onesparse]] — the other extension in the corpus built on *semirings*
  (SuiteSparse:GraphBLAS linear algebra over user-chosen semirings). ProvSQL's
  `GenericCircuit::evaluate<S>()` dispatch table (plus/times/monus/…) is the
  provenance-circuit analogue of GraphBLAS semiring ops; useful contrast on
  "semiring as a first-class configurable evaluation strategy".
- [[pgrouting]] — C++ (Boost Graph) extension with the same C++-exception →
  `ereport`/`elog` firewall at the SQL boundary; direct comparison point for the
  `catch(std::exception)` → `elog(ERROR)` translation and the Boost dependency.
- [[pg-libphonenumber]] — smaller C++ extension whose whole reason-for-being is
  the same exception-firewall pattern; the minimal version of ProvSQL's seam.
- [[parquet_s3_fdw]] — C++ FDW that also has to keep C++ exceptions from
  unwinding through PG's setjmp stack; another firewall exemplar.
- [[pgrx]] — Rust safety-boundary contrast: pgrx makes the panic↔`ereport`
  boundary a framework guarantee, where ProvSQL hand-writes the C++ equivalent
  per entry point (and leaves the internal-`elog`-skips-destructors hazard open).
- [[pg_background]] / [[prest_bgworker]] — other background-worker users;
  contrast ProvSQL's *persistent, IPC-served* worker (pipe + mmap store) with
  their task-runner workers.
- [[wasmer-postgres]] / [[pglite-fusion]] — the WASM/PGlite corner ProvSQL's
  `PROVSQL_INPROCESS_STORE` build targets; contrast on collapsing the
  multi-process design for a single-process in-browser Postgres.

## Sources

- `https://raw.githubusercontent.com/PierreSenellart/provsql/master/README.md`
  — HTTP 200 (a stub containing only the path `doc/provsql.md`).
- `https://raw.githubusercontent.com/PierreSenellart/provsql/master/doc/provsql.md`
  — HTTP 200. The real README; thesis, install, Studio, license.
- `.../Makefile` — HTTP 200. Thin porcelain wrapper forwarding to
  `Makefile.internal`.
- `.../Makefile.internal` — HTTP 200. The real PGXS build: `MODULE_big`, `OBJS`
  wildcard over `src/*.c` + `src/*.cpp` + `src/semiring/*.cpp` +
  `src/distributions/*.cpp`, Boost link, `with_llvm = no`, generated control +
  install-script assembly, the `tdkc` / `provsql_migrate_mmap` tool targets.
- `.../provsql.common.control` — HTTP 200. `requires = 'uuid-ossp'`,
  `relocatable = false`, `trusted = true`, `default_version = '1.11.0-dev'`.
- `.../provsql.control` — HTTP 404. Generated at build time from
  `provsql.common.control` (major-version-gated `trusted` strip).
- `.../provsql.control.in`, `.../Makefile.in` — HTTP 404. Not the build model
  (PGXS + `.common.control`, not autoconf).
- `.../src/provsql.c` — HTTP 200 (619,860 bytes, 15,361 lines). The C core:
  `PG_MODULE_MAGIC`, the GUC block + `_PG_init`, all five hooks, and the
  `Query`-tree provenance rewriter. All `provsql.c` cites point here.
- `.../src/provsql_shmem.c` + `.h` — HTTP 200. `provsqlSharedState`, LWLock
  wrappers, pipe fds, and the `PROVSQL_INPROCESS_STORE` FIFO variant.
- `.../src/provsql_mmap.c` — HTTP 200. Background-worker registration + entry
  point, the `STARTWRITEM`/`ADDWRITEM`/`SENDWRITEM` IPC macros, and the
  `PG_FUNCTION_INFO_V1` gate/table-info SQL functions.
- `.../src/provsql_mmap.h` — HTTP 200. Worker + IPC declarations.
- `.../src/MMappedCircuit.cpp` — HTTP 200. The mmap circuit store, the worker
  dispatch switch, the main loop, Boost-serialised sub-circuit transfer, the
  tombstone table-info scheme, `createGenericCircuit` BFS.
- `.../src/MMappedCircuit.h` — HTTP 200.
- `.../src/GenericCircuit.hpp` — HTTP 200. The `evaluate<S>()` semiring template
  and the provenance-class soundness gate.
- `.../src/GenericCircuit.cpp` — HTTP 200 (structure only).
- `.../src/where_provenance.cpp` — HTTP 200. The `try/catch → provsql_error`
  exception-firewall exemplar (lines 180-187) and SPI use.
- `.../src/provsql_error.h` — HTTP 200. `provsql_error` = `elog(ERROR, "ProvSQL:
  " …)` (plus the `tdkc` stub note).
- `.../src/provsql_utils.h` — HTTP 200. The `constants_t` OID cache.
- `.../src/Circuit.hpp` + `.h` — HTTP 200 (skim).
- `.../src/provsql_utils_cpp.h` — HTTP 200 (skim; `extern "C"` PG-header wrap).
- `.../src/circuit_cache.h` — HTTP 200 (cited, body not fetched).
- Probes that 404'd (names guessed from the task brief, resolved from
  `Makefile.internal` instead): `src/ProvenanceEvaluate.cpp`,
  `src/provsql_mmap.cpp` (it is `.c`), `src/Circuit.cpp`, `src/provsql_utils.cpp`
  (it is `.h`-only on the C++ side; the C body is `provsql_utils.c`, not
  fetched), `src/provsql_error.c`/`.cpp` (macro-only header, no TU),
  `src/circuit_cache.c`, `src/semiring/Semiring.hpp`,
  `src/semiring/Counting.cpp`, `src/semiring/BooleanFormula.cpp`,
  `src/MMapProvenanceMapping.*`, `src/provsql_interface.*`.
- GitHub git/trees API + `get_file_contents` MCP — not usable (session scoped to
  a different repo; 403). File set enumerated from `Makefile.internal`'s `OBJS`
  wildcards plus direct raw probes.
