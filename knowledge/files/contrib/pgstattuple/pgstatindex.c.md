# pgstatindex.c

Covers `source/contrib/pgstattuple/pgstatindex.c` (811 lines): the
index-stat side of pgstattuple — `pgstatindex` (B-tree),
`pgstatginindex`, `pgstathashindex`, and `pg_relpages` (any AM with
storage).

## One-line summary

Three index-specific full-scan stat functions (B-tree, GIN
metapage-only, hash full-scan) plus a generic `pg_relpages` that
returns the number of blocks of any relation with storage. All have
v1.5 entry points that drop the C `superuser()` check and rely on
the `pg_stat_scan_tables` grant.

## Public API / entry points

- `pgstatindex(text)` / `pgstatindex_v1_5(text)` —
  `source/contrib/pgstattuple/pgstatindex.c:143` / `:168`. Pre-1.5
  has superuser check.
- `pgstatindexbyid(regclass)` / `pgstatindexbyid_v1_5(regclass)` —
  `:186` / `:203`.
- `pg_relpages(text)` / `pg_relpages_v1_5(text)` — `:413` / `:432`.
- `pg_relpagesbyid(regclass)` / `pg_relpagesbyid_v1_5(regclass)` —
  `:446` / `:463`.
- `pgstatginindex(regclass)` / `pgstatginindex_v1_5(regclass)` —
  `:503` / `:517`. **GIN: metapage-only, no full-scan.**
- `pgstathashindex(regclass)` — `:608`. **No v1.5 variant** — added
  later (per `pgstattuple--1.4--1.5.sql`, hash stats are part of
  1.5 from inception, no need for a pre-1.5 entry point with
  superuser check). Has `REVOKE / GRANT` to
  `pg_stat_scan_tables`.
- Internal helpers:
  - `pgstatindex_impl` — `:213` (the B-tree workhorse).
  - `pg_relpages_impl` — `:473`.
  - `pgstatginindex_internal` — `:524`.
  - `GetHashPageStats` — `:793`.

## Key invariants

- INV-1: Same predefined-role pattern as `pgstattuple.c`. v1.5+
  entries have NO C-level check; pre-1.5 entries have hardcoded
  `superuser()` to handle the "library-upgraded-but-extension-not"
  case [verified-by-code; comments at `:138, :161, :180, :409,
  :444, :499`].
- INV-2: B-tree-specific (`pgstatindex`): `IS_INDEX(rel) AND
  IS_BTREE(rel)` (`:225-229`). GIN-specific (`:544`), hash-specific
  (`:634`).
- INV-3: `indisvalid` required for all index stats (`:247-251,
  :561-565, :651-655`) — "A !indisready index could lead to
  ERRCODE_DATA_CORRUPTED later, so exit early" (`:241-246` comment).
- INV-4: Non-local temp rejection (`:236, :555, :645`).
- INV-5: Partitioned-index ban via `relation_open` (not
  `index_open`) at `:542, :632` — comment at `:538-541, :629-631`:
  "the latter allows partitioned indexes, and these are forbidden
  here." Same trick as `hashfuncs.c:421-422`.
- INV-6: Read-stream-based batched reads in B-tree and hash scans
  (`:292-299, :681-688`), using `READ_STREAM_FULL |
  READ_STREAM_USE_BATCHING` with `block_range_read_stream_cb`.
  Safe because the callback takes no locks (comments at `:288-291,
  :677-680`).

## Notable internals

**Three different scan shapes.**
- **pgstatindex (B-tree)**: full scan of pages 1..nblocks, classify
  each via `BTPageOpaque` flags into deleted/empty/leaf/internal,
  sum `PageGetExactFreeSpace` for leaves, count fragmentation
  (`opaque->btpo_next < blkno` means a backward link →
  fragmented).
- **pgstatginindex**: reads ONLY the metapage. Returns
  (version, pending_pages, pending_tuples). Cheap; no full scan.
- **pgstathashindex**: full scan including bucket / overflow /
  bitmap pages. Classifies via `LH_PAGE_TYPE`. Per-page detail via
  `GetHashPageStats` (counts live/dead items, sums free space).

**Read-stream + batchmode.** `:292-299, :681-688`: the
`block_range_read_stream_cb` is `READ_STREAM_USE_BATCHING`-safe
because it just hands back sequential block numbers and never
acquires locks. The actual `LockBuffer(BUFFER_LOCK_SHARE)` happens
in the consumer loop (`:310, :698`). Pattern recently added — the
in-tree `read_stream` API is for batched async I/O.

**Fragmentation metric.** `:339-340`: an leaf page is "fragmented"
if its `btpo_next` (the right-sibling link) points to a LOWER
block number than itself. The fragments percentage is reported in
the result (`:387-390`).

**`max_avail` computation.** `:329`: `BLCKSZ - (BLCKSZ -
pd_special + SizeOfPageHeaderData)` — i.e. the bytes available
between the page header and the special area. Used to compute
the "avg_leaf_density" percentage at `:381-385`.

**`pg_relpages` is the cheap escape hatch.** `:413-492`: just opens
the relation under `AccessShareLock` and returns
`RelationGetNumberOfBlocks`. Works on ANY relation with storage
(not just heap, not just indexes). Cost: O(1) — no scan.

**No read-stream for GIN.** `pgstatginindex` is metapage-only so it
just does `ReadBuffer + LockBuffer(GIN_SHARE)` (`:570-571`). The
metapage holds all the stats GIN exposes — `nPendingPages`,
`nPendingHeapTuples`, `ginVersion`. The whole rest of the index
isn't touched.

**Per-AM corruption checks in hash.** `:702-709, :733-737`: if a
hash page has wrong special-space size OR an unknown page-type,
`ereport(ERROR, ERRCODE_INDEX_CORRUPTED)`. This is stronger than
the heap-side equivalent in `pgstattuple.c` (which silently treats
corrupted as "maybe corrupted" with no errror — see
`pgstattuple.c:493-494`).

## Trust boundary / Phase D surface

**Same predefined-role discipline as `pgstattuple.c`.** Members of
`pg_stat_scan_tables` (and therefore `pg_monitor`) can run these
functions on any relation. Layered correctly: REVOKE FROM PUBLIC,
GRANT TO pg_stat_scan_tables, in
`pgstattuple--1.4--1.5.sql` lines 36-37 (pgstatindex), 56-57
(pgstatginindex), 91-92 (pgstatindex regclass), 135-136
(pgstathashindex).

**RLS implications via index stats.** Index size + leaf count +
fragmentation tells `pg_stat_scan_tables` members:
- Approximate row count of an RLS-protected table (via leaf-page
  density × leaf count).
- Index health (fragmentation %).
- Hash-collision distribution (via overflow page counts).

These are aggregate metrics, not raw values. Lower-impact than the
row-count leak in `pgstattuple.c`, but still informative.
**[ISSUE-security: pgstatindex leaf-count + density let
`pg_stat_scan_tables` members estimate row counts of RLS-protected
tables (maybe; less direct than pgstattuple proper)]** —
`source/contrib/pgstattuple/pgstatindex.c:325-345`.

**Hash-table page corruption errors out under
ERRCODE_INDEX_CORRUPTED.** `:702-709`. Good defense — a corrupted
index page is reported to the caller rather than silently producing
garbage stats. Compare `pgstattuple.c:455-497` (hash) which has a
`/* maybe corrupted */` empty fall-through. Inconsistent across the
module.
**[ISSUE-defense-in-depth: pgstatindex hash scan errors on
corruption; pgstattuple's pgstat_hash_page silently swallows the
same condition — same module, two policies (nit)]** —
`source/contrib/pgstattuple/pgstatindex.c:702-709` vs
`source/contrib/pgstattuple/pgstattuple.c:491-494`.

**Cost amplification.** Full B-tree and hash scans on a huge index
have the same DoS profile as `pgstattuple` proper. `pgstatginindex`
is exempt (metapage only). `pg_relpages` is exempt (O(1)).

**GIN pending-list leak.** `pgstatginindex` exposes
`nPendingHeapTuples` — the count of heap tuples whose GIN entries
are still in the pending list. For an RLS-protected table, this
leaks "how many rows were recently inserted but not yet folded into
the index", which is a side-channel into write rates.
**[ISSUE-security: pgstatginindex pending-list count leaks recent
insert rate of RLS-protected tables (nit; aggregate info)]** —
`source/contrib/pgstattuple/pgstatindex.c:577`.

**`LockRelationForExtension` NOT used here.** Unlike
`pgstattuple.c:552-554` which holds an extension lock while
counting blocks, `pgstatindex_impl` and `pgstathashindex` just call
`RelationGetNumberOfBlocks` directly (`:282, :666`). Inconsistent
with the same-module pattern. Likely a latent bug if a concurrent
index extension races, but in practice index extension is rare
during stat reads.
**[ISSUE-concurrency: pgstatindex.c does not take
LockRelationForExtension before counting blocks, unlike
pgstattuple.c — inconsistent treatment, may race with concurrent
extension (nit)]** — `:282, :666`.

**Partitioned-index ban.** Good. Stops accidental whole-tree scans
when called on a partitioned index parent.

## Cross-references

- `source/src/include/access/nbtree.h` — `BTMetaPageData`,
  `BTPageOpaque`, `P_ISDELETED`/`P_IGNORE`/`P_ISLEAF` macros.
- `source/src/include/access/hash.h` — `HashMetaPage`,
  `LH_PAGE_TYPE` constants.
- `source/src/include/access/gin_private.h` — `GinMetaPageData`.
- `source/src/backend/storage/aio/read_stream.c` — the
  `read_stream` API used here.
- `knowledge/files/contrib/pgstattuple/pgstattuple.c.md` — the
  sister file; same predefined-role pattern.
- `knowledge/files/contrib/pgstattuple/pgstatapprox.c.md` — the
  VM-skip heap-stats alternative.

<!-- issues:auto:begin -->
- [Issue register — `pgstattuple`](../../../issues/pgstattuple.md)
<!-- issues:auto:end -->

## Issues spotted

- **[ISSUE-security: pgstatindex leaf metrics enable row-count
  estimation of RLS-protected tables (maybe)]** —
  `source/contrib/pgstattuple/pgstatindex.c:325-345`.
- **[ISSUE-security: pgstatginindex pending-list count leaks
  recent-insert rate of RLS-protected tables (nit)]** — `:577`.
- **[ISSUE-defense-in-depth: pgstatindex hash scan errors on
  corruption while pgstattuple's hash path silently swallows; same
  module, two policies (nit)]** — `:702-709`.
- **[ISSUE-concurrency: no LockRelationForExtension around
  RelationGetNumberOfBlocks; inconsistent with pgstattuple.c
  (nit)]** — `:282, :666`.
- **[ISSUE-security: full B-tree/hash index scans are cost-
  amplification vectors (likely; same as pgstattuple)]** —
  `:301-346, :690-740`.
- **[ISSUE-api-shape: pgstathashindex has no v1.5 alias because
  hash stats are new in 1.5; means upgrading from 1.4 → 1.5
  changes the function set; pre-1.5 callers will not have this
  symbol (nit; documented in extension control files)]**.
- **[ISSUE-correctness: GIN pending-list stats reflect a moment in
  time; concurrent inserts immediately invalidate (nit)]** — `:574-577`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pgstattuple.md](../../../subsystems/contrib-pgstattuple.md)
