# pg_jitter — ideology / divergence-from-core notes

> Extension: `vladich/pg_jitter` @ `master`. **There is no `.control` file
> and no `CREATE EXTENSION`** — pg_jitter is a **JIT provider**, a shared
> library named by the `jit_provider` GUC and loaded by core's `jit.c`, not a
> SQL-level extension. It registers via the documented
> `_PG_jit_provider_init(JitProviderCallbacks *cb)` entry point
> `[verified-by-code: src/pg_jitter_meta.c:1589; src/pg_jitter_sljit.c:244;
> src/pg_jitter_mir.c:365; src/pg_jitter_asmjit.cpp:134]`. The one piece of
> module bookkeeping is `PG_MODULE_MAGIC_EXT(.name = "pg_jitter")`
> `[verified-by-code: src/pg_jitter_meta.c:60]`. 203★, C (with one C++ backend,
> `pg_jitter_asmjit.cpp`). One durable "how this diverges from core PG design"
> doc. All `file:line` cites point into the **pg_jitter tree** (`src/*.c`,
> `src/*.h`, `README.md`, `CMakeLists.txt`), **NOT** into PG `source/`.
> Confidence tags: `[verified-by-code]` `[from-README]` `[from-comment]`
> `[inferred]` `[unverified]`.
>
> **Sibling note:** pg_jitter is unusual — **there is no close sibling in the
> corpus.** Almost every other ideology doc is a type, an access method, a
> background worker, an FDW, or a hook-chaining extension. pg_jitter plugs into
> a *different* core extension surface entirely: the JIT-provider ABI
> (`JitProviderCallbacks` + `_PG_jit_provider_init`), which core itself uses
> for its in-tree LLVM provider (`src/backend/jit/llvm/`). The nearest
> *thematic* neighbors are [[knowledge/ideologies/pg-strom]] (also generates
> native code at query time, but as a GPU executor via custom-scan + FDW hooks,
> not via the JIT-provider ABI) and [[knowledge/ideologies/pgrx]] /
> [[knowledge/ideologies/pglite-fusion]] (foreign codegen toolchains brought
> into PG, but for authoring functions, not for replacing the expression
> compiler). Read this doc as the corpus's single entry on the
> **`jit_provider` plug-point**.

## Domain & purpose

pg_jitter is an **alternative JIT provider** for PostgreSQL 14–18 that replaces
core's LLVM-based JIT with one of three lightweight native-codegen backends —
**sljit** (C, register machine), **AsmJIT** (C++, native assembler), and
**MIR** (C, medium-level typed IR) `[from-README: README.md:5]`. The thesis is
that LLVM's JIT compiles expressions in *tens to hundreds of milliseconds*,
which only pays off on heavy OLAP queries; pg_jitter compiles in *microseconds*,
making JIT worthwhile for ordinary OLTP queries too `[from-README:
README.md:9-13]`. Core ships `jit_above_cost = 100000` precisely because LLVM is
slow to compile; the README recommends lowering it to ~200–2000 for pg_jitter
`[from-README: README.md:23, 175]`.

The work it accelerates is the same work core's JIT targets: PostgreSQL
interprets expressions by walking `ExprState->steps[]` (the `execExprInterp.c`
opcode array) and does per-row tuple deforming. pg_jitter walks that same
`steps[]` array and emits native machine code for the hot opcodes, delegating
the rest back to PG's `ExecEval*` C functions `[from-README: README.md:183-188;
verified-by-code: src/pg_jitter_sljit.c:2924, 683-684]`. On top of plain
expression JIT it layers specialized paths the core JIT does not have: PCRE2 +
StringZilla SIMD for LIKE/ILIKE/regexp, and pre-compiled binary-search trees /
hash probes for CASE and `IN (ANY)` `[from-README: README.md:33-34]`.

The interesting anthropology is that pg_jitter **occupies a core-sanctioned
extension slot** — `jit_provider` is a documented, swappable interface — and yet
its presence in that slot drives an unusual set of divergences, because the
*one* in-tree implementation of that interface (LLVM) is the implicit reference,
and pg_jitter must re-derive everything LLVM gets "for free" (executable-memory
management, ResourceOwner integration, parallel-worker behavior) without LLVM.

## How it hooks into PG

- **The `jit_provider` GUC names the `.so`.** Core's `jit.c` reads
  `jit_provider` (a `PGC_POSTMASTER` string GUC), `load_external_function`s the
  named library, and calls its `_PG_jit_provider_init`. pg_jitter ships **four**
  such libraries: `pg_jitter` (the meta dispatcher) and `pg_jitter_sljit` /
  `pg_jitter_asmjit` / `pg_jitter_mir` (the concrete backends), each
  independently selectable `[from-README: README.md:122-130, 217;
  verified-by-code: src/pg_jitter_meta.c:11]`. Because `jit_provider` is
  `PGC_POSTMASTER`, picking a *provider* needs a reload/restart, but the meta
  provider then re-exposes a `PGC_USERSET` GUC (`pg_jitter.backend`) for restart-
  free *backend* switching `[from-README: README.md:60, 126-130]`.

- **`_PG_jit_provider_init(JitProviderCallbacks *cb)`** is the entry point. Each
  library fills the three-callback struct:
  - `cb->compile_expr` — `meta_compile_expr` / `sljit_compile_expr` /
    `mir_compile_expr` / `asmjit_compile_expr`
  - `cb->release_context` — the *shared* `pg_jitter_release_context` for the three
    concrete backends; the meta provider uses its own `meta_release_context`
  - `cb->reset_after_error` — `sljit_reset_after_error` etc.; meta fans out to all
  `[verified-by-code: src/pg_jitter_meta.c:1593-1595; src/pg_jitter_sljit.c:245-247;
  src/pg_jitter_mir.c:366-368; src/pg_jitter_asmjit.cpp:136-138]`.

- **The JIT context extends `JitContext`.** `PgJitterContext` embeds
  `JitContext base` as its **first member** so a `PgJitterContext *` is freely
  castable to the `JitContext *` PG hands back to `release_context`
  `[verified-by-code: src/pg_jitter_common.h:122-137]`. `pg_jitter_get_context`
  mirrors `llvmjit.c`'s get-or-create pattern: it reuses `es_jit` if set, else
  `MemoryContextAllocZero(TopMemoryContext, …)`, wires `base.flags` from
  `es_jit_flags`, registers with the ResourceOwner, and stashes itself in
  `parent->state->es_jit` `[verified-by-code: src/pg_jitter_common.c:673-707;
  from-comment: "Follows the pattern in llvmjit.c:222-246"
  src/pg_jitter_common.c:671]`.

- **GUCs** are registered in `_PG_jit_provider_init`, not `_PG_init` (a provider
  has no `_PG_init`). The meta provider defines `pg_jitter.backend` (enum:
  sljit/asmjit/mir/auto), `pg_jitter.parallel_mode`, `pg_jitter.shared_code_max`,
  `pg_jitter.deform_cache`, `pg_jitter.min_expr_steps`, the adaptive-selection
  GUCs, and more — all `PGC_USERSET`, most flagged `GUC_ALLOW_IN_PARALLEL`
  `[verified-by-code: src/pg_jitter_meta.c:1619-1734]`. Concrete backends guard
  every `DefineCustom*Variable` with `if (!GetConfigOption(..., true, false))`
  so that loading one backend after another (or after meta) does not double-
  define `[verified-by-code: src/pg_jitter_sljit.c:253-305]`. See
  [[knowledge/idioms/guc-variables]].

- **No catalog, no install SQL for the provider itself.** There is a
  `sql/pg_jitter_functions.sql` exposing helper SQL functions (e.g.
  `pg_jitter_current_backend()` `[verified-by-code: src/pg_jitter_meta.c:1329-1334]`),
  but the provider is wired purely through `jit_provider` + the callbacks struct
  — no `pg_proc`/`pg_type` rows are required to make JIT happen. Contrast every
  `CREATE EXTENSION`-based ideology doc. See [[knowledge/idioms/catalog-conventions]]
  (by its *absence* here).

## Where it diverges from core idioms

### 1. The plug-point IS the core extension surface — but pg_jitter REPLACES llvmjit rather than layering a hook

Most extensions in the corpus diverge by *adding* behavior through a hook chain
(`ProcessUtility_hook`, `planner_hook`, `ExecutorStart_hook`) — they save the
previous hook and call through to it. The JIT-provider interface is categorically
different: it is a **single-occupant slot**. `jit_provider` names exactly one
`.so`, and that library's `compile_expr` is THE expression compiler for the
backend `[from-README: README.md:122-126]`. There is no "previous provider" to
chain to; pg_jitter does not wrap llvmjit, it *displaces* it. This is the
cleanest example in the corpus of an extension that diverges not by adding a
layer but by **substituting an entire core subsystem implementation** through a
documented ABI. Core's own llvmjit provider (`src/backend/jit/llvm/llvmjit.c`,
dispatched by `src/backend/jit/jit.c`) is the reference implementation of the
exact same three callbacks; pg_jitter is a second, independent implementation of
`JitProviderCallbacks`. The only thing it shares with core is the ABI shape and
the `ExprState->steps[]` it consumes `[verified-by-code:
src/pg_jitter_sljit.c:244-247; from-README: README.md:183]`.

### 2. Code generation bypasses LLVM IR entirely — direct native emission per opcode, with a fallback to PG's own ExecEval*

llvmjit lowers each `ExprEvalStep` into LLVM IR and lets LLVM's optimizer +
codegen produce machine code (the slow part). pg_jitter walks the same
`state->steps[]` and emits target-native instructions *directly* for the hot
opcodes via its backend's low-level IR (sljit's LIR, AsmJIT's assembler, MIR's
typed ops), with **no IR-optimization pass** `[from-README: README.md:29,
183-188; verified-by-code: src/pg_jitter_sljit.c:4 "Walks ExprState->steps[] and
emits native code using sljit's LIR", 683-684, 2924-2925]`. Opcodes it does not
emit native code for are handled by `pg_jitter_fallback_step(state, op,
econtext)`, which re-dispatches on `ExecEvalStepOp` and calls the matching
`ExecEval*` C function — i.e. the *interpreter's* implementation, reused as a
runtime library `[verified-by-code: src/pg_jitter_common.c:823-833]`. This
"native-for-hot-opcodes, call-the-interpreter-for-the-rest" hybrid is a
deliberate inversion of LLVM's "lower everything, optimize globally" model, and
is what buys the microsecond compile times. The README frames three "tiers":
Tier 0 emits leaf ops inline (no `FunctionCallInfo`), Tier 1 makes direct calls
to unwrapped `jit_*` natives (bypassing fmgr), Tier 2 calls C wrappers for
pass-by-reference types `[from-README: README.md:190-194]`. See
[[knowledge/idioms/fmgr]] — pg_jitter's whole point is to *not* go through fmgr
on the hot path.

### 3. Executable-memory lifecycle is bolted onto PG's ResourceOwner by hand, with a backend-specific free callback per compiled function

LLVM's MCJIT owns its executable memory; PG's llvmjit provider hands the whole
thing to `jit_release_context`. pg_jitter has no such runtime, so it builds the
lifecycle itself. A `PgJitterContext` carries a linked list of `CompiledCode`
records, each holding a `free_fn` + `data` `[verified-by-code:
src/pg_jitter_common.h:83-88, 122-137]`. Every compiled function is registered
via `pg_jitter_register_compiled` (alloc'd in `TopMemoryContext`, prepended to
the list) `[verified-by-code: src/pg_jitter_common.c:713-723]`, and
`pg_jitter_release_context` walks the list calling each `free_fn` when the
query's ResourceOwner releases `[verified-by-code:
src/pg_jitter_common.c:784-790]`. The free callbacks are backend-specific:
`sljit_free_code()` (unmaps mmap'd executable memory), `JitRuntime::release()`
(AsmJIT), or `MIR_gen_finish()` + `MIR_finish()` (tears down the whole MIR
context) `[from-README: README.md:226-228]`. The registration even has an
exception-safe variant, `pg_jitter_register_compiled_or_free`, wrapping the
list-link `MemoryContextAlloc` in `PG_TRY`/`PG_CATCH` so that an OOM ERROR while
recording the cleanup record still frees the just-allocated executable code
"Several backends allocate executable code outside PostgreSQL memory contexts"
`[verified-by-code: src/pg_jitter_common.c:725-743]`. This is the
mmap-executable-memory analog of the hand-rolled allocator hooks other
vendored-library types carry — core types never manage executable pages. See
[[knowledge/idioms/memory-contexts]] and [[knowledge/idioms/error-handling]].

### 4. The ResourceOwner integration spans two incompatible PG APIs, and the meta provider exposes a pointer-identity hazard in `ResourceOwnerForget`

The JIT context registers on `CurrentResourceOwner` so it is freed at query end.
But the API split across versions: PG14–16 use the JIT-specific
`ResourceOwnerEnlargeJIT` / `ResourceOwnerRememberJIT` / `ResourceOwnerForgetJIT`
(via `utils/resowner_private.h`), while PG17+ use the generic
`ResourceOwnerDesc` mechanism with a custom descriptor
(`pg_jitter_resowner_desc`, `release_phase = RESOURCE_RELEASE_BEFORE_LOCKS`,
`release_priority = RELEASE_PRIO_JIT_CONTEXTS`) `[verified-by-code:
src/pg_jitter_common.c:624-667]`. The double-forget hazard is explicit: on
PG14–16, PG's own `jit_release_context` calls `ResourceOwnerForgetJIT` *after*
the callback returns, so `pg_jitter_release_context` must **not** also forget
(it would corrupt the ResourceOwner); on PG17+ pg_jitter owns the desc and must
forget itself `[verified-by-code: src/pg_jitter_common.c:797-806; from-comment].`
The sharper divergence is in the **meta** provider: because each backend `.so`
links its *own copy* of `pg_jitter_common.c`, each has a *distinct*
`pg_jitter_resowner_desc` address, and `ResourceOwnerForget` matches by pointer.
If the meta provider let a backend create the context, the desc used to Remember
would not match the one used to Forget. The fix is `meta_ensure_context`:
pre-create the JIT context with the *meta's* desc before delegating
`compile_expr`, so the backend's `pg_jitter_get_context` finds `es_jit` already
set and returns it without re-registering `[verified-by-code:
src/pg_jitter_meta.c:13-19 (header comment), 1132-1136]`. This per-`.so`-static-
duplication footgun is unique to a multi-library provider; no single-`.so`
extension hits it.

### 5. `reset_after_error` is a near-no-op for concrete backends but a fan-out for meta — and the asymmetry is load-bearing

Core's `JitProviderCallbacks.reset_after_error` exists so a provider can clean
global mutable state after a transaction aborts mid-compile. pg_jitter's concrete
backends declare they have *none*: `pg_jitter_reset_after_error` is documented as
"Nothing to do — our backends don't maintain global mutable state"
`[verified-by-code: src/pg_jitter_common.c:812-814]`. (Each backend overrides
with its own `sljit_reset_after_error` etc., but the shared philosophy is
"per-context state, nothing global to unwind".) The meta provider, by contrast,
*must* fan the call out to every loaded backend, because after an error it cannot
know which backend was mid-compile: `meta_reset_after_error` loops over all
available backends calling each `cb.reset_after_error()` `[verified-by-code:
src/pg_jitter_meta.c:1316-1324]`. The same fan-out logic governs the deform-cache
reset in `meta_release_context`: it resets *all* backends' `dispatch_fast[]`
caches, not just the one used, because under Linux `RTLD_GLOBAL` all backends'
deform-dispatch calls resolve to the first-loaded backend's copy via the PLT, so
`backends_used` undercounts and resetting only the recorded backend leaves a
stale cache that crashes on `TupleDesc` pointer reuse `[verified-by-code:
src/pg_jitter_meta.c:1209-1230; from-comment].` This is an error-recovery
discipline far more involved than a single-implementation provider needs — it is
the cost of hosting three independent codegens behind one callback set.

### 6. Cross-query caching of compiled deform code — core JIT recompiles every query

A standout divergence from llvmjit's "compile fresh per query" model:
`pg_jitter.deform_cache` (default `on`) **caches compiled tuple-deform functions
across queries within a backend process** `[from-README: README.md:154;
verified-by-code: src/pg_jitter_meta.c:1646-1654]`. The deform dispatch keeps a
static `dispatch_fast[]` cache keyed by `TupleDesc` pointer
`[verified-by-code: src/pg_jitter_meta.c:1211-1213 (comment)]`. This is only safe
because the cache is invalidated aggressively: `release_context` clears the
fast-path cache since "TupleDesc pointers from this query may be reused by palloc
for different layouts in future queries" `[verified-by-code:
src/pg_jitter_common.c:775-779]`. The microsecond compile times make a
cross-query code cache worthwhile in a way it never was for LLVM (where the
compile cost dwarfs the cache-hit savings only on repeated heavy queries) — but
the `TupleDesc`-pointer-reuse hazard it introduces is a genuinely novel
correctness obligation that core's per-query model sidesteps entirely.

### 7. Parallel workers can SHARE compiled code via a DSM segment addressed through a GUC string — core recompiles per worker

Core's JIT compiles independently in every parallel worker. pg_jitter offers
three `pg_jitter.parallel_mode` settings: `off` (workers fall back to the
interpreter), `per_worker` (each worker JIT-compiles independently, the default
and core-like behavior), and the experimental `shared` mode (the leader compiles
once and workers reuse the code via DSM) `[from-README: README.md:146;
verified-by-code: src/pg_jitter_meta.c:1612-1616]`. The `shared` transport is the
striking part: the leader `dsm_create`s a segment (size = `shared_code_max`),
writes compiled code into it keyed by a deterministic `(plan_node_id,
global_ordinal)` expression identity, and stores the `dsm_handle` so workers can
attach `[verified-by-code: src/pg_jitter_common.c:3079-3097, 3115-3155]`. The
identity must be deterministic because "Both leader and worker traverse the plan
tree in the same deterministic order (ExecInitNode), so the global counter
matches between them" — and the ordinal is explicitly *not* reset per node, to
avoid duplicate keys that would make a worker load the wrong code → SIGSEGV
`[verified-by-code: src/pg_jitter_common.c:3084-3097, 3089-3094 (comment)].`
Workers discover the handle through a shmem slot and `dsm_attach`; the README
notes PG serializes extension GUCs to workers via `SerializeGUCState`, which is
how the handle/config crosses the boundary `[from-README: README.md (Memory
Management / parallel); verified-by-code: src/pg_jitter_common.c:3103-3108,
3160-3200]`. Sharing *executable* code across workers — copying machine code that
must remain position-independent or be re-based — is a problem llvmjit never
solves; pg_jitter's sljit path even forces `SLJIT_REWRITABLE_JUMP` so calls stay
relocatable when code is `memcpy`'d to a different worker address
`[verified-by-code: src/pg_jitter_sljit.c:2884-2890 (comment)]`. See
[[knowledge/idioms/guc-variables]] (the GUC-as-DSM-handle-channel) and core's
parallel-query machinery (`src/backend/access/transam/parallel.c`,
`SerializeGUCState`).

### 8. Lazy, file-probing backend loading with graceful degradation, instead of a hard dependency

The meta provider loads backend `.so`s **lazily on first use** and caches them
for process lifetime `[from-README: README.md:212-215]`. `meta_load_backend`
first `pg_file_exists`-probes `pkglib_path/<libname><DLSUFFIX>` to avoid an ERROR
from `load_external_function` on a missing file, then loads inside
`PG_TRY`/`PG_CATCH` so a missing-symbol failure degrades to a `WARNING` and a
marked-unavailable backend rather than aborting `[verified-by-code:
src/pg_jitter_meta.c:386-426]`. If the selected backend is absent,
`meta_compile_expr` falls through every other backend in priority order, and if
none load, returns `false` so PG's interpreter runs `[verified-by-code:
src/pg_jitter_meta.c:1182-1199]`. This "install whatever subset of backends you
want; the provider negotiates" posture is a more defensive load model than a
typical extension's hard `shared_preload_libraries` dependency — it exists
because the three backends have different platform support (AsmJIT is
ARM64/x86_64 only; sljit/MIR cover s390x/ppc/etc.) `[from-README:
README.md:64, 203]`.

## Notable design decisions (with cites)

- **One codebase, PG 14–18, via `#if PG_VERSION_NUM` in
  `src/pg_jitter_compat.h`.** Handles the PG14–16 vs PG17+ ResourceOwner API
  split, PG18's `CompactAttribute` / split `EEOP_DONE` / `CompareType` rename /
  new opcodes `[from-README: README.md:232-236; verified-by-code:
  src/pg_jitter_common.c:624-667 shows the resowner fork].`
- **Skip-JIT heuristics to avoid net-negative compilation.** `compile_expr`
  bails for tiny expressions (`expr_has_fast_path`, a `min_expr_steps` threshold
  default 4, "smart skip" when nothing is inlineable), returning `false` so the
  interpreter runs `[verified-by-code: src/pg_jitter_sljit.c:2895-2920;
  from-README: README.md:153].` This matters more than for LLVM because
  pg_jitter is invoked at far lower `jit_above_cost`.
- **Experimental adaptive backend auto-selection.** With `pg_jitter.backend =
  auto`, the meta provider times compiles/executions per (expression-profile,
  backend) and uses epsilon-greedy exploration to converge on the fastest
  backend per profile `[verified-by-code: src/pg_jitter_meta.c:1052-1102,
  1138-1169; from-README: README.md:140, 159-167].`
- **A C++ backend living in the same provider family.** `pg_jitter_asmjit.cpp`
  is the only C++ TU, kept thin (756 lines) and conforming to the same
  `_PG_jit_provider_init` ABI as the C backends `[verified-by-code:
  src/pg_jitter_asmjit.cpp:134-138].`
- **Specialized non-expression optimizations beyond what core JIT does.** PCRE2
  (itself sljit-backed) + StringZilla SIMD for pattern matching, and
  precompiled binary-search / hash structures for CASE / IN
  `[from-README: README.md:33-34].`
- **CMake build, not PGXS/meson, with backend libraries as sibling checkouts.**
  Built via `./build.sh` against `pg_config`, expecting patched sljit/MIR
  siblings `[from-README: README.md:79-106; verified-by-code: CMakeLists.txt
  present, 787 lines].`

## Links into corpus

- [[knowledge/ideologies/pg-strom]] — the nearest thematic neighbor: also
  generates native code at query time, but as a GPU executor wired through
  custom-scan / FDW hooks, **not** through the `jit_provider` ABI. **Contrast:**
  pg-strom *adds* an executor path; pg_jitter *replaces* the expression compiler
  in a single-occupant core slot.
- [[knowledge/ideologies/pgrx]] / [[knowledge/ideologies/pglite-fusion]] —
  foreign codegen/runtime toolchains hosted in PG, but for authoring functions,
  not for substituting the JIT. Structural contrast on which core surface is
  occupied.
- [[knowledge/idioms/guc-variables]] — `_PG_jit_provider_init`-time
  `DefineCustom*Variable` (no `_PG_init`), the `GetConfigOption` double-define
  guard across backends (#sec How it hooks), and the GUC-as-DSM-handle channel
  for parallel code sharing (#7).
- [[knowledge/idioms/memory-contexts]] — the hand-rolled compiled-code lifecycle
  on `TopMemoryContext` + a per-function `free_fn` list (#3), and the aux
  `AllocSetContext` for query-lifetime helper allocations.
- [[knowledge/idioms/error-handling]] — `PG_TRY`/`PG_CATCH` around
  exception-safe code registration (#3) and around lazy backend loading (#8);
  the `reset_after_error` fan-out (#5).
- [[knowledge/idioms/fmgr]] — pg_jitter's tiers exist to *bypass* fmgr/fcinfo on
  the hot path (#2); the fallback path re-enters PG's `ExecEval*` interpreter
  functions.
- [[knowledge/idioms/catalog-conventions]] — relevant by **absence**: a JIT
  provider needs no catalog rows, no `.control`, no `CREATE EXTENSION`.
- Core JIT machinery referenced in prose: the provider dispatcher
  `src/backend/jit/jit.c` (reads `jit_provider`, calls
  `_PG_jit_provider_init`, owns `jit_release_context`), the reference LLVM
  provider under `src/backend/jit/llvm/` (`llvmjit.c`'s get-or-create context
  pattern that `pg_jitter_get_context` mirrors), the expression interpreter
  `src/backend/executor/execExprInterp.c` (the `ExprState->steps[]` opcode array
  both consume), and parallel-query GUC serialization in
  `src/backend/access/transam/parallel.c` (`SerializeGUCState`).

## Sources

| URL | HTTP |
|---|---|
| https://api.github.com/repos/vladich/pg_jitter/git/trees/master?recursive=1 | 200 |
| https://raw.githubusercontent.com/vladich/pg_jitter/master/README.md | 200 |
| https://raw.githubusercontent.com/vladich/pg_jitter/master/CMakeLists.txt | 200 |
| https://raw.githubusercontent.com/vladich/pg_jitter/master/src/pg_jitter_meta.c | 200 |
| https://raw.githubusercontent.com/vladich/pg_jitter/master/src/pg_jitter_common.c | 200 |
| https://raw.githubusercontent.com/vladich/pg_jitter/master/src/pg_jitter_common.h | 200 |
| https://raw.githubusercontent.com/vladich/pg_jitter/master/src/pg_jit_funcs.c | 200 |
| https://raw.githubusercontent.com/vladich/pg_jitter/master/src/pg_jit_funcs.h | 200 |
| https://raw.githubusercontent.com/vladich/pg_jitter/master/src/pg_jitter_sljit.c | 200 |
| https://raw.githubusercontent.com/vladich/pg_jitter/master/src/pg_jitter_mir.c | 200 |
| https://raw.githubusercontent.com/vladich/pg_jitter/master/src/pg_jitter_asmjit.cpp | 200 |
| https://raw.githubusercontent.com/vladich/pg_jitter/master/src/pg_jitter_compat.h | 200 |

**Fetch notes / substitutions:**

- **Branch `master` was correct** (no 404). The repo is large and active
  (203★), not sparse — there was ample code to characterize the provider
  divergences with `[verified-by-code]` cites.
- **The prompt's manifest hint (`*.control`, install SQL) does not apply.**
  pg_jitter is a JIT *provider*, not a `CREATE EXTENSION` module: there is no
  `.control` file in the tree at all, and the `_PG_jit_provider_init` /
  `JitProviderCallbacks` machinery replaces it. This is itself the headline
  divergence (#1) and is recorded as such rather than as a missing file. The
  only SQL is `sql/pg_jitter_functions.sql` (helper functions like
  `pg_jitter_current_backend`), not a provider-install script.
- **Four provider libraries, not one.** The build emits `pg_jitter` (meta) plus
  `pg_jitter_sljit` / `pg_jitter_asmjit` / `pg_jitter_mir`. The
  `_PG_jit_provider_init` / callback cites span all four C/C++ entry files
  `[verified-by-code].`
- **Files read in depth:** `README.md` (full), `pg_jitter_meta.c` (entry point,
  load/dispatch/release/reset, GUC registration — lines 1–60, 367–426,
  1122–1340, 1580–1742), `pg_jitter_common.c` (context lifecycle, ResourceOwner
  fork, release/reset, shared-DSM parallel code — lines 620–850, 3076–3205),
  `pg_jitter_common.h` (`PgJitterContext` / `CompiledCode` structs),
  `pg_jitter_sljit.c` (`_PG_jit_provider_init`, GUC guards, `sljit_compile_expr`
  entry + skip heuristics — lines 240–310, 2847–2920, grep of compile path),
  plus `_PG_jit_provider_init` confirmation in `pg_jitter_mir.c` and
  `pg_jitter_asmjit.cpp`.
- **Not read line-by-line:** the bulk of the code-generation bodies in
  `pg_jitter_sljit.c` (9642 lines) / `pg_jitter_mir.c` (9467 lines), the deform
  JIT (`pg_jitter_deform_jit.c`), PCRE2/SIMD/yyjson helper TUs, and the tier-2
  wrappers. Claims about per-opcode emission, the three tiers, PCRE2/StringZilla,
  and the AsmJIT/MIR free-callback specifics rest on the README
  (`[from-README]`) plus the call-site/struct/entry-point cites
  (`[verified-by-code]`); they were not verified against the full codegen bodies.
  The adaptive auto-selection and shared-DSM mechanisms were verified at the
  control-flow level (`meta_compile_expr`, `pg_jitter_init_shared_dsm`,
  `pg_jitter_get_expr_identity`) but not exhaustively traced through every
  backend's emit.
