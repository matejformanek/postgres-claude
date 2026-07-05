# datasketches — a two-layer C/C++ shim that wraps the Apache DataSketches C++ template library as mergeable, parallel-safe PG aggregates with a live-C++-object `internal` state

> Ideology note produced by the pg-extension-anthropologist cloud routine.
> Repo: `apache/datasketches-postgresql` @ branch `master`
> (`default_version = '1.8.0-SNAPSHOT'`), fetched 2026-07-05.
> Caveat: characterization based on the files actually fetched via
> `raw.githubusercontent.com` — `README.md`, `Makefile`,
> `datasketches.control`, `sql/datasketches_cpc_sketch.sql`,
> `sql/datasketches_theta_sketch.sql` (aggregate-shape only), and the CPC
> wrapper set read in full: `src/cpc_sketch_pg_functions.c`,
> `src/cpc_sketch_c_adapter.cpp`, `src/cpc_sketch_c_adapter.h`,
> `src/common.c`, `src/base64.c`, `src/global_hooks.c`, `src/allocator.h`,
> `src/postgres_h_substitute.h`, `src/agg_state.h`, `src/ptr_with_size.h`,
> plus the `theta_sketch_c_adapter.h` signatures for the set-op variant. The
> **DataSketches C++ core** (`cpc_sketch_alloc`, `cpc_union_alloc`, the KLL /
> theta / HLL / fi template classes) is an **external dependency, NOT vendored
> here** — the `Makefile` assumes a directory/symlink `datasketches-cpp` next
> to the repo (README §"Downloading DataSketches C++ Core"); there is no
> `.gitmodules` at repo root (probe → 404), so it is a build-time download /
> symlink rather than a git submodule. All statements about core-library
> internals are tagged `[inferred]` — only the wrapper was read.

## Domain & purpose

datasketches is an **approximate-aggregate library binding**: it exposes the
Apache DataSketches streaming-algorithm C++ core to SQL as first-class
PostgreSQL aggregate functions and custom types [from-README]. The sketch
families wrapped are CPC and HLL (distinct counting), Theta and Array-of-Doubles
(distinct counting *with set operations* — union / intersection / a-not-b), KLL
float/double and REQ and classic Quantiles (rank / quantile / PMF / CDF
estimation), and Frequent-Strings (heavy hitters) [from-README, Makefile:38-56
`OBJS`]. Its thesis is the mergeability contract that separates a sketch from a
running `count(distinct)`: a sketch is a fixed-footprint summary that can be
built in parallel, serialized, stored in a column, shipped between machines, and
**unioned** back together with no loss of the error guarantee — so
`cpc_sketch_union(cpc_sketch)` is as much a first-class aggregate as
`cpc_sketch_distinct(anyelement)` [verified-by-code,
sql/datasketches_cpc_sketch.sql:73-131]. The extension's whole job is to make a
foreign C++ template library obey PG's aggregate ABI, memory model, error model,
and type system without leaking C++ across the boundary.

## How it hooks into PG

Pure **`CREATE EXTENSION` / lazy-load**, no `shared_preload_libraries`, no
executor / planner / utility hooks. Build is PGXS `MODULE_big = datasketches`
over a fixed `OBJS` list that pairs, per sketch, a `_pg_functions.c` (PG-facing)
with a `_c_adapter.cpp` (C++-facing), plus shared `common.o`, `base64.o`,
`global_hooks.o` [verified-by-code, Makefile:19,38-56]. The `.control` is a
plain relocatable extension with `module_pathname = '$libdir/datasketches'`
[verified-by-code, datasketches.control:1-5].

`PG_MODULE_MAGIC` lives in `common.c` (a C translation unit), version-guarding
the PG-16 move of varlena macros into `varatt.h`
[verified-by-code, common.c:27-31,31]. `_PG_init` lives *separately* in
`global_hooks.c` and does exactly one thing — `cpc_init()`, which triggers the
CPC core's one-time global compression-table initialization; `_PG_fini` calls a
no-op `cpc_cleanup()` [verified-by-code, global_hooks.c:28-34]. This is the only
per-backend global state; the module is otherwise stateless between calls.

Each sketch ships as a **custom type that is a thin relabel of `bytea`**. The
type is declared shell-first, then completed with `INPUT`/`OUTPUT` set to the
*generic, sketch-agnostic* `pg_sketch_in` / `pg_sketch_out` (base64 text codec,
shared by every sketch type) and `STORAGE = EXTERNAL`; two `WITHOUT FUNCTION`
`ASSIGNMENT` casts bridge `bytea <-> cpc_sketch` in both directions
[verified-by-code, sql/datasketches_cpc_sketch.sql:18-35; common.c:44-66]. The
on-disk bytes ARE the DataSketches core's own portable serialization, which is
byte-compatible with the Java/Python sketch libraries [inferred, from-README].

The aggregate wiring is textbook PG parallel-aggregate machinery, fully
populated [verified-by-code, sql/datasketches_cpc_sketch.sql:73-131]:

- `STYPE = internal` — transition state is an opaque pointer, not a SQL value.
- `SFUNC = cpc_sketch_build_agg` (transition), `FINALFUNC` = either
  `..._from_internal` (emit the sketch bytea) or `..._get_estimate_from_internal`
  (emit `double precision`) — two aggregates over one state shape.
- `COMBINEFUNC = cpc_sketch_combine`, `SERIALFUNC = cpc_sketch_serialize_state`,
  `DESERIALFUNC = cpc_sketch_deserialize_state`, `PARALLEL = SAFE` — the full
  partial-aggregate quartet, so the sketch can be split across parallel workers.

## Where it diverges from core idioms

- **Two-layer C/C++ split with a hand-rolled minimal ABI, deliberately keeping
  `postgres.h` out of C++.** The PG-facing `*_pg_functions.c` files are plain C
  (fmgr macros, `AggCheckCallContext`, `MemoryContextSwitchTo`, `PG_GETARG_*`);
  the `*_c_adapter.cpp` files are C++ that instantiate the core templates and
  **never include `postgres.h`**. Instead `postgres_h_substitute.h` redeclares a
  bare-minimum ABI — `typedef void* Datum;`, `pg_float8_get_datum`, `pg_error`,
  and a local `pg_unreachable()` — because "there is some problem compiling C++
  code using GCC 4.8.5 (standard on current RHEL) with postgres.h included"
  [verified-by-code, postgres_h_substitute.h:20-43]. The real
  `Float8GetDatum` / `ereport` bodies live back in the C file `common.c`
  (`pg_float8_get_datum`, `pg_error`) and are called across `extern "C"`
  [verified-by-code, common.c:70-86]. Core PG extensions written in C++ normally
  just include `postgres.h`; datasketches treats it as un-includable and rebuilds
  a redirect layer.

- **The custom type carries no bespoke varlena struct — it is `bytea` with a
  base64 façade.** There is no `cpc_sketch` C struct, no per-type
  send/recv/in/out logic: `pg_sketch_in` / `pg_sketch_out` are *generic across
  all sketch families* and do nothing but base64 decode/encode into a `bytea`
  [verified-by-code, common.c:44-66; base64.c:39-99]. The type distinction lives
  entirely in the catalog (distinct type OIDs, distinct aggregate signatures);
  the physical representation is identical `bytea` for every sketch. Contrast
  core custom types (and `[[postgresql-hll]]`), which define a real varlena
  layout with typed accessors.

- **Transition state is a live C++ object behind `internal`, not a serialized
  value.** `struct agg_state { enum agg_state_type type; unsigned lg_k; void*
  ptr; }` holds a raw pointer to a heap-constructed C++ `cpc_sketch` or
  `cpc_union` for the *entire* aggregation; it is only ever flattened to `bytea`
  at the serialfn (parallel handoff) or finalfn (result) boundary
  [verified-by-code, agg_state.h:25-29; cpc_sketch_pg_functions.c:82-108,
  246-273]. This is the sharpest divergence from the sibling extensions: it
  keeps a mutable native object and materializes lazily, where hll/topn keep a
  materialized value at all times (see Links).

- **PG memory context is threaded *into* the C++ allocator.** `palloc_allocator<T>`
  is a C++11 `Allocator` whose `allocate`/`deallocate` call PG's
  `palloc`/`pfree` (again via hand-declared `extern "C"` prototypes, not
  `postgres.h`), and every core template is instantiated as
  `cpc_sketch_alloc<palloc_allocator<char>>` [verified-by-code, allocator.h:24-71;
  cpc_sketch_c_adapter.cpp:27-28]. So the sketch's *internal* growth allocates
  from the current PG `MemoryContext`, and the wrappers scrupulously
  `MemoryContextSwitchTo(aggcontext)` around every construct/update so the object
  outlives the per-tuple context [verified-by-code, cpc_sketch_pg_functions.c:77-80].
  Objects are built with **placement-new over `palloc`** —
  `new (palloc(sizeof(cpc_sketch_pg))) cpc_sketch_pg(...)` — and torn down by an
  explicit `->~cpc_sketch_pg()` + `pfree` [verified-by-code,
  cpc_sketch_c_adapter.cpp:37-53]. C++ `operator new`/`delete` are bypassed
  entirely; the heap is PG's.

- **A C++-exception ↔ `ereport` firewall on every boundary crossing.** Every
  function in the `.cpp` adapter is wrapped `try { ... } catch (std::exception& e)
  { pg_error(e.what()); } pg_unreachable();` [verified-by-code,
  cpc_sketch_c_adapter.cpp:37-44 and every function through 158]. `pg_error`
  (in the C file) turns the C++ message into `ereport(ERROR,
  errcode(ERRCODE_INTERNAL_ERROR), errmsg("%s", message))`
  [verified-by-code, common.c:78-86]. No C++ exception is ever allowed to
  propagate through `extern "C"` into PG's `longjmp` world; the trailing
  `pg_unreachable()` exists because `pg_error` does not return.

- **`lg_k` is smuggled as a one-byte prefix on the *serialized state*.** The
  parallel serialfn writes the core serialization at offset `VARHDRSZ + 1` and
  stashes the `lg_k` config in the single byte at `VARHDRSZ`; deserialize reads
  `*VARDATA` back as `lg_k` and skips one byte [verified-by-code,
  cpc_sketch_pg_functions.c:264-265,292-293]. The *final* sketch bytea (from
  `..._from_internal`) has no such prefix (`VARHDRSZ` header only,
  cpc_sketch_pg_functions.c:166) — so the internal partial-aggregate wire format
  and the user-visible sketch format deliberately differ by one byte.

- **`internal`-typed functions defend themselves with `AggCheckCallContext`.**
  Because the state is a raw pointer, calling these functions outside an
  aggregate would be a type-unsafe pointer forge; every transition/serial/final
  function `elog(ERROR, "... called in non-aggregate context")` if
  `!AggCheckCallContext` [verified-by-code, cpc_sketch_pg_functions.c:77-79,
  157-159, 185-187]. This is the standard PG guard for `internal`-state
  aggregates, applied consistently.

## Notable design decisions

- **Union is an aggregate, not just a function.** `cpc_sketch_union(cpc_sketch)`
  and `theta_sketch_union(theta_sketch)` are `CREATE AGGREGATE`s whose SFUNC
  (`..._union_agg`) deserializes each incoming sketch bytea and folds it into a
  live `cpc_union` accumulator, sharing the same `combine`/`serialize`/`final`
  functions as the build aggregate [verified-by-code,
  sql/datasketches_cpc_sketch.sql:113-131;
  cpc_sketch_pg_functions.c:110-146]. Mergeability is thus symmetric: you can
  aggregate raw values into a sketch, or aggregate pre-built sketches into one.

- **`agg_state.type` discriminates mutable-sketch vs union accumulator, resolved
  lazily at finalize.** The state can hold either a `cpc_sketch` (`MUTABLE_SKETCH`)
  or a `cpc_union` (`UNION`); `from_internal` / `serialize_state` / `combine` all
  check `if (stateptr->type == UNION) stateptr->ptr = cpc_union_get_result(...)`
  to collapse a union to a sketch before serializing [verified-by-code,
  cpc_sketch_pg_functions.c:163-165, 261-262; agg_state.h:23]. `combine` always
  builds a fresh `cpc_union`, folds both incoming states in, and resolves — so
  `COMBINEFUNC` is where parallel partials meet [verified-by-code,
  cpc_sketch_pg_functions.c:200-244].

- **Anyelement hashing bottoms out at the raw datum bytes.** The build transition
  fetches the argument's `typlen/typbyval/typalign` via `get_typlenbyvalalign`
  and feeds the core `update()` the varlena payload (`VARDATA_ANY` /
  `VARSIZE_ANY_EXHDR`), the by-value datum address, or the by-ref pointer
  [verified-by-code, cpc_sketch_pg_functions.c:91-103]. Distinct-counting is
  therefore over the *physical representation* of the value, not a semantic
  equality — an `[inferred]` caveat for callers mixing types that compare equal
  but serialize differently.

- **`STORAGE = EXTERNAL` on the type disables compression but allows TOAST
  out-of-line.** Chosen so sketch blobs live out-of-line without PGLZ churn
  [verified-by-code, sql/datasketches_cpc_sketch.sql:31] [inferred rationale].

- **Bidirectional `WITHOUT FUNCTION` casts to/from `bytea`.** Because the type IS
  a `bytea` physically, the casts are pure relabels (no function, `ASSIGNMENT`),
  letting users store sketches in `bytea` columns and back with zero copy
  [verified-by-code, sql/datasketches_cpc_sketch.sql:34-35].

- **A private base64 codec rather than PG's `encode()/decode()`.** `base64.c`
  hand-rolls encode/decode with a static lookup table so the C `in`/`out`
  functions don't depend on `utils/builtins` encoding entry points; it is
  lenient on decode (ignores whitespace, tolerates partial padding)
  [verified-by-code, base64.c:23-111].

- **`ptr_with_size` is the serialize return ABI.** The C++ side returns
  `{ void* ptr; unsigned long long size; }`; the C side then `SET_VARSIZE`s the
  buffer in place — the C++ core serializes directly into a `palloc`'d buffer
  that already reserves `header_size` (`VARHDRSZ` or `VARHDRSZ+1`) leading bytes
  for the varlena header [verified-by-code, ptr_with_size.h:23-26;
  cpc_sketch_c_adapter.cpp:98-111; cpc_sketch_pg_functions.c:166-169]. No copy
  between the C++ vector and the PG varlena.

- **`_PG_init` is used for library init, not hooks.** Splitting `PG_MODULE_MAGIC`
  (in `common.c`) from `_PG_init` (in `global_hooks.c`) is unusual; the
  motivation is that CPC needs one-time global compression-table setup
  independent of the varlena-type plumbing [verified-by-code, global_hooks.c:20-30].

## Links into corpus

- [[postgresql-hll]] — the hand-rolled-HLL sibling. Sharpest contrast on the
  state-ABI axis: postgresql-hll defines a real `hll_t` varlena and keeps the
  aggregate state *as that materialized type* throughout, whereas datasketches
  keeps a live C++ object behind `internal` and only serializes at parallel /
  final boundaries. Same domain (distinct counting), opposite state discipline.
- [[topn]] — JSONB-aggregate-state sibling. topn's transition state is a
  serialized value (its own type over JSONB-ish storage) rather than an opaque
  `internal` pointer; contrast the "materialized-state-always" vs
  "live-object-until-boundary" choice, and the shared theme of mergeable
  approximate aggregates with `combinefn`/`serialfn`/`deserialfn`.
- [[timescaledb-toolkit]] — the Rust analogue: its `flat_serialize` /
  `#[aggregate]` machinery solves the exact same problem (a native-language
  mergeable aggregate state flattened to a PG varlena at the serialize boundary)
  that datasketches solves in C++ with `palloc_allocator` + `ptr_with_size`.
- [[pgrouting]] — C++-core-behind-`extern "C"` firewall sibling; contrast the
  boost/C++ algorithm library wrapped for PG and the exception-to-`ereport`
  boundary discipline.
- [[parquet_s3_fdw]] — another C++-library wrapper crossing the `extern "C"`
  seam into PG's C world; useful contrast on how each keeps C++ exceptions from
  reaching PG's `longjmp`.
- [[pg-libphonenumber]] — small, focused C++-library-to-PG-type wrapper; the
  clearest minimal example of the same C-shim-over-C++-lib pattern.

## Sources

- `https://raw.githubusercontent.com/apache/datasketches-postgresql/master/README.md` — HTTP 200. Sketch inventory, C++-core-as-separate-download, build steps.
- `.../master/Makefile` — HTTP 200. `MODULE_big`, per-sketch `OBJS` pairing `.c` + `_c_adapter.cpp`, `-std=c++11`, `-lstdc++`, `datasketches-cpp` external dir assumption.
- `.../master/datasketches.control` — HTTP 200. `default_version = '1.8.0-SNAPSHOT'`, relocatable.
- `.../master/sql/datasketches_cpc_sketch.sql` — HTTP 200. Type shell + base64 I/O, `WITHOUT FUNCTION` bytea casts, the full parallel-aggregate quartet, build/distinct/union aggregates.
- `.../master/sql/datasketches_theta_sketch.sql` — HTTP 200 (aggregate-shape scan only). Confirms union / intersection / a-not-b set-op aggregates.
- `.../master/src/cpc_sketch_pg_functions.c` — HTTP 200 (name probe: `..._pg_functions.cpp` → 404; the PG-facing files are `.c`). Read in full: transition/serial/deserial/combine/final + scalar functions.
- `.../master/src/cpc_sketch_c_adapter.cpp` — HTTP 200. The C++ adapter: template instantiation, placement-new over palloc, per-function try/catch firewall.
- `.../master/src/cpc_sketch_c_adapter.h` — HTTP 200. `extern "C"` signatures.
- `.../master/src/common.c` — HTTP 200 (`common.cpp` → 404; `common.h` → 404). `PG_MODULE_MAGIC`, generic `pg_sketch_in/out`, `pg_error`, `pg_floatN_get_datum`.
- `.../master/src/base64.c` + `base64.h` — HTTP 200. Private base64 codec.
- `.../master/src/global_hooks.c` — HTTP 200 (`global_hooks.cpp` → 404). `_PG_init` → `cpc_init()`, `_PG_fini` → no-op.
- `.../master/src/allocator.h` — HTTP 200. `palloc_allocator<T>` C++ Allocator over `palloc`/`pfree`.
- `.../master/src/postgres_h_substitute.h` — HTTP 200 (`.cpp` → 404). Minimal ABI to avoid including `postgres.h` in C++ (GCC 4.8.5 / RHEL rationale in-comment).
- `.../master/src/agg_state.h` — HTTP 200. `struct agg_state` + `enum agg_state_type`.
- `.../master/src/ptr_with_size.h` — HTTP 200. Serialize return struct.
- `.../master/src/theta_sketch_c_adapter.h` — HTTP 200. Set-op signatures (union/intersection/a_not_b) for the divergent theta variant.
- `.../master/.gitmodules` — HTTP 404. C++ core is an external download/symlink (`datasketches-cpp`), not a vendored submodule.
- `.../master/src/*.cpp` for the PG-facing files, `common.cpp`, `common.h`, `global_hooks.cpp`, `postgres_h_substitute.cpp` — HTTP 404 (wrong extension / header-only; resolved by probing `.c` variants).
- Apache DataSketches C++ core (`cpc_sketch_alloc`, `cpc_union_alloc`, KLL/theta/HLL/fi templates) — NOT fetched (external repo `apache/datasketches-cpp`); all core-internal claims tagged `[inferred]`.
