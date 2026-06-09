# Wrappers (supabase/wrappers) — the FDW C API repackaged as a safe Rust framework, plus WebAssembly FDWs loaded at runtime

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `supabase/wrappers` @ branch `main`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Cites verified against the files
> fetched on 2026-06-08 (see Sources footer). Three trees matter:
> `supabase-wrappers/` (the framework crate / `ForeignDataWrapper` trait),
> `wrappers/` (the pgrx extension bundling ~18 native FDWs + the WASM host), and
> `wasm-wrappers/` (the ecosystem of guest WASM FDWs, out of scope here).

## Domain & purpose

Wrappers is "a development framework for Postgres Foreign Data Wrappers (FDW),
written in Rust ... [whose] goal is to make Postgres FDW development easier" and
"also a collection of FDWs built by Supabase" (`README.md:1-5`) `[from-README]`.
It ships one PostgreSQL extension (`wrappers`) that contains FDWs for Stripe,
BigQuery, ClickHouse, MongoDB, Redis, S3, Firebase, DuckDB, Iceberg, and ~10
more (`README.md:8-44`), plus a generic `wasm_fdw` that runs *third-party*
WebAssembly FDWs. Two ideologies sit on top of each other: (1) **the FDW C
callback API re-expressed as a high-level safe-Rust trait** so authors never
touch `FdwRoutine`, and (2) **a WebAssembly host that loads untrusted FDW code
into the backend at `CREATE SERVER` time**. It is the framework-shaped sibling
of the single-purpose `[[knowledge/ideologies/cstore_fdw]]` (FDW-as-storage): a
framework for many FDWs rather than one FDW.

## How it hooks into PG

The extension is built with **pgrx** (the Rust/PG framework). The control file
sets `relocatable = true`, `superuser = false`, and notably comments out
`module_pathname` to opt into pgrx "versioned shared-object mode"
(`wrappers/wrappers.control:1-6`) `[verified-by-code]`. There is no SQL-level
`CREATE FOREIGN DATA WRAPPER ... HANDLER` boilerplate written by hand — the
`#[wrappers_fdw(...)]` proc-macro on a struct generates the C `FdwRoutine`
handler and the `pg_extern` SQL bindings. The doc-comment shows the contract:
the macro turns a struct + a `ForeignDataWrapper` impl into a `handler
hello_world_fdw_handler` referenced by `CREATE FOREIGN DATA WRAPPER`
(`supabase-wrappers/src/lib.rs:68-295`, esp. `:239`) `[verified-by-code]`.
`FdwRoutine` itself is a `PgBox<pg_sys::FdwRoutine>`
(`supabase-wrappers/src/lib.rs:334-335`).

The core abstraction is the `ForeignDataWrapper<E>` trait
(`supabase-wrappers/src/interface.rs:866`) whose methods map **one-to-one** onto
the PG FDW callbacks documented at fdw-callbacks.html (the trait's own
doc-comments link there): `new` (server options), `get_rel_size`, `begin_scan`
(receiving pushed-down `quals` / `columns` / `sorts` / `limit`), `iter_scan`
(fill a `Row` or return `None`), `re_scan`, `end_scan`, `begin_modify` /
`insert` / `update` / `delete`, `import_foreign_schema`, and `validator`
(`interface.rs:866-1000+`) `[verified-by-code]`. Cross-ref
`[[knowledge/subsystems/foreign]]` (PG's FDW machinery), the
`access-method-apis` skill (the sibling pluggable-API surface), and
`[[knowledge/idioms/fmgr]]` (the `pg_extern`/handler plumbing pgrx
generates).

## Where it diverges from core idioms

### 1. The FDW C callback API is hidden behind a typed Rust trait, with a `Cell`/`Row` value model instead of `Datum`/`TupleTableSlot`

A core FDW author writes a `FdwRoutine` of C function pointers operating on
`TupleTableSlot`, `Datum`, and `Oid`. Wrappers replaces all of it with a trait
whose scan loop is `fn iter_scan(&mut self, row: &mut Row) -> Result<Option<()>,
E>` (`interface.rs:`, trait body) `[verified-by-code]`, where a `Row` is a list
of `Cell`s — a Rust enum over `Bool`, `I16/I32/I64`, `F32/F64`, `Numeric`,
`String`, `Date`, `Timestamp`, `Timestamptz`, `Json(JsonB)`, `Bytea`, `Uuid`,
and array variants (`interface.rs:38-128`) `[verified-by-code]`. The framework
owns the `Cell ↔ Datum` marshalling so each FDW deals only in safe Rust values.
This is a deliberate safe abstraction *over* — not a replacement of — the C API;
the README stresses it provides "higher level interfaces, without hiding
lower-level C APIs" (`README.md:50`). Cross-ref
`[[knowledge/data-structures/heap-tuple-layout]]` (the `Datum`/slot model it
wraps), `[[knowledge/idioms/memory-contexts]]` (it ships its own `memctx`
module, `lib.rs:316`, to bridge Rust ownership and PG memory contexts).

### 2. Qual/sort/limit pushdown is a framework service, not per-FDW plumbing

Core FDWs each re-derive which `WHERE`/`ORDER BY`/`LIMIT` clauses are safe to
push down. Wrappers parses these in the framework and hands `begin_scan` ready
`quals: &[Qual]`, `sorts: &[Sort]`, and `limit: Option<Limit>`
(`interface.rs` trait `begin_scan`, plus the dedicated `qual.rs` / `sort.rs` /
`limit.rs` / `upper.rs` modules in the crate) `[verified-by-code]`. "`WHERE`,
`ORDER BY`, `LIMIT` pushdown are supported" out of the box (`README.md:51`)
`[from-README]`. Centralizing pushdown extraction so every FDW author gets it
free is a framework inversion of the normal per-wrapper responsibility.
Cross-ref `[[knowledge/subsystems/optimizer]]`, `[[knowledge/architecture/planner]]`.

### 3. `wasm_fdw` loads untrusted WebAssembly FDWs into the backend at `CREATE SERVER` time

This is the load-bearing divergence and has no core analogue. The generic
`WasmFdw` FDW reads three required server options — `fdw_package_url`,
`fdw_package_name`, `fdw_package_version` — plus an optional
`fdw_package_checksum`, then in `new()` builds a wasmtime `Engine` with
`wasm_component_model(true)`, **downloads** the component, instantiates it, and
links host functions (`wrappers/src/fdw/wasm_fdw/wasm_fdw.rs:433-470`)
`[verified-by-code]`. So `CREATE SERVER ... OPTIONS (fdw_package_url '...',
...)` causes a Postgres backend to fetch and run arbitrary third-party code.
The download path supports `file://` (local), `warg://`/`wargs://` (a warg
package registry, rewritten to `http(s)://` and fetched via `warg_client`), and
plain `http(s)://` URLs (`wasm_fdw.rs:55-148`) `[verified-by-code]`. The guest
FDW implements the same scan/modify lifecycle, called across the Component Model
boundary: `call_init`, `call_begin_scan`, `call_iter_scan`, `call_end_scan`,
`call_begin_modify`, etc., each dispatched against a `Bindings::V1`/`V2` ABI
(`wasm_fdw.rs:219-324`) `[verified-by-code]`. Dynamically pulling remote code
into the per-connection backend is something core never does — extensions are
vetted `.so`s on disk; here the "extension logic" is a versioned WASM artifact
named in DDL. Cross-ref `[[knowledge/subsystems/foreign]]`,
the `extension-development` skill, and the `gucs-bgworker-parallel`
skill (the parallel/loading boundaries a remote-loaded FDW must respect).

### 4. Remote WASM downloads are SHA-256-pinned; `file://` is exempt

Because the WASM is fetched at runtime, integrity is enforced in code: remote
downloads require a checksum — "package checksum must be specified for remote
downloads" — and after fetching, the bytes are hashed and compared:
`hex::encode(Sha256::digest(&bytes)) != expected_checksum` errors out
(`wasm_fdw.rs:137-191`) `[verified-by-code]`. The `validator` enforces this at
DDL time too: it requires `fdw_package_url/name/version`, and requires
`fdw_package_checksum` *unless* the URL is `file://`
(`wasm_fdw.rs:551-561`) `[verified-by-code]`. There is also a host/guest ABI
**version handshake**: the guest declares a required host version
(`call_host_version_requirement`) which the host checks with semver
`VersionReq` before calling `init` (`wasm_fdw.rs:36-44`, `:468-469`)
`[verified-by-code]`. Building a supply-chain integrity + ABI-compat gate
inside an FDW is a posture core's static-`.so` model never needs. Cross-ref
`[[knowledge/idioms/error-handling]]` (the `ErrorReport`/`ERRCODE_FDW_ERROR`
mapping, `wasm_fdw/mod.rs:`).

### 5. Host functions expose a controlled syscall surface (HTTP, JWT, time, stats) to guest WASM

A WASM component is sandboxed and cannot make network calls on its own, so the
host (`FdwHost`) implements a capability set the guest can call: `http`, `jwt`,
`time`, `stats`, `utils` modules are linked in
(`wrappers/src/fdw/wasm_fdw/host/mod.rs:1-5`, with `HostRow`/`HostColumn`/
`HostQual`/`HostSort`/`HostLimit`/`HostOptions`/`HostContext` resource impls,
`:64-200+`) `[verified-by-code]`. The guest sees `Qual`/`Sort`/`Row`/`Column`
as Component-Model `Resource` handles whose methods trampoline back into Rust.
Hand-designing the exact syscall surface a foreign FDW is allowed (notably an
HTTP client, since most guest FDWs are REST wrappers) is a userspace
capability-security model layered onto the backend. Cross-ref
`[[knowledge/idioms/locking-overview]]` and `[[knowledge/subsystems/storage-buffer]]`
(shared state the host deliberately does *not* expose to the guest).

### 6. Built on pgrx, so the entire extension is Rust with a generated SQL surface

Like `[[knowledge/ideologies/zombodb]]`, Wrappers is a pgrx extension: cites
land in `.rs`, `PG_MODULE_MAGIC`/`_PG_init`/`pg_extern` are macro-generated, and
the install SQL is emitted by `cargo pgrx` rather than hand-written
(`README.md:55-66`) `[from-README]`. The `polyfill` module (`lib.rs:318`)
backfills FDW C symbols across PG major versions so one Rust codebase targets
many servers. Cross-ref `[[knowledge/ideologies/zombodb]]`,
`[[knowledge/ideologies/pg_duckdb]]` (the other Rust/C++ pgrx-adjacent
extensions).

## Notable design decisions (cited)

- **`module_pathname` is intentionally commented out** to select pgrx
  "versioned shared-object mode" (`wrappers.control:3-4`) `[verified-by-code]`
  — each build links a version-suffixed `.so`, easing in-place upgrades. A
  deliberate inversion of the usual `module_pathname = '$libdir/<ext>'`.
- **`superuser = false`, `relocatable = true`** (`wrappers.control:5-6`) — the
  extension installs without superuser; the privilege boundary is the FDW server
  options / `validator`, not install-time superuser-gating.
- **Two WASM ABI versions coexist** (`Bindings::V1` / `Bindings::V2`,
  `wasm_fdw.rs:215-216`, instantiate-or-fallback at `:460-466`)
  `[verified-by-code]` — the host tries V1 then V2, so older and newer guest
  components both load against one host.
- **A `Cell` carries `unsafe impl Send`** (`interface.rs:81`) and a hand-written
  `Clone` (`interface.rs:83-128`) `[verified-by-code]` — the value model is
  tuned to cross the Rust/C and Rust/WASM boundaries, including async backends
  (`README.md:48` "Support both sync and async backends").
- **`get_rel_size` lets each FDW feed row-count/row-width estimates to the
  planner** (`interface.rs`, `get_rel_size` doc) `[verified-by-code]` — the
  framework surfaces the cost-estimation seam rather than hiding it, matching
  core's `GetForeignRelSize`.

## Links into corpus

- `[[knowledge/subsystems/foreign]]` + `access-method-apis` skill — the FDW
  callback surface Wrappers re-expresses as a Rust trait; the single most
  important cross-reference.
- the `extension-development` skill — pgrx-generated control/SQL/
  handler; `module_pathname`-commented versioned-`.so` mode; `superuser=false`.
- `[[knowledge/subsystems/optimizer]]` + `[[knowledge/architecture/planner]]` —
  qual/sort/limit pushdown delivered to `begin_scan` as a framework service.
- `[[knowledge/data-structures/heap-tuple-layout]]` + `[[knowledge/idioms/memory-contexts]]`
  — the `Cell`/`Row` value model and `memctx` bridge over `Datum`/slots.
- `[[knowledge/idioms/error-handling]]` — guest errors mapped to
  `ERRCODE_FDW_ERROR` via `ErrorReport`.
- `[[knowledge/ideologies/cstore_fdw]]` — single-purpose FDW (FDW-as-storage);
  Wrappers is the framework-for-many-FDWs counterpart. Both bend the same
  `foreign-data` API.
- `[[knowledge/ideologies/zombodb]]` + `[[knowledge/ideologies/pg_duckdb]]` —
  fellow Rust/pgrx-built extensions; useful for the macro-generated-SQL pattern.
- `.claude/skills/extension-development/SKILL.md` — control-file fields,
  handler registration, the static-`.so` model that `wasm_fdw` deliberately
  breaks by loading remote code at runtime.

## Sources

Fetched 2026-06-08 (branch `main`):

- `https://api.github.com/repos/supabase/wrappers/git/trees/main?recursive=1`
  @ 2026-06-08 → HTTP 200 (tree listing; manifest path `wrappers/src/lib.rs`
  corrected — the framework crate is `supabase-wrappers/`, the pgrx extension is
  `wrappers/`, and there is a separate `wasm-wrappers/` guest ecosystem).
- `https://raw.githubusercontent.com/supabase/wrappers/main/README.md`
  @ 2026-06-08 → HTTP 200 (79 lines).
- `https://raw.githubusercontent.com/supabase/wrappers/main/wrappers/wrappers.control`
  @ 2026-06-08 → HTTP 200 (6 lines).
- `https://raw.githubusercontent.com/supabase/wrappers/main/supabase-wrappers/src/interface.rs`
  @ 2026-06-08 → HTTP 200 (1521 lines; `Cell`/`Row`/`ForeignDataWrapper` trait).
- `https://raw.githubusercontent.com/supabase/wrappers/main/supabase-wrappers/src/lib.rs`
  @ 2026-06-08 → HTTP 200 (337 lines; `wrappers_fdw` macro doc, `FdwRoutine`).
- `https://raw.githubusercontent.com/supabase/wrappers/main/wrappers/src/fdw/wasm_fdw/wasm_fdw.rs`
  @ 2026-06-08 → HTTP 200 (568 lines; download + instantiate + call_* dispatch).
- `https://raw.githubusercontent.com/supabase/wrappers/main/wrappers/src/fdw/wasm_fdw/mod.rs`
  @ 2026-06-08 → HTTP 200 (60 lines; `WasmFdwError` → `ERRCODE_FDW_ERROR`).
- `https://raw.githubusercontent.com/supabase/wrappers/main/wrappers/src/fdw/wasm_fdw/host/mod.rs`
  @ 2026-06-08 → HTTP 200 (631 lines; `FdwHost` resource impls + host modules).

All cites are `[verified-by-code]` against the fetched `.rs`/`.control`
(`ForeignDataWrapper` trait shape, `Cell`/`Row` value model, `wrappers_fdw`
macro contract, WASM download/checksum/version-handshake, host-function
linking) except the "development framework" framing and the FDW catalogue,
which are `[from-README]`. The native per-source FDWs (`stripe_fdw`,
`bigquery_fdw`, …), the `supabase-wrappers-macros` proc-macro internals, the
`scan.rs`/`modify.rs`/`qual.rs` framework module bodies, and the
`wasm-wrappers/` guest FDWs were not deep-read.
