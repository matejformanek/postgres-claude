# pg-extend-rs — the abandoned pre-pgrx attempt at Rust PG extensions, with an opt-in (not universal) longjmp barrier

> Routine: pg-extension-anthropologist (cloud). Repo: `bluejekyll/pg-extend-rs`
> @ branch `master`, fetched 2026-07-01 via raw.githubusercontent.com (GitHub
> API + git-tree blocked through the proxy; paths resolved from README +
> workspace `Cargo.toml`). Fetched: `README.md`, `pg-extend/src/lib.rs`,
> `pg-extend/src/pg_sys.rs`, `pg_datum.rs`, `pg_error.rs`, `pg_alloc.rs`,
> `pg_bool.rs`, `pg-extend/build.rs`, `pg-extend/Cargo.toml`, workspace
> `Cargo.toml`, `pg-extern-attr/src/lib.rs`, `log.rs`. 404: `pg_type.rs` fetched
> but not read in depth; `native.rs`, a standalone `panic.rs` (there is none —
> panic handling lives in `lib.rs`). **This repo is ABANDONED** (crate `pg-extend`
> 0.2.1, PG ceiling v12, ~2019-2020 era). It is the predecessor pgrx superseded
> and the framework `wasmer-postgres` is built on. Claims are cited to fetched
> source or tagged.

## Domain & purpose

A crate pair — `pg-extend` (runtime) + `pg-extern-attr` (proc-macros) — that let
you write PG extensions in Rust by wrapping the C extension ABI. README goals
list auto Datum conversion, a `pg_magic` macro, a `pg_extern` attribute, panic→PG
error handlers, and a palloc allocator; most other items are marked *tbd*
`[from-README]`. It targets PG 9/10/11/12 via feature flags
(`pg-extend/Cargo.toml:29-32`) `[verified-by-code]`. It is the "before pgrx"
datapoint: an early, incomplete bridge that pgrx (Eric Ridge / zombodb) later
rebuilt comprehensively.

## How it hooks into PG

- **Magic block.** `pg_magic!(version: …)` (`lib.rs:32-61`) emits `#[no_mangle]
  #[link_name = "Pg_magic_func"] extern "C" fn Pg_magic_func()` returning a
  `Pg_magic_struct` filled from `FUNC_MAX_ARGS`/`INDEX_MAX_KEYS`/`NAMEDATALEN`/
  `USE_FLOAT*_BYVAL` (`lib.rs:43-51`) — the Rust analogue of `PG_MODULE_MAGIC`
  `[verified-by-code]`. It also calls `register_panic_handler()` *inside*
  `Pg_magic_func` (`lib.rs:55`), with an author "TODO: is this a good idea here?"
  (`lib.rs:53`) — a telling uncertainty about lifecycle `[from-comment]`. There is
  no `_PG_init` hook surface (cf. wasmer-postgres.md, which notes the same gap).
- **The extern-fn macro.** `#[pg_extern]` (`pg-extern-attr/src/lib.rs:485`) keeps
  the original fn and appends two items via `impl_info_for_fn` (`:291`): (1) the
  V1 info function `pg_finfo_pg_<name>()` returning `Pg_finfo_record { api_version:
  1 }` (`get_info_fn`, `:278-289`) — a direct port of the C `PG_FUNCTION_INFO_V1`
  macro, whose expansion the doc-comment reproduces (`:439-449`); (2) the wrapper
  `pub extern "C" fn pg_<name>(func_call_info: FunctionCallInfo) -> Datum`
  (`:330`) `[verified-by-code]`.
- **fmgr call glue + Datum marshalling.** `get_args` (`lib.rs:69-100`) yields
  `Option<Datum>` per arg, handling the PG12 `NullableDatum` array vs the older
  split `arg[]`/`argnull[]` layout behind `cfg(postgres12)` (`lib.rs:74-99`)
  `[verified-by-code]`. The macro then converts each Datum through
  `TryFromPgDatum::try_from(&memory_context, PgDatum::from_option(...))`
  (`attr:106-115`), calls the user fn, and wraps the result in `PgDatum::from`
  (`attr:353-356`). It even generates the `CREATE OR REPLACE FUNCTION … LANGUAGE
  C` DDL at runtime (`attr:407-410`) plus a `STRICT` clause inferred from whether
  args are `Option<_>` (`sql_function_options`, `attr:191-221`), emitted by a
  `<name>_pg_create_stmt()` helper and the `pg_create_stmt_bin!` macro
  (`lib.rs:263`) — there is no `.control`/`CREATE EXTENSION` packaging, just raw
  `LANGUAGE C` functions `[verified-by-code]`.

## Where it diverges from core idioms and from pgrx

**The panic/longjmp boundary (the centerpiece).** PG `elog(ERROR)` does a
`siglongjmp` off `PG_exception_stack`; letting that jump through live Rust frames
skips destructors and is UB. pg-extend-rs's answer is `guard_pg`
(`lib.rs:163-197` unix, `:207-239` windows): it saves `PG_exception_stack`,
installs a local `sigsetjmp` restore point (`lib.rs:170`), and on a caught jump
translates it into a Rust `panic!(JumpContext { jump_value })` (`lib.rs:183`). A
global panic hook installed by `register_panic_handler` (`lib.rs:108-137`) then
inspects the payload: a `JumpContext` means "a PG longjmp in flight" and it
re-issues the `siglongjmp` (`lib.rs:124-129`); any other panic is routed to
`error!` (`lib.rs:132`), which itself triggers PG's `elog(ERROR)` longjmp. The
`#[pg_extern]` wrapper additionally wraps the whole call in
`std::panic::catch_unwind` (`attr:344-357`) and, on `Err`, downcasts the payload
and calls `error!` to hand control back to PG (`attr:371-393`).

This is conceptually pgrx's `pg_guard_ffi_boundary` — the same `sigsetjmp`
save/restore of `PG_exception_stack` (pgrx.md:65-76) — but with two decisive
differences:

1. **Opt-in vs universal.** pgrx wraps **every** bindgen-generated `extern
   "C-unwind"` symbol with `#[pg_guard]` automatically (pgrx.md:65-76,155-156).
   pg-extend-rs's `guard_pg` is `pub(crate)` and applied *by convention* — the
   `pg_sys` module doc itself only says calls "should **generally** be wrapped in
   `pg_extend::guard_pg`" (`pg_sys.rs:28`) `[from-comment]`. Nothing enforces it;
   the datum-conversion and user-code paths call `pg_sys` functions directly,
   unguarded. That gap — a longjmp from an unguarded C call unwinding through Rust
   — is exactly the soundness hole pgrx closed by making the guard total.
2. **Unwinding ABI.** pg-extend-rs relies on `catch_unwind` across `extern "C"`
   and `panic!(JumpContext{…})` payload syntax (`lib.rs:183`) — both from a Rust
   era before the `C-unwind` ABI; unwinding across a plain `extern "C"` frame was
   UB then. pgrx uses `extern "C-unwind"` throughout (pgrx.md:65-72). The old
   `panic!(struct)` form no longer even compiles on modern Rust — a concrete
   abandonment marker `[verified-by-code]`.

**Bindings.** pg-extend-rs runs **bindgen at build time**: `build.rs` shells
`pg_config --includedir-server`, whitelists `pg.*`/log-level vars, and writes
`$OUT_DIR/postgres.rs` (`build.rs` `get_bindings`/`generate`/`write_to_file`),
which `pg_sys.rs:30` pulls in via `include!(concat!(env!("OUT_DIR"),
"/postgres.rs"))` `[verified-by-code]`. So every build needs bindgen + clang + PG
headers present, and the ABI is re-derived each time. pgrx instead **commits
per-major-version bindgen output** (`pg13.rs`..`pg18.rs`, pgrx.md:45,152) — more
robust, reproducible, and offline-buildable. build.rs also parses
`pg_majorversion.h` with libclang to emit a `postgres{9,10,11,12}` cfg
(`build.rs` `get_postgres_feature_version`) `[verified-by-code]`.

**Memory.** `PgAllocator` wraps a `MemoryContextData` pointer (`pg_alloc.rs:21`),
projects `CurrentMemoryContext` (`:30-32`), and offers `exec`/`exec_with_guard`
to switch context (`:36-66`). Frees go through the context's `methods.free_p`
under `guard_pg` (`:68-76`). RAII is via `PgAllocated<'mc,T>` whose `Drop` frees
back to the owning context (`:82-88,154`). Notably there is **no Rust
`#[global_allocator]`** override — despite the README's "allocator that uses
palloc and pfree" aspiration, it is a MemoryContext *projection*, not a global
allocator; ordinary Rust heap allocs still hit the system allocator
`[verified-by-code]`.

## Notable design decisions

- **PG-version portability via `cfg` inside one crate** — `NullableDatum` vs
  `arg[]/argnull[]` split (`lib.rs:74-99`) and per-OS `sigsetjmp`/`siglongjmp`
  selection (`lib.rs:139-153`; linux hand-declares `__sigsetjmp`,
  `pg_sys.rs:36-39`) `[verified-by-code]`.
- **`PgDatum::is_null` documented as panic-forbidden** at the FFI boundary
  ("if it panics it will cause the full Postgres DB to restart", `pg_datum.rs:53`)
  — awareness of the boundary hazard, handled ad hoc rather than structurally
  `[from-comment]`.
- **`pg_error` module already self-deprecated** in favor of `log` macros
  (`pg_error.rs:9,27,68`); `log.rs` reimplements `trace!`..`fatal!` wrapping
  `errstart`/`errfinish` under `guard_pg` (`log.rs:224,237`) `[verified-by-code]`.
- **A `Bool` conversion type** to paper over bindgen rendering C `bool` as `u8`
  (linux) vs `i8`/`char` elsewhere (`pg_bool.rs:44-58`) `[verified-by-code]`.
- **FDW support via `#[pg_foreignwrapper]`** (`attr:504-518`) — but the workspace
  disables FDW examples: "FDW support broken with PostgreSQL 11+" (workspace
  `Cargo.toml`, issue #49) `[from-comment]`.
- **Link hack over PGXS** — no PGXS/meson; the README requires `.cargo/config`
  with `-C link-arg=-undefined dynamic_lookup` so unresolved PG symbols bind at
  `.so` load (`README`) `[from-README]`.

## Why abandoned & the lineage

README enumerates many unfinished goals as *tbd* (all-Datum support, table
returns, `log` integration, psql-script generators) `[from-README]`; the crate is
0.2.1, ceilings at PG12, FDW broke on PG11+ (issue #49), and the panic path uses
since-removed Rust syntax (`lib.rs:183`) `[verified-by-code]`. The decisive
technical shortfall vs the successor is that `guard_pg` was opt-in and rode a
pre-`C-unwind` unwinding model, so longjmp-through-Rust safety was never total.
**Lineage: pg-extend-rs → (superseded by) pgrx**, which made the `sigsetjmp`
barrier universal and vendored per-version bindings; **`wasmer-postgres` is a
downstream consumer** still pinned to pg-extend-rs's git `master`
(wasmer-postgres.md:29-30,168) `[verified-by-code]`.

## Links into corpus

- `[[pgrx]]` — the successor; the `pg_guard_ffi_boundary` / committed-bindgen
  contrast is the spine of this doc.
- `[[wasmer-postgres]]` — downstream consumer built on pg-extend-rs.
- `[[pgzx]]` — the Zig-language analogue of the same "bridge Rust/Zig ↔ C
  extension ABI" problem.

## Sources

- `https://raw.githubusercontent.com/bluejekyll/pg-extend-rs/master/README.md` → 200
- `.../pg-extend/src/lib.rs` → 200
- `.../pg-extend/src/pg_sys.rs` → 200
- `.../pg-extend/src/pg_datum.rs` → 200
- `.../pg-extend/src/pg_type.rs` → 200 (not deep-read)
- `.../pg-extend/src/pg_error.rs` → 200
- `.../pg-extend/src/pg_bool.rs` → 200
- `.../pg-extend/src/pg_alloc.rs` → 200
- `.../pg-extend/src/log.rs` → 200
- `.../pg-extend/build.rs` → 200
- `.../pg-extend/Cargo.toml` → 200
- `.../Cargo.toml` (workspace) → 200
- `.../pg-extern-attr/src/lib.rs` → 200
- `.../pg-extend/src/panic.rs` → 404 (no such file; panic logic in lib.rs)
- `.../pg-extend/src/native.rs` → 404
- GitHub git-tree API → blocked/403 through proxy (layout from README + Cargo.toml)
