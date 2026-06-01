# `src/backend/storage/page/bufpage.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 1530
- **Source:** `source/src/backend/storage/page/bufpage.c`

## Purpose

The on-disk page format implementation. Every block PG writes to a
relation is a "page" of this shape: `PageHeaderData` at the front, an
ItemId (line pointer) array growing forward, tuples growing backward
from the end, with an AM-specific "special space" trailer. This file
provides the routines to *initialize*, *verify*, *add to*, *delete
from*, and *defragment* such a page. The buffer manager calls
`PageIsVerified` after every disk read and `PageSetChecksum` before
every disk write. The heap, btree, gist, brin, etc. AMs call
`PageAddItem` and friends. [from-comment in bufpage.h:24-78]

## Top of file

Includes pgstat, checksum impl, memdebug, memutils. GUC
`ignore_checksum_failure` is defined here (line 27).

## Public API (bufpage.h)

- Initialization / verification: `PageInit`, `PageIsVerified`,
  `PageSetChecksum`.
- Item add / delete: `PageAddItemExtended` (with `PageAddItem` macro
  wrapper), `PageIndexTupleDelete`, `PageIndexMultiDelete`,
  `PageIndexTupleDeleteNoCompact`, `PageIndexTupleOverwrite`.
- Defrag: `PageRepairFragmentation`, `PageTruncateLinePointerArray`.
- Free-space inspection: `PageGetFreeSpace`,
  `PageGetFreeSpaceForMultipleTuples`, `PageGetExactFreeSpace`,
  `PageGetHeapFreeSpace`.
- Temp-page utilities: `PageGetTempPage`, `PageGetTempPageCopy`,
  `PageGetTempPageCopySpecial`, `PageRestoreTempPage`.

Most accessors (`PageGetItem`, `PageGetItemId`, `PageGetMaxOffsetNumber`,
`PageGetPageSize`, `PageIsNew`, `PageGetLSN`, etc.) are inline
functions or macros in `bufpage.h`.

## Types of note (bufpage.h)

- `PageData = char`, `Page = PageData *` (lines 80–81): a Page is just
  a pointer to BLCKSZ bytes of memory.
- `PageHeaderData` (bufpage.h:184–197): `pd_lsn` (PageXLogRecPtr),
  `pd_checksum`, `pd_flags`, `pd_lower`, `pd_upper`, `pd_special`,
  `pd_pagesize_version`, `pd_prune_xid`, then the flexible-array
  `pd_linp[]` of ItemIdData.
- `PageXLogRecPtr` (bufpage.h:101-136): two-word LSN with
  endianness-aware getters/setters because some platforms historically
  stored it as two 32-bit halves.
- `PD_*` flag bits and `PG_PAGE_LAYOUT_VERSION` are defined in
  `bufpage.h`.

## Invariants

- `pd_lower <= pd_upper <= pd_special <= BLCKSZ`. Violation is a hard
  corruption: `PageAddItemExtended` PANICs and
  `PageRepairFragmentation` ERRORs. [verified-by-code] (`bufpage.c:220-227`,
  `732-740`)
- `pd_special` is MAXALIGN'd. [verified-by-code] (`bufpage.c:141, 736`)
- Tuple region grows downward from `pd_special` toward `pd_lower`;
  free space is the gap `[pd_lower, pd_upper)`.
- Checksum is *not* maintained continuously — it is computed and
  stamped only when the buffer is flushed (`PageSetChecksum`,
  `bufpage.c:1517`). Most pages in shared buffers therefore have stale
  checksum fields. [from-README] (`page/README:18-25`)
- All-zero ("PageIsNew") pages are accepted as valid by
  `PageIsVerified` — they arise legitimately when extension crashes
  before the WAL record for the init lands. [from-comment]
  (`bufpage.c:71-79`, `148-152`)
- `PageAddItemExtended`: **no ereport(ERROR)** allowed (`bufpage.c:200`)
  — the caller may be holding locks across the call.

## Functions of note

**`PageInit` (lines 41–60)** — MemSet zeros, then sets pd_lower =
`SizeOfPageHeaderData` and pd_upper = pd_special = pageSize -
specialSize. Notably does *not* compute a checksum.

**`PageIsVerified` (lines 93–172)** — called after every disk read.
Branches on `PageIsNew`: if zero, accept; else, compute checksum, check
header sanity (`pd_flags` valid bits, lower<=upper<=special<=BLCKSZ,
pd_special MAXALIGN'd). Interrupts are held across the checksum compute
because runtime checksum-state changes (`pg_enable_data_checksums`) could
otherwise change the calculation mid-flight (lines 110–129).

**`PageAddItemExtended` (lines 202–365)** — the workhorse for adding a
tuple. Selects an offset (either reused free line pointer, or appended
at maxoff+1), reserves space (`pd_upper -= MAXALIGN(size)`,
`pd_lower += sizeof(ItemIdData)` if a new linp is needed), and memcpys
the item. Refuses with WARNING + InvalidOffsetNumber on the various "no
fit" / "too many heap items" / "OVERWRITE on used itemid" cases. The
`PAI_IS_HEAP` flag enforces MaxHeapTuplesPerPage.

**`compactify_tuples` (lines 482–689)** — static helper for fragment
repair. Two paths: `presorted=true` (items already in reverse linp
order, which is the common case for never-updated pages) does an
in-place memmove sweep; `presorted=false` copies through a
PGAlignedBlock scratch buffer. Optimized for the common
heap-just-pruned case.

**`PageRepairFragmentation` (lines 707–841)** — heap-page-only defrag.
Walks the line-pointer array, collects live ItemIds into a stack array
of `itemIdCompactData`, then calls `compactify_tuples`. Sets / clears
`PD_HAS_FREE_LINES` hint. Caller must hold a full cleanup lock on the
buffer (`bufpage.c:702-703`).

**`PageSetChecksum` (lines 1517–1530)** — called immediately before
writing to disk (and from bulk_write.c). Skips if checksums disabled
or page is new. Holds interrupts across the compute.

## Cross-refs

- Inbound: every AM (`access/heap/*`, `access/nbtree/*`,
  `access/gist/*`, …), `bufmgr.c` (verify on read, set checksum on
  write), `bulk_write.c`.
- Outbound: `pg_checksum_page` (storage/checksum.c via
  storage/checksum_impl.h).

## Open questions

- The full `PageIndexTupleOverwrite` shuffling math (lines 1413–1500)
  I read but not in deep detail — claim of correctness against
  variable-sized index tuples is `[from-comment]`.

## Tag tally

`[verified-by-code]` 6 / `[from-comment]` 5 / `[from-README]` 1 /
`[unverified]` 0.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
