# Wasmer Postgres (wasmerio/wasmer-postgres) — arbitrary WebAssembly run inside the backend via hand-rolled `pg-extend-rs` bindings, with the FDW API repurposed as a read-only introspection view

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `wasmerio/wasmer-postgres` @ branch `master` (~430★, Rust). All
> `file:line` cites below point into that repo (not `source/`), since this doc
> characterizes an *external* extension's divergence from core idioms. Cites
> verified against the files fetched on 2026-06-17 (see Sources footer). This is
> the early-Wasmer-runtime, archived-ish ancestor of the modern WASM-in-PG
> approach; the directly-relevant contrast is `[[knowledge/ideologies/wrappers]]`
> (Supabase `wasm_fdw`), which is far more mature.

## Domain & purpose

Wasmer Postgres is "a complete and mature WebAssembly runtime for Postgres based
on Wasmer ... an original way to extend your favorite database capabilities"
(`README.md:4-5`) `[from-README]`. It loads a `.wasm` module into the running
backend and exposes its exported functions as SQL-callable functions — so you
write a function in Rust (or any WASM-targeting language), compile to WASM, and
call it from `SELECT` at near-native speed (`README.md:62-100`) `[from-README]`.
The pitch is explicitly a faster alternative to PL/pgSQL for compute (the
benchmark table shows a 73× Fibonacci speedup at n=5000, `README.md:172-223`)
`[from-README]`. It is a young, experimental project: the README self-describes
as "still in heavy development. This is a 0.1.0 version" and works "on Postgres
10 only" (`README.md:15-17`, `:53-55`) `[from-README]`.

## How it hooks into PG

Unlike most modern Rust PG extensions, this is **not built on pgrx**. It uses
the older, now-defunct `pg-extend-rs` framework (`bluejekyll/pg-extend-rs`,
crates `pg-extend` + `pg-extern-attr`, pinned to a git `branch = "master"`,
`Cargo.toml:19-20`) `[verified-by-code]`. The crate compiles to a `cdylib`
(`Cargo.toml:12-13`) and embeds the **`wasmer-runtime` 0.6.0** engine
(`Cargo.toml:17-18`) `[verified-by-code]` — an early Wasmer with no Component
Model, no WASI sandbox policy surface, no fuel metering.

The module-magic boilerplate is one macro: `pg_magic!(version:
pg_sys::PG_VERSION_NUM)` (`src/lib.rs:3`) `[verified-by-code]` — the
`pg-extend-rs` analogue of `PG_MODULE_MAGIC`. There is no `_PG_init`-style hook
chain; the extension installs no planner/executor/utility hooks. The control
file is minimal — `relocatable = true`, `default_version = '0.1.0'`, and
**notably named `wasm.control`, so the extension is `CREATE EXTENSION wasm`**,
not `wasmer` (`src/wasm.control:1-4`) `[verified-by-code]`. Per the README the
extension also ships a hand-written PL/pgSQL layer (`wasm_init`,
`wasm_new_instance`, and the `ns_<fn>` wrapper functions are PL/pgSQL — see the
`\df+` output showing `Language | plpgsql`, `README.md:104-127`) `[from-README]`
that calls down into the C/Rust `invoke_function_N` entry points.

Two distinct surfaces hook in:

1. **SQL-callable functions** via `#[pg_extern]` (the `pg-extern-attr`
   proc-macro): `new_instance` (`src/instance.rs:26-27`) and a fixed ladder
   `invoke_function_0` … `invoke_function_10` (`src/instance.rs:147-325`)
   `[verified-by-code]`. **This is the actual WASM-execution path.**
2. **Two foreign-data wrappers** via `#[pg_foreignwrapper]`:
   `InstancesForeignDataWrapper` and `ExportedFunctionsForeignDataWrapper`
   (`src/foreign_data_wrappers/instances.rs:14-17`,
   `src/foreign_data_wrappers/exported_functions.rs:17-18`) `[verified-by-code]`.

**The investigated question, settled:** the `src/foreign_data_wrappers/`
directory does hook in via the real FDW API (`pg_fdw::{ForeignData, ForeignRow}`
+ generated `CREATE FOREIGN TABLE`, `instances.rs:50-56`), but it does **NOT**
execute any WASM. It is used purely as a **read-only introspection / catalog
view**: the two foreign tables `wasm.instances` and `wasm.exported_functions`
expose the in-process instance registry (`README.md:131-170`,
`instances.rs:30-57`) `[verified-by-code]`. So the answer is *both*, but with a
sharp division of labor: SQL functions run WASM; the FDW only reports on what's
loaded. Cross-ref `[[knowledge/subsystems/foreign]]`,
`[[knowledge/idioms/fdw-routine-callbacks]]`, `[[knowledge/idioms/fmgr]]`.

## Where it diverges from core idioms

### 1. The FDW API is repurposed as a read-only `pg_catalog`-style introspection view, not a data source

A core FDW (`postgres_fdw`, `file_fdw`) wraps an *external* data source —
another database, a file, an API. Here both FDWs read **process-local backend
state**: `begin()` snapshots the global instance `HashMap` into a `Vec<Row>`
(`instances.rs:30-43`; `exported_functions.rs:33-76`) `[verified-by-code]`. The
`schema()` callback emits a `CREATE FOREIGN TABLE ... (id text, wasm_file text)`
DDL string (`instances.rs:51-55`) `[verified-by-code]`. This is the FDW machinery
bent into the role PG normally fills with system views over shared memory (e.g.
`pg_stat_activity` via a set-returning function). Using `CREATE FOREIGN TABLE`
as a window onto in-backend runtime state — rather than `pg_proc`/SRF — is the
inversion. Cross-ref `[[knowledge/idioms/fdw-iterate-scan]]`,
`[[knowledge/subsystems/contrib-postgres_fdw]]` (the canonical "real" FDW).

### 2. WASM linear memory and the engine live entirely outside PG's MemoryContext / shmem world

The `wasmer-runtime` `Instance` owns its own linear memory in the Wasmer
allocator; nothing here goes through `palloc`/MemoryContexts. Worse, the instance
registry is a **`static mut INSTANCES: Option<RwLock<HashMap<...>>>`** lazily
initialized on first use (`src/instance.rs:13-24`) `[verified-by-code]`. This is
process-local backend-private state guarded by a Rust `RwLock` — *not* a PG
LWLock, *not* shared memory. Under PG's per-connection fork model that means an
instance created via `new_instance` in one backend is **invisible to every other
backend**; `wasm.instances` only ever shows what the current connection loaded.
A core extension sharing cross-backend state would use a shmem hash + an LWLock
tranche. Cross-ref `[[knowledge/idioms/memory-contexts]]`,
`[[knowledge/idioms/locking-overview]]`, `[[knowledge/subsystems/storage-ipc]]`,
`[[knowledge/subsystems/storage-buffer]]` (the shared state it bypasses).

### 3. Arbitrary, unsigned WASM is loaded from an arbitrary filesystem path with no sandbox policy

`new_instance(wasm_file: String)` does `File::open` on a caller-supplied absolute
path, reads the bytes, and instantiates with an **empty import object**
(`imports! {}`, `src/instance.rs:27-41`) `[verified-by-code]`. There is no
checksum/signature pinning (contrast `wasm_fdw`'s SHA-256 gate in
`[[knowledge/ideologies/wrappers]]`), no allow-list of paths, no WASI capability
configuration, and the module gets the host backend's privileges. The instance
key is a UUIDv5 derived from the module's `WasmHash` (`instance.rs:44-49`)
`[verified-by-code]` — a content identifier, not an integrity check. Because the
SQL function is reachable by any role that can `EXECUTE` it, this is a path to
running native-speed arbitrary code in the backend with weaker controls than
even `LANGUAGE C`. Cross-ref the `extension-development` skill (the vetted-`.so`
trust model this sidesteps).

### 4. The Rust↔C type bridge is a hand-cranked arity ladder, not a variadic / SRF design

PG has `VARIADIC` and the fmgr machinery for arbitrary argument counts. Here the
authors instead generated **eleven near-identical functions** `invoke_function_0`
through `invoke_function_10`, each with a fixed `i64` argument count
(`src/instance.rs:147-325`) `[verified-by-code]`, all delegating to one private
`invoke_function(instance_id, function_name, arguments: &[i64])`
(`instance.rs:65-145`). Every SQL argument is forced through `i64`; inside,
each is downcast to the WASM param type (`Type::I32 => Value::I32(*argument as
i32)`, `instance.rs:100-111`) `[verified-by-code]`. Float/`f32`/`f64` arguments
are explicitly rejected at call time ("not supported yet", `instance.rs:103-110`)
`[verified-by-code]`, and only single-result functions return a value
(`instance.rs:128-136`). The README confirms only `i32`/`i64`/`v128` map to
`integer`/`bigint`/`decimal` and "Floats are partly implemented"
(`README.md:125-127`) `[from-README]`. Cross-ref `[[knowledge/idioms/fmgr]]`.

### 5. Error propagation collapses every failure into `error!` + `None`

The `pg-extend` `error!` macro is used for all failure cases — unknown function,
arity mismatch, unsupported float arg, call failure, missing instance
(`src/instance.rs:73-143`) `[verified-by-code]`. Several of these *also* `return
None` afterward (`instance.rs:78`, `:94`, `:109`, `:124`, `:142`), so depending
on how `error!` maps to `ereport` elevel, the function either ERRORs out or
silently yields SQL NULL. There is no SQLSTATE selection, no `errdetail`/
`errhint` structure — failures are flat formatted strings. A core SQL-callable C
function would pick a deliberate `ERRCODE_*` via `ereport`. The FDW field
accessors return `Err("Unknown field")` as a bare `&str`
(`instances.rs:74`, `exported_functions.rs:108`) `[verified-by-code]`, leaning on
`pg-extend` to translate. Cross-ref `[[knowledge/idioms/error-handling]]`.

## Notable design decisions (cited)

- **Control file is `wasm.control`** → the extension is `CREATE EXTENSION wasm`,
  a deliberately short name; `comment` and `relocatable = true` are the only
  other fields (`src/wasm.control:1-4`) `[verified-by-code]`. No `superuser`,
  `module_pathname`, or `requires` line.
- **Instance registry is `static mut` + lazy init** (`src/instance.rs:13-24`)
  `[verified-by-code]` — backend-private, not shmem; a fork-model footgun
  (see divergence #2).
- **UUIDv5 instance keys from the module hash** (`instance.rs:44-49`)
  `[verified-by-code]` — identical bytes → identical id, so re-loading the same
  module is idempotent in the registry; but the key is also the public handle
  users paste into `invoke_function_N`.
- **WASM→PG type table is duplicated** between the call path
  (`instance.rs:100-111`, i32/i64 only) and the introspection FDW
  (`exported_functions.rs:36-43`, which additionally maps `F32/F64 → numeric`
  and `V128 → decimal`) `[verified-by-code]` — the FDW *advertises* types the
  call path can't actually accept yet.
- **Empty import object** (`imports! {}`, `instance.rs:39`) `[verified-by-code]`
  — guest WASM gets *no* host functions at all (no HTTP/time/stats surface,
  unlike `wasm_fdw`'s capability host). Pure compute only; the guest cannot call
  back into PG or the network.
- **Built on the abandoned `pg-extend-rs`** (`Cargo.toml:19-20`) and
  **`wasmer-runtime` 0.6.0** (`Cargo.toml:17`) `[verified-by-code]` — both
  long-superseded; this fixes the project to ~PG 10 (`README.md:53-55`).

## Links into corpus

- `[[knowledge/ideologies/wrappers]]` — the single most important contrast:
  Supabase `wasm_fdw` is the mature WASM-in-backend design (Component Model,
  SHA-256 pinning, ABI version handshake, a deliberate host-capability syscall
  surface). wasmer-postgres is the primitive ancestor: empty imports, no
  integrity gate, FDW used only for introspection rather than as the WASM host.
- `[[knowledge/subsystems/foreign]]` + `[[knowledge/idioms/fdw-routine-callbacks]]`
  + `[[knowledge/idioms/fdw-iterate-scan]]` — the FDW callback surface this
  extension repurposes into a read-only introspection view.
- `[[knowledge/subsystems/contrib-postgres_fdw]]` + `[[knowledge/subsystems/contrib-file_fdw]]`
  — canonical "real data source" FDWs, against which the introspection-view
  inversion stands out.
- `[[knowledge/idioms/fmgr]]` — the SQL-callable entry point the
  `invoke_function_N` arity ladder hand-implements instead of using VARIADIC.
- `[[knowledge/idioms/memory-contexts]]` + `[[knowledge/idioms/locking-overview]]`
  + `[[knowledge/subsystems/storage-ipc]]` — the MemoryContext/shmem/LWLock
  machinery the `static mut` registry and Wasmer linear memory bypass.
- `[[knowledge/idioms/error-handling]]` — the `ereport`/SQLSTATE discipline the
  flat `error!`-then-`None` pattern skips.
- `.claude/skills/extension-development/SKILL.md` — control-file fields and the
  vetted-`.so` trust model the unsigned-arbitrary-path loader sidesteps.

## Sources

Fetched 2026-06-17 (branch `master`), all via
`https://raw.githubusercontent.com/wasmerio/wasmer-postgres/master/<path>`:

- `.../README.md` @ 2026-06-17T00:00Z → HTTP 200 (238 lines).
- `.../Cargo.toml` @ 2026-06-17T00:00Z → HTTP 200 (19 lines; `pg-ext-wasm`,
  `wasmer-runtime` 0.6.0, `pg-extend-rs`).
- `.../src/lib.rs` @ 2026-06-17T00:00Z → HTTP 200 (6 lines; `pg_magic!` + two
  module decls — the real entry points live in `instance.rs`).
- `.../src/instance.rs` @ 2026-06-17T00:00Z → HTTP 200 (325 lines; `new_instance`
  + `invoke_function_0..10`, the WASM-execution path).
- `.../src/wasm.control` @ 2026-06-17T00:00Z → HTTP 200 (3 lines; control file is
  `wasm.control`, not `wasmer.control` — extension name is `wasm`).
- `.../src/foreign_data_wrappers/mod.rs` @ 2026-06-17T00:00Z → HTTP 200 (2 lines).
- `.../src/foreign_data_wrappers/instances.rs` @ 2026-06-17T00:00Z → HTTP 200
  (76 lines; `wasm.instances` introspection FDW).
- `.../src/foreign_data_wrappers/exported_functions.rs` @ 2026-06-17T00:00Z →
  HTTP 200 (111 lines; `wasm.exported_functions` introspection FDW).

No 404 gaps. All cites are `[verified-by-code]` against the fetched `.rs`/
`.control`/`.toml` except the runtime framing, benchmarks, PG-10-only support,
the PL/pgSQL wrapper layer, and the `wasm_init`/`ns_<fn>` user surface, which are
`[from-README]` (the PL/pgSQL `.sql` install script and `justfile` were not
fetched). The `pg-extend-rs` macro internals (`pg_magic!`, `#[pg_extern]`,
`#[pg_foreignwrapper]` expansions) were not deep-read.
