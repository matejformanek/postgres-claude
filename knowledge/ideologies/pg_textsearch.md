# pg_textsearch — a BM25 index AM that returns corpus-statistic-ranked rows through an ORDER BY operator, where core FTS is stateless per-row

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `timescale/pg_textsearch` @ branch `main` (internal/historical name
> "Tapir"; symbol prefix `tp_`). All `file:line` cites below point into that
> repo (not `source/`), since this doc characterizes an *external* extension's
> divergence from core idioms. Cites verified against the files fetched on
> 2026-06-12 (see Sources footer). Depth note: the C is a large tree
> (`src/{access,scoring,segment,memtable,index,planner,types}`); this doc
> deep-reads the index-AM core (`access/handler.c`, `access/scan.c`,
> `access/build.c`), the scorer (`scoring/bm25.c`, `scoring/bmw.c`), the
> metapage (`index/metapage.c`), `mod.c`, and the install SQL. The segment
> codec, memtable spill mechanics, and compaction were skimmed, not audited.
> Read alongside `[[knowledge/ideologies/paradedb]]` (the other in-PG BM25
> index AM), `[[knowledge/ideologies/pgvector]]` (the score-via-AM pattern),
> and core's GIN + `tsvector`/`ts_rank` FTS.

## Domain & purpose

pg_textsearch "provid[es] BM25-based full-text search with configurable ranking
parameters" (`README.md`, Overview) `[from-README]`. The user writes
`CREATE INDEX ... USING bm25 (content) WITH (text_config='english', k1=1.5,
b=0.8)` and queries with `ORDER BY content <@> 'search terms' LIMIT k`
(`README.md`, Syntax) `[from-README]`. The reason to document it: it is a clean
worked example of the divergence between **core PostgreSQL FTS — stateless per
row** (a `tsvector` is computed and ranked from one tuple; `ts_rank` sees no
corpus) — **and BM25, a corpus-statistics ranking model** needing global
term/document frequencies and an average document length. pg_textsearch bolts a
stateful, corpus-aware IR ranker onto PG by building a custom inverted index AM
that *materializes* those corpus statistics in an index metapage and returns rows
pre-ranked through an `ORDER BY` operator — the trick pgvector uses for distance.
It is the Timescale sibling of `[[knowledge/ideologies/paradedb]]`'s `pg_search`
(both expose `CREATE INDEX ... USING bm25`), but where ParadeDB embeds a Tantivy
(Lucene-family) engine, pg_textsearch implements the inverted index, posting
lists, and BM25 scorer in C directly against PG's buffer/WAL machinery.

## How it hooks into PG

A lazy-loaded extension (no `shared_preload_libraries` required for the AM
itself): `PG_MODULE_MAGIC` declares "1.4.0-dev" (`src/mod.c:28-31`)
`[verified-by-code]`. `relocatable = false`, `module_pathname =
'$libdir/pg_textsearch'`, `comment = 'Full-text search with BM25 ranking'`
(`pg_textsearch.control`) `[verified-by-code]`.

- **Custom index access method.** `tp_handler(internal) RETURNS
  index_am_handler` is registered via `CREATE ACCESS METHOD bm25 TYPE INDEX
  HANDLER tp_handler` (`sql/pg_textsearch--1.4.0-dev.sql:13-15`)
  `[verified-by-code]`. The handler builds an `IndexAmRoutine` with
  `ambuild = tp_build`, `aminsert = tp_insert`, `ambeginscan = tp_beginscan`,
  `amgettuple = tp_gettuple` (`src/access/handler.c:90-101`) `[verified-by-code]`.
- **The capability flags are the whole story.** `amcanorderbyop = true` and
  `amconsistentordering = true`, while `amcanorder = false`, `amgetbitmap =
  NULL`, `amcanbackward = false`, `amcanmulticol = false`, `amoptionalkey =
  true`, `amcanbuildparallel = true` (`src/access/handler.c:54-81`)
  `[verified-by-code]`. So this AM does **not** enforce a natural index order
  and does **not** do bitmap scans; it only knows how to stream tuples in the
  order requested by an `ORDER BY` operator — exactly pgvector's HNSW profile.
- **The operator + opclass.** `<@>` is `(text, bm25query) → float4` backed by
  `bm25_text_bm25query_score` (`sql/...--1.4.0-dev.sql:131-135`), bound into the
  opclass as `OPERATOR 1 <@> FOR ORDER BY float_ops` plus `FUNCTION 8`
  (`...:155-160`) `[verified-by-code]`. `FOR ORDER BY float_ops` is what tells
  the planner this is a distance-style ordering operator, not a boolean filter.
- **The query type.** `bm25query` is a real base type (`bm25query_in/out/recv/
  send`, `STORAGE = extended`, `ALIGNMENT = int4`, `...:75-85`) produced by
  `to_bm25query(text)` or `to_bm25query(text, index_name)` (`...:88-96`)
  `[verified-by-code]`. The two-arg form embeds the target index OID so partial
  and ambiguous-index queries can name their index explicitly (`README.md`,
  partial-index note) `[from-README]`.
- **Score-passing mechanism.** `tp_gettuple` runs the scoring query, then for
  each result row sets `scan->xs_orderbyvals[0] = Float4GetDatum(bm25_score)`
  with `xs_recheckorderby = false` (`src/access/scan.c:348-354`)
  `[verified-by-code]`. The score is **negated** —
  `bm25_score = (raw_score > 0) ? -raw_score : raw_score` (`scan.c:351`) — so
  ascending sort surfaces the best matches first (`README.md`: "returns negative
  BM25 scores ... Lower values indicate better matches") `[from-README]`.
- **GUCs + object-access hook.** `_PG_init` defines ~12 GUCs including
  `pg_textsearch.default_limit` (1000), `compress_segments`, `segments_per_level`
  (8), `bulk_load_threshold`, `memtable_pages_threshold`, `memory_limit`
  (`src/mod.c:205-373`) `[verified-by-code]`, and installs `tp_object_access` to
  catch `DROP` of registered indexes for cleanup (`src/mod.c:391-410`)
  `[verified-by-code]`.

Cross-ref `.claude/skills/access-method-apis/SKILL.md`,
`.claude/skills/wal-and-xlog/SKILL.md`, `.claude/skills/gucs-bgworker-parallel/SKILL.md`.

## Where it diverges from core idioms

### 1. Ranking is corpus-stateful — the index materializes N, doc-frequency, and avgdl that core FTS never keeps

This is the central divergence. Core FTS is **per-row**: `to_tsvector` turns one
document into lexeme positions, and `ts_rank` ranks from that single `tsvector`
plus a query — it has no notion of how many documents exist or how common a term
is across the corpus. BM25 cannot be computed that way: its IDF term needs the
total document count `N` and each term's document frequency `df`, and its
length-normalization needs the corpus average document length `avgdl`.
pg_textsearch keeps all of this **in the index metapage**: `total_docs`,
`total_len`, segment `level_heads`/`level_counts`, memtable chain pointers, and
`text_config_oid` (`src/index/metapage.c:27-48`) `[verified-by-code]`. The IDF
is `log(1 + (N - df + 0.5)/(df + 0.5))` (`src/scoring/bm25.c:20-29`), and the
scorer reads `metap->total_docs`/`metap->total_len` and computes `avgdl =
total_len / total_docs` (`bm25.c:112-126`); per-term `df` is a batched lookup
unified across the memtable and disk segments (`bm25.c:158-162`)
`[verified-by-code]`. So the index is not just an access path — it is the
*statistical state* the ranker depends on, which core's `ts_rank` never needs and
core's GIN never keeps.

### 2. Its own inverted index (posting lists + LSM segments + on-disk memtable), not core GIN

Core ranked FTS is GIN over `tsvector` plus a post-scan `ts_rank` sort.
pg_textsearch ships a bespoke inverted index instead: an L0 **memtable** that
"resides on-disk as a chain of doc-record pages within the index relation
itself," spilled into immutable **segments** organized "in multiple segments
across levels (similar to LSM trees)" with `segments_per_level` before automatic
compaction (`README.md`, Architecture/LSM) `[from-README]`. The metapage's
`memtable_head_blkno`/`memtable_tail_blkno` and `level_heads[]`/`level_counts[]`
arrays are the on-page realization of that LSM structure
(`src/index/metapage.c:38-48`) `[verified-by-code]`. This is an LSM write path
(buffer writes, periodic compaction) grafted onto a system whose native AMs
(B-tree, GIN) are update-in-place B+-tree-family structures — a different storage
philosophy living inside one index relation. Compaction is synchronous on
memtable spill, not a background worker (`README.md`, Limitations) `[from-README]`.

### 3. Scores flow to `ORDER BY` via `xs_orderbyvals` — the pgvector trick, not a post-sort

Core ranked FTS computes `ts_rank(...)` as an ordinary expression in the target
list and lets the executor `Sort` node order by it; the GIN index only filters.
pg_textsearch instead declares `<@>` a `FOR ORDER BY float_ops` operator
(`sql/...--1.4.0-dev.sql:155-160`) and has the AM *return rows already ranked*,
handing the per-row score back through `scan->xs_orderbyvals[0]`
(`src/access/scan.c:348-354`) `[verified-by-code]`. This is structurally
identical to `[[knowledge/ideologies/pgvector]]`'s `ORDER BY embedding <-> q LIMIT
k`: the relevance/distance value is produced by the index, not recomputed by a
Sort. The consequence is that `LIMIT` is load-bearing — `ORDER BY ... LIMIT n`
activates Block-Max WAND top-k (below), and without a `LIMIT` the scan only
scores up to `pg_textsearch.default_limit` (1000) documents (`README.md`,
Ordering) `[from-README]`, with the scan dynamically doubling its internal limit
(`new_limit = so->max_results_used * 2`, capped at `TP_MAX_QUERY_LIMIT`) when
results exhaust (`src/access/scan.c:328-334`) `[verified-by-code]`.

### 4. Block-Max WAND top-k retrieval — an IR algorithm core's executor has no analogue for

To make `ORDER BY <@> LIMIT k` cheap, pg_textsearch implements **Block-Max WAND**:
a min-heap of the current top-k, plus pivot selection that walks terms sorted by
doc id accumulating max scores until the sum exceeds the heap threshold
(`src/scoring/bmw.c:1281-1289`), and block-level skipping that calls
`block_max_skip_advance()` to jump a term iterator past a posting block whose
upper-bound score cannot beat the threshold (`bmw.c:1327-1340`)
`[verified-by-code]`. This is a classic IR retrieval optimization (skip
posting-list blocks that cannot enter the top-k) with no counterpart in core's
GIN-scan-then-Sort path. It is the reason this AM *needs* `amcanorderbyop` rather
than `amgetbitmap`: the ranking and the early-termination are inseparable from the
scan.

### 5. Tokenization reuses core, but ranking does not — a partial divergence

Unlike the storage and ranking, the *tokenizer* is deliberately core: `tp_build`
→ `tp_tokenize_text` calls `to_tsvector_byid` via `DirectFunctionCall2Coll`
keyed by the index's `text_config_oid` (`src/access/build.c:912`)
`[verified-by-code]`, so stemming, stop-words, and lexeme normalization come from
the same `text search configuration` core FTS uses. It therefore inherits core's
2047-char word-length cap and the default parser's CJK behavior
(`README.md`, Tokenization) `[from-README]`, and chunks documents over the 1 MB
lexeme-dictionary cap into 256 KB segments merging term frequencies
(`README.md`, Large Document Handling) `[from-README]`. The divergence is narrow
and surgical: it borrows core's *lexical analysis* but replaces core's *ranking
function and index*. Build accumulates `total_docs`/`total_len` per batch and
writes them to the metapage (`src/access/build.c:1116-1173`) `[verified-by-code]`.

### 6. WAL/locking: GenericXLog instead of a custom rmgr — the opposite choice from ParadeDB

The v1.3.0+ memtable "operates under standard buffer locks with WAL logging via
`GenericXLog`," explicitly eliminating shared-memory memtables, custom WAL
resource managers, and docid-page recovery scaffolding; crash recovery is plain
WAL replay needing no extension code loaded (`README.md`, Memtable Design)
`[from-README]`. Metapage mutations must be wrapped in a `GenericXLog` record by
callers (`src/index/metapage.c:68-69, 113`) `[from-comment]`. This is a pointed
contrast with `[[knowledge/ideologies/paradedb]]`, which registers a **custom
rmgr** for its Tantivy segments — pg_textsearch deliberately stays on the
`GenericXLog` path so streaming replication and PITR work with zero bespoke redo
code, at the cost of `GenericXLog`'s full-page-delta overhead.

## Notable design decisions (cited)

- **`<@>` is one operator, two right-hand forms.** Implicit `'terms'` (text
  literal, auto-coerced) and explicit `to_bm25query('terms','index_name')`; the
  scan reads `orderby->sk_subtype` to tell which it got and extracts either the
  plain text or the `TpQuery`'s index OID + text (`src/access/scan.c:82-126`)
  `[verified-by-code]`. The implicit form does not work inside PL/pgSQL — use the
  explicit `to_bm25query()` (`README.md`, Limitations) `[from-README]`.
- **BM25 params are per-index, set at `CREATE INDEX`.** `k1` (1.2) and `b` (0.75)
  are index `WITH` options, threaded through the scorer signature
  (`src/scoring/bm25.c:89-96`) `[verified-by-code]` — so tuning saturation and
  length-normalization is an index property, not a query argument.
- **Partition-local statistics, by design.** On partitioned tables each
  partition keeps its own corpus stats, so "scores ... are not directly
  comparable across partitions" (`README.md`, Limitations) `[from-README]` — a
  direct consequence of divergence #1 (the stats live in each index's metapage).
- **No phrase queries / no positions.** Positions are not stored; phrase search
  is left to an `ILIKE` post-filter (`README.md`, Limitations) `[from-README]`.
- **Bulk-load tuning surface.** `bulk_load_threshold` (terms/txn) and
  `memtable_pages_threshold` drive auto-spill; `bm25_force_merge('idx')`
  consolidates segments post-load; parallel builds need `maintenance_work_mem >=
  64MB` (`README.md`, Tuning; `src/mod.c:257-285`) `[from-README]`/`[verified-by-code]`.
- **`amcanbuildparallel = true`** (`src/access/handler.c:62`) with a dedicated
  `build_parallel.c` — parallel inverted-index build, which core GIN gained only
  relatively recently.

## Links into corpus

- `[[knowledge/ideologies/paradedb]]` — the OTHER in-PG BM25 index AM (`CREATE
  INDEX ... USING bm25`). Compare/contrast: ParadeDB embeds a Tantivy/Lucene
  engine in PG pages with a **custom rmgr**; pg_textsearch writes the inverted
  index, posting codec, and BM25/BMW scorer in C and rides **GenericXLog**.
  Different stacks, same opclass-as-ranking-operator hook.
- `[[knowledge/ideologies/pgvector]]` — the canonical score-via-index-AM pattern:
  `ORDER BY col <op> q LIMIT k` with `amcanorderbyop`, the operator's value handed
  back through `xs_orderbyvals`. pg_textsearch is the FTS instance of the same
  mechanism (BM25 score where pgvector has distance).
- `[[knowledge/ideologies/zombodb]]` — contrast: zombodb *delegates* FTS to a
  remote Elasticsearch cluster through the index-AM API and bypasses local
  storage; pg_textsearch keeps the inverted index inside PG pages and computes
  BM25 locally. Both are index-AM-as-search-engine, one remote, one embedded.
- `[[knowledge/architecture/access-methods]]` — the `IndexAmRoutine` /
  opclass / strategy machinery all three extensions plug into; the
  `amcanorderbyop` + `FOR ORDER BY` path specifically.
- `.claude/skills/access-method-apis/SKILL.md` — `ambuild`/`aminsert`/
  `amgettuple` wiring, ORDER-BY operator opclasses, `xs_orderbyvals`.
- `.claude/skills/wal-and-xlog/SKILL.md` — the `GenericXLog` choice for the
  on-disk memtable and metapage updates.
- core GIN + `tsvector`/`ts_rank` — the stateless per-row FTS this diverges from.

## Anthropology takeaway

pg_textsearch is the corpus's sharpest illustration that **ranking model dictates
where state must live**. Core FTS is stateless per row because `ts_rank` is a
local function; adopting BM25 — *defined* over corpus statistics (N, df, avgdl) —
forces you to materialize and maintain those statistics somewhere, and that
somewhere becomes the index itself (the metapage, `src/index/metapage.c:27-48`).
Every other divergence cascades: you need your own inverted index for posting
lists and per-term df (not GIN); Block-Max WAND to make top-k cheap (not a
post-Sort); `amcanorderbyop` + `FOR ORDER BY` to return ranked rows with scores
(`xs_orderbyvals`, the pgvector pattern); and partition-local stats fall out as a
caveat. It is the "score-producing index AM" shape pgvector pioneered, applied to
IR instead of ANN, and a clean foil to ParadeDB: same `USING bm25` surface, two
opposite bets — hand-write the IR engine on GenericXLog (Timescale) vs embed
Tantivy on a custom rmgr (ParadeDB). For a future `knowledge/issues` note, the
load-bearing `LIMIT` and the `default_limit=1000` silent cap are a "the index
only ranks the top-k; everything past the cap is invisible to ORDER BY" gotcha
worth flagging next to pgvector's `ivfflat` probe-count recall caveat.

## Sources

Fetched 2026-06-12 (branch `main`). GitHub REST tree API (`api.github.com/...`)
returned **HTTP 403** via the fetch tool; directory listings were recovered from
the GitHub HTML tree pages (`github.com/.../tree/...`, HTTP 200) instead, and all
source bodies from `raw.githubusercontent.com` (HTTP 200).

- `https://api.github.com/repos/timescale/pg_textsearch/git/trees/main?recursive=1`
  @ 2026-06-12 → HTTP 403 (blocked; substituted HTML tree pages below).
- `https://github.com/timescale/pg_textsearch/tree/main/{src,src/access,src/scoring,src/index,src/types,sql}`
  @ 2026-06-12 → HTTP 200 each (directory listings only).
- `https://raw.githubusercontent.com/timescale/pg_textsearch/main/README.md`
  @ 2026-06-12 → HTTP 200 (read in full; the primary `[from-README]` source).
- `.../main/pg_textsearch.control` @ 2026-06-12 → HTTP 200 (small; comment +
  module path + relocatable).
- `.../main/src/mod.c` @ 2026-06-12 → HTTP 200 (deep-read: `_PG_init`, GUCs,
  object-access hook, module magic).
- `.../main/src/access/handler.c` @ 2026-06-12 → HTTP 200 (deep-read:
  `IndexAmRoutine` flags + callback wiring).
- `.../main/src/access/scan.c` @ 2026-06-12 → HTTP 200 (deep-read: `tp_gettuple`,
  `xs_orderbyvals`, negation, limit doubling, orderby parsing).
- `.../main/src/access/build.c` @ 2026-06-12 → HTTP 200 (deep-read: tokenization
  via `to_tsvector_byid`, stats accumulation to metapage).
- `.../main/src/scoring/bm25.c` @ 2026-06-12 → HTTP 200 (deep-read: IDF formula,
  k1/b, metapage stats read, avgdl).
- `.../main/src/scoring/bmw.c` @ 2026-06-12 → HTTP 200 (skim-read: BMW top-k heap,
  pivot, block-max skip).
- `.../main/src/index/metapage.c` @ 2026-06-12 → HTTP 200 (deep-read: metapage
  struct fields, GenericXLog notes).
- `.../main/sql/pg_textsearch--1.4.0-dev.sql` @ 2026-06-12 → HTTP 200 (read for
  `CREATE ACCESS METHOD`, operator/opclass, `bm25query` type, `to_bm25query`).
  Initial guess `sql/pg_textsearch--1.0.sql` was **404** — the base install file
  for `main` is the dev-versioned `--1.4.0-dev.sql` (substituted).

Cites tagged `[verified-by-code]` rest on the fetched C/SQL bodies above;
`[from-README]` claims (LSM/compaction internals, GenericXLog recovery story,
partition-local stats, large-doc chunking, limitations) rest on the README, which
is detailed but is author documentation, not code. The segment codec, memtable
spill finalization, and compaction paths were not opened — claims about *that*
they form an LSM with synchronous compaction are `[from-README]`, not audited.
