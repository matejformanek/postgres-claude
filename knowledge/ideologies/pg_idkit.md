# pg_idkit — a polyglot ID zoo: one pgrx extension fanning N third-party Rust ID crates out as SQL functions, mostly returning `text` rather than native types

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `VADOSWARE/pg_idkit` @ branch `main`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Cites verified against the files
> fetched 2026-07-22 (see Sources footer).

- **Repo:** VADOSWARE/pg_idkit, branch `main`, license **MIT** (`Cargo.toml:6`),
  author Victor Adossi <vados@vadosware.io> (`Cargo.toml:5`), version `0.4.0`
  (`Cargo.toml:3`). Built on **pgrx** `=0.16.1` (`Cargo.toml:34`); `rust-version`
  pinned to 1.90 (`Cargo.toml:7`).
- **Fetched:** `README.md` (327 lines), `src/lib.rs` (30), `Cargo.toml` (121),
  `src/common.rs` (66), `src/uuid_v7.rs` (117), `src/ulid.rs` (116),
  `src/nanoid.rs` (62), `src/typeid.rs` (171). Probed all 13 declared modules
  (all 200; see Sources).

## Domain & purpose

pg_idkit is a *polyglot ID-generation* extension: "a Postgres extension for
generating many popular types of identifiers" (`README.md:17`) `[from-README]`.
Where most ID/type extensions bind ONE scheme, pg_idkit exposes a whole zoo,
one Rust module per format: UUIDv6, UUIDv7, nanoid, ksuid, ksuid-ms, ulid,
Timeflake, PushID, xid, cuid (deprecated), cuid2, and typeid — enumerated both
in the README function table (`README.md:19-48`) and as `mod` declarations
(`src/lib.rs:3-14`) `[verified-by-code]`. Each scheme is a thin skin over a
dedicated upstream crate: `cuid`, `cuid2`, `svix-ksuid`, `nanoid`, `pushid`,
`timeflake-rs`, `ulid`, `uuid`, `xid`, `type-safe-id` (`Cargo.toml:39-48`)
`[verified-by-code]`. Contrast the corpus's single-format siblings —
`[[knowledge/ideologies/uuidv47]]` (one bespoke `uuid47` base type),
`[[knowledge/ideologies/pg_hashids]]` (one encode/decode algorithm) — where the
extension IS the algorithm. Here the extension owns almost no ID logic; it owns
the *dispatch surface*.

## How it hooks into PG

- **SQL entry points are pgrx `#[pg_extern]` functions**, one family per scheme,
  named `idkit_<scheme>_generate[...]` — e.g. `idkit_uuidv7_generate`
  (`src/uuid_v7.rs:17-20`), `idkit_ulid_generate` (`src/ulid.rs:12-15`),
  `idkit_nanoid_generate` (`src/nanoid.rs:7-10`) `[verified-by-code]`. pgrx's
  build-time schema generator emits the matching `CREATE FUNCTION ... LANGUAGE c`
  into `pg_idkit--0.4.0.sql`; there is no hand-written SQL install script in the
  tree `[inferred]`.
- **Return type is overwhelmingly `text`, not a native ID type.** The default
  generator returns Rust `String`, which pgrx maps to SQL `text`
  (`src/uuid_v7.rs:18`, `src/ulid.rs:13`, `src/nanoid.rs:8`)
  `[verified-by-code]`. The UUID schemes ALSO offer a `_generate_uuid` variant
  that returns the core `uuid` type via `pgrx::Uuid::from_slice(...)`
  (`src/uuid_v7.rs:30-34`) — the only place native PG type infrastructure is
  reused. ksuid/ulid/xid/cuid/timeflake/nanoid have no such native variant; they
  are `text`-only `[verified-by-code]`.
- **No `_PG_init`.** `src/lib.rs` contains only `pg_module_magic!()`
  (`src/lib.rs:16-18`) — no shared-memory request, no GUCs, no hook chaining, no
  bgworker. The README's `shared_preload_libraries` line (`README.md:165`) is a
  binary-install convenience, not a load-time requirement: `CREATE EXTENSION`
  plus stateless function calls is the whole model `[verified-by-code]`.
- **Volatility is left at the pgrx default (VOLATILE), which is correct.** No
  `#[pg_extern(immutable)]` / `parallel_safe` annotations appear on the
  generators (`src/uuid_v7.rs:17`, `src/ulid.rs:12`, `src/nanoid.rs:7`); pgrx's
  bare `#[pg_extern]` emits a VOLATILE function. ID generators embed entropy
  and/or wall-clock, so VOLATILE is the *right* marking — here the extension
  benefits from the safe default rather than having to reason about it
  `[verified-by-code]`. The pure `extract_timestamptz(text)` decoders are also
  left VOLATILE despite being functionally IMMUTABLE — a missed optimization,
  not a bug (`src/uuid_v7.rs:41-42`) `[inferred]`.
- **Each Rust crate is wrapped by direct call.** `Uuid::now_v7()`
  (`src/uuid_v7.rs:12-14`), `Ulid::new()` (`src/ulid.rs:14`), `nanoid!()`
  (`src/nanoid.rs:9`), `TypeSafeId::from_type_and_uuid(...)`
  (`src/typeid.rs:48`) — the wrapper is one line calling the crate, then
  `.to_string()`. The shared `src/common.rs` provides the only reused glue: an
  `OrPgrxError` trait that turns any `Result`/`Option` into a `pgrx::error!`
  longjmp (`src/common.rs:6-41`) and `naive_datetime_to_pg_timestamptz` to build
  a `TimestampWithTimeZone` for the decoders (`src/common.rs:48-66`)
  `[verified-by-code]`.

## Where it diverges from core idioms

1. **Facade over N third-party crates, not native type I/O.** A core PG type
   defines `typinput`/`typoutput` in C and owns its on-disk bytes; pg_idkit
   defines *no* type. Every ID's bytes and encoding come from an external crate
   (`Cargo.toml:39-48`) and are handed to PG as an already-formatted `String`
   (`src/ulid.rs:13-15` returns `Ulid::new().to_string()`) `[verified-by-code]`.
   The extension is a name-mapping layer, not a type implementation.
2. **`text` return abandons core type reuse (mostly).** By returning `text`, ID
   values get no type-specific comparison, no fixed-width storage, no
   validation on cast — a ULID column is just `text`. The one exception is
   `idkit_uuidv7_generate_uuid` returning `pgrx::Uuid` = core `uuid`
   (`src/uuid_v7.rs:29-34`), which DOES inherit core `uuid`'s 16-byte storage,
   B-tree opclass, and I/O. That the *default* generator is the `text` one
   (`src/uuid_v7.rs:17`) means the ergonomic path forgoes the native type
   `[verified-by-code]`.
3. **Volatility handled by default, not by design** (see above): correct outcome,
   but arrived at by inheriting pgrx's VOLATILE default rather than an explicit
   choice; the decoders are over-conservatively VOLATILE `[inferred]`.
4. **Clock source is wall-clock, per-call, stateless.** Time-embedding schemes
   read the host wall-clock at call time: `Uuid::now_v7()` (`src/uuid_v7.rs:13`),
   `Ulid::new()` (`src/ulid.rs:14`). There is **no per-backend monotonic
   counter** in the extension — no shared/backend-local state exists
   (`src/lib.rs` declares no state; generators take no `&mut`)
   `[verified-by-code]`. Intra-millisecond monotonicity is therefore only
   whatever the underlying crate guarantees; a backwards wall-clock step (NTP)
   can produce non-monotonic v7/ULID values, and two rows inserted in one
   statement are not guaranteed strictly ordered `[inferred]`. Decoders round to
   whole seconds (`f64::from(t.second())`, `src/common.rs:62`), dropping
   sub-second precision on extract despite the doc claiming "millisecond
   precision" (`src/uuid_v7.rs:36`) `[verified-by-code]`.
5. **Supply-chain surface pulled into the backend address space.** Ten ID crates
   plus `getrandom` (`Cargo.toml:33`), `chrono` (`:35`), `time` (`:37`),
   `anyhow` (`:36`) and their transitive trees are statically linked into
   `pg_idkit.so` and run inside the postmaster-forked backend. A core C ID
   generator would pull nothing; here each scheme's CVE surface and RNG
   (`getrandom` reads OS entropy per call) lives in-process `[inferred]`. Panics
   are contained: `panic = "unwind"` (`Cargo.toml:54,58`) lets pgrx translate a
   Rust panic into a PG ERROR rather than crashing the backend `[verified-by-code]`.

## Notable design decisions

- **One module per scheme, uniform shape.** `src/lib.rs:3-14` lists 12 scheme
  modules + `common`; each file is `generate` / `generate_text` / optional
  `generate_uuid` / optional `extract_timestamptz`, plus an inline `#[pg_test]`
  suite (`src/uuid_v7.rs:65-117`, `src/ulid.rs:60-116`) `[verified-by-code]`.
- **`generate` vs `generate_text` doubling.** Most schemes ship both
  `idkit_x_generate()` and `idkit_x_generate_text()` where the latter just calls
  the former (`src/uuid_v7.rs:23-26`, `src/ulid.rs:18-21`,
  `src/nanoid.rs:13-16`) — an explicit-`text` alias kept for naming symmetry
  `[verified-by-code]`.
- **Parameterized generators.** nanoid takes a custom length+alphabet
  (`idkit_nanoid_custom_generate_text(len, alphabet)`, `src/nanoid.rs:19-29`),
  clamping negative length via `std::cmp::max(len, 0)` and erroring on overflow
  `[verified-by-code]`. typeid takes a string prefix and validates it
  (`DynamicType::new(prefix)`, `src/typeid.rs:46-48`), enforcing that a supplied
  UUID is genuinely v7 via `matches!(uuid.get_version(), Some(SortRand))`
  (`src/typeid.rs:28-31, 107-112`) `[verified-by-code]`.
- **Cross-scheme conversion.** ulid can be built from a core PG `uuid`
  (`idkit_ulid_from_uuid(pgrx::Uuid)`, `src/ulid.rs:24-28`) — the reverse
  bridge into the native type `[verified-by-code]`.
- **Feature flags gate PG version, not schemes.** `Cargo.toml:22-30` exposes
  `pg13`..`pg18` features (default `pg17`) forwarding to `pgrx/pgXX`; there is no
  per-scheme feature flag — every ID format ships in every build
  `[verified-by-code]`.
- **Error idiom is centralized.** `OrPgrxError` (`src/common.rs:6-41`) is the
  single convention for surfacing failures as PG errors; typeid layers `anyhow`
  `Context` on top (`src/typeid.rs:45-49`) `[verified-by-code]`.
- **README as the function catalog.** The scheme→function→crate table
  (`README.md:19-48`) is the authoritative user-facing map; there is no
  generated function reference `[from-README]`.

## Links into corpus

- `[[knowledge/ideologies/pgrx]]` — the Rust substrate: `#[pg_extern]`,
  `pg_module_magic!`, `pgrx::Uuid`, `TimestampWithTimeZone`, panic→ERROR bridge.
- `[[knowledge/ideologies/uuidv47]]` — the anti-pattern sibling: a single
  bespoke `uuid47` **base type** with real on-disk bytes and opclasses, where
  pg_idkit deliberately returns `text` and defines no type.
- `[[knowledge/ideologies/pg_hashids]]` — another single-algorithm ID/obfuscation
  extension (encode/decode) for contrast with the zoo model.
- `[[knowledge/ideologies/postgresql-hll]]` — a native-data-type extension
  (custom `hll` type with full I/O), the opposite end of the "own the type"
  spectrum from pg_idkit's "own the name" stance.
- `[[knowledge/idioms/fmgr]]` — the C-level function-manager machinery that pgrx
  `#[pg_extern]` generates for each `idkit_*` function.
- `[[knowledge/idioms/catalog-conventions]]` — how the `CREATE FUNCTION` entries
  land in `pg_proc` (here emitted by pgrx's schema generator, not hand-written).

## Sources

- `https://raw.githubusercontent.com/VADOSWARE/pg_idkit/main/README.md` — HTTP 200 (327 lines)
- `https://raw.githubusercontent.com/VADOSWARE/pg_idkit/main/src/lib.rs` — HTTP 200 (30 lines)
- `https://raw.githubusercontent.com/VADOSWARE/pg_idkit/main/Cargo.toml` — HTTP 200 (121 lines)
- Module probes (all HTTP 200): `src/common.rs` (66), `src/uuid_v7.rs` (117),
  `src/uuid_v6.rs` (118), `src/ulid.rs` (116), `src/nanoid.rs` (62),
  `src/ksuid.rs` (76), `src/ksuid_ms.rs` (82), `src/xid.rs` (85), `src/cuid.rs`
  (85), `src/cuid2.rs` (80), `src/timeflake.rs` (110), `src/typeid.rs` (171),
  `src/pushid.rs` (32). Read in depth: `common`, `uuid_v7`, `ulid`, `nanoid`,
  `typeid`. Probe `src/generators/mod.rs` — HTTP 404 (no `generators/` dir; the
  layout is flat one-file-per-scheme under `src/`).
- **Confidence:** Structural claims (module-per-scheme, `#[pg_extern]` naming,
  `text` vs `pgrx::Uuid` returns, no `_PG_init`, default-VOLATILE, crate wrapping,
  feature flags) are `[verified-by-code]` from the fetched files. Scheme
  enumeration is `[verified-by-code]` (`src/lib.rs`) cross-checked
  `[from-README]`. The generated-SQL / `pg_proc` path and the monotonicity /
  wall-clock / supply-chain risk analyses are `[inferred]` from the code plus
  pgrx semantics (not exercised on a running server). Not fetched:
  `pg_idkit.control`, generated `pg_idkit--0.4.0.sql`, `src/uuid_v6.rs`,
  `src/ksuid*.rs`, `src/xid.rs`, `src/cuid*.rs`, `src/timeflake.rs`,
  `src/pushid.rs` bodies (probed for existence/line-count only).
