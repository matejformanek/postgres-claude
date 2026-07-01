# topn — an approximate top-frequent-items aggregate whose state is JSONB, not bytea

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `citusdata/postgresql-topn` @ branch `master`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> files fetched on 2026-06-30 (see Sources footer). TopN is hll's sibling — both
> are Citus approximate-aggregate types — so this doc explicitly contrasts the two.

## Domain & purpose

TopN computes the **approximate most-frequent N items** in a data set: the
top product IDs, the top users, the top events in some dimension
(`README.md:4`). It is not a new SQL type — it stores its result in plain
`jsonb` — but a pair of **aggregates** (`topn_add_agg`, `topn_union_agg`) plus
a `topn(jsonb, n)` set-returning extractor that together implement the
**Space-Saving frequent-items algorithm** (`topn.c:5-6`). The headline trick is
the same composability that makes hll useful: a materialized TopN summary for
one time-bucket can be `topn_union`-ed with another, so "top 10 products in
January" is an aggregate-of-aggregates over per-day summaries rather than a
re-scan of the base table (`README.md:84-115`). The approximation: it keeps far
more counters than you ask for (default `100*N`-ish, GUC-tuned) and, when it
runs out of room, **evicts the bottom half of all counters** — so the genuine
top items almost never get evicted and carry accurate counts
(`README.md:20-23`). For an anthropologist the interesting questions are: *why
pick JSONB as the durable aggregate state instead of an opaque varlena like
hll*, and *how do you make a lossy custom aggregate parallel- and
Citus-distribution-safe*.

## How it hooks into PG

`PG_MODULE_MAGIC` (`topn.c:40`). `_PG_init` does exactly one thing: register
the `topn.number_of_counters` GUC via `DefineCustomIntVariable`
(`topn.c:168-188`) at `PGC_USERSET`, default 1000, range `1 .. JSONB_MAX_PAIRS`
`[verified-by-code]`. There is **no planner hook, no shared_preload_libraries
requirement** — unlike hll, which chains `create_upper_paths_hook` to poison
HashAggregate costs. TopN is "just" a pile of `PG_FUNCTION_INFO_V1` C functions
(`topn.c:89-97`) wired into two SQL aggregates.

The aggregate wiring is the load-bearing part, and it lives in the install /
upgrade SQL, not in C:

- The **public type is `jsonb`**: `topn_add` / `topn_union` / `topn`
  take and return `jsonb` (`update/topn--2.0.0.sql`), so a TopN summary is a
  legible `{"item": freq, …}` object you can store in an ordinary `jsonb`
  column, dump, ship over the wire, and read by eye.
- The **transition state is `internal`**: `STYPE = internal`
  (`update/topn--2.0.0.sql`). In C this `internal` is an opaque pointer to a
  `TopnAggState`, which is *literally a lone dynahash `HTAB`*
  (`topn.c:100-106, 954-959`) — the comment says "it is actually a lone HTAB".
- The aggregates carry the full parallel/distributed state machine, added in
  `update/topn--2.3.0--2.3.1.sql`:
  `SFUNC = topn_add_trans` / `topn_union_trans`, `FINALFUNC = topn_pack`,
  `COMBINEFUNC = topn_union_internal`, `SERIALFUNC = topn_serialize`,
  `DESERIALFUNC = topn_deserialize`, `PARALLEL = SAFE` `[verified-by-code]`.
- `topn_union` is also exposed as a `+` operator on `jsonb`, declared its own
  commutator (`update/topn--2.0.0.sql`).

So there are **two distinct serialization shapes** for the same aggregate state:
the durable/public one is **JSONB** (produced by `FINALFUNC topn_pack`,
`topn.c:644-676`), and the transient cross-worker one is **bytea** (produced by
`SERIALFUNC topn_serialize`, `topn.c:521-554`). That split is the core of the
design.

## Where it diverges from core idioms

### 1. Approximate, lossy aggregation in place of exact `GROUP BY … ORDER BY … LIMIT`

The whole point is to *not* do the exact thing. The honest query is
`SELECT item, count(*) … GROUP BY item ORDER BY 2 DESC LIMIT n`, which is exact
but scans and sorts everything (`README.md:14`). TopN trades exactness for a
fixed-footprint counter table and an eviction rule: `PruneHashTable` sorts the
counters by frequency and **drops everything below a chosen cut index**
(`topn.c:881-920`), keeping only `numberOfRemainingElements` of them
`[verified-by-code]`. Core PG aggregates are exact by contract; an aggregate
that silently discards data once it exceeds `topn.number_of_counters * 3`
counters (`README.md:144`, `UnionFactor = 3` at `topn.c:50`) is a deliberate
break with that contract — accuracy is a tunable, not a guarantee.

### 2. JSONB as the durable aggregate state — the deliberate anti-hll choice

This is the standout divergence and the explicit hll contrast. hll's final
type is an **opaque fixed-size `bytea`-like varlena** (a register array with a
binary header); you cannot read an hll value, and its on-disk bytes are a
private format. TopN instead materializes to **human-readable JSONB**: a
`{"key": frequency, …}` object built by `MaterializeAggStateToJsonb`
(`topn.c:926-951`) which literally `appendStringInfo`s a JSON string and parses
it back with a copy-pasted jsonb parser (`topn.c:1187-1211`)
`[verified-by-code]`. Why pay that cost?

- **Portability / mergeability across nodes.** A JSONB summary is
  self-describing and version-independent — no struct layout, no endianness, no
  ABI to match. That matters for the Citus distributed case
  (`[[knowledge/ideologies/citus]]`): a TopN summary computed on a worker node
  can be shipped to the coordinator and `topn_union`-ed there even across
  heterogeneous binaries. An opaque-bytea state would need byte-compatible
  builds on every node.
- **First-class mergeability.** `topn_union(jsonb, jsonb)` (`topn.c:375-397`)
  rehydrates both JSONBs into HTABs (`MergeJsonbIntoTopnAggState`,
  `topn.c:765-822`), merges, prunes, re-materializes — so any two stored
  summaries combine with a plain SQL operator, no internal handle required.
- The cost: every `topn_add` rebuilds the whole JSONB
  (`topn.c:347-367`) and re-parses on the next call. JSONB-as-state trades CPU
  and re-serialization churn for legibility and node-portability — the opposite
  of hll's "pack it tight, never look inside" stance.

### 3. A split-personality transition state: HTAB in flight, two wire formats out

Core aggregates with an `internal` transition state need a serialize/deserialize
pair *only* to cross a parallel-worker boundary, and that pair round-trips the
*internal* representation. TopN has **two** exit formats from the same
`TopnAggState` HTAB:

- `FINALFUNC topn_pack` → **JSONB** (the user-visible result, `topn.c:644-676`).
- `SERIALFUNC topn_serialize` → **bytea**: a raw `memcpy` of every
  `FrequentTopnItem` struct out of the HTAB into a flat `bytea`
  (`topn.c:521-554`), with `topn_deserialize` reading them straight back
  (`topn.c:560-594`) `[verified-by-code]`.

The serialize path is a flat struct dump — fast, binary, only ever consumed by
a sibling worker in the same query — while the final path is the slow,
portable, legible JSONB. Maintaining two encodings of one state, chosen by
*which boundary the state is crossing* (parallel worker vs. durable result), is
a richer contract than the single serialize/finalize pair core aggregates
usually carry.

### 4. Parallel-safety markings gated behind a PG-version `#if` macro in SQL

TopN must compile its install SQL against PG 9.6 (no parallel aggregation) up
through 17. It does this with an `IFPARALLEL(...)` C-preprocessor macro **inside
the `.sql` file** (`update/topn--2.3.0--2.3.1.sql`): `#if PG_VERSION_NUM <
100000` makes it a no-op, otherwise it expands. On old PGs the whole
`COMBINEFUNC`/`SERIALFUNC`/`DESERIALFUNC`/`PARALLEL = SAFE` block and the
`ALTER FUNCTION … PARALLEL SAFE` statements simply vanish; on new PGs they
arm parallel and Citus partial aggregation `[verified-by-code]`. Running the C
preprocessor over a SQL install script is itself a divergence from the
plain-SQL install-script idiom (`[[knowledge/idioms/catalog-conventions]]`).
Same flavor of version-tax as hll's in-function `#if`s, but pushed into the
catalog wiring.

### 5. Fixed-width keys and a Space-Saving eviction that prunes by frequency

The counter struct is a **fixed 256-byte char key** plus an int64 frequency
(`FrequentTopnItem`, `topn.c:113-117`; `MAX_KEYSIZE 256`, `topn.c:51`), so the
HTAB entries are POD and the bytea serialize path is a clean struct `memcpy`.
Keys longer than 256 bytes are rejected with an error
(`topn.c:712-718, 787-793`). The Space-Saving eviction keeps an inflated
working set (`NumberOfCounters * UnionFactor`, i.e. 3× the requested counters,
`topn.c:453, 817, 997`) and, on overflow, sorts and **drops the bottom half**
(`remainingElements = sizeOfHashTable / 2`, `topn.c:454, 816, 998`)
`[verified-by-code]` — the inflation-then-halve rhythm is what gives the true
top-N its accuracy cushion (`README.md:21`).

## Notable design decisions (cited)

- **`internal` STYPE is a bare HTAB, no wrapper struct.** `TopnAggState` is
  typedef'd but `topnHashtable()` just casts it to `HTAB *` (`topn.c:954-959`);
  the "struct" is the dynahash table itself, allocated in the aggregate memory
  context via `AggCheckCallContext` + `MemoryContextSwitchTo(aggctx)`
  (`topn.c:417-430`) `[verified-by-code]`. This is the standard "internal state
  must live in the agg context, not the per-tuple context" idiom
  (`[[knowledge/idioms/aggregate-trans-state]]`).
- **GUC range is bounded by the JSONB pair limit.** `topn.number_of_counters`
  maxes at `JSONB_MAX_PAIRS` (`topn.c:184`, def'd `topn.c:72`) because the
  state must serialize into a single JSONB object — the storage format caps the
  algorithm's precision knob `[verified-by-code]`.
- **`topn(jsonb, n)` errors if `n > number_of_counters`** (`topn.c:238-242`):
  you cannot ask for more top items than the summary was built to track
  `[verified-by-code]`.
- **Overflow-safe frequency addition.** `IncreaseItemFrequency` saturates at
  `INT64_MAX` rather than wrapping (`topn.c:1009-1021`) `[verified-by-code]` —
  a frequent-items counter that runs for a long time can't silently roll over.
- **A whole jsonb parser is copy-pasted from core** (`topn.c:1040-1211`, marked
  "DISCLAIMER: COPY-PASTED FROM POSTGRES SOURCE CODE") to turn the materialized
  JSON string back into a `jsonb` Datum, with `#if PG_VERSION_NUM` shims around
  `makeJsonLexContextCstringLen`'s changing signature (`topn.c:59-68`)
  `[from-comment]`. Re-implementing `jsonb_in` rather than calling it is the
  price of producing JSONB by string-building instead of by the builder API.
- **`topn_add_trans` outside an aggregate context is a hard error**
  (`AggCheckCallContext`, `topn.c:417-422`, repeated in every trans/serial/
  final fn) `[verified-by-code]` — the `internal`-typed functions refuse to run
  as plain UDFs, the standard guard against an attacker passing a forged
  pointer.

## Links into corpus

- `[[knowledge/ideologies/postgresql-hll]]` — the sibling Citus approximate
  aggregate. Direct contrast: hll uses an opaque fixed-size register-array
  varlena and a planner hook to force GroupAggregate; TopN uses a growable
  JSONB map, no hook, and leans on JSONB's portability for the distributed
  merge. Both pay a PG-version `#if` portability tax.
- `[[knowledge/ideologies/citus]]` — the distributed engine TopN's mergeable
  JSONB state and `COMBINEFUNC`/partial-aggregation wiring target.
- `[[knowledge/idioms/aggregate-partial-finalize]]` — the
  combine/serialize/deserialize/finalfunc machinery TopN implements; TopN's
  twist is two distinct exit formats (JSONB final vs. bytea serial).
- `[[knowledge/idioms/aggregate-trans-state]]` — the `internal` STYPE living in
  the aggregate memory context.
- `[[knowledge/idioms/aggregate-hash-vs-sort]]` — why a large per-group
  transition state interacts with HashAggregate (the cliff hll hooks the planner
  to avoid; TopN keeps its state bounded by pruning instead).
- `[[knowledge/idioms/fmgr]]` — the `PG_FUNCTION_INFO_V1` / `PG_GETARG_*` /
  set-returning-function (`SRF_*`) entry points the extension is built from.
- `[[knowledge/idioms/catalog-conventions]]` — `CREATE AGGREGATE` /
  `CREATE OPERATOR` wiring, and the unusual C-preprocessed install SQL.
- `.claude/skills/parallel-query/SKILL.md` — `PARALLEL SAFE` markings and the
  serialize/deserialize boundary.

## Sources

Fetched 2026-06-30 (branch `master`, `default_version = '2.7.0'`). The base
install SQL `update/topn--2.0.0.sql` declares the aggregates WITHOUT
combine/serialize/deserialize; the parallel-safe machinery (`COMBINEFUNC`,
`SERIALFUNC`, `DESERIALFUNC`, `PARALLEL = SAFE`) was added in
`update/topn--2.3.0--2.3.1.sql` and all later `update/*.sql` increments
(2.3.1→2.7.0) are version-bump no-ops (verified by fetching each).

- `https://raw.githubusercontent.com/citusdata/postgresql-topn/master/README.md`
  @ 2026-06-30 → HTTP 200 (7.7 KB, 150 lines).
- `https://raw.githubusercontent.com/citusdata/postgresql-topn/master/topn.control`
  @ 2026-06-30 → HTTP 200 (109 bytes; `default_version = '2.7.0'`,
  `comment = 'type for top-n JSONB'`).
- `https://raw.githubusercontent.com/citusdata/postgresql-topn/master/topn.c`
  @ 2026-06-30 → HTTP 200 (31 KB, 1228 lines) — THE core: aggregate trans/
  combine/serial/deserial/final fns, the HTAB-as-`internal`-state, the
  Space-Saving prune, the JSONB materializer + copy-pasted parser, the GUC.
- `https://raw.githubusercontent.com/citusdata/postgresql-topn/master/update/topn--2.0.0.sql`
  @ 2026-06-30 → HTTP 200 (base aggregate + operator declarations, no parallel
  machinery).
- `https://raw.githubusercontent.com/citusdata/postgresql-topn/master/update/topn--2.0.0--2.1.0.sql`
  @ 2026-06-30 → HTTP 200 (`topn` becomes a SETOF `topn_record` SRF).
- `https://raw.githubusercontent.com/citusdata/postgresql-topn/master/update/topn--2.3.0--2.3.1.sql`
  @ 2026-06-30 → HTTP 200 — the parallel-aggregation upgrade: adds
  `topn_serialize`/`topn_deserialize`/`topn_union_internal`, the `IFPARALLEL`
  macro, and re-creates both aggregates with `PARALLEL = SAFE`.
- `update/topn--2.1.0--2.2.0.sql`, `--2.2.0--2.2.1`, `--2.2.1--2.2.2`,
  `--2.2.2--2.3.0`, `--2.3.1--2.4.0`, `--2.4.0--2.5.0`, `--2.5.0--2.6.0`,
  `--2.6.0--2.7.0` @ 2026-06-30 → HTTP 200 each (all version-bump no-ops).
- Tree listing
  `https://api.github.com/repos/citusdata/postgresql-topn/git/trees/master?recursive=1`
  @ 2026-06-30 → HTTP 200 (the C file is `topn.c` at repo root; the `sql/` dir
  holds regress fixtures, `update/` holds install + upgrade scripts).

All cites into `topn.c` — the GUC registration, the `internal`-as-HTAB
transition state, the JSONB materialize-via-string-build, the bytea struct-dump
serialize path, the Space-Saving prune-bottom-half eviction, and the saturating
frequency add — are `[verified-by-code]` against the fetched file. The
Space-Saving accuracy claim (inflate to `100*N` so the true top-N rarely evicts)
and the "think of TopN as hll's cousin" framing are `[from-README]`.
