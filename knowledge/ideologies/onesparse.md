# OneSparse — embeds SuiteSparse:GraphBLAS as first-class PG types whose objects live in GraphBLAS's own allocator, bridged into Postgres via the expanded-object API

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `OneSparse/OneSparse` @ branch `main`. All `file:line` cites point into
> that repo (not `source/`). Cites verified against the files fetched on
> 2026-06-16 (see Sources footer). Read alongside
> `[[knowledge/ideologies/pgrouting]]` — the cousin two-language graph engine
> that copies data OUT to a C++/Boost heap per call; OneSparse instead keeps the
> foreign GraphBLAS object *live* as a first-class expanded datum. Cross-ref the
> core expanded-object machinery (`src/include/utils/expandeddatum.h`).

## Domain & purpose

OneSparse embeds **SuiteSparse:GraphBLAS** — the reference implementation of the
GraphBLAS spec, which expresses graph algorithms as *linear algebra over
semirings* (sparse matrix/vector multiplication where `+`/`*` are replaced by an
arbitrary monoid/binary-op pair) — and exposes its objects as first-class
Postgres types. The headers pulled in are `<GraphBLAS.h>`, `<LAGraph.h>`,
`<LAGraphX.h>` (`src/onesparse.h:52-54`) `[verified-by-code]` — LAGraph being
the algorithm library (BFS, PageRank, SSSP, triangle count) layered on
GraphBLAS. The control file describes the extension as an "Example Postgres
extension for 'expanded' data types" (`onesparse.control:2`) `[from-comment]`,
which is the design thesis stated plainly: it is a worked example of wrapping an
external library's opaque object model as PG base types via the expanded-object
(EOH) API. The SQL surface (inferred from the C type machinery) is a family of
base types — `matrix`, `vector`, `scalar`, plus the *algebra* objects `semiring`,
`monoid`, `binaryop`, `unaryop`, `descriptor` (`src/onesparse.h:224-235`)
`[verified-by-code]` — with overloaded operators and graph algorithms exposed as
SQL-callable functions under a `graph/` module (`src/onesparse.h:234`)
`[inferred]`. The reason to document it: OneSparse is the corpus's sharpest case
of a whole foreign C library's object model — *with its allocator and its
threading model* — promoted to a native PG type.

## How it hooks into PG

`_PG_init` does **not** install hooks or a background worker; it bootstraps the
GraphBLAS/LAGraph runtime and registers the extension's algebra catalog
in-process:

```
LAGraph_Init(msg);
initialize_types(); initialize_descriptors(); initialize_unaryops();
initialize_indexunaryops(); initialize_binaryops(); initialize_monoids();
initialize_semirings(); initialize_gucs();
```

(`src/onesparse.c:370-384`) `[verified-by-code]`. `LAGraph_Init` is the
LAGraph wrapper that calls `GrB_init` underneath; OneSparse passes it no
allocator arguments, so GraphBLAS initializes with its **default allocator
(system `malloc`/`calloc`/`realloc`/`free`)** — there is no
`GxB_init(..., palloc, ...)` anywhere in the fetched code. `[verified-by-code,
src/onesparse.c:375]` (negative: no `GxB_init` call present). See divergence #2 —
this is the load-bearing fact about memory residency.

`PG_MODULE_MAGIC` is declared at top of `src/onesparse.c:2` `[verified-by-code]`.
The `initialize_*` functions populate in-process name→handle lookup tables
(`lookup_type`, `lookup_semiring`, `lookup_binaryop`, …,
`src/onesparse.h:207-214`) `[verified-by-code]` — GraphBLAS's predefined
operators (e.g. `GrB_PLUS_TIMES_SEMIRING_INT64`, `src/onesparse.c:323-349`) are
the algebra catalog, resolved by string name at type-input time.

The base types are custom expanded objects, each with the same five-part
skeleton (matrix shown, scalar/semiring identical in shape):

- A **flat** varlena struct (`os_FlatMatrix`: `vl_len_` + serialized bytes,
  `src/matrix/matrix.h:5-9`) and an **expanded** struct embedding
  `ExpandedObjectHeader hdr` plus the live `GrB_Matrix` handle
  (`os_Matrix`, `src/matrix/matrix.h:11-20`) `[verified-by-code]`.
- An `ExpandedObjectMethods` table wiring `get_flat_size` + `flatten`
  (`matrix_methods`, `src/matrix/matrix.c:11-14`) `[verified-by-code]`.
- A `new_*` constructor that creates a dedicated `AllocSetContext`, calls
  `EOH_init_header`, allocates the GraphBLAS object, and registers a
  reset-callback (`new_matrix`, `src/matrix/matrix.c:90-140`)
  `[verified-by-code]`.
- An `expand_*` that deserializes the flat datum back into a live object
  (`expand_matrix`, `src/matrix/matrix.c:143-167`) `[verified-by-code]`.
- A `DatumGet*` that returns the EOHP if already expanded, else detoasts +
  expands (`DatumGetMatrix`, `src/matrix/matrix.c:182-202`) `[verified-by-code]`.

GUCs are minimal: `onesparse.burble` (`PGC_USERSET` bool toggling SuiteSparse's
diagnostic "burble" trace) and `onesparse.jit_control` (`PGC_POSTMASTER` string,
values `off/pause/run/load/on`) (`src/guc.c:111-141`) `[verified-by-code]`.

Cross-ref `[[knowledge/idioms/fmgr]]`,
`[[knowledge/idioms/catalog-conventions]]`,
`[[knowledge/idioms/guc-variables]]`,
`.claude/skills/fmgr-and-spi/SKILL.md`,
`.claude/skills/catalog-conventions/SKILL.md`,
`.claude/skills/memory-contexts/SKILL.md`.

## Where it diverges from core idioms

### 1. An opaque external-library handle as a first-class expanded datum

`GrB_Matrix` is an opaque pointer into SuiteSparse — its internal representation
(hypersparse/sparse/bitmap/full, CSR/CSC) is invisible to PG. OneSparse makes it
a PG datum by storing the handle inside an expanded object: `os_Matrix` embeds
`ExpandedObjectHeader hdr` followed by the live `GrB_Matrix matrix`
(`src/matrix/matrix.h:11-20`) `[verified-by-code]`. The flatten/expand bridge is
GraphBLAS's own serializer:

- `matrix_get_flat_size` calls `GxB_Matrix_serialize` to get a byte blob +
  size, caching them on the expanded struct (`src/matrix/matrix.c:33-43`)
  `[verified-by-code]`.
- `flatten_matrix` `memcpy`s those serialized bytes into the pre-allocated
  varlena result and `SET_VARSIZE`s it (`src/matrix/matrix.c:48-87`)
  `[verified-by-code]`.
- `expand_matrix` calls `GxB_Matrix_deserialize` to rebuild a live `GrB_Matrix`
  from the flat bytes (`src/matrix/matrix.c:143-167`) `[verified-by-code]`.

So the on-disk/TOAST form of a `matrix` column is a SuiteSparse serialization
blob; the in-memory form is a live opaque handle. Core's expanded-object API
(`expandeddatum.h`, `EOHPGetRWDatum`/`DatumGetEOHP`) was built for things like
the expanded `array` type that PG itself owns end-to-end; OneSparse uses the
*same* API to host an object whose bytes it cannot interpret at all — it can only
ask GraphBLAS to (de)serialize. Contrast `[[knowledge/ideologies/pgrouting]]`,
which never holds a live foreign object across a call: it copies edge rows into a
Boost graph, runs, copies results out, and frees. OneSparse keeps the foreign
object resident and re-presentable as a datum.

### 2. Memory dual-residency: GraphBLAS `malloc` vs MemoryContext, bridged by a reset-callback that calls `GrB_*_free`

This is the central divergence. The GraphBLAS object's own storage is allocated
by **GraphBLAS's allocator (system `malloc`)** — because `_PG_init` calls
`LAGraph_Init`/`GrB_init` without handing it `palloc`
(`src/onesparse.c:375`) `[verified-by-code]`. PG's MemoryContext machinery
therefore cannot see, account for, or reclaim that memory. The only PG-visible
allocation is the small `os_Matrix` wrapper struct, which lives in a dedicated
child `AllocSetContext` created per object (`new_matrix`,
`src/matrix/matrix.c:105-109`) `[verified-by-code]`.

The bridge that prevents a leak: `new_matrix` registers a
`MemoryContextCallback` via `MemoryContextRegisterResetCallback` on that child
context (`src/matrix/matrix.c:131-136`) `[verified-by-code]`; the callback
`context_callback_matrix_free` calls `GrB_Matrix_free(&matrix->matrix)`
(`src/matrix/matrix.c:169-177`) `[verified-by-code]`. So when PG resets/deletes
the owning context (end of query, etc.), the callback fires and hands the
external `malloc`'d memory back to GraphBLAS. The same pattern is duplicated
verbatim for scalars (`context_callback_scalar_free` →
`GrB_Scalar_free`, `src/scalar/scalar.c:226-231, 325-333`) and semirings
(`context_callback_semiring_free` → `GrB_Semiring_free`,
`src/semiring/semiring.c:95-100, 118-126`) `[verified-by-code]`. This is the
idiomatic core mechanism (reset-callbacks exist precisely to free foreign
resources tied to a context — cf. `[[knowledge/idioms/memory-contexts]]`), used
here at scale to keep two allocators in lockstep. The risk it accepts: peak RSS
of a GraphBLAS workload is invisible to `work_mem`/`MemoryContextStats` and
sits entirely in `malloc` arenas.

### 3. GraphBLAS internal multithreading (OpenMP) inside a single-threaded backend

SuiteSparse:GraphBLAS parallelizes its kernels with OpenMP across multiple
threads by default. A PG backend is a single OS process that the executor and
the entire fmgr/elog/longjmp machinery assume is single-threaded. OneSparse runs
GraphBLAS *inside* that backend, so a single `matrix @ matrix` call can spin up
an OpenMP thread team within one connection's process. The fetched `guc.c`
exposes `burble` and `jit_control` but **no GUC capping `GxB_NTHREADS`/OpenMP
thread count** (`src/guc.c:111-141`) `[verified-by-code]` (negative result over
the fetched file) — meaning thread count is left to GraphBLAS's global default
(or `OMP_NUM_THREADS`), not bounded per-backend by OneSparse. The correctness
caveat: GraphBLAS worker threads must never call back into PG's
non-thread-safe machinery (palloc, ereport, CHECK_FOR_INTERRUPTS); the design
relies on GraphBLAS confining PG interaction to the calling thread. `[inferred]`
from the absence of a thread GUC and the single allocator/printf hook wiring.

### 4. JIT/codegen type machinery: PG composite types → C struct source text

`src/jit/types.c` is a code generator, not a type. `jit_type(PG_FUNCTION_ARGS)`
takes a composite-type OID, walks its `TupleDesc`, and emits **C source text** —
a `typedef struct { ... }` whose fields are the SQL columns mapped to C types
(`bool`, `int64_t`, `double`, `pg_uuid_t`, fixed `char[N]` for `bpchar`,
`unsigned char[N]` for `bit`/`varbit`) — returning it as `text`
(`jit_type`, `src/jit/types.c:143-221`) `[verified-by-code]`. The companion
`get_field_layout` computes each attribute's `kind`/`size`/`align` for a binary
struct layout (`src/jit/types.c:223-360`) `[verified-by-code]`. This exists to
feed SuiteSparse's **JIT-compiled user-defined types/operators**: GraphBLAS's
JIT (the `onesparse.jit_control` GUC drives `GxB_JIT_C_CONTROL`,
`src/guc.c:65-109`) compiles C kernels at runtime, and a PG composite type can be
projected into a matching C struct so GraphBLAS can operate on it as a UDT.
`[inferred]` — the file generates struct source text and layout metadata; the
consumer (handing it to the GraphBLAS JIT) is not in the fetched files. Arrays
and variable-length types are explicitly rejected as not fixed-size
(`src/jit/types.c:132-139, 255-260`) `[verified-by-code]`.

### 5. Algebra-as-types: semirings/monoids/binary-ops are catalog objects, not functions

GraphBLAS's algebraic structures are reified as PG datums. `semiring` is a base
type whose I/O functions resolve a string name to a predefined `GrB_Semiring`
handle: `semiring_in` calls `new_semiring(input, …)` which does
`lookup_semiring(name)` and errors on an unknown name
(`semiring_in`/`new_semiring`, `src/semiring/semiring.c:148-157, 61-104`)
`[verified-by-code]`; `semiring_out` simply prints the stored name
(`src/semiring/semiring.c:159-170`) `[verified-by-code]`. The flat form is just
the name string (`flatten_semiring` strncpys `semiring->name`,
`src/semiring/semiring.c:39-58`) `[verified-by-code]` — a semiring datum is a
*named reference* into the in-process operator table, re-resolved on expand. So
SQL can pass `'plus_times_int64'::semiring` as a value to a matrix-multiply
function: the algebra is first-class data, which is how OneSparse exposes the
full GraphBLAS generality (any monoid×binaryop) without a combinatorial
explosion of SQL functions. The default algebra per element type is wired in C
(`default_semiring`/`default_monoid`/`default_binaryop`,
`src/onesparse.c:267-349`) `[verified-by-code]`.

## Notable design decisions (cited)

- **GraphBLAS errors are funneled through `elog(ERROR)`** by the `OS_CHECK`
  macro, which on any non-`SUCCESS`/`NO_VALUE` info code fetches `GrB_error`'s
  message and raises (`src/onesparse.h:71-81`) `[verified-by-code]`. This is the
  language-boundary firewall analogue to pgRouting's C++ try/catch, but simpler:
  GraphBLAS returns error codes, not exceptions, so a macro suffices.
- **`burble` diagnostics route into PG's `NOTICE` stream**: `initialize_gucs`
  installs `burble_notice_func` as GraphBLAS's `GxB_PRINTF` callback
  (`src/guc.c:114-115`), and the function `ereport(NOTICE, …)`s the formatted
  GraphBLAS trace (`src/guc.c:16-37`) `[verified-by-code]`.
- **`onesparse.jit_control` is `PGC_POSTMASTER`** (`src/guc.c:135`)
  `[verified-by-code]` — GraphBLAS JIT mode is fixed at server start, not
  per-session, while `burble` is `PGC_USERSET` (`src/guc.c:123`).
- **Identity-preserving detoast fast-paths**: `DatumGetMatrixMaybeA/AB/ABC`
  compare a cached `flat_datum_pointer` so that when the same matrix is passed as
  multiple arguments it is expanded once, not N times
  (`src/matrix/matrix.c:204-296`) `[verified-by-code]` — a deliberate avoidance
  of redundant `GxB_Matrix_deserialize` work.
- **Per-object child MemoryContext** (`AllocSetContextCreate` named "expanded
  matrix"/"expanded scalar"/"expanded semiring", `src/matrix/matrix.c:105`,
  `src/scalar/scalar.c:202`, `src/semiring/semiring.c:79`) `[verified-by-code]`
  gives each datum its own reset scope, so the `GrB_*_free` callback fires at
  exactly the right granularity.
- **Serialized-blob caching on the expanded struct** (`serialized_data`/
  `serialized_size`/`flat_size` cached after first `GxB_Matrix_serialize`,
  `src/matrix/matrix.c:26-43`) `[verified-by-code]` — flatten is cheap if
  `get_flat_size` already serialized.

## Links into corpus

- `[[knowledge/ideologies/pgrouting]]` — the contrast cousin: a thin C/fmgr
  shell over a C++/Boost graph engine that copies data to a private STL heap
  *per call* and frees it before returning. OneSparse instead keeps the foreign
  GraphBLAS object live as an expanded datum, with the foreign allocator and
  foreign (OpenMP) threading model resident in the backend.
- `[[knowledge/idioms/memory-contexts]]` — `AllocSetContextCreate`,
  `MemoryContextRegisterResetCallback`, and the reset-callback-frees-foreign-
  resource pattern OneSparse leans on to bridge two allocators.
- `[[knowledge/idioms/fmgr]]` — `PG_FUNCTION_INFO_V1`, `PG_GETARG_*`,
  `SearchSysCache1(TYPEOID, …)`/`GETSTRUCT` introspection in the JIT codegen.
- `[[knowledge/idioms/catalog-conventions]]` — custom base types
  (`matrix`/`vector`/`scalar`/`semiring`/…) with name-keyed I/O and an
  algebra-as-data catalog.
- `[[knowledge/idioms/guc-variables]]` — `DefineCustomBoolVariable`/
  `DefineCustomStringVariable` with check/assign hooks that push state into a
  foreign library's globals (`GxB_BURBLE`, `GxB_JIT_C_CONTROL`).
- `.claude/skills/memory-contexts/SKILL.md`,
  `.claude/skills/fmgr-and-spi/SKILL.md`,
  `.claude/skills/catalog-conventions/SKILL.md`.

## Anthropology takeaway

OneSparse is the corpus's sharpest "wrap a whole foreign C library's object model
as a first-class PG type via the expanded-object API, with the foreign allocator
and foreign threading model coming along for the ride" case. The expanded-object
machinery in core was designed so PG-owned types (notably the expanded `array`)
could avoid repeated flatten/unflatten in tight loops; OneSparse repurposes it as
a *foreign-object bridge* — the expanded form holds an opaque `GrB_Matrix` it
cannot introspect, and (de)serialization is delegated wholesale to
`GxB_Matrix_serialize`/`_deserialize`. Two core assumptions get stretched. First,
memory residency: the actual matrix data lives in GraphBLAS's `malloc` heap,
invisible to MemoryContext accounting and `work_mem`, reclaimed only because a
`MemoryContextRegisterResetCallback` faithfully calls `GrB_*_free` when the owning
context resets — an elegant but load-bearing use of an existing hook. Second,
concurrency: a single-threaded PG backend now hosts an OpenMP thread team
whenever a kernel runs, with no per-backend thread cap in the fetched GUCs — a
real operational concern for a process that the rest of PG assumes is
single-threaded. The algebra-as-types decision (semirings/monoids as named
catalog data) and the JIT codegen that projects PG composite types into C struct
source round out the picture: OneSparse doesn't *port* GraphBLAS to PG idioms, it
*hosts* GraphBLAS inside PG and teaches the two memory/error/threading models to
coexist at the datum boundary.

## Sources

Fetched 2026-06-16 (branch `main`), all via
`raw.githubusercontent.com/OneSparse/OneSparse/main/<path>`:

- `README.md` @ 2026-06-16 → HTTP 200 (482 bytes; badge/links stub only —
  points to the hosted docs site, no prose to cite; all behavioral claims rest on
  code, not README).
- `onesparse.control` @ 2026-06-16 → HTTP 200 (208 bytes; `comment`,
  `schema = onesparse`, `relocatable = false`).
- `src/onesparse.c` @ 2026-06-16 → HTTP 200 (8134 bytes; `_PG_init`,
  `LAGraph_Init`, default-algebra tables, type-promotion, SPI helper —
  deep-read).
- `src/onesparse.h` @ 2026-06-16 → HTTP 200 (7571 bytes; includes, `OS_CHECK`
  macro, lookup/init prototypes, module include list — deep-read).
- `src/matrix/matrix.c` @ 2026-06-16 → HTTP 200 (6655 bytes; flatten/expand,
  `new_matrix`, reset-callback `GrB_Matrix_free`, detoast fast-paths —
  deep-read).
- `src/matrix/matrix.h` @ 2026-06-16 → HTTP 200 (2619 bytes; `os_FlatMatrix`/
  `os_Matrix` structs, EOH macros).
- `src/scalar/scalar.c` @ 2026-06-16 → HTTP 200 (8754 bytes; per-type
  flatten/expand, scalar reset-callback — deep-read).
- `src/semiring/semiring.c` @ 2026-06-16 → HTTP 200 (4035 bytes; name-keyed
  I/O, semiring reset-callback — deep-read).
- `src/guc.c` @ 2026-06-16 → HTTP 200 (3018 bytes; `onesparse.burble`,
  `onesparse.jit_control`, burble→NOTICE bridge — deep-read).
- `src/jit/types.c` @ 2026-06-16 → HTTP 200 (7855 bytes; `jit_type` C-struct
  codegen, `get_field_layout` — deep-read).

All cites are `[verified-by-code]` against the fetched files except: the
GraphBLAS-spec / semiring-algebra framing (`[from-comment]` on the control file +
spec knowledge), the `LAGraph_Init`→`GrB_init`→system-`malloc` chain (verified
*negatively* — no `GxB_init(palloc,...)` appears in the fetched `onesparse.c`;
the deeper `GrB_init` internals were not in scope), the OpenMP-threading concern
and the JIT-codegen consumer (`[inferred]` — `types.c` produces struct source +
layout, but the call site handing it to the GraphBLAS JIT is in unfetched files),
and the `graph/` algorithm SRF surface (`[inferred]` from the `#include
"graph/graph.h"` at `src/onesparse.h:234`, contents not fetched).
