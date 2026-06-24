---
source_url: https://www.postgresql.org/docs/current/pageinspect.html
fetched_at: 2026-06-23T00:00:00Z
anchor_sha: 9a60f295bcb1
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — pageinspect (low-level page inspection)

`pageinspect` is the SQL window onto raw on-disk page bytes — the contrib
module a backend hacker reaches for to confirm what's *actually* in a heap or
index page, independent of MVCC visibility. Every function is **superuser-only**
(the raw bytes bypass all row-level protection). The standard idiom is
`get_raw_page()` to grab a `bytea` block, then a decoder over that `bytea`.
`[from-docs]`

## The entry point: get_raw_page + page_header

- `get_raw_page(relname text, fork text, blkno bigint) returns bytea` — reads
  one 8KB block from a named fork. `fork` ∈ `'main'` / `'fsm'` / `'vm'` /
  `'init'`. A 2-arg shorthand `get_raw_page(relname, blkno)` defaults to
  `'main'`. Returns a time-consistent copy of the block. `[from-docs]`
- `page_header(page bytea) returns record` decodes the `PageHeaderData` struct
  common to **all** heap and index pages: `lsn, checksum, flags, lower, upper,
  special, pagesize, version, prune_xid`. The `checksum` field shown is whatever
  is stored on the page (may be wrong if the page is corrupt; meaningless if
  data checksums are disabled). `[from-docs]` Struct ref:
  `source/src/include/storage/bufpage.h`. `[from-docs]`
- `page_checksum(page bytea, blkno bigint) returns smallint` recomputes the
  checksum — and the checksum **depends on the block number**, so you must pass
  the same `blkno` you read the page from, or the result is garbage. `[from-docs]`
- `fsm_page_contents(page bytea) returns text` walks the FSM binary-tree nodes
  (one line per non-zero node, plus the "next" slot pointer). Ref:
  `source/src/backend/storage/freespace/README`. `[from-docs]`

## Heap decoding — the infomask is the whole game

- `heap_page_items(page bytea) returns setof record` lists **every** line
  pointer on a heap page, plus tuple headers + raw data for in-use pointers —
  regardless of MVCC visibility. This is *the* function for "is this tuple
  dead/frozen/HOT-updated?" forensics. Returns `t_infomask` / `t_infomask2`
  among the per-tuple columns. `[from-docs]` Refs:
  `source/src/include/storage/itemid.h` (line pointers),
  `source/src/include/access/htup_details.h` (tuple header). `[from-docs]`
- `heap_tuple_infomask_flags(t_infomask integer, t_infomask2 integer) returns
  record` is the human-readable decoder: `raw_flags` (individual bit names) +
  `combined_flags` (macro-level composites like `HEAP_XMIN_FROZEN`, which is two
  bits together). Feed it the columns from `heap_page_items()`. `[from-docs]`
- `tuple_data_split(rel_oid oid, t_data bytea, t_infomask int, t_infomask2 int,
  t_bits text [, do_detoast bool]) returns bytea[]` splits a tuple's raw
  `t_data` into per-attribute `bytea`s using exactly the `heap_page_items()`
  return columns; `do_detoast` (default `false`) optionally detoasts. `[from-docs]`
- `heap_page_item_attrs(page bytea, rel_oid regclass [, do_detoast bool])` =
  `heap_page_items()` but returns the decoded attribute array instead of raw
  `t_data`. `[from-docs]`

## B-tree decoding — high-key and downlink semantics

- `bt_metap(relname)` → metapage: `magic, version, root, level, fastroot,
  fastlevel, last_cleanup_num_delpages, last_cleanup_num_tuples,
  allequalimage`. `[from-docs]`
- `bt_page_stats(relname, blkno)` → per-page summary: `blkno, type, live_items,
  dead_items, avg_item_size, page_size, free_size, btpo_prev, btpo_next,
  btpo_level, btpo_flags` (the last four from `BTPageOpaqueData` special space).
  `bt_multi_page_stats(relname, blkno, blk_count)` runs it over a range;
  a **negative** `blk_count` means "to end of index". `[from-docs]`
- `bt_page_items(relname, blkno)` (or the `bytea` form) — the non-obvious
  semantics live here `[from-docs]`:
  - On a **leaf** page, `itemoffset` 1 is the **high key**; its `ctid` is NOT a
    heap pointer, it's the page's upper-bound separator.
  - On an **internal** page, the first real data item after the high key has all
    index columns truncated (`data` NULL) but a valid **downlink** in `ctid`
    (the child block number).
  - Posting-list tuples (deduplication) expose multiple heap TIDs in `tids[]`;
    the `htid` column gives the canonical heap TID regardless of representation.
  Refs: `source/src/include/access/itup.h`; docs §65.1.4 (B-tree structure +
  deduplication). `[from-docs]`

## Other AMs (each throws on a wrong-AM page)

- **BRIN**: `brin_page_type`, `brin_metapage_info` (`magic, version,
  pagesperrange, lastrevmappage`), `brin_revmap_data` (range-map TIDs),
  `brin_page_items(page, index)` (`itemoffset, blknum, attnum, allnulls,
  hasnulls, placeholder, empty, value`). Ref:
  `source/src/include/access/brin_tuple.h`. `[from-docs]`
- **GIN**: `gin_metapage_info` (pending-list head/tail + page/tuple counts),
  `gin_page_opaque_info` (`rightlink, maxoff, flags` e.g. `{data,leaf,compressed}`),
  `gin_leafpage_items` (compressed `first_tid, nbytes, tids[]`). `[from-docs]`
- **GiST**: `gist_page_opaque_info` (`lsn, nsn, rightlink, flags`; `nsn` =
  next-split number), `gist_page_items(page, index_oid)` (decoded `keys`) vs
  `gist_page_items_bytea(page)` (raw `key_data`, no OID needed). `[from-docs]`
- **Hash**: `hash_page_type`, `hash_page_stats` (`hasho_prevblkno,
  hasho_nextblkno, hasho_bucket, hasho_flag, hasho_page_id`), `hash_page_items`,
  `hash_bitmap_info(index, blkno)` (overflow-page bitmap status),
  `hash_metapage_info` (`maxbucket, highmask, lowmask, ovflpoint, spares[],
  mapp[]`, …). `[from-docs]`

## Links into corpus

- Page layout / `PageHeaderData`: [docs-distilled/storage-page-layout.md](./storage-page-layout.md)
- FSM internals: [docs-distilled/storage-fsm.md](./storage-fsm.md)
- Visibility map (the `'vm'` fork): [docs-distilled/storage-vm.md](./storage-vm.md)
- HOT chains (what `heap_page_items` infomask reveals): [docs-distilled/storage-hot.md](./storage-hot.md)
- B-tree structure + dedup: [docs-distilled/btree.md](./btree.md)
- Per-AM page formats: [docs-distilled/gin.md](./gin.md), [docs-distilled/gist.md](./gist.md), [docs-distilled/brin.md](./brin.md), [docs-distilled/hash-index.md](./hash-index.md)
- Relevant skills: `debugging` (SQL-level page inspection), `access-method-apis`,
  `wal-and-xlog`. The `debugging` skill names pageinspect as a primary
  runtime-inspection tool.
