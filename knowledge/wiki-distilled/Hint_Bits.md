---
source_url: https://wiki.postgresql.org/wiki/Hint_Bits
fetched_at: 2026-06-02T09:33:33Z
wiki_last_edited: 2015-04-29T01:24Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
primary: false
staleness: wiki page is from 2015 — predates checksums-by-default discussion;
  omits the WAL-flush/MarkBufferDirtyHint machinery. Supplemented below with
  [verified-by-code] facts from the corpus.
---

# Wiki distilled — Hint Bits

What hint bits are, why a read-only query can still write pages, and the real
mechanism (which the 2015 wiki page only half-covers). Page-format companion:
`knowledge/docs-distilled/storage.md`.

## What the wiki page says

- **Four hint bits** record the *known* commit/abort fate of a tuple's inserting
  and deleting transactions: XMIN_COMMITTED, XMIN_ABORTED, XMAX_COMMITTED,
  XMAX_ABORTED. [from-wiki]
- **They are a cache of CLOG/pg_xact.** The first reader to determine a tuple's
  visibility must consult `pg_clog` (now `pg_xact`) for the inserting/deleting
  xid's status; once known, it stamps the hint bit so later readers skip the
  CLOG lookup. "First one to check" pays the cost. [from-wiki]
- **Reads cause writes:** "A plain SELECT, count(*), or VACUUM on the entire
  table will check every tuple for visibility and set its hint bits." Setting a
  hint bit dirties the page, so a read-only workload generates writes — the
  classic "why is my SELECT doing I/O" surprise. [from-wiki]
- **Piecemeal access amplifies it:** fetching single tuples via index scans can
  rewrite the same page many times as different tuples' hint bits get set over
  successive visits. [from-wiki]
- **CLOG page allocation overhead:** "One transaction in every 32K writing
  transactions does have to do extra work when it assigns itself an XID, namely
  create and zero out the next page of pg_clog." (32 K = one 8 kB CLOG page at
  2 bits/xid.) [from-wiki]

## What the wiki page omits — corpus supplement

The 2015 page does **not** name `t_infomask`, `SetHintBits`,
`MarkBufferDirtyHint`, or the WAL-flush rule. These are the load-bearing
details:

- **Where the bits live:** `t_infomask` in the heap tuple header.
  `HEAP_XMIN_COMMITTED 0x0100`, `HEAP_XMIN_INVALID 0x0200`
  (the wiki's "XMIN_ABORTED"), `HEAP_XMAX_COMMITTED 0x0400`,
  `HEAP_XMAX_INVALID 0x0800`. Both XMIN bits set together (`0x0300`) is reused to
  mean **frozen** (`HEAP_XMIN_FROZEN`) — they are hints, not authoritative state.
  [verified-by-code, source/src/include/access/htup_details.h:204-208, via
  knowledge/files/src/include/access/htup_details.h.md]
- **The setter is `SetHintBits` / `SetHintBitsExt`** in `heapam_visibility.c`,
  called from the `HeapTupleSatisfies*` routines when a referenced xact's fate
  becomes newly known. On change it calls **`MarkBufferDirtyHint`** (bufmgr.c) —
  *not* `MarkBufferDirty` — so the write is a dirty-hint, page is flushed
  eventually but the change itself is not WAL-logged in the normal case.
  [verified-by-code, source/src/backend/access/heap/heapam_visibility.c:142,199,
  via knowledge/files/src/backend/access/heap/heapam_visibility.c.md]
- **The crash-safety rule the wiki misses:** a hint bit may be set **only after
  the committing xact's commit-record WAL is flushed to disk**. `SetHintBitsExt`
  checks `XLogNeedsFlush` for the relevant LSN; if the WAL isn't durable yet it
  **declines to set the bit** (a later visit will). Setting
  `HEAP_X*_COMMITTED` prematurely could, after a crash, leave a tuple marked
  committed whose transaction never made it to disk → silent data corruption.
  [verified-by-code, source/src/backend/access/heap/heapam_visibility.c:142-198]
  **This is the single most important hint-bit invariant.**
- **Checksums / `wal_log_hints` change the cost model** (post-2015): with data
  checksums enabled (or `wal_log_hints=on`), a hint-bit-only change to an
  otherwise-clean page triggers a **full-page image in WAL** the first time the
  page is touched after a checkpoint, because the checksum must stay consistent.
  So on a checksummed cluster, "read-only" hint-bit setting can emit WAL, not
  just dirty buffers. [inferred — consistent with `pd_checksum` in
  `storage.md`; wiki predates checksums-by-default]
- **Ordering rule that makes hints safe to compute:** visibility code must call
  `TransactionIdIsInProgress` (scans the PGPROC array) **before**
  `TransactionIdDidCommit` (reads pg_xact); `xact.c` records commit in pg_xact
  *before* clearing `MyProc->xid`, so this order can never mistake a
  just-committed xact for a crashed one. [from-comment,
  source/src/backend/access/heap/heapam_visibility.c:177-191, via per-file doc]

## Why it matters operationally

- A large `COPY`/bulk-load followed by the first `SELECT *` over the table is the
  textbook "second query writes the whole table" case: the load left every
  tuple's xmin unhinted, and the first full scan sets them. Running an explicit
  `VACUUM` (or letting autovacuum/`VACUUM FREEZE`) after a bulk load front-loads
  this cost. [inferred, from-wiki]
- Hint bits are *not* required for correctness — they are a pure performance
  cache. A page can be evicted before its hint-bit write reaches disk and nothing
  is lost; the next reader simply re-derives from CLOG. [from-wiki + from-comment]

## Links into corpus

- [[knowledge/files/src/include/access/htup_details.h.md]] — `t_infomask` bit
  values (HEAP_XMIN_COMMITTED 0x0100 … at lines 204–208), frozen-state reuse.
- [[knowledge/files/src/backend/access/heap/heapam_visibility.c.md]] —
  `SetHintBits`/`SetHintBitsExt` (142/199), the WAL-flush-before-hint rule
  (142–198), the IsInProgress-before-DidCommit ordering (177–191).
- [[knowledge/subsystems/access-heap.md]] — heap MVCC visibility producer.
- [[knowledge/data-structures/heap-tuple-layout.md]] — where `t_infomask` sits
  in the header.
- [[knowledge/docs-distilled/storage.md]] — `pd_checksum`/`pd_lsn` page-header
  fields that interact with hint-bit WAL/full-page-image behavior.

## Confidence note

The wiki content is tagged `[from-wiki]` and is accurate but incomplete and
dated (2015). Every supplement that names a symbol or invariant is
`[verified-by-code]` against the per-file corpus (last verified `ef6a95c7c64`;
treated current per STATE.md anchor delta). The checksum/`wal_log_hints`
amplification is `[inferred]` and should be confirmed against `bufmgr.c`
`MarkBufferDirtyHint` + `XLogSaveBufferForHint` in a future file-backfill run.
</content>
</invoke>
