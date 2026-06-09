# pgrx — reimplementing the entire C extension ABI as a safe Rust surface (the substrate under zombodb & wrappers)

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `pgcentralfoundation/pgrx` @ branch `develop`. All `file:line` cites
> below point into that repo (not `source/`), since this doc characterizes an
> *external* framework's divergence from core idioms. Cites verified against the
> files fetched on 2026-06-09 (see Sources footer).

## Domain & purpose

pgrx is "a framework for creating Postgres extensions in 100% Rust"
(`pgrx/src/lib.rs:10`) `[verified-by-code]` that "strives to be as idiomatic and
safe as possible" and supports Postgres 13–18 from one codebase
(`README.md:15-17`) `[from-README]`. Where every other ideology in this directory
*is* an extension, pgrx is the **meta-substrate**: it is the framework two
already-documented extensions are built on. Its license header records the
lineage — "Portions Copyright 2019-2021 ZomboDB, LLC … 2021-2023 Technology
Concepts & Design, Inc. … 2023 PgCentral Foundation"
(`pgrx/src/lib.rs:1-9`) `[verified-by-code]` — pgrx was extracted from zombodb
and is now the foundation under `[[knowledge/ideologies/zombodb]]` and
`[[knowledge/ideologies/wrappers]]`. Documenting it explains *how* those Rust
extensions reach Postgres internals at all.

The user-facing promise is that this compiles into a working extension:

```rust
use pgrx::prelude::*;
#[pg_extern]
fn my_to_lowercase(input: &str) -> String { input.to_lowercase() }
```

(`pgrx/src/lib.rs:14-22`) `[verified-by-code]` — no `PG_FUNCTION_INFO_V1`, no
`Datum` marshalling, no `foo--1.0.sql`, no Makefile. pgrx generates all of it.

## How it hooks into PG

pgrx does not "hook into" PG via one seam — it **re-expresses the whole C
extension ABI**. Its module map (`pgrx/src/lib.rs:41-77`) `[verified-by-code]`
is a Rust mirror of `src/include/`: `bgworkers`, `fcinfo`, `guc`, `heap_tuple`,
`htup`, `itemptr`, `list`, `lwlock`, `memcx`/`memcxt`, `nodes`, `palloc`,
`pgbox`, `rel`, `shmem`, `spi`, `spinlock`, `stringinfo`, `aggregate`,
`callbacks`, `datum`, … Each wraps the corresponding core subsystem. The actual
machinery is four layers:

1. **`pgrx-pg-sys`** — per-major-version bindgen output. The crate ships
   pre-generated Rust bindings to each PG release's C headers as
   `pgrx-pg-sys/src/include/pg13.rs … pg18.rs` (+ `pgNN_oids.rs`)
   `[verified-by-code]`, feature-gated so one source tree targets PG 13–18
   (`README.md:Target Multiple Postgres Versions`). This is the raw, unsafe
   `pg_sys::*` surface every higher layer sits on.
2. **`pgrx`** — the safe wrappers (the module map above).
3. **`pgrx-macros`** (re-exported wholesale, `pgrx/src/lib.rs:32-33`) — the proc
   macros `#[pg_extern]`, `#[pg_guard]`, `#[pg_aggregate]`, `#[derive(PostgresType)]`,
   etc. that generate the fmgr glue and SQL.
4. **`pgrx-sql-entity-graph`** — compile-time SQL schema generation
   (`pgrx/src/lib.rs:35-36`, `impl_sql_translatable` / `pgrx_resolved_type`)
   `[verified-by-code]`.

Cross-ref `[[knowledge/idioms/fmgr]]`, `[[knowledge/idioms/memory-contexts]]`,
`[[knowledge/idioms/error-handling]]`, `[[knowledge/idioms/catalog-conventions]]`,
`.claude/skills/extension-development/SKILL.md`.

## Where it diverges from core idioms

### 1. The defining divergence: a `sigsetjmp` barrier wraps *every* C call, reconciling Postgres `longjmp` with Rust unwinding

This is the hardest problem in the framework and its central idea. Postgres
error handling is `ereport(ERROR)` → `siglongjmp` off `PG_exception_stack`
(`error-handling` skill). Rust error handling is stack-unwinding `panic!`. The
two are mutually corrupting: a `longjmp` over live Rust frames skips their
destructors (UB); a Rust `panic` across the C frames skips Postgres' cleanup.
pgrx's answer is `pg_guard_ffi_boundary`, which the file's own docs say is "used
to protect **every** bindgen-generated Postgres `extern "C-unwind"` function"
(`pgrx-pg-sys/src/submodules/ffi.rs:72-85`) `[verified-by-code]`. It saves
`PG_exception_stack` + `error_context_stack`, installs its own `sigsetjmp`
restore point via the `cee_scape` crate's `call_with_sigsetjmp`
(`:171-179`), runs the wrapped C function, and on a Postgres-side `siglongjmp`
catches it at the boundary and re-raises it as a controlled Rust unwind
(`:137-143`). The complementary `submodules/panic.rs` + `submodules/pg_try.rs`
carry the other direction (Rust panic → `ereport`). No core analogue exists
because core is uniformly C with one `setjmp` discipline; pg_duckdb's
`InvokeCPPFunc` (`[[knowledge/ideologies/pg_duckdb]]`) solves the *same* class of
problem for C++ at hook boundaries, but pgrx solves it *universally and
bidirectionally* for every one of the thousands of generated `pg_sys` calls.
Cross-ref `[[knowledge/idioms/error-handling]]`, `[[knowledge/idioms/locking-overview]]`
(the boundary is explicitly main-thread-only — it manipulates `static mut`
exception stacks unsynchronized, `ffi.rs:163-168`).

### 2. `#[pg_extern]` synthesizes the `PG_FUNCTION_INFO_V1` wrapper and Datum marshalling the developer never writes

Core requires every SQL-callable C function to be `Datum foo(PG_FUNCTION_ARGS)`
with hand-written `PG_GETARG_*`/`PG_RETURN_*` + a `PG_FUNCTION_INFO_V1(foo)`
declaration (`fmgr-and-spi` skill). pgrx's proc macro generates that wrapper from
an ordinary typed Rust fn: the `fcinfo` module provides the primitives
(`pg_getarg::<T: FromDatum>`, `pg_arg_is_null`, `pg_return_null`,
`pg_get_collation`, all `unsafe` over `pg_sys::FunctionCallInfo`,
`pgrx/src/fcinfo.rs:96-196`) `[verified-by-code]`, and the macro emits the
`extern "C"` entry point that unpacks args via `FromDatum`, calls the user fn
behind the FFI guard, and repacks the result via `IntoDatum`. The argument/return
type mapping lives in the `datum` module (`FromDatum`/`IntoDatum` traits,
`pgrx/src/datum/mod.rs`) `[verified-by-code]`. So the entire fmgr calling
convention becomes a compile-time codegen detail. Cross-ref
`[[knowledge/idioms/fmgr]]`.

### 3. SQL schema is *generated from the Rust AST*, not hand-written install scripts

Core extensions ship `foo--1.0.sql` + `foo--1.0--1.1.sql` upgrade scripts by
hand (`extension-development` skill). pgrx replaces this with a compile-time
**SQL entity graph**: every `#[pg_extern]`, `#[derive(PostgresType)]`,
`#[pg_operator]`, etc. registers itself (via `impl_sql_translatable` /
`pgrx_resolved_type`, `pgrx/src/lib.rs:35-36`) into `pgrx-sql-entity-graph`,
which topologically orders the dependencies and emits `CREATE FUNCTION` /
`CREATE TYPE` / `CREATE OPERATOR` in correct order (`cargo pgrx schema`,
`README.md:Automatic Schema Generation`) `[from-README]`. This inverts the core
convention: the catalog DDL is *derived from* the C(/Rust) signatures rather than
written to match them by hand — eliminating the classic drift between a
`pg_proc` entry and its C function. Cross-ref `[[knowledge/idioms/catalog-conventions]]`,
`catalog-conventions` skill.

### 4. Rust allocations are projected onto Postgres MemoryContexts — `PgMemoryContexts` + `PgBox<T>`

Core C uses `palloc`/`MemoryContextSwitchTo` with the OOM-throws-`ereport`
contract (`memory-contexts` skill). pgrx exposes this as a compiler-checked Rust
enum: `PgMemoryContexts` "around Postgres' various `MemoryContext`s provides
simple accessibility … in a compiler-checked manner", and `PgBox<T>` "projects
Postgres-allocated memory pointers as if they're first-class Rust types"
(`pgrx/src/memcxt.rs:11-17`, enum at `:41-58`) `[verified-by-code]`. The
`CurrentMemoryContext` variant even reproduces core's caveat in its doc comment —
that during query execution it "usually points to a context that gets reset after
each" tuple (`:52-58`). pgrx also routes Rust's own allocator through palloc (the
`palloc` module), so a `Vec` or `String` created in extension code lives in a PG
context and is freed by `MemoryContextReset`, not Rust `Drop` — a deliberate
subversion of Rust's ownership model to match PG's arena lifetimes. Cross-ref
`[[knowledge/idioms/memory-contexts]]`.

### 5. A managed dev environment (`cargo-pgrx`) replaces PGXS/meson end-to-end

Core extensions build via PGXS or meson against an installed server
(`build-and-run` skill). pgrx ships `cargo-pgrx`: `cargo pgrx init` downloads and
builds private PG installs (13–18), `cargo pgrx run` launches the extension in a
throwaway cluster + `psql`, `cargo pgrx test` runs Rust `#[pg_test]` units
*inside a live backend* across versions, `cargo pgrx package` builds install
artifacts (`README.md:Key Features`) `[from-README]`. The test story is the
notable inversion: `#[pg_test]` functions execute in a real Postgres backend
(they need the `pg_sys` runtime), so "unit tests" are really in-backend
integration tests — pgrx makes that transparent. Cross-ref `[[knowledge/conventions/testing]]`,
`testing` skill, `build-and-run` skill.

## Notable design decisions (cited)

- **Bindings are committed, not generated at build time** — `pgrx-pg-sys/src/include/pg13.rs
  … pg18.rs` are checked-in bindgen output `[verified-by-code]`, so downstream
  builds don't need libclang per-build and the exact `pg_sys` surface per major
  version is auditable in-repo.
- **`#[pg_guard]` is a public macro, not just internal** — users annotate their
  own `extern "C"` callbacks (e.g. bgworker mains, hook fns) with `#[pg_guard]`
  to get the same panic/longjmp safety the framework applies internally
  (`pgrx/src/lib.rs:32-33` re-exports it). Cross-ref `[[knowledge/idioms/bgworker-and-parallel]]`.
- **Every `fcinfo` helper is `unsafe` and documents why** — each carries "we
  cannot ensure the `fcinfo` argument is a valid pointer … This is your
  responsibility" (`pgrx/src/fcinfo.rs:89-95,111-141`) — pgrx draws the
  safe/unsafe line exactly at the raw-pointer FFI surface and pushes safety up
  into the generated wrappers.
- **Main-thread-only by construction** — the FFI boundary aborts/checks in a
  multithreaded context because it mutates `static mut PG_exception_stack`
  (`pgrx-pg-sys/src/submodules/ffi.rs:163-168`, `thread_check.rs`), matching
  Postgres' per-connection single-threaded backend model. Cross-ref
  `[[knowledge/architecture/process-model]]`.
- **Modern PG-version range 13–18** — narrower than some C extensions because
  each supported major needs committed bindings + per-version feature gates.

## Links into corpus

- `[[knowledge/idioms/error-handling]]` — `pg_guard_ffi_boundary` is the single
  most important cross-ref: the universal `sigsetjmp` bridge between
  `ereport`/`longjmp` and Rust unwinding (`pgrx-pg-sys/src/submodules/ffi.rs`).
- `[[knowledge/idioms/fmgr]]` — `#[pg_extern]` + the `fcinfo` module
  generate the `PG_FUNCTION_INFO_V1`/`PG_GETARG`/`PG_RETURN` convention; `spi`
  module wraps SPI.
- `[[knowledge/idioms/memory-contexts]]` — `PgMemoryContexts` enum + `PgBox<T>` +
  palloc-backed Rust allocator.
- `[[knowledge/idioms/catalog-conventions]]` — the SQL entity graph derives
  `CREATE FUNCTION/TYPE/OPERATOR` from the Rust AST instead of hand-written
  install scripts.
- `[[knowledge/ideologies/zombodb]]` + `[[knowledge/ideologies/wrappers]]` —
  both are *built on pgrx*; zombodb is its literal ancestor (the license header).
  This doc is the substrate those two assume.
- `[[knowledge/ideologies/pg_duckdb]]` — the C++ `InvokeCPPFunc` boundary is the
  same exception-model-bridging problem pgrx solves universally for Rust.
- `.claude/skills/extension-development/SKILL.md`, `.claude/skills/fmgr-and-spi/SKILL.md`,
  `.claude/skills/memory-contexts/SKILL.md`, `.claude/skills/error-handling/SKILL.md`
  — pgrx is the systematic Rust restatement of all four.

## Anthropology takeaway (for STATE.md / cross-corpus)

The other ideologies abuse *one* pluggable seam; pgrx abstracts *all* of them.
It is the corpus's answer to "what does the full C extension ABI look like once
someone insists on memory safety?" The load-bearing insight for Phase D is
`pg_guard_ffi_boundary`: it is a precise, working specification of the
`ereport`/`longjmp` ↔ structured-unwinding mismatch that core never has to name
because it lives entirely on one side of it. Any future "should core expose a
panic-safe / unwind-aware error boundary for non-C callers?" discussion has its
reference implementation here. Secondary signal: the committed per-version
`pg_sys` bindings (`pgrx-pg-sys/src/include/pgNN.rs`) are a machine-readable
census of exactly which core symbols changed across PG 13→18 — a ready-made ABI
drift oracle.

## Sources

Fetched 2026-06-09 (branch `develop`):

- `https://api.github.com/repos/pgcentralfoundation/pgrx/git/trees/develop?recursive=1`
  @ 2026-06-09 → HTTP 200 (tree listing; used to discover crate/module layout).
- `https://raw.githubusercontent.com/pgcentralfoundation/pgrx/develop/README.md`
  @ 2026-06-09 → HTTP 200 (21112 bytes).
- `https://raw.githubusercontent.com/pgcentralfoundation/pgrx/develop/pgrx/src/lib.rs`
  @ 2026-06-09 → HTTP 200 (14369 bytes; module map, license/lineage, example).
- `https://raw.githubusercontent.com/pgcentralfoundation/pgrx/develop/pgrx/src/fcinfo.rs`
  @ 2026-06-09 → HTTP 200 (13883 bytes; fmgr-glue primitives).
- `https://raw.githubusercontent.com/pgcentralfoundation/pgrx/develop/pgrx/src/memcxt.rs`
  @ 2026-06-09 → HTTP 200 (27167 bytes; PgMemoryContexts/PgBox — header + enum read).
- `https://raw.githubusercontent.com/pgcentralfoundation/pgrx/develop/pgrx/src/spi.rs`
  @ 2026-06-09 → HTTP 200 (17043 bytes, skimmed).
- `https://raw.githubusercontent.com/pgcentralfoundation/pgrx/develop/pgrx/src/datum/mod.rs`
  @ 2026-06-09 → HTTP 200 (8486 bytes; FromDatum/IntoDatum).
- `https://raw.githubusercontent.com/pgcentralfoundation/pgrx/develop/pgrx-pg-sys/src/submodules/ffi.rs`
  @ 2026-06-09 → HTTP 200 (11592 bytes; pg_guard_ffi_boundary — deep-read).

All cites are `[verified-by-code]` against the fetched `.rs` (module map,
lineage, FFI boundary, fcinfo primitives, memcxt enum/docs, datum traits) except
the dev-environment/test workflow, multi-version targeting, and SQL-generation
end-user narrative, which are `[from-README]`. `pgrx-macros` proc-macro internals
and `pgrx-sql-entity-graph` ordering were inferred from their re-exports + README
(not deep-read), tagged where claims exceed a cite.
