---
source_url: https://www.postgresql.org/docs/current/storage-page-layout.html
fetched_at: 2026-06-11T00:00:00Z
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — §66.6: Database Page Layout

The on-disk shape of every 8 KB heap/index page: the five-part layout, the
`PageHeaderData` and `HeapTupleHeaderData` field tables, line pointers, and the
`pd_lower`/`pd_upper` free-space accounting a storage hacker reads constantly.

## The five parts of a page (in address order) [from-docs]

1. **`PageHeaderData`** — 24 bytes, general page info + free-space pointers.
2. **`ItemIdData`** — array of 4-byte line pointers, grows **forward** from the
   header (allocated low→high).
3. **Free space** — the gap between `pd_lower` and `pd_upper`.
4. **Items** — the actual tuples, stored **backward** from the end of the page.
5. **Special space** — AM-specific (e.g. b-tree sibling links); **empty for
   ordinary heap tables**, in which case `pd_special` == page size. [from-docs]

The two-ended layout is the key invariant: new line pointers consume free space
from the low end (`pd_lower` rises), new tuples from the high end (`pd_upper`
falls); the page is full when they meet.
[verified-by-code, source/src/include/storage/bufpage.h — `PageHeaderData`,
`pd_lower`/`pd_upper`/`pd_special`; via knowledge/files/src/include/storage/bufpage.h.md]

## PageHeaderData fields (24 bytes) [from-docs]

| Field | Type | Bytes | Meaning |
|---|---|---|---|
| `pd_lsn` | PageXLogRecPtr | 8 | LSN of next byte after the last WAL record touching this page (WAL-before-data rule) |
| `pd_checksum` | uint16 | 2 | Page checksum (only meaningful if checksums enabled) |
| `pd_flags` | uint16 | 2 | Flag bits |
| `pd_lower` | LocationIndex | 2 | Offset to start of free space |
| `pd_upper` | LocationIndex | 2 | Offset to end of free space |
| `pd_special` | LocationIndex | 2 | Offset to start of special space |
| `pd_pagesize_version` | uint16 | 2 | Page size + layout version (v4 since PG 8.3) |
| `pd_prune_xid` | TransactionId | 4 | Oldest unpruned XMAX on page, or 0 (prune hint) |

- `pd_lsn` is what enforces **WAL-before-data**: the buffer manager refuses to
  flush a dirty page until WAL up to `pd_lsn` is on durable storage. [from-docs]
  [verified-by-code, source/src/include/storage/bufpage.h]
- `pd_prune_xid` is a *hint*, not authoritative: it tells `heap_page_prune_opt`
  whether a prune scan is worth attempting. [from-docs]

## Line pointers (`ItemIdData`, 4 bytes each) [from-docs]

- Packs **offset to item**, **item length**, and **lp_flags** state bits.
- A `ItemPointer`/CTID = (block number, line-pointer index). The index into this
  array is what an index entry or a `t_ctid` forward pointer stores.
- **Line pointers are never moved while in use** — that stability is what lets
  long-lived index entries and CTIDs keep pointing at a row across page
  defragmentation. Only the tuple bodies move during compaction. [from-docs]
  [verified-by-code, source/src/include/storage/itemid.h — `ItemIdData`,
  `LP_UNUSED`/`LP_NORMAL`/`LP_REDIRECT`/`LP_DEAD`; via
  knowledge/files/src/include/storage/itemid.h.md]

## HeapTupleHeaderData fields (23 bytes fixed) [from-docs]

| Field | Type | Bytes | Meaning |
|---|---|---|---|
| `t_xmin` | TransactionId | 4 | Inserting XID |
| `t_xmax` | TransactionId | 4 | Deleting/locking XID |
| `t_cid` | CommandId | 4 | Insert/delete CID (union with `t_xvac`) |
| `t_ctid` | ItemPointerData | 6 | TID of this or the next-newer row version (HOT/update chain) |
| `t_infomask2` | uint16 | 2 | Attribute count (low bits) + flag bits |
| `t_infomask` | uint16 | 2 | Status flag bits |
| `t_hoff` | uint8 | 1 | Offset from tuple start to user data (MAXALIGN'd) |

Then, optionally and in order: **null bitmap** (present iff `HEAP_HASNULL` in
`t_infomask`; one bit/column, 1 = not null), legacy **OID** (iff
`HEAP_HASOID_OLD`), **MAXALIGN padding**, then **user data** starting at `t_hoff`.
[from-docs]
[verified-by-code, source/src/include/access/htup_details.h; via
knowledge/data-structures/heap-tuple-layout.md]

## Reading a column value [from-docs]

- Fixed-width columns are laid out sequentially; variable-length columns share a
  `struct varlena` header (length + flags), and may be inline, compressed, or a
  TOAST pointer to out-of-line storage (§66.2).
- You cannot interpret the bytes without `pg_attribute.attlen` (width) and
  `attalign` (alignment). Accessors: `heap_getattr()`, `fastgetattr()`,
  `heap_getsysattr()`. [from-docs]
  [verified-by-code, source/src/include/access/htup_details.h — `fastgetattr`,
  `heap_getsysattr`]

## Checksums [from-docs]

- `pd_checksum` is computed/validated only when data checksums are enabled (at
  `initdb` time, or via `pg_checksums`). The algorithm lives in
  `src/include/storage/checksum_impl.h`.
  [verified-by-code, source/src/include/storage/checksum_block_internal.h.md
  is the per-file note; algorithm in checksum_impl.h]

## Links into corpus

- [[knowledge/files/src/include/storage/bufpage.h.md]] — `PageHeaderData`,
  `PageGetFreeSpace`, the macros enforcing the two-ended layout.
- [[knowledge/files/src/include/storage/itemid.h.md]] — `lp_flags` states.
- [[knowledge/data-structures/heap-tuple-layout.md]] — the `t_infomask`/
  `t_infomask2` bit catalogue this chapter only sketches.
- [[knowledge/files/src/include/access/htup_details.h.md]] — accessors + flags.
- [[knowledge/docs-distilled/storage-hot.md]] — how `t_ctid` chains + line-pointer
  redirects build on this layout.
- [[knowledge/subsystems/storage-buffer.md]] — `pd_lsn` and the WAL-before-data
  flush rule.

## Gaps / follow-ups

- The docs table omits most `t_infomask` bits (`HEAP_XMIN_COMMITTED`, etc.); the
  authoritative list is in `htup_details.h` and the heap-tuple-layout data-structure
  doc. This distillation deliberately defers to those rather than re-listing.
