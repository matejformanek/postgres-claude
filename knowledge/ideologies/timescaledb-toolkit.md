# timescaledb-toolkit — ideology / divergence notes

TimescaleDB Toolkit ships "hyperfunctions" — advanced analytical AGGREGATES and
custom TYPES (time-weighted averages, percentile/uddsketch/tdigest sketches, ASAP
smoothing, counter/gauge/state accessors, timevector pipelines) for TimescaleDB
and plain PostgreSQL. It is built entirely on [[pgrx]] (the Rust extension
framework), but its interesting divergence is *how* it bends pgrx + the PG
aggregate API to ship dozens of stable, **parallel-safe**, **continuous-aggregate-compatible**
aggregate types — each carrying its full sketch state in a versionable, zero-copy
on-disk varlena form. It is the Rust analytics sibling of [[timescaledb]] (the C
core hypertable engine); Toolkit does not implement hypertables, it complements
them. `[from-README]` (Readme.md:5-12).

## Domain & purpose

Toolkit's mission is "ease all things analytics when using TimescaleDB, with a
particular focus on developer ergonomics and performance" `[from-README]`
(Readme.md:5-7). Concretely it provides aggregates whose *intermediate state* is
exposed to the user as a first-class SQL type (a `UddSketch`, `StateAgg`,
`CounterSummary`, `TimeWeightSummary`, `Timevector`…), so the partial form can be
materialized in a continuous aggregate, re-aggregated ("rolled up") at a coarser
grain, and then queried by many different accessor functions without recomputing.
The control file declares the extension `trusted`, `superuser`, non-`relocatable`,
comment "Library of analytical hyperfunctions, time-series pipelining, and other
SQL utilities" `[verified-by-code]` (extension/timescaledb_toolkit.control:1-5).

## How it hooks into PG

- **All entry points are pgrx attribute macros.** SQL-callable functions are
  `#[pg_extern(immutable, parallel_safe, …)]`; schemas are declared with
  `#[pg_schema] pub mod toolkit_experimental { … }` `[verified-by-code]`
  (state_aggregate.rs:142-143, 542). pgrx's `cargo-pgrx` generates the install
  SQL from these.
- **A custom `#[aggregate]` macro imitates `CREATE AGGREGATE`.** Toolkit's own
  `aggregate_builder` crate provides `#[aggregate] impl name { type State; fn
  transition; fn finally; const PARALLEL_SAFE; fn serialize; fn deserialize; fn
  combine }` `[from-README]` (crates/aggregate_builder/Readme.md:11-43). The macro
  expands each method into a `#[pgrx::pg_extern(immutable, parallel_safe)]`
  outer function and emits the `CREATE AGGREGATE` via `pgrx::extension_sql!` with
  `stype = internal`, `sfunc`, `finalfunc`, `parallel = safe`, `serialfunc`,
  `deserialfunc`, `combinefunc` `[from-README]`
  (crates/aggregate_builder/Readme.md:96-256). A real instance: the
  `compact_state_agg` aggregate is defined `#[aggregate] impl
  toolkit_experimental::compact_state_agg` with all six functions and a hand-written
  `extension_sql!("CREATE AGGREGATE …")` block listing the six generated fns in
  `requires = [...]` `[verified-by-code]` (state_aggregate.rs:470-541).
- **`stype = internal` + a pointer-stealing transition.** State lives behind
  `pgrx::Internal`/`Inner<Option<State>>`; the generated transition steals the
  state out, leaving `None`, so a panic frees state once rather than twice
  `[from-README]` (crates/aggregate_builder/Readme.md:106-138).
- **Memory-context discipline is automated.** The macro wraps the transition and
  combine bodies in `crate::aggregate_utils::in_aggregate_context(__fcinfo, ||
  …)`, which calls `pg_sys::AggCheckCallContext` to fetch the aggregate memory
  context and switches into it so state outlives the per-tuple context
  `[verified-by-code]` (aggregate_utils.rs:23-46; usage at state_aggregate.rs:559).
  Deserialize deliberately does *not* switch, "because the postgres aggregates do
  not do so" `[from-README]` (crates/aggregate_builder/Readme.md:198-200).
- **Custom types are pgrx `PostgresType` varlenas built on `pg_type!`.** The
  `pg_type!` macro (type_builder.rs) generates a `$name<'input>` wrapper plus a
  flat-serializable `$nameData` struct, manually implementing `PostgresType`,
  `FromDatum`, `IntoDatum` (the pgrx derive can't handle the `'input` lifetime on
  pgrx 0.16) `[verified-by-code]` (type_builder.rs:131-134, 292, 349). I/O is
  RON-based via `ron_inout_funcs!` `[verified-by-code]`
  (state_aggregate.rs:415,454).
- **Parallel safety + continuous-aggregate compatibility come from the
  combinefunc + serial/deserial set.** Every generated outer fn is
  `parallel_safe`; supplying `combinefunc`/`serialfunc`/`deserialfunc` is exactly
  what lets PG run partial aggregation across parallel workers and materialize
  partials in continuous aggregates `[verified-by-code]`
  (state_aggregate.rs:474, 528-531) `[inferred]` (the partial→worker→combine path
  is core PG behavior; see [[aggregate-partial-finalize]]).

## Where it diverges from core idioms — THE headline

### 1. Flat serialization: a bespoke fixed-layout, zero-copy varlena image

Toolkit does not use core PG's `typsend`/`typreceive` binary I/O, nor pgrx's
default `PostgresType` bincode/CBOR serialization, for the *on-disk* form of its
sketch types. Instead the `flat_serialize!` macro (own crate) takes a struct
description and generates code that reads/writes each field in declaration order,
supporting variable-length trailing fields whose length is named by an earlier
field (`data: [u8; self.data_len]`) `[from-README]`
(crates/flat_serialize/Readme.md:1-7, 25-33). The deserialize path is zero-copy:
`Data::try_ref(&bytes)` returns a reference *into* the byte buffer plus the
remaining bytes `[from-README]` (crates/flat_serialize/Readme.md:50-57). A real
on-disk layout: `CompactStateAgg` is a `pg_type!` whose fields include
`states_len: u64`, `durations: [DurationInState; self.durations_len]`,
`states: [u8; self.states_len]` — a self-describing flat record `[verified-by-code]`
(state_aggregate.rs:146-161). The varlena bridge: `to_pg_bytes()` does
`pg_sys::palloc0(len)`, `fill_slice`, then `pgrx::set_varsize_4b(...)` to stamp the
varlena header in place — and refuses sizes over `0x3FFFFFFF`
`[verified-by-code]` (type_builder.rs:272-289). `FromDatum` detoasts via
`pg_detoast_datum_packed` and reads back through `FlatSerializable`
`[verified-by-code]` (type_builder.rs:292-312). This is a deliberate "we own the
byte image" choice so the format is **versionable and stable across releases**,
unlike a derive-generated encoding.

### 2. Explicit `toolkit_experimental` vs stable-schema stability discipline

Atypical of extensions: Toolkit gates unstable features behind a
`toolkit_experimental` schema and *promotes* them to the default schema only once
stabilized. The `#[pg_schema] pub mod toolkit_experimental` is a literal SQL
schema `[verified-by-code]` (state_aggregate.rs:142). New aggregates land there
(`CREATE AGGREGATE toolkit_experimental.compact_state_agg`) `[verified-by-code]`
(state_aggregate.rs:521); the stable `rollup` aggregate exists in *both* the
experimental and default schema (two separate `CREATE AGGREGATE` blocks)
`[verified-by-code]` (state_aggregate/rollup.rs:8-49). The README documents a
"tag-notes" experimental section and a dedicated `feature-stabilization` issue
template exists `[from-README]` (Readme.md:21;
.github/ISSUE_TEMPLATE/feature-stabilization.md). The control file carries a long
`upgradeable_from` list of every prior version for generated upgrade scripts
`[verified-by-code]` (extension/timescaledb_toolkit.control:7-9).

### 3. The `->` arrow / pipeline operator: a fluent, un-SQL-like accessor API

Toolkit overloads the `->` operator to chain accessors over an aggregate's state.
Each accessor is a tiny `pg_type!` carrying its arguments (e.g.
`AccessorApproxPercentile { percentile: f64 }`), generated by an `accessor!`
macro `[verified-by-code]` (accessors.rs:7-50). The operator is a
`#[pg_operator] #[opname(->)]` function taking `(sketch, accessor)` and applying
it: `arrow_uddsketch_approx_percentile(sketch: UddSketch, accessor:
AccessorApproxPercentile) -> f64` `[verified-by-code]` (uddsketch.rs:569-576). So
`sketch -> approx_percentile(0.5)` is the fluent form of
`approx_percentile(0.5, sketch)`. Timevector "pipelines" extend the same `->` to
chain transforms (`timevector -> sort() -> delta()`), with the documented caveat
that PG's parser forces custom operators to be **left-associative**, so explicit
parenthesization is needed to pre-build a pipeline object `[from-README]`
(docs/timeseries_pipeline_elements.md:9-25). This two-step
inner-aggregate + outer-accessor convention is a deliberate design (not an
accident of pgrx) — see §Notable.

### 4. Approximation sketches carry full state across workers & cagg materialization

The sketch aggregates (uddsketch/tdigest/hyperloglog/count-min) keep their entire
internal sketch as the serialized aggregate state, so the partial survives
parallel-worker combine *and* continuous-aggregate materialization. `UddSketch`'s
transition builds an `UddSketchInternal`, `uddsketch_combine` merges two sketches,
and `uddsketch_serialize`/`deserialize` round-trip a `SerializedUddSketch`
`[verified-by-code]` (uddsketch.rs:32-46, 80-119). Because the *whole sketch* is
the on-disk type, the "two-step" docs note re-aggregation is exact for
stackable sketches but warn `tdigest` re-aggregation "can lead to more error …
because the algorithm is not deterministic in its re-aggregation"
`[from-README]` (docs/two-step_aggregation.md:149).

### 5. Rust-over-C ABI concerns inherited from pgrx

palloc bridging is explicit and manual: state allocation uses `pg_sys::palloc0`
+ `set_varsize_4b` (type_builder.rs:281-286); the aggregate context is fetched via
raw `pg_sys::AggCheckCallContext` (aggregate_utils.rs:39) `[verified-by-code]`.
The pointer-steal-on-transition pattern exists specifically so a Rust panic
unwinding into PG frees `State` once rather than double-freeing
`[from-README]` (crates/aggregate_builder/Readme.md:108-114). Panic→ereport
bridging itself is pgrx's responsibility — see [[pgrx]].

## Notable design decisions (with cites)

- **Two-step aggregation is a stated philosophy, not incidental.** "the inner
  aggregate call creates a machine-readable partial form" reused by many
  accessors; it cleanly separates aggregate-time params (bucket count, error
  target) from access-time params (which percentile), and it is "how and when
  aggregates can be re-aggregated or 'stacked'" — explicitly to integrate with
  continuous aggregates `[from-README]` (docs/two-step_aggregation.md:13-26,
  82-95).
- **`rollup` is the re-aggregation entry point.** A second-level
  `CREATE AGGREGATE rollup(...)` merges already-computed `StateAgg`s, asserting
  non-overlapping time ranges and panicking on overlap — encoding the "stackable"
  invariant in code `[verified-by-code]` (state_aggregate/rollup.rs:30-49,
  90-104).
- **Serialize takes `&mut State`.** Toolkit's `#[aggregate]` allows a mutable
  serialize receiver and notes "technically you should not mutate in serialize …
  though there are cases you can get away with it when using an internal
  transition type" `[from-README]` (crates/aggregate_builder/Readme.md:176-182;
  real use state_aggregate.rs:496-498).
- **RON for text I/O.** Human-readable input/output uses Rust Object Notation via
  `ron_inout_funcs!`, diverging from PG's usual hand-written `typinput`/`typoutput`
  C functions `[verified-by-code]` (state_aggregate.rs:415, accessors.rs:20).
- **A `CachedDatum` field memoizes the flattened varlena** so repeated
  `IntoDatum` calls don't re-serialize `[verified-by-code]`
  (type_builder.rs:1-5, 131, 237-269).
- **Built and tested on a pinned toolchain** (Rust 1.89.0, cargo-pgrx 0.18.0, PG
  15-18) — a tight ABI coupling typical of pgrx extensions `[from-README]`
  (Readme.md:38, 55, 105).

## Links into corpus

- [[pgrx]] — THE framework Toolkit is built on (every macro, the varlena bridge,
  panic→ereport). Primary link.
- [[timescaledb]] — the C core hypertable engine; Toolkit is its analytics sibling
  and continuous-aggregate-compatible companion.
- [[aggregate-partial-finalize]] — why combinefunc/serialfunc/deserialfunc enable
  parallel partial aggregation, the mechanism Toolkit relies on.
- [[aggregate-trans-state]] — the `stype = internal` transition-state machinery
  Toolkit drives from Rust.
- [[parallel-query]] / [[parallel-worker-coordination]] — `PARALLEL SAFE` markings
  + combine across workers.
- [[memory-contexts]] — `in_aggregate_context` / `AggCheckCallContext` switching.
- [[fmgr]] / [[spi]] — the `FunctionCallInfo` / `Datum` boundary pgrx wraps.
- [[catalog-conventions]] — `CREATE AGGREGATE` / `CREATE OPERATOR` / `CREATE TYPE`
  registration that the generated SQL emits.
- [[optimizer]] — the optimizer's combining of identical inner aggregate calls
  that makes two-step aggregation cheap.

> Corpus gap: there is no dedicated aggregate-API *authoring* idiom doc (how to
> declare sfunc/finalfunc/combine/serial/deserial from an extension); the closest
> are [[aggregate-partial-finalize]] and [[aggregate-trans-state]], which describe
> core internals, not the extension-author surface.
> Corpus gap: no idiom doc on the "exposed partial-aggregate-as-SQL-type" pattern
> (materializing an aggregate's intermediate state as a first-class type for
> re-aggregation), which is Toolkit's central design move.

## Sources

Tree (HTTP 200, fetched 2026-06-20):
- https://api.github.com/repos/timescale/timescaledb-toolkit/git/trees/main?recursive=1

Files via raw.githubusercontent.com/timescale/timescaledb-toolkit/main/ (all HTTP
200, fetched 2026-06-20):
- Readme.md
- extension/timescaledb_toolkit.control
- extension/Cargo.toml (skimmed — feature/pg-version flags)
- crates/aggregate_builder/Readme.md (the `#[aggregate]` macro contract + expansion)
- crates/aggregate_builder/src/lib.rs (fetched, 1068 lines; skimmed — macro impl)
- crates/flat_serialize/Readme.md
- crates/flat_serialize/flat_serialize/src/lib.rs (fetched, skimmed — runtime traits)
- crates/flat_serialize/flat_serialize_macro/src/lib.rs (fetched, skimmed — proc-macro)
- extension/src/aggregate_utils.rs
- extension/src/state_aggregate.rs (representative real aggregate: pg_type!, #[aggregate], extension_sql!)
- extension/src/state_aggregate/rollup.rs (re-aggregation aggregate)
- extension/src/state_aggregate/accessors.rs (build! accessors; skimmed)
- extension/src/accessors.rs (the `accessor!` macro)
- extension/src/type_builder.rs (the `pg_type!` macro: varlena/FromDatum/IntoDatum/flatten)
- extension/src/uddsketch.rs (sketch aggregate + `->` arrow operator)
- docs/two-step_aggregation.md
- docs/timeseries_pipeline_elements.md

GitHub code-search API used to locate the `->` operator and `pg_type!` macro
(HTTP 200, fetched 2026-06-20):
- https://api.github.com/search/code?q=...repo:timescale/timescaledb-toolkit
No 404s encountered.
