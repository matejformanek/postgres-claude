# contrib-pageinspect (raw page + per-AM page-format inspectors)

- **Source path:** `source/contrib/pageinspect/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.13` (per `pageinspect.control`)
- **Trusted:** no (superuser install + per-function grants)

## 1. Purpose

Extract a single 8KB page from any relation fork as a `bytea`,
then offer per-access-method decoders that turn that bytea into
SQL rows of "what's on this page." Used for:

- Forensic debugging — read tuple offset/length, line-pointer
  redirects, dead-tuple stubs, page LSN.
- Documentation / teaching — show what a B-tree internal page
  looks like, what `pd_lower` / `pd_upper` mean in practice.
- Test-suite ground truth — TAP tests grep page-level invariants
  without parsing on-disk format from scratch.

The seven inspector files mirror the seven page-format
families: heap, btree, brin, gin, gist, hash, fsm.

## 2. The architecture: bytea-in, rows-out

The flow is two-stage by design:

1. **`get_raw_page(relname, fork, blkno)`** — returns the page as
   bytea
   [verified-by-code `rawpage.c:46-90`]. Takes `AccessShareLock`,
   pins the buffer, copies the 8KB into a freshly-palloc'd
   bytea, releases the buffer.
2. **`<am>_page_items(page bytea, ...)`** — type-specific decoder
   that walks the bytea and returns one row per item.

The split means clients can store the bytea (e.g. capture a
snapshot of a corrupting page before VACUUM clobbers it), then
decode offline. It also means inspection is purely read-only —
the decoders never touch shared buffers again.

## 3. The seven decoder files

| File | LOC | Decodes |
|---|---|---|
| `heapfuncs.c` | 624 | Heap pages — `heap_page_items`, `heap_page_item_attrs`, `tuple_data_split` |
| `btreefuncs.c` | 937 | B-tree pages — `bt_page_items`, `bt_page_stats`, `bt_metap`, `bt_multi_page_stats` |
| `brinfuncs.c` | 436 | BRIN summary + revmap pages |
| `ginfuncs.c` | 282 | GIN metapage, leaf pages, posting trees |
| `gistfuncs.c` | 369 | GiST internal + leaf pages |
| `hashfuncs.c` | 574 | Hash buckets, overflow pages, metapage, bitmap |
| `fsmfuncs.c` | 65 | FSM page contents |

[verified-by-code via `wc -l source/contrib/pageinspect/*.c`]

`rawpage.c` (376 LOC) hosts both the get_raw_page family and
`page_header()` / `page_checksum()` — utilities that work for any
page regardless of AM.

## 4. The page-header utilities

- **`page_header(page bytea)`** — decodes the universal `PageHeaderData`
  prefix (LSN, checksum, flags, `pd_lower`/`pd_upper`/`pd_special`,
  `pd_pagesize_version`, prune-XID).
- **`page_checksum(page bytea, blkno int)`** — computes what the
  checksum *should* be given the block number. Compare against the
  decoded `pd_checksum` to detect torn writes / bit rot. **Note
  the blkno parameter**: page checksum includes the block number
  to detect mis-placed pages.

## 5. Heap inspectors — the workhorses

- **`heap_page_items(page bytea)`** — one row per item-id slot,
  including tombstones. Columns include `lp_off`, `lp_len`,
  `lp_flags`, plus the full HeapTupleHeaderData decoded
  (`t_xmin`, `t_xmax`, `t_field3`, `t_ctid`, `t_infomask*`,
  `t_hoff`, `t_bits`, `t_oid`).
- **`heap_page_item_attrs(page bytea, rel_oid regclass)`** —
  same plus the user attributes, decoded against the relation's
  TupleDesc. Useful when reading a specific row's stored value.
- **`tuple_data_split(rel_oid oid, t_data bytea, t_infomask int,
  t_infomask2 int, t_bits text)`** — splits a tuple-data bytea
  into per-attribute byteas using the catalog's pg_attribute
  layout. Reusable on captured tuple data.

## 6. B-tree inspectors

- **`bt_metap(relname)`** — metapage: root block, level, fast-root,
  oldest-deleted-XID. The `bt_multi_page_stats` SRF added in 1.12
  [verified-by-code `pageinspect--1.11--1.12.sql:9`] returns one
  row per page across a block range — efficient for whole-index
  stats without one SQL call per page.
- **`bt_page_stats(relname, blkno)`** — per-page summary:
  level, type (leaf / internal / root / deleted), live + dead
  item counts, sibling pointers.
- **`bt_page_items(relname, blkno)` / `bt_page_items(page bytea, ...)`** —
  per-item rows on a leaf or internal page. Internal-page rows
  include the downlink block number; leaf-page rows include the
  heap TID.

## 7. The other AMs in brief

- **BRIN**: `brin_page_type`, `brin_metapage_info`, `brin_revmap_data`,
  `brin_page_items` — revmap traversal + per-summary inspection.
- **GIN**: `gin_metapage_info`, `gin_page_opaque_info`,
  `gin_leafpage_items` — surfaces the GIN pending list + posting
  tree structure.
- **GiST**: `gist_page_opaque_info`, `gist_page_items`, with one
  row per internal/leaf entry.
- **Hash**: `hash_page_type`, `hash_page_stats`, `hash_page_items`,
  `hash_bitmap_info`, `hash_metapage_info` — bucket / overflow
  inspection.

[verified-by-code SQL grants in `pageinspect--1.5.sql:194-273`,
`pageinspect--1.5--1.6.sql:13-90`]

## 8. Production-use guidance

- **`get_raw_page` takes a buffer pin** — safe on running systems
  but every call costs a buffer-manager round-trip. Don't loop a
  SELECT across millions of blocks; use the AM-specific stats SRFs
  where available.
- **Inspectors NEVER mutate state.** Free of dirty-page
  side-effects; pure decoders post-`get_raw_page`.
- **Decoder ERRORs are the bug, not a corruption indicator.** If
  `heap_page_items` raises on an apparently-healthy page, file an
  upstream bug — pageinspect's decoders should accept any valid
  page.
- **TOAST pages need `bytea` casting awareness.** `heap_page_items`
  on a TOAST relation returns toast-chunk tuples; the user-data
  columns will look like opaque bytea.

## 9. Version notes

- 1.13 (`pageinspect--1.12--1.13.sql`) — recent additions, see
  the upgrade script.
- 1.12 added `bt_multi_page_stats` for efficient whole-index
  walks.
- 1.6 added `page_checksum` + `hash_*` family.
- 1.5 is the historical baseline that introduced the bytea-based
  signatures still used today.

## 10. Invariants

- **[INV-1]** `get_raw_page` returns exactly 8192 bytes (or
  `BLCKSZ` if PG was compiled with a different block size).
- **[INV-2]** Decoders are purely functional on the bytea input
  (no `BufferDesc` access, no locks held during decode).
- **[INV-3]** `page_checksum(blkno)` must be passed the
  original block number to compute correctly; checksum includes
  block.
- **[INV-4]** `bt_index_parent_check`'s and pageinspect's btree
  decoders are independent — amcheck verifies; pageinspect only
  observes.

## 11. Useful greps

- All entry points across the AM-specific files:
  `grep -RIn 'PG_FUNCTION_INFO_V1' source/contrib/pageinspect/`
- Page-fork enum:
  `grep -n 'ForkNumber\|MAIN_FORKNUM\|VISIBILITYMAP_FORKNUM' source/contrib/pageinspect/rawpage.c`
- Bytea-page interpretation pattern:
  `grep -n 'PG_GETARG_BYTEA' source/contrib/pageinspect/heapfuncs.c | head -5`

## 12. Cross-references

- `knowledge/data-structures/heap-tuple-layout.md` — the
  `HeapTupleHeaderData` layout this extension decodes.
- `knowledge/subsystems/storage-buffer.md` — `ReadBufferExtended`
  underlies `get_raw_page`.
- `knowledge/subsystems/access-heap.md`,
  `knowledge/subsystems/access-nbtree.md` — the AM internals these
  decoders mirror.
- `.claude/skills/debugging/SKILL.md` — pageinspect is the
  go-to for "what's actually on this page" debugging.
- `source/contrib/pageinspect/rawpage.c` — the `get_raw_page`
  entry point.
- `source/contrib/pageinspect/heapfuncs.c` — heap decoders.
- `source/contrib/pageinspect/btreefuncs.c` — B-tree decoders.

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**9 files.**

| File |
|---|
| [`contrib/pageinspect/brinfuncs.c`](../files/contrib/pageinspect/brinfuncs.c.md) |
| [`contrib/pageinspect/btreefuncs.c`](../files/contrib/pageinspect/btreefuncs.c.md) |
| [`contrib/pageinspect/fsmfuncs.c`](../files/contrib/pageinspect/fsmfuncs.c.md) |
| [`contrib/pageinspect/ginfuncs.c`](../files/contrib/pageinspect/ginfuncs.c.md) |
| [`contrib/pageinspect/gistfuncs.c`](../files/contrib/pageinspect/gistfuncs.c.md) |
| [`contrib/pageinspect/hashfuncs.c`](../files/contrib/pageinspect/hashfuncs.c.md) |
| [`contrib/pageinspect/heapfuncs.c`](../files/contrib/pageinspect/heapfuncs.c.md) |
| [`contrib/pageinspect/pageinspect`](../files/contrib/pageinspect/pageinspect.md) |
| [`contrib/pageinspect/rawpage.c`](../files/contrib/pageinspect/rawpage.c.md) |

<!-- /files-owned:auto -->
