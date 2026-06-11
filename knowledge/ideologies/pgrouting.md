# pgRouting — a thin C/fmgr shell over a C++/Boost-Graph engine, with a catch-all exception firewall at the language boundary

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `pgRouting/pgrouting` @ branch `develop`. All `file:line` cites point
> into that repo (not `source/`). Cites verified against the files fetched on
> 2026-06-10 (see Sources footer). Read alongside `[[knowledge/ideologies/pgrx]]`
> (the inverse boundary — Rust unwinding ↔ ereport-longjmp) and
> `[[knowledge/ideologies/postgis]]` (its required dependency).

## Domain & purpose

pgRouting "extends the PostGIS/PostgreSQL geospatial database to provide
geospatial routing and other network analysis functionality" — shortest path
(Dijkstra, A*, bidirectional, Bellman-Ford), driving distance, TSP, and more
(`README.md:31-46`) `[from-README]`. The algorithms are implemented against the
**Boost Graph Library** (BGL ≥ 1.56, `README.md:56-61`) `[from-README]`. The
reason to document it: pgRouting is the corpus's cleanest example of a
**two-language extension** — a deliberately thin C/fmgr layer that marshals
Postgres arguments and a substantial C++ engine that runs STL/Boost graph
algorithms — and of the discipline required to keep C++ exceptions from ever
crossing into Postgres's longjmp-based error world.

## How it hooks into PG

`relocatable = true`, `requires = 'plpgsql,postgis'`, with a CMake-templated
control file: `default_version = '${PROJECT_VERSION}'`,
`module_pathname = '${PROJECT_MODULE_PATHNAME}'`
(`sql/common/pgrouting.control:1-6`) `[verified-by-code]` — the `.in`→generated
`.control` and the `${...}` placeholders confirm the build is **CMake + Boost**,
not PGXS or in-tree meson (`README.md:68-95`) `[from-README]`. There is no
`_PG_init`, no hooks, no GUCs, no shmem: pgRouting is a pure
`CREATE EXTENSION pgrouting CASCADE` library of SQL-callable set-returning
functions. Each algorithm is a `PG_FUNCTION_INFO_V1` SRF; e.g.
`_pgr_dijkstra_v4` (`src/dijkstra/dijkstra.c:40-157`) `[verified-by-code]`.

The layering, visible end-to-end in the Dijkstra path:

1. **C / fmgr SRF** (`dijkstra.c`) — `SRF_IS_FIRSTCALL` setup,
   `PG_GETARG_*`/`text_to_cstring`/`PG_GETARG_ARRAYTYPE_P` argument extraction,
   then a call into the process layer `pgr_process_shortestPath(...)` with
   `&result_tuples, &result_count` out-params (`dijkstra.c:51-103`)
   `[verified-by-code]`.
2. **C++ driver** (`shortestPath_driver.cpp`) — `do_shortestPath(...)` reads the
   edge/point SQL into STL `std::vector<Edge_t>`, builds a
   `DirectedGraph`/`UndirectedGraph`, dispatches to `dijkstra(...)` /
   `bdDijkstra` / `bellmanFord` / etc., and post-processes a
   `std::deque<Path>` (`shortestPath_driver.cpp:116-291`) `[verified-by-code]`.
3. **Boundary conversion** — `to_postgres::get_tuples(paths, return_tuples)`
   turns the C++ `std::deque<Path>` into a C `Path_rt*` array
   (`shortestPath_driver.cpp:291`) the C SRF then iterates with
   `SRF_RETURN_NEXT` + `heap_form_tuple` (`dijkstra.c:118-156`)
   `[verified-by-code]`.

Cross-ref `[[knowledge/idioms/fmgr]]`,
`[[knowledge/idioms/memory-contexts]]`,
`.claude/skills/fmgr-and-spi/SKILL.md`,
`.claude/skills/error-handling/SKILL.md`.

## Where it diverges from core idioms

### 1. The algorithm's working set lives in the C++ heap (STL/new), not Postgres memory contexts

Core C code allocates everything through `palloc` in a `MemoryContext` so the
executor can reclaim it on error or context reset. pgRouting's heavy data —
the parsed edge vectors, the Boost graph, the `std::deque<Path>` results — are
ordinary C++ STL containers (`std::vector<Edge_t> edges`, `std::deque<Path>
paths`, `shortestPath_driver.cpp:175-231`) `[verified-by-code]`, owned by RAII
and freed by destructors, entirely **outside** Postgres's
`CurrentMemoryContext`. Only at the very end does the result cross into
palloc'd memory: the C SRF builds its per-row `values`/`nulls` with `palloc`
and the boundary `get_tuples` produces the `Path_rt*` the
`multi_call_memory_ctx` owns (`dijkstra.c:130-151`, `:54`) `[verified-by-code]`.
This is the *opposite* of `[[knowledge/ideologies/pgrx]]`, which projects
Postgres `palloc`/`MemoryContext` up into Rust; pgRouting keeps the two heaps
separate and only marshals the answer across. Cross-ref
`[[knowledge/idioms/memory-contexts]]`.

### 2. A catch-all exception firewall — C++ exceptions must never reach Postgres's longjmp

This is the load-bearing divergence. Postgres reports errors by `ereport` →
`siglongjmp`; a C++ exception unwinding through that machinery (or a longjmp
unwinding through C++ stack frames with destructors) is undefined behavior.
pgRouting's driver therefore wraps its *entire* body in a `try` with a complete
catch ladder — `AssertFailedException`, `const std::pair<std::string,
std::string>&`, `const std::string&`, `std::exception&`, and a final `catch
(...)` — each of which writes into `std::ostringstream &err / &log / &notice`
out-parameters instead of propagating (`shortestPath_driver.cpp:143, 296-308`)
`[verified-by-code]`. No exception is allowed to escape `do_shortestPath`; the
C/process layer (not fetched) inspects the `err` stream after the call and
*then* issues `ereport(ERROR, …)` on the C side, where longjmp is safe. So the
two error models are bridged by **catch-everything-and-return-a-string** at the
C++ edge, mirrored by `ereport`-from-C — the dual of pgrx's
`pg_guard_ffi_boundary` (which wraps C calls in `sigsetjmp` to catch the inbound
longjmp). pgRouting also threads a running `hint` string so the catch blocks can
report *which* SQL query was executing when an exception fired
(`shortestPath_driver.cpp:141, 163-194, 303`) `[verified-by-code]`. Cross-ref
`[[knowledge/idioms/error-handling]]`, `[[knowledge/ideologies/pgrx]]`.

### 3. It is GPL-2.0-or-later, not the PostgreSQL license

Almost every extension in the doc-set ships under the PostgreSQL/MIT-style
license; pgRouting is "GPL-2.0-or-later" for most features, with some Boost-
licensed and MIT-X-licensed parts (`README.md:117-122`) `[from-README]`. The
source headers carry the full GPL-2 notice (`dijkstra.c:19-31`)
`[verified-by-code]`. This is a genuine ecosystem divergence: a copyleft
loadable module linked into the (PostgreSQL-licensed) backend, a licensing
posture core contrib never takes. Worth flagging for anyone surveying the
extension ecosystem's legal surface.

### 4. Hard dependency on PostGIS + plpgsql; CMake/Boost build, not PGXS/meson

`requires = 'plpgsql,postgis'` (`pgrouting.control:6`) `[verified-by-code]`
means pgRouting cannot be installed without PostGIS — it is an extension *on top
of* another large extension, consuming PostGIS geometry for its network
representation. The build needs perl, a C++14-capable compiler, Boost ≥ 1.56,
and CMake ≥ 3.12 (`README.md:54-62`) `[from-README]` — a heavier, non-standard
toolchain than the PGXS Makefile most contrib uses. Cross-ref
`[[knowledge/ideologies/postgis]]`, `.claude/skills/extension-development/SKILL.md`.

## Notable design decisions (cited)

- **Variadic dispatch on `PG_NARGS()`**: one C entry point serves both the
  many-to-many (`PG_NARGS()==8`) and combinations (`==6`) signatures, branching
  on argument count (`dijkstra.c:56-103`) `[verified-by-code]` — a single SRF
  backing several SQL overloads.
- **Explicit deprecation-with-migration discipline**: the new `_pgr_dijkstra_v4`
  coexists with a deprecated `_pgr_dijkstra` that carries `TODO(v4.2) define
  SHOWMSG`, `TODO(v4.3) change to WARNING`, `TODO(v5) Move to legacy` and emits
  `ERRCODE_WARNING_DEPRECATED_FEATURE` when `SHOWMSG` is defined
  (`dijkstra.c:159-188`) `[verified-by-code]` — a staged ABI sunset plan written
  into the source.
- **Generated-from-template source**: file headers say "Generated with Template
  by … pgRouting developers" (`dijkstra.c:3-4`, `shortestPath_driver.cpp:13-15`)
  `[from-comment]` — the C/driver glue per algorithm is code-generated to keep the
  boundary uniform across dozens of algorithms.
- **One driver multiplexes many algorithms**: `do_shortestPath` dispatches on a
  `Which` enum across Dijkstra, bidirectional Dijkstra, Edward-Moore,
  DAG-shortest-path, Bellman-Ford, and edge-disjoint
  (`shortestPath_driver.cpp:233-284`) `[verified-by-code]`, sharing the SQL-read +
  graph-build + post-process scaffolding.

## Links into corpus

- `[[knowledge/ideologies/pgrx]]` — the inverse boundary: pgrx wraps every C call
  in `sigsetjmp` to catch Postgres's longjmp into Rust; pgRouting wraps its C++
  body in `try/catch(...)` to keep C++ exceptions from reaching Postgres's
  longjmp. Two halves of the same impedance-mismatch problem.
- `[[knowledge/ideologies/postgis]]` — required dependency; pgRouting is an
  extension layered on the PostGIS geometry stack.
- `[[knowledge/idioms/fmgr]]` — `PG_FUNCTION_INFO_V1` SRF ValuePerCall,
  `SRF_FIRSTCALL_INIT`/`SRF_RETURN_NEXT`, `get_call_result_type` +
  `heap_form_tuple`.
- `[[knowledge/idioms/memory-contexts]]` — the algorithm's STL working set lives
  outside Postgres contexts; only the result array is marshaled into
  `multi_call_memory_ctx`.
- `[[knowledge/idioms/error-handling]]` — the catch-all → `ostringstream` →
  C-side `ereport` bridge between C++ exceptions and `ereport`/longjmp.

## Anthropology takeaway

pgRouting is the doc-set's archetype of a **"compute engine bolted onto Postgres
through a narrow fmgr straw"**: the SQL-callable surface is a thin, often
code-generated C shell, and all the substance is a separate C++/Boost library
with its own heap and its own error model. The single most reusable observation
is the **language-boundary error firewall**: any extension embedding C++ (or any
exception-using runtime) must, like pgRouting, guarantee that no exception
crosses into Postgres's `siglongjmp` world — the `try { … } catch (...) { err <<
… }` + out-param pattern, paired with `ereport` on the C side, is the safe
bridge, and it is the exact mirror image of pgrx's `pg_guard_ffi_boundary`. That
pairing — pgRouting (C++→PG) and pgrx (PG→Rust) — would make an excellent
`knowledge/idioms` note on **bridging Postgres's longjmp error model with a
foreign runtime's exception/unwind model**, a recurring hazard for any non-C
extension. Two secondary threads for an ecosystem survey: pgRouting's STL-heap
working set sidesteps `MemoryContext` accounting entirely (so a runaway graph
search is invisible to `pg_backend_memory_contexts`), and its GPL-2 license +
mandatory PostGIS dependency + CMake/Boost toolchain make it an outlier on the
legal and build-system axes the rest of the corpus rarely touches.

## Sources

Fetched 2026-06-10 (branch `develop`):

- `https://api.github.com/repos/pgRouting/pgrouting/git/trees/develop?recursive=1`
  @ 2026-06-10 → HTTP 200 (tree listing; manifest `pgrouting.control.in` and
  `include/c_common/pgr_alloc.hpp` are both 404 — the control template lives at
  `sql/common/pgrouting.control` and `c_common/` has no `pgr_alloc.hpp`;
  substituted `src/dijkstra/shortestPath_driver.cpp` for the C++ boundary story).
- `https://raw.githubusercontent.com/pgRouting/pgrouting/develop/README.md`
  @ 2026-06-10 → HTTP 200 (3056 bytes; intro, requirements, build, license).
- `.../develop/pgrouting.control.in` @ 2026-06-10 → HTTP 404.
- `.../develop/include/c_common/pgr_alloc.hpp` @ 2026-06-10 → HTTP 404.
- `.../develop/sql/common/pgrouting.control` @ 2026-06-10 → HTTP 200 (188 bytes;
  `requires=plpgsql,postgis`, CMake-templated version/path).
- `.../develop/src/dijkstra/dijkstra.c` @ 2026-06-10 → HTTP 200 (10274 bytes;
  deep-read — the C/fmgr SRF layer, `_pgr_dijkstra_v4` + deprecated `_pgr_dijkstra`).
- `.../develop/src/dijkstra/shortestPath_driver.cpp` @ 2026-06-10 → HTTP 200
  (10010 bytes; deep-read — STL/Boost engine, algorithm dispatch, the catch-all
  exception ladder, boundary `get_tuples`).

All cites are `[verified-by-code]` against the fetched `.c`/`.cpp`/`.control`
except the algorithm inventory, BGL/C++14/CMake build requirements, and license
breakdown, which are `[from-README]`, and the "generated with template" note,
which is `[from-comment]`. The C *process* layer (`shortestPath_process.cpp`,
which calls `do_shortestPath` and turns the `err` stream into `ereport`), the
`c_common`/`cpp_common` PG↔C++ data getters, and the Boost algorithm bodies
(`dijkstra.hpp` etc.) were not fetched; the claim that the C side issues
`ereport(ERROR)` from the populated `err` stream is `[inferred]` from the driver
writing errors to out-params rather than throwing, tagged accordingly.
