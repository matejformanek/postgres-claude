# tdigest — an approximate-percentile aggregate that ships a *real* first-class varlena type, and otherwise plays the core aggregate/parallel contract straight

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `tvondra/tdigest` @ branch `master`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> extension's relationship to core idioms. Cites verified against the files
> fetched on 2026-07-06 (see Sources footer). tdigest is the sibling of topn
> and hll — all three are approximate aggregates — but it is the *conformant*
> one: written by a core PostgreSQL committer (Tomas Vondra), it is the
> reference foil showing what "textbook use of the parallel-aggregate API"
> looks like, the way `tds_fdw` is the well-behaved FDW foil. This doc
> contrasts it explicitly with topn and hll.

## Domain & purpose

tdigest implements the **t-digest** data structure (Ted Dunning, 2013): an
on-line, mergeable sketch for estimating quantiles / percentiles / trimmed
means over a numeric stream (`README.md:5-9`) `[from-README]`. It is the
approximate analogue of core PG's exact `percentile_cont(0.95) WITHIN GROUP
(ORDER BY a)`, but it parallelizes cleanly and uses bounded memory set by a
`compression` knob (`README.md:39-51`) `[from-README]`. The headline
composability trick — same as topn/hll — is that a materialized digest for one
partition can be `tdigest_percentile`-ed later or merged with another digest,
so "95th percentile per bucket" becomes an aggregate over pre-built digests
instead of a re-scan (`README.md:87-120`) `[from-README]`. For an
anthropologist the interesting questions are: *why does tdigest ship a genuine
stored SQL type* where topn reuses `jsonb` and hll hides behind an opaque blob,
and *what does a by-the-book SERIALFUNC/COMBINEFUNC/DESERIALFUNC parallel
aggregate look like when a core committer writes it*.

## How it hooks into PG

`PG_MODULE_MAGIC` (`tdigest.c:22`) `[verified-by-code]`. There is **no
`_PG_init`, no GUC, no planner hook, no `shared_preload_libraries`
requirement** — the extension is a flat pile of `PG_FUNCTION_INFO_V1` C
functions (`tdigest.c:114-159`) wired into a stored type plus a family of
aggregates. This is *less* machinery than topn (which registers a
`topn.number_of_counters` GUC in `_PG_init`) and far less than hll (which
chains a planner hook). tdigest touches the catalog only through ordinary
`CREATE TYPE` / `CREATE FUNCTION` / `CREATE AGGREGATE` in the install SQL
`[verified-by-code]`.

The wiring lives in `tdigest--1.0.0.sql` and is the load-bearing part:

- The **public/result type is a first-class `tdigest` varlena type**, declared
  with the full I/O quartet — `INPUT = tdigest_in`, `OUTPUT = tdigest_out`,
  `RECEIVE = tdigest_recv`, `SEND = tdigest_send`, `INTERNALLENGTH = variable`,
  `STORAGE = external` (`tdigest--1.0.0.sql:102-131`) `[verified-by-code]`.
  This is the standout divergence from its siblings: topn materializes to
  `jsonb`, hll to an opaque register blob; tdigest defines its own persistable,
  dumpable, TOAST-able type.
- The **transition state is `internal`**: every aggregate declares
  `STYPE = internal` (`tdigest--1.0.0.sql:62-70`) `[verified-by-code]`, an
  opaque pointer to a `tdigest_aggstate_t` (`tdigest.c:72-87`).
- The **full parallel contract is present from v1.0.0** (not bolted on later as
  in topn): every aggregate carries `SFUNC` + `FINALFUNC` +
  `SERIALFUNC = tdigest_serial` + `DESERIALFUNC = tdigest_deserial` +
  `COMBINEFUNC = tdigest_combine` + `PARALLEL = SAFE`
  (`tdigest--1.0.0.sql:62-221`) `[verified-by-code]`.

There are **two aggregate forms**, exactly the "build vs. combine" pair:

1. *Add raw values one at a time* — `tdigest(double, int)` returning the
   `tdigest` type (`tdigest--1.0.0.sql:138-146`), and the compute-in-one-shot
   `tdigest_percentile(double, int, double)` returning the percentile
   (`tdigest--1.0.0.sql:62-70`) `[verified-by-code]`.
2. *Combine pre-built digests* — `tdigest(tdigest)`
   (`tdigest--1.0.0.sql:213-221`) and `tdigest_percentile(tdigest, double)`
   (`tdigest--1.0.0.sql:173-181`), whose SFUNC ingests whole stored digests
   rather than scalars `[verified-by-code]`.

Later versions add pre-weighted `(value, count, …)` variants
(`tdigest--1.0.1--1.2.0.sql`, all `PARALLEL = SAFE`) and trimmed-mean
aggregates `tdigest_avg` / `tdigest_sum` (`tdigest--1.2.0--1.3.0.sql`)
`[verified-by-code]`. Versions 1.0.0→1.0.1, 1.3.0→1.4.3 are empty no-op
upgrade scripts `[verified-by-code]`.

## Where it diverges from core idioms

This extension is **largely conformant** — the "divergences" are (a) the
approximate-aggregate contract that all three siblings share, and (b) the
*choice to define a real type*, which is a divergence *from its siblings*, not
from core. Enumerated:

### 1. Approximate aggregation: accuracy is a tunable, not a guarantee

Like topn and hll, tdigest deliberately does *not* do the exact thing. The
honest query is `percentile_cont(...) WITHIN GROUP (...)`, exact but sort-bound
and unparallelizable (`README.md:39-51`) `[from-README]`. tdigest trades exact
answers for a bounded-memory sketch whose fidelity is governed by the
`compression` parameter (range `[10, 10000]`, `tdigest.c:110-111`)
`[verified-by-code]`. Core PG aggregates are exact by contract; an aggregate
whose error is a function of a knob is the shared break all three approximate
extensions make.

### 2. A first-class stored type, where the siblings piggyback (the anti-topn/anti-hll choice)

topn's durable state is `jsonb`; hll's is an opaque register varlena. tdigest
instead ships its own **`tdigest` varlena type** with a legible on-disk layout:
a `tdigest_t` header (`vl_len_`, `flags`, `int64 count`, `compression`,
`ncentroids`) followed by a `FLEXIBLE_ARRAY_MEMBER` of `centroid_t {double
mean; int64 count}` kept sorted by mean (`tdigest.c:35-42`, `tdigest.c:27-30`)
`[verified-by-code]`. Because it is a genuine type it has:

- **A human-readable text representation.** `tdigest_out`/`tdigest_in`
  round-trip the format `flags N count N compression N centroids N (mean, count)
  (mean, count) …`, parsed with `sscanf` and range-validated
  (`tdigest.c:2605-2668`) `[verified-by-code]`. You can `SELECT` a digest, read
  it by eye, dump it in `pg_dump` output, and re-`INSERT` the text — none of
  which hll's opaque blob allows.
- **Binary `SEND`/`RECV`** for the wire, plus **`STORAGE = external`** so the
  flat centroid array TOASTs like any large varlena
  (`tdigest--1.0.0.sql:114-131`) `[verified-by-code]`.
- **A forward-compatible on-disk version flag.** `TDIGEST_STORES_MEAN`
  (`tdigest.c:52-55`) marks digests that store `(mean, count)` centroids; old
  `(sum, count)` digests are transparently upconverted in memory by
  `tdigest_update_format` **without rewriting the stored bytes**
  (`tdigest.c:836-859`) `[from-comment]` — a genuine on-disk-format migration
  story, the kind of thing you only build when your bytes are meant to persist.

The cost tradeoff is the inverse of topn's: topn pays JSON re-parse churn for
node-portability; tdigest keeps a tight binary type but takes on the full
burden of being a real PG type (I/O funcs, TOAST, version flag).

### 3. Two serialization shapes from one state — but idiomatically split

Like topn, tdigest has **two distinct exit formats** from its `internal`
transition state, chosen by which boundary the state crosses:

- `FINALFUNC` (`tdigest_digest`) → the **`tdigest` type** (the user-visible
  varlena result, `tdigest.c:2096-2115`), or the `tdigest_percentiles` finalizer
  → a `double`/`double[]` percentile (`tdigest.c:2045-2061`, `2121-2143`)
  `[verified-by-code]`.
- `SERIALFUNC` (`tdigest_serial`) → a **`bytea`**: a flat `memcpy` of the
  aggstate header + percentile array + value array + centroid array into one
  varlena (`tdigest.c:2174-2216`), read straight back by `tdigest_deserial`
  (`tdigest.c:2219-2273`) `[verified-by-code]`. This transient format is only
  ever consumed by a sibling parallel worker.

Note the aggstate serialized here (`tdigest_aggstate_t`) is *not* the on-disk
`tdigest_t` type — it is the larger working state carrying the requested
percentiles/values and an *uncompacted* centroid buffer. So tdigest actually
has **three** representations: the durable type, the cross-worker bytea, and
the in-flight aggstate. That is one more than a minimal aggregate needs, and it
is exactly the richness the two-form (build/combine) design requires.

### 4. Everything else is textbook — the conformance is the finding

Where topn copy-pastes a jsonb parser and hll hooks the planner, tdigest does
the boring correct thing at every turn, which is why it is the reference foil:

- **Memory-context discipline is impeccable.** Every transition/final/combine
  function opens with `AggCheckCallContext(fcinfo, &aggcontext)` and `elog(ERROR
  …)` if called outside an aggregate (`tdigest.c:994-996`) `[verified-by-code]`
  — the standard guard against a forged `internal` pointer. New state is
  allocated only after `MemoryContextSwitchTo(aggcontext)` and switched back
  (`tdigest.c:1021-1040`) `[verified-by-code]`. `tdigest_combine` copies the
  source state into the *long-lived* agg context before merging
  (`tdigest.c:2322-2324`) `[verified-by-code]` — the exact idiom
  `[[knowledge/idioms/aggregate-trans-state]]` prescribes.
- **Single-chunk aggstate allocation.** `tdigest_aggstate_allocate` `palloc0`s
  one MAXALIGN'd block covering the struct, the percentile/value arrays, and the
  full `BUFFER_SIZE(compression)` centroid buffer, then hands out interior
  pointers (`tdigest.c:875-920`) `[verified-by-code]` — no per-value repalloc.
- **Detoasting is explicit.** `PG_GETARG_TDIGEST` wraps
  `PG_DETOAST_DATUM` (`tdigest.c:91`) `[verified-by-code]` so the external-stored
  type is always fully detoasted before the centroid array is walked.

## Notable design decisions (cited)

- **k2 scaling function drives centroid merging.** `tdigest_compact` merges
  adjacent centroids while the size-bound `z = proposed_count * normalizer`
  satisfies `z ≤ q(1-q)` at both endpoints, with `normalizer = compression / (2π
  · N · log N)` (`tdigest.c:470-491`) `[verified-by-code]`. A header comment
  records that the code started on the k1 function, hit a centroid-count bug,
  and switched to a simpler k2 copy from ajwerner's implementation
  (`tdigest.c:426-432`) `[from-comment]`.
- **Compaction alternates direction to cancel bias.** Even compactions sweep
  left-to-right, odd ones right-to-left (`tdigest.c:458-467`)
  `[verified-by-code]`, per the t-digest paper's anti-bias note.
- **Buffered inserts, compact on overflow.** New values append as singleton
  centroids into an over-sized buffer of `BUFFER_SIZE(compression) = 10 ·
  compression` (`tdigest.c:107`), and `tdigest_compact` fires only when the
  buffer fills (`tdigest.c:782-786`) `[verified-by-code]` — amortizing the
  sort/merge cost, the "micro-benchmarks say 10×delta" tradeoff quoted from the
  paper (`tdigest.c:94-106`) `[from-comment]`.
- **Percentile read is linear interpolation between centroid means.**
  `tdigest_compute_quantiles` compacts+sorts, walks centroids accumulating
  count to the goal `percentile · count`, then interpolates
  (`tdigest.c:548-602+`) `[verified-by-code]`; percentiles 0.0/1.0 short-circuit
  to the first/last centroid mean (`tdigest.c:573-586`) `[verified-by-code]`.
- **Means, not sums, to fight rounding drift.** Centroids store `(mean, count)`
  and the merge skips recomputing the mean when two centroids already share it,
  deliberately to keep equal means from drifting apart over repeated compactions
  (`tdigest.c:44-51`, `tdigest.c:501-513`) `[from-comment]`.
- **The `internal` functions refuse non-aggregate contexts** uniformly — the
  `AggCheckCallContext` guard is repeated in ~30 call sites across every
  trans/serial/deserial/combine/final function `[verified-by-code]`, the
  standard defense for `internal`-typed C functions.

## Links into corpus

- `[[knowledge/ideologies/topn]]` — the closest sibling. Direct contrast: topn
  stores state as legible `jsonb` and rebuilds/reparses it every step for
  node-portability; tdigest ships a tight binary `tdigest` type with its own
  I/O funcs and TOAST. Both expose two exit formats (final result vs. bytea
  serial) from an `internal` state. topn adds a GUC + `_PG_init`; tdigest adds
  neither.
- `[[knowledge/ideologies/postgresql-hll]]` — the opaque-blob sibling. hll
  hides its registers behind a private varlena and hooks the planner to force
  GroupAggregate; tdigest's type is legible (text I/O) and needs no planner
  hook because its bounded compaction keeps the state small.
- `[[knowledge/ideologies/datasketches]]` — the other approximate-aggregate
  family; same build/combine two-form aggregate shape.
- `[[knowledge/idioms/aggregate-partial-finalize]]` — the
  combine/serialize/deserialize/finalfunc machinery tdigest implements straight;
  its twist is a stored *type* as the final format and a flat bytea as the
  serial format.
- `[[knowledge/idioms/aggregate-trans-state]]` — the `internal` STYPE living in
  the aggregate memory context via `AggCheckCallContext` +
  `MemoryContextSwitchTo`; tdigest is the clean reference implementation.
- `[[knowledge/idioms/fmgr]]` — the `PG_FUNCTION_INFO_V1` / `PG_GETARG_*` /
  `PG_DETOAST_DATUM` entry points the extension is built from.
- `[[knowledge/idioms/memory-contexts]]` — the single-chunk `palloc0` aggstate
  and the switch-to-aggcontext-before-allocate discipline.
- `.claude/skills/parallel-query/SKILL.md` — `PARALLEL SAFE` markings and the
  SERIALFUNC/DESERIALFUNC cross-worker boundary tdigest arms from v1.0.0.

## Sources

Fetched 2026-07-06 (branch `master`, `default_version = '1.4.3'`,
`tdigest.control`). The base install SQL `tdigest--1.0.0.sql` already declares
every aggregate WITH the full `COMBINEFUNC`/`SERIALFUNC`/`DESERIALFUNC`/`PARALLEL
= SAFE` machinery — unlike topn, tdigest was parallel-ready from its first
release. `MODULE_big = tdigest`, `OBJS = tdigest.o` (single C file); `DATA` lists
one base script plus seven chained upgrades (`Makefile`).

- `https://raw.githubusercontent.com/tvondra/tdigest/master/README.md`
  @ 2026-07-06 → HTTP 200 (21697 bytes).
- `https://raw.githubusercontent.com/tvondra/tdigest/master/tdigest.control`
  @ 2026-07-06 → HTTP 200 (94 bytes; `default_version = '1.4.3'`,
  `relocatable = true`, `comment = 'Provides tdigest aggregate function.'`).
- `https://raw.githubusercontent.com/tvondra/tdigest/master/Makefile`
  @ 2026-07-06 → HTTP 200 (1309 bytes; `MODULE_big = tdigest`, `OBJS =
  tdigest.o`, `REGRESS` includes `parallel_query`, `combine_crash`,
  `trimmed_aggregates`).
- `https://raw.githubusercontent.com/tvondra/tdigest/master/tdigest.c`
  @ 2026-07-06 → HTTP 200 (92666 bytes, 3540 lines) — THE core: the `tdigest_t`
  on-disk type + `centroid_t`, the `tdigest_aggstate_t` internal state, the k2
  `tdigest_compact` compaction, the buffered `tdigest_add`, the
  serialize/deserialize/combine parallel trio, the text/binary I/O funcs, the
  quantile interpolation, the `TDIGEST_STORES_MEAN` version flag.
- `https://raw.githubusercontent.com/tvondra/tdigest/master/tdigest--1.0.0.sql`
  @ 2026-07-06 → HTTP 200 (7354 bytes) — declares the `tdigest` type + all
  aggregates with the full parallel contract; the build-form and combine-form
  aggregates.
- `https://raw.githubusercontent.com/tvondra/tdigest/master/tdigest--1.0.1--1.2.0.sql`
  @ 2026-07-06 → HTTP 200 (3559 bytes) — adds pre-weighted `(value, count, …)`
  aggregate variants + `tdigest_add`/`tdigest_union` SQL helpers, all `PARALLEL
  = SAFE`.
- `https://raw.githubusercontent.com/tvondra/tdigest/master/tdigest--1.2.0--1.3.0.sql`
  @ 2026-07-06 → HTTP 200 (4051 bytes) — adds trimmed-mean aggregates
  `tdigest_avg` / `tdigest_sum`.
- Empty (0-byte) no-op upgrade scripts, HTTP 200 each @ 2026-07-06:
  `tdigest--1.0.0--1.0.1.sql`, `tdigest--1.3.0--1.4.0.sql`,
  `tdigest--1.4.0--1.4.1.sql`, `tdigest--1.4.1--1.4.2.sql`,
  `tdigest--1.4.2--1.4.3.sql` (version-bump-only releases).

All cites into `tdigest.c` — `PG_MODULE_MAGIC`, the on-disk `tdigest_t` /
`centroid_t` layout, the `internal` `tdigest_aggstate_t`, the
`AggCheckCallContext` + `MemoryContextSwitchTo` discipline, the k2 compaction,
the bytea `tdigest_serial` flat dump, the linear-interpolation quantile read,
and the `TDIGEST_STORES_MEAN` version flag — are `[verified-by-code]` against
the fetched file. The t-digest algorithm/purpose framing and the
pre-aggregation composability claim are `[from-README]`. No `_PG_init`, GUC, or
hook exists in the fetched `tdigest.c` (grep-verified) `[verified-by-code]`.
