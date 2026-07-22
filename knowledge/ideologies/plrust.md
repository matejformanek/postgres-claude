# plrust — a *trusted* PL that compiles the user's Rust to native machine code at `CREATE FUNCTION` time, then locks the artifact in `pg_proc.prosrc`

- **Repo**: `pgcentralfoundation/plrust` (historically `tcdi/plrust`), branch `main`.
  License **"The PostgreSQL License"** (`Cargo.toml:6` declares `license = "PostgreSQL Open Source License"`; README §License `[from-README]`). Author org: **Technology Concepts & Design, Inc. (TCDI)** / PostgreSQL Global Development — copyright headers read `Portions Copyright 2021-2025 Technology Concepts & Design, Inc.` (e.g. `plrust/src/lib.rs:3`), `authors = ["TCDI"]` (`Cargo.toml:4`). Crate `plrust` v1.2.8.
- **Fetched** (raw.githubusercontent.com, all HTTP 200):
  - `README.md` (~169 lines)
  - `plrust/src/lib.rs` (~302) — handlers, `_PG_init`, default lints
  - `plrust/src/user_crate/mod.rs` (~646) — the typestate FSM
  - `plrust/src/user_crate/build.rs` (~202) — cargo/plrustc invocation
  - `plrust/src/user_crate/verify.rs` (~126) — safe/unsafe split rationale
  - `plrust/src/user_crate/validate.rs` (~66) — required-lint gate
  - `plrust/src/user_crate/crating.rs` (~641) — lib.rs + Cargo.toml codegen
  - `plrust/src/user_crate/cargo.rs` (~166) — `RUSTC=plrustc`, env sanitizing
  - `plrust/src/user_crate/loading.rs` (~69) & `ready.rs` (~155) — memfd/dlopen
  - `plrust/src/user_crate/lint.rs` (~147) — lint sets
  - `plrust/src/gucs.rs` (~211), `plrust/src/plrust.rs` (~170), `plrust/src/pgproc.rs` (~227), `plrust/src/prosrc.rs` (~250), `plrust/src/error.rs` (~40), `plrust/Cargo.toml` (~72)
  - `plrust-trusted-pgrx/{README.md,Cargo.toml}`

## Domain & purpose

PL/Rust is a **loadable procedural language** whose function bodies are the Rust programming language, but unlike every other PL in this corpus it does **not interpret or JIT** them — it compiles each function to a native `.so` and `dlopen`s it (`README.md:5` `[from-README]`). Contrast the interpreted/VM PLs: [[knowledge/ideologies/plv8]] embeds V8 and runs JS in a VM, [[knowledge/ideologies/pljava]] runs bytecode on a JVM, [[knowledge/ideologies/plr]] shells into an embedded R interpreter, [[knowledge/ideologies/plsh]] execs a shell. Those are "safe" only because the VM/interpreter mediates every operation. PL/Rust has **no interpreter between the user code and the CPU**, so it must manufacture safety at compile time (a hardened compiler + forbidden lints) and at the standard-library boundary (a syscall-blocking `std` fork). On `x86_64`/`aarch64` Linux (and macOS) it can be a genuine `CREATE TRUSTED LANGUAGE`; elsewhere it degrades to untrusted (`README.md:14`, `plrust/src/lib.rs:13-26` `[verified-by-code]`).

## How it hooks into PG

- **Built on pgrx.** plrust is itself a pgrx extension, and *each user function is itself a mini-pgrx extension* (`README.md:41-43` `[from-README]`; `pgrx = "=0.11.0"` at `Cargo.toml:43`). See [[knowledge/ideologies/pgrx]] — its build substrate.
- **The language-handler trio**, all declared with pgrx `#[pg_extern]`:
  - `plrust_call_handler(fcinfo) -> Datum` — the `language_handler`, hand-written SQL because pgrx can't emit a `CREATE FUNCTION` whose sole arg is `FunctionCallInfo` (`plrust/src/lib.rs:169-199`). It pulls `flinfo.fn_oid` and calls `plrust::evaluate_function(fn_oid, fcinfo)` (`plrust/src/lib.rs:180-189`) `[verified-by-code]`.
  - `plrust_validator(fn_oid, fcinfo)` — gate-keeps via `pg_sys::CheckFunctionValidatorAccess`, then **unloads any prior version and compiles the function immediately**, deliberately ignoring `check_function_bodies` for *compilation* (only using it to decide whether to eagerly load) — "we need to compile the function when it's created to avoid locking during function execution" (`plrust/src/lib.rs:226-262`) `[verified-by-code]`.
  - inline handler: not present — plrust has no anonymous `DO` block handler; only handler + validator are wired.
- **`CREATE [TRUSTED] LANGUAGE plrust`** is emitted by `extension_sql!` at build time, choosing the `TRUSTED` variant under `#[cfg(feature = "trusted")]` and the bare `CREATE LANGUAGE` + a `RAISE WARNING 'plrust is **NOT** ... trusted'` otherwise (`plrust/src/lib.rs:272-302`) `[verified-by-code]`. Routing: `CREATE FUNCTION ... LANGUAGE plrust` sets `pg_proc.prolang` to this language, so fmgr dispatches every call through `plrust_call_handler` (standard PG PL routing; see [[knowledge/idioms/fmgr]]).
- **`_PG_init`** hard-requires `shared_preload_libraries` (errors with `ERRCODE_OBJECT_NOT_IN_PREREQUISITE_STATE` if `process_shared_preload_libraries_in_progress` is false), installs a color-eyre panic hook, then `gucs::init()`, `hooks::init()`, a tracing subscriber, and `plrust::init()` (`plrust/src/lib.rs:118-165`) `[verified-by-code]`.
- A bootstrap `extension_sql!` refuses any non-UTF8 database (`plrust/src/lib.rs:66-78`) `[verified-by-code]`.

## Where it diverges from core idioms — compile native code at `CREATE FUNCTION`, and make it trusted

This is the load-bearing story. Core PG PLs store text and interpret it per-call; plrust turns `CREATE FUNCTION` into `rustc`.

**(1) Per-function crate → `plrustc` → per-function `.so` → dlopen.** Compilation is a linear **typestate finite-state machine** `UserCrate<P>`: `FnCrating → FnVerify → FnBuild → FnLoad → FnValidate → FnReady`, with Rust ownership guaranteeing one-way, one-shot consumption of each stage (`plrust/src/user_crate/mod.rs:53-67`, stage impls at `:83-223`) `[verified-by-code]`. `compile_function` (`plrust/src/plrust.rs:100-137`) provisions a real Cargo crate under `plrust.work_dir`, writing a generated `src/lib.rs` and `Cargo.toml` to disk (`crating.rs:182-211`), then runs `cargo rustc --release --target <triple>` (`build.rs:105-114`). The compiler is **not** stock rustc: `cargo.rs:80-83` sets `RUSTC=plrustc`, plrust's own hardened rustc driver that runs the extra `plrust_*` lint passes; `build.rs:192-199` further constrains it via `PLRUSTC_USER_CRATE_NAME` and `PLRUSTC_USER_CRATE_ALLOWED_SOURCE_PATHS` (only the crate dir + target dir are readable source paths). The resulting `lib<crate>.so` bytes are read back into memory (`build.rs:116-127`) `[verified-by-code]`. Loading avoids a stable on-disk path entirely: on Linux the bytes are written to an **anonymous `memfd`**, sealed shrink/grow/seal, and `dlopen`ed through `/proc/self/fd/<fd>` so the file "won't be overwritten between when we finish writing it and when it is dlopen'd" (`ready.rs:50-90`); other platforms use a `tempfile` deleted right after load (`ready.rs:92-108`) `[verified-by-code]`. The symbol fetched is `plrust_fn_oid_<db>_<fn>_wrapper` (`ready.rs:110-116`, name built in `plrust.rs:145-147`) `[verified-by-code]`.

**(2) The `postgrestd` sandbox.** Trust hinges on a forked Rust standard library. `plrust/src/lib.rs:28-38`: the `trusted` cargo feature sets `const TRUSTED = true`, "which will cause plrust user functions to be compiled with `postgrestd`" — a std fork that blocks filesystem/network/process syscalls so compiled code can't escape (`README.md:50` references installing `postgrestd`; the platform guard `plrust/src/lib.rs:13-26` restricts trusted mode to Linux/macOS x86_64/aarch64) `[from-README]`/`[inferred]`. The submodule/build wiring for postgrestd lives outside the fetched files, so the syscall-blocking mechanism itself is `[inferred]`. Belt-and-suspenders: user deps are pinned to **`plrust-trusted-pgrx`**, a deliberately minimal re-export of pgrx exposing only "trusted" surface — data types, logging, SPI, triggers — explicitly *not* for general use (`plrust-trusted-pgrx/README.md`; `crating.rs:252` writes `pgrx = { version = <ver>, package = "plrust-trusted-pgrx" }`) `[verified-by-code]`.

**(3) Trusted vs untrusted mode** is a compile-time cargo feature of *plrust itself*, not a naming convention. plrust rejects the `plperl`/`plperlu` two-name idiom: Postgres decides trust solely from `CREATE TRUSTED LANGUAGE`, not the name (`README.md:147-149`) `[from-README]`. Consequently trusted and untrusted are **distinct compilation targets** and a function compiled under one will refuse to load under the other even on identical hardware; you cannot install both on one cluster (`README.md:154-158`) `[from-README]`.

**(4) How the artifact is stored, keyed, and re-validated.** Divergent from every text-based PL: plrust overwrites `pg_proc.prosrc` with a **JSON `ProSrcEntry`** carrying the original `src`, the `trusted_pgrx_version`, a `capabilities` set, and a `lib` map from `CompilationTarget` (e.g. `x86_64`, `aarch64`) → a `SharedLibrary` of gzip-then-URL-safe-base64-encoded `.so` bytes plus the `LintSet` it was built with (`prosrc.rs:37-99`) `[verified-by-code]`. It writes this by hand-rolling a `heap_copytuple` → `set_by_name("prosrc", …)` → `CatalogTupleUpdate` + `CommandCounterIncrement` in the validator path (`prosrc.rs:188-217`) `[verified-by-code]`. Because the source, deps, and GUC state fully determine the build, a `pg_restore` that hands back the JSON is transparently recompiled: `extract_source_and_capabilities_from_json` peels out just `"src"` and ignores the stored binaries (`prosrc.rs:145-156`, `mod.rs:308-358`) `[verified-by-code]`. **Re-validation on every load** is enforced two ways: (a) `FnValidate::new` refuses to load a `.so` whose recorded `LintSet` is missing any currently `required_lints()`, erroring `MissingLints` (`validate.rs:34-51`, `error.rs:38-39`) `[verified-by-code]`; (b) a **generation number** = `(xmin << 32) | cmin` of the `pg_proc` tuple (`pgproc.rs:120-123`) is compared on each call, and a concurrent `CREATE OR REPLACE`/`ALTER FUNCTION` triggers an in-place `dlclose`+reload (`plrust.rs:44-98`) `[verified-by-code]`.

**(5) fmgr / memory-context conventions.** plrust does not re-implement fmgr or memory contexts — pgrx re-imposes them. Each user `.so` is a pgrx extension whose `#[pg_extern]` macro emits the `#[no_mangle] unsafe extern "C" fn ..._wrapper` that speaks the fmgr V1 ABI; the call crosses `pg_guard_ffi_boundary` so Rust panics and PG `ereport` longjmps are marshalled correctly (`ready.rs:118-125`) `[verified-by-code]` — see [[knowledge/idioms/fmgr]]. plrust reads catalog config through PG's own memory contexts (`cargo.rs:136-165` switches into a fresh `PgMemoryContexts::new("configdata")` to call `get_configdata` and free it wholesale) — see [[knowledge/idioms/memory-contexts]]. The subtle divergence `verify.rs` documents: pgrx-generated wrapper code is *itself* `unsafe`, so plrust can't just point rustc's `unsafe` detector at the whole crate. It emits the function **twice** — a `pub mod opened` with the `#[pg_extern]` wrapper (the real, callable one) and a lint-only `mod forbidden` holding the bare fn under `#![forbid(unsafe_code)]` + the full lint set, which "really, truly, will not run" but forces rustc to typecheck the user body under maximum lints (`verify.rs:9-25`, `crating.rs:139-142`, `crating.rs:285-320`) `[verified-by-code]`.

## Notable design decisions

- **Default forbidden-lint list** is a null-terminated `&CStr` baked into the binary (`plrust/src/lib.rs:91-116`): `plrust_extern_blocks`, `plrust_lifetime_parameterized_traits`, `implied_bounds_entailment`, `plrust_autotrait_impls`, `plrust_closure_trait_impl`, `plrust_static_impls`, `plrust_fn_pointers`, `plrust_filesystem_macros`, `plrust_env_macros`, `plrust_async`, `plrust_leaky`, `plrust_external_mod`, `plrust_print_macros`, `plrust_stdio`, `plrust_suspicious_trait_object`, `unsafe_code`, `deprecated`, `suspicious_auto_trait_impls`, `where_clauses_object_safety`, `soft_unstable`. A code comment warns that removing `#![forbid(unsafe_code)]` is only for a fully-untrusted rebuild `[verified-by-code]`.
- **Two lint GUCs, split by trust role**: `plrust.compile_lints` (applied at build; defaults to `DEFAULT_LINTS`) and `plrust.required_lints` (checked at *load*; a `.so` missing any required lint is refused) — plus a `PLRUST_REQUIRED_LINTS` **env var** that the root user can set to override the DBA who only controls `postgresql.conf`; the two are unioned (`lint.rs:98-147`, `gucs.rs:95-111`) `[verified-by-code]`.
- **GUCs** (`gucs.rs:49-121`) `[verified-by-code]`: `plrust.work_dir` (Sighup; where crates are built — `work_dir()` panics if unset, `:123-132`), `plrust.PATH_override`, `plrust.tracing_level`, `plrust.allowed_dependencies` (path to a TOML crate allow-list), `plrust.compilation_targets` (**Postmaster** context; comma-sep `x86_64,aarch64` for cross-compile), `plrust.compile_lints`, `plrust.required_lints`, `plrust.trusted_pgrx_version` (defaults to the `plrust-trusted-pgrx` version captured from `build.rs` via `env!`, and is always pinned as `=<ver>` at `gucs.rs:202-211`). Per-target dynamic GUCs `plrust.<target>_linker` and `plrust.<target>_pgrx_bindings_path` are looked up with `GetConfigOption(..., missing_ok=true)` (`gucs.rs:168-200`).
- **Dependency allow-list.** When `plrust.allowed_dependencies` is set, user `[dependencies]` are intersected against the allow-list and version/feature-matched exactly, else rejected (`mod.rs:349-352`, `restrict_dependencies` at `:413-466`); with no allow-list the admin has said "YOLO" and anything parses (`mod.rs:360-391`) `[verified-by-code]`. Exposed to SQL via `allowed_dependencies()` SRF (`plrust/src/lib.rs:201-219`).
- **Cross-compilation** builds one `.so` per configured target in a loop, always including the host triple first, storing each under its `CompilationTarget` key so a restore onto different hardware picks the right binary (`build.rs:74-86`, `plrust.rs:118-127`, keyed map in `prosrc.rs:91-92`) `[verified-by-code]`.
- **Build hardening in the cargo env** (`cargo.rs`): `RUSTFLAGS` forced empty (macOS gets only `dynamic_lookup`), and a `sanitize_env` strips `DOCS_RS`, `RUSTC_WRAPPER`, `CARGO_MANIFEST_DIR`, etc. so nothing leaks from the postmaster's environment into the user build (`cargo.rs:31-38`, `:122-130`); `pg_config` is passed as `PGRX_PG_CONFIG_*` env vars rather than a GUC (`cargo.rs:97-118`) `[verified-by-code]`. Release profile forces `panic = "unwind"` (`crating.rs:256-258`).
- **`pgproc.rs`** is a safe RAII wrapper over a `pg_proc` SysCache entry (`SearchSysCache1(PROCOID, …)` → `ReleaseSysCache` on `Drop`, `pgproc.rs:42-67`), typed accessors for `prosrc/prolang/proargtypes/proargmodes/proisstrict/proretset`, and the generation-number derivation from `xmin`/`cmin` (`pgproc.rs:87-123`) `[verified-by-code]`. See [[knowledge/idioms/catalog-conventions]].
- **On-disk `.so` is never trusted as authoritative**: `crate_name` deliberately no longer encodes the host triple because the binaries are keyed by triple inside `prosrc` instead (`plrust.rs:156-170`); the build cleans up its crate dir on both success and failure (`plrust.rs:129-134`, `build.rs:155-160`) `[verified-by-code]`.

## Links into corpus

- [[knowledge/ideologies/pgrx]] — the build/ABI substrate; plrust *is* a pgrx extension and every user function is a mini-pgrx extension.
- [[knowledge/ideologies/plv8]] — interpreted JS in a VM; the sandbox-by-VM contrast to plrust's sandbox-by-compiler+postgrestd.
- [[knowledge/ideologies/pljava]] — JVM bytecode PL; another "trust via managed runtime" contrast.
- [[knowledge/ideologies/plsh]] · [[knowledge/ideologies/pldotnet]] · [[knowledge/ideologies/plr]] — sibling PLs (shell, CLR, R) for the PL landscape.
- [[knowledge/ideologies/pg_tle]] · [[knowledge/ideologies/pgextwlist]] — trusted-extension / allow-list neighbors; compare plrust's dependency allow-list and required-lint gate.
- [[knowledge/subsystems/contrib-sepgsql]] — kernel-level MAC, a different point on the "confine untrusted server-side code" spectrum vs plrust's syscall-blocking std.
- [[knowledge/idioms/fmgr]] — the V1 call ABI pgrx re-imposes on each user `.so` (`_wrapper` symbol, `pg_guard_ffi_boundary`).
- [[knowledge/idioms/memory-contexts]] — plrust switches into `PgMemoryContexts::new("configdata")` for catalog reads.
- [[knowledge/idioms/guc-variables]] — the eight+ `plrust.*` GUCs and per-target dynamic GUC lookups.
- [[knowledge/idioms/catalog-conventions]] — the `pg_proc` SysCache wrapper and the `CatalogTupleUpdate` of `prosrc`.

## Sources

All fetched `2026-07-22` from `https://raw.githubusercontent.com/pgcentralfoundation/plrust/main/`:

- `README.md` — **200**
- `plrust/src/lib.rs` — **200**
- `plrust/src/user_crate/mod.rs` — **200**
- `plrust/src/user_crate/build.rs` — **200**
- `plrust/src/user_crate/verify.rs` — **200**
- `plrust/src/user_crate/validate.rs` — **200**
- `plrust/src/user_crate/loading.rs` — **200**
- `plrust/src/user_crate/ready.rs` — **200** (probed; holds `FnReady::load`/dlopen/memfd)
- `plrust/src/user_crate/lint.rs` — **200** (probed)
- `plrust/src/user_crate/crating.rs` — **200** (probed; lib.rs + Cargo.toml codegen)
- `plrust/src/user_crate/cargo.rs` — **200** (probed; `RUSTC=plrustc`, env sanitizing)
- `plrust/src/gucs.rs` — **200**
- `plrust/src/plrust.rs` — **200**
- `plrust/src/pgproc.rs` — **200**
- `plrust/src/prosrc.rs` — **200**
- `plrust/src/error.rs` — **200**
- `plrust/Cargo.toml` — **200**
- `plrust-trusted-pgrx/README.md` — **200** (probed)
- `plrust-trusted-pgrx/Cargo.toml` — **200** (probed)

No 404s; no substitutions were needed. The `postgrestd` fork itself is a git submodule referenced by README/build tooling and was **not** fetched (its syscall-blocking implementation is therefore `[inferred]`, not read). `plrustc` (the hardened rustc driver) lives in a sibling `plrustc/` tree also not fetched; its lint-pass implementations are `[inferred]` from the lint names in `plrust/src/lib.rs:91-116` and the `RUSTC=plrustc` wiring in `cargo.rs:80-83`.

**Confidence.** The compile-at-CREATE pipeline, typestate FSM, `plrustc` invocation, memfd/dlopen loading, `prosrc` JSON storage (gzip+base64, per-target keying), generation-number reload, required-lint load gate, GUC definitions, dependency allow-list, and handler wiring are all `[verified-by-code]` against the fetched sources with the cited `file:line`s. Trusted-vs-untrusted being a single-install compile-time choice and the two-name-idiom rejection are `[from-README]` (`README.md:147-158`). The **postgrestd** syscall-blocking mechanism and **plrustc** lint internals are `[from-README]`/`[inferred]` — I read the wiring that *selects* and *invokes* them but not their implementations. The claim that removing `#![forbid(unsafe_code)]` is only safe in an untrusted rebuild is `[from-comment]` (`plrust/src/lib.rs:83-90`).
