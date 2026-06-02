---
source_url: https://www.postgresql.org/docs/current/storage.html
also_fetched:
  - https://www.postgresql.org/docs/current/storage-page-layout.html
fetched_at: 2026-06-02T09:33:33Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter 66: Database Physical Storage

The official "physical storage format" chapter. This run distills the chapter
index (66.1–66.7) plus the substantive **66.6 Database Page Layout** sub-page,
which is the part that carries non-obvious on-disk-format detail. Other
sub-sections (TOAST, FSM, VM, init fork, HOT) are queued for their own docs
sub-pages and only summarized here.

## Chapter map (66.1–66.7)

- **66.1 Database File Layout** — per-relation files under
  `base/<dboid>/<relfilenode>`, segmented at 1 GB, plus `_fsm` / `_vm` /
  `_init` forks. [from-docs]
- **66.2 TOAST** — oversized attributes pushed out-of-line. Two variants the
  index page calls out explicitly: *out-of-line on-disk* and *out-of-line
  in-memory* storage. [from-docs]
- **66.3 Free Space Map** (`_fsm` fork) / **66.4 Visibility Map** (`_vm` fork)
  / **66.5 The Initialization Fork** (`_init`, for unlogged relations).
  [from-docs]
- **66.6 Database Page Layout** — the per-8 kB-block format. Detailed below.
- **66.7 Heap-Only Tuples (HOT)** — update chains kept within one page so no
  index entry is needed for the new version. [from-docs]

## Non-obvious claims — Database Page Layout (66.6)

- **Page = 8 kB by default**, set at compile time via `BLCKSZ`; every block of
  every relation/fork uses the same layout. [from-docs]
  [verified-by-code, source/src/include/storage/bufpage.h:24-78 — ASCII layout
  diagram, via knowledge/files/src/include/storage/bufpage.h.md]
- **Five regions in order:** PageHeaderData → `ItemIdData` array (line pointers,
  growing **forward**) → free space → items/tuples (growing **backward** from
  the end) → special space (AM-specific). The bidirectional growth lets the line
  pointer array be reordered during compaction **without moving tuple bodies** —
  the line-pointer index is the permanent row address. [from-docs]
  [verified-by-code, source/src/include/storage/bufpage.h:24-78]
- **`PageHeaderData` is 24 bytes**, fields:
  `pd_lsn` (8, LSN of last WAL touching the page) · `pd_checksum` (2, only
  meaningful if data checksums enabled at initdb) · `pd_flags` (2) ·
  `pd_lower` (2, offset to start of free space) · `pd_upper` (2, offset to end
  of free space) · `pd_special` (2, offset to special space) ·
  `pd_pagesize_version` (2; **version 4 since PG 8.3**) ·
  `pd_prune_xid` (4, oldest un-pruned XMAX or 0 — a *hint* for HOT pruning).
  [from-docs]
  [verified-by-code, source/src/include/storage/bufpage.h:184-197 — struct, via
  knowledge/files/src/include/storage/bufpage.h.md]
- **`pd_lsn` gates hint-bit/checksum safety:** because the page's last-WAL LSN
  lives in the header, hint-bit-only changes (which are *not* WAL-logged unless
  `wal_log_hints`/checksums) can still be ordered against WAL flush. (Cross-link:
  this is the mechanism the Hint_Bits wiki page glosses over — see
  `knowledge/wiki-distilled/Hint_Bits.md`.) [inferred]
- **`pd_lower`/`pd_upper` ARE the free space:** the gap between them is the
  unallocated middle. A new line pointer consumes 4 bytes at `pd_lower`; a new
  tuple consumes its size below `pd_upper`. [from-docs]
- **`ItemIdData` (line pointer) is 4 bytes:** an (offset, length) pair plus 2
  status bits (`lp_flags`). `LocationIndex` offsets are `uint16` but effectively
  cap at 2^15 because `lp_off` is 15 bits — hence the practical page-size ceiling
  at 32 kB. [from-docs]
  [verified-by-code, source/src/include/storage/bufpage.h:90 — LocationIndex
  comment]
- **`pd_flags` bits worth knowing:** `PD_HAS_FREE_LINES` (recyclable line
  pointers exist), `PD_PAGE_FULL` (used by HOT to decide pruning is worthwhile),
  `PD_ALL_VISIBLE` (every tuple visible to all — drives index-only scans and
  must stay in sync with the visibility map). [from-docs]
  [verified-by-code, source/src/include/storage/bufpage.h:34-40 PD_* defs, via
  per-file doc]

## Non-obvious claims — Table Row Layout (66.6.1)

- **`HeapTupleHeaderData` is 23 bytes** on most platforms, before the optional
  null bitmap and the user data. [from-docs]
  [verified-by-code, source/src/include/access/htup_details.h:153 — struct, via
  knowledge/files/src/include/access/htup_details.h.md]
- **The xmin/cmin/xmax/cmax/xvac overlay trick:** the header stores `t_xmin`,
  `t_xmax`, and a *union* of `t_cid` and `t_xvac` in one 4-byte slot — command
  ID and the legacy VACUUM-FULL xid never coexist. Combo CIDs (when one backend
  both inserts and deletes within a command) are resolved by `combocid.c`.
  [from-docs]
  [verified-by-code, source/src/include/access/htup_details.h:122-153, via
  per-file doc]
- **`t_ctid` (6 bytes)** points at *this* tuple normally, or the *next* version
  for an updated row — this is the update-chain link. The docs state, and the
  header comment makes precise, the chain-walk safety rule: a referenced slot
  must be non-empty **and** the referenced tuple's `xmin` must equal the
  referencing tuple's `xmax`, because VACUUM can reclaim the newer version first.
  [from-docs]
  [from-comment, source/src/include/access/htup_details.h:86-103 — "most-cited
  invariant for update-chain walkers", via per-file doc]
- **`t_infomask` / `t_infomask2`:** flag words. `t_infomask2`'s low 11 bits
  (`HEAP_NATTS_MASK 0x07FF`) hold the attribute count; high bits carry
  `HEAP_HOT_UPDATED` / `HEAP_ONLY_TUPLE` / `HEAP_KEYS_UPDATED`. [from-docs]
  [verified-by-code, source/src/include/access/htup_details.h:291-296, via
  per-file doc]
- **`t_hoff` (1 byte) must be a MAXALIGN multiple** — it is the offset to user
  data, so padding is inserted after the null bitmap (and after the optional OID
  slot) to honor alignment. `GETSTRUCT(tuple)` is literally
  `(char*)t_data + t_hoff`. [from-docs]
  [from-comment, source/src/include/access/htup_details.h:118-119; accessor at
  :716-792, via per-file doc]
- **Null bitmap is present only if `HEAP_HASNULL` is set** in `t_infomask`; it
  follows the fixed header, 1 bit/column, **bit set = NOT null**. When absent,
  every column is non-null. So a table with no nullable values pays zero bitmap
  cost. [from-docs]
  [verified-by-code, source/src/include/access/htup_details.h:190 HEAP_HASNULL,
  via per-file doc]
- **TOAST trigger:** a row wider than ~2 kB (`TOAST_TUPLE_THRESHOLD`, ≈ 1/4 page)
  triggers the toaster, which compresses and/or moves `HEAP_HASEXTERNAL`
  attributes out of line until the row fits. The index page also notes an
  in-memory out-of-line variant (used for expanded/short-lived datums).
  [from-docs]

## Numeric constants to remember

| Constant | Value | Source |
|---|---|---|
| Default page size (`BLCKSZ`) | 8192 B | docs / bufpage.h |
| `PageHeaderData` size | 24 B | docs |
| `HeapTupleHeaderData` size | 23 B | docs / htup_details.h:153 |
| `ItemIdData` size | 4 B | docs |
| Page layout version | 4 (since 8.3) | bufpage.h `PG_PAGE_LAYOUT_VERSION` |
| `MaxTupleAttributeNumber` | 1664 | htup_details.h:34 |
| `MaxHeapAttributeNumber` | 1600 | htup_details.h:48 |
| TOAST threshold | ~2 kB | docs §66.2 |
| Line-pointer offset width | 15 bits → 32 kB page ceiling | bufpage.h:90 |

## Links into corpus

- [[knowledge/files/src/include/storage/bufpage.h.md]] — verified
  `PageHeaderData` at lines 184–197, page ASCII diagram at 24–78, `PD_*` flags.
- [[knowledge/files/src/include/access/htup_details.h.md]] — verified
  `HeapTupleHeaderData` at line 153, infomask bit table, `t_ctid` chain
  invariant at 86–103, `t_hoff`/MAXALIGN at 118–119.
- [[knowledge/data-structures/heap-tuple-layout.md]] — the focused
  struct-level synthesis this chapter corresponds to.
- [[knowledge/subsystems/access-heap.md]] — heap AM that produces/consumes this
  layout.
- [[knowledge/subsystems/storage-buffer.md]] — pages live in shared buffers;
  `pd_lsn` is what the buffer manager checks before flush.
- [[knowledge/wiki-distilled/Hint_Bits.md]] — the hint-bit half of why
  read-only queries dirty these pages (companion distillation, same run).

## Gaps / follow-ups

- The chapter's TOAST (66.2), FSM (66.3), VM (66.4), init-fork (66.5), and HOT
  (66.7) sub-pages each merit their own distilled doc — they were summarized,
  not mined, this run. Suggest seeding `storage-toast`, `storage-fsm`,
  `storage-vm`, `storage-hot` into the docs queue.
- Line numbers cited via the per-file corpus docs were last verified at
  `ef6a95c7c64`; STATE.md records the delta to the current anchor
  `4b0bf0788b` as build-system-only with no corpus impact, so they are treated
  as still valid. [inferred]
</content>
</invoke>
