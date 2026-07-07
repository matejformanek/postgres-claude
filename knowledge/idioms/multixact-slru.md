# MultiXact dual SLRU — offsets + members, with the "next-mxact = end-of-mine" trick

A **MultiXactId** is the heap manager's compact representation of a set of
TransactionIds (plus per-XID lock-mode flags) sharing a row lock. Unlike CLOG,
which is 2 bits per XID at a fixed page index, a MultiXactId resolves to a
**variable-length** array of `(xid, status)` pairs. The implementation splits
the storage across two SLRUs:

- `pg_multixact/offsets/` — one `MultiXactOffset` (8 bytes) per MultiXactId; this
  is the **pointer** into the members area.
- `pg_multixact/members/` — packed 20-byte groups containing 4 flag bytes
  followed by 4 TransactionIds; one entry per (xid, status) pair.

The clever bit is that a MultiXactId's **member count is not stored anywhere**.
It is computed as `nextMulti.offset − thisMulti.offset` — i.e. the next
multixact's starting offset is the end of mine. Every `RecordNewMultiXact`
writes **both** offsets (its own and the next-position sentinel); every
`GetMultiXactIdMembers` reads **both**.

This doc covers the dual-SLRU layout, the create/read access patterns
(including bank-hopping under the SLRU per-bank lock), the two-truncate dance
in `TruncateMultiXact`, and the wraparound bookkeeping that keeps the
counters monotonic across crash.

Companion docs:
- [[slru-page-replacement]] — the underlying buffer cache + bank-lock dance both SLRUs sit on.
- [[clog-slru]] — single-SLRU sibling with a 2-bit-per-XID fixed-size encoding.
- [[tuple-locking-modes]] — heapam's perspective on what MultiXact lock-mode flags mean.

## Anchors

- `source/src/backend/access/transam/multixact.c:1-67` — file banner: "two SLRU areas … this trick allows us to store variable length arrays of TransactionIds."
- `source/src/include/access/multixact.h:36-46` — `MultiXactStatus` enum (ForKeyShare … Update).
- `source/src/include/access/multixact.h:55-59` — `MultiXactMember { xid; status }`.
- `source/src/include/access/multixact_internal.h:26-44` — offsets-page macros (`MULTIXACT_OFFSETS_PER_PAGE = BLCKSZ/8`).
- `source/src/include/access/multixact_internal.h:52-78` — members-page macros (`MULTIXACT_MEMBERGROUP_SIZE = 20`, `MULTIXACT_MEMBERGROUPS_PER_PAGE = 409`).
- `source/src/include/access/multixact_internal.h:93-122` — `MXOffsetToFlagsOffset` / `MXOffsetToMemberOffset` / `MXOffsetToFlagsBitShift`.
- `source/src/backend/access/transam/multixact.c:816-961` — `RecordNewMultiXact` (writes both offsets + the member rows; bank-hops as needed).
- `source/src/backend/access/transam/multixact.c:1171-1398` — `GetMultiXactIdMembers` (two-stage lookup, length = next-offset − offset).
- `source/src/backend/access/transam/multixact.c:1785-1813` — `SimpleLruRequest` for both SLRUs; **members uses `long_segment_names = true`**.
- `source/src/backend/access/transam/multixact.c:2677-2801` — `TruncateMultiXact` (members-first, then offsets, in a critical section).
- `source/src/backend/access/transam/multixact.c:2810-2835` — `MultiXactOffsetPagePrecedes` (modular) vs `MultiXactMemberPagePrecedes` (plain `<`).

## Why two SLRUs

The file banner spells out the alternative and why it was rejected:

> We could alternatively use one area containing counts and TransactionIds,
> with valid MultiXactId values pointing at slots containing counts; but that
> way seems less robust since it would get completely confused if someone
> inquired about a bogus MultiXactId that pointed to an intermediate slot
> containing an XID.

[from-comment] (`multixact.c:19-25`).

The two-SLRU design means a corrupted or replayed-from-future MultiXactId
lookup either finds a zero-offset (→ raise an explicit error) or a sane
offset range (→ read N members), but cannot accidentally interpret a member
TransactionId as a length.

## Offsets-SLRU layout

```
pg_multixact/offsets/<segno>
  page i  = MULTIXACT_OFFSETS_PER_PAGE × MultiXactOffset (uint64)
  at BLCKSZ = 8 KiB → 1024 offsets per page
  at SLRU_PAGES_PER_SEGMENT = 32 → 32 768 offsets per segment file
```

A MultiXactId `m` indexes into:

```c
/* multixact_internal.h:34-44 */
page  = m / MULTIXACT_OFFSETS_PER_PAGE   /* = m / 1024 */
entry = m % MULTIXACT_OFFSETS_PER_PAGE
```

`MultiXactOffset` is **64-bit** (it counts members, which can vastly exceed
4 billion across the cluster's lifetime). One offset = 8 bytes;
`MULTIXACT_OFFSETS_PER_PAGE = BLCKSZ / sizeof(MultiXactOffset)`. [verified-by-code]
(`multixact_internal.h:31-32`).

## Members-SLRU layout — the 20-byte group

The members area carries `(xid, status)` pairs but the per-pair alignment
would force packing tricks if naively interleaved. The chosen layout is a
**group** of 5 words (4 + 4 + 4 + 4 + 4 = 20 bytes):

```
        +---------------------------+  +0
        |  4 flag bytes (1 byte/xid)|     (uint32 flagsword, with each xid's
        |                           |      MultiXactStatus in its 8-bit slot)
        +---------------------------+  +4
        |  TransactionId xid[0]     |
        +---------------------------+  +8
        |  TransactionId xid[1]     |
        +---------------------------+  +12
        |  TransactionId xid[2]     |
        +---------------------------+  +16
        |  TransactionId xid[3]     |
        +---------------------------+  +20
```

```c
/* multixact_internal.h:64-78 */
#define MXACT_MEMBER_BITS_PER_XACT       8
#define MULTIXACT_FLAGBYTES_PER_GROUP    4
#define MULTIXACT_MEMBERS_PER_MEMBERGROUP    4   /* = FLAGBYTES × 1 byte/flag */
#define MULTIXACT_MEMBERGROUP_SIZE       (4 × sizeof(TransactionId) + 4)
                                                 /* = 20 bytes */
#define MULTIXACT_MEMBERGROUPS_PER_PAGE  (BLCKSZ / 20)        /* = 409 */
#define MULTIXACT_MEMBERS_PER_PAGE       (409 × 4)            /* = 1636 */
```

This packs `BLCKSZ / 20 = 409` groups per page, wasting 12 bytes per page
("simplicity (and performance) trumps space efficiency here" — banner).
[from-comment] (`multixact_internal.h:52-63`).

A MultiXactOffset (a position in the members area) decomposes into:

```c
/* multixact_internal.h:80-122 */
page          = offset / 1636
group_in_page = (offset / 4) % 409
member_in_grp = offset % 4
byteoff       = group_in_page × 20
flagsoff      = byteoff
memberoff     = byteoff + 4 + member_in_grp × 4
bshift        = member_in_grp × 8
```

The 8-bit-per-status field (`MXACT_MEMBER_BITS_PER_XACT = 8`) actually
holds a small enum value (0..5, see `MultiXactStatus`) — the spare bits
allow forward compatibility but are currently unused. [verified-by-code]
(`multixact_internal.h:65-67`).

## Long segment filenames

MultiXactOffset is `uint64`, so the members SLRU's segment numbers can
exceed `2^24` over a cluster's lifetime. The offsets SLRU's segment count is
bounded by `MaxMultiXactId / MULTIXACT_OFFSETS_PER_PAGE / SLRU_PAGES_PER_SEGMENT`
which fits in 24 bits. So:

- **offsets** SLRU: `long_segment_names = false` (4–6 hex chars, max segno `2^24-1`).
- **members** SLRU: `long_segment_names = true` (15 hex chars, max segno `2^60-1`).

[verified-by-code] (`multixact.c:1788`, `multixact.c:1803`).

This is the **only** SLRU in the tree that uses long filenames at the time
of writing. The 15-char width (not 16) keeps members filenames visually
distinct from 24-char WAL segments. [from-comment] (`slru.c:96-105`).

## RecordNewMultiXact — write path

`RecordNewMultiXact(multi, offset, nmembers, members)` is called under the
`MultiXactGenLock` (the global counter lock) inside a critical section. It
does **three** writes through the bank-locked SLRU layer:

1. **My offset** — write `offset` at `offsets[multi]`.
2. **Next mxact's offset** — write `offset + nmembers` at `offsets[multi+1]`.
   This is the "end-of-mine" trick: the *next* mxact's pointer doubles as
   *my* length sentinel.
3. **My members** — write the `nmembers` `(xid, status)` pairs into the
   members SLRU starting at byte position derived from `offset`.

```c
/* multixact.c:850-863 — write my offset */
lock = SimpleLruGetBankLock(MultiXactOffsetCtl, pageno);
LWLockAcquire(lock, LW_EXCLUSIVE);
slotno = SimpleLruReadPage(MultiXactOffsetCtl, pageno, true, &multi);
offptr = (MultiXactOffset *) shared->page_buffer[slotno];
offptr += entryno;
if (*offptr != offset) {
    Assert(*offptr == 0);              /* must be unset, not stale */
    *offptr = offset;
    shared->page_dirty[slotno] = true;
}
```

The `*offptr == 0` assertion is the "already set by a racing peer" guard:
multiple backends may generate MultiXactIds concurrently, and the
*previous* mxact's `RecordNewMultiXact` may have already filled in *our*
slot (as its next-mxact sentinel). If so, just confirm equality and skip
re-writing. [from-comment] (`multixact.c:841-848`).

Step 2 may have to cross a page boundary — if `next_pageno != pageno`, swap
the bank lock (`multixact.c:877-885`). Note: this is a **release-then-acquire**
swap, not a held-while-acquiring, so it cannot deadlock — but it does
allow a window where neither lock is held, which is fine because the
critical section + MultiXactGenLock serialize the broader operation.
[verified-by-code] (`multixact.c:876-885`).

Step 3 walks the member groups. For each member, derive `pageno =
MXOffsetToMemberPage(offset)`. If the page (and hence possibly bank)
changes, swap the bank lock. The inner write is:

```c
/* multixact.c:943-956 — write one member */
memberptr = page_buffer[slotno] + memberoff;
*memberptr = members[i].xid;

flagsptr = (uint32 *) (page_buffer[slotno] + flagsoff);
flagsval = *flagsptr;
flagsval &= ~(0xFF << bshift);
flagsval |= (members[i].status << bshift);
*flagsptr = flagsval;
shared->page_dirty[slotno] = true;
```

The flagsword is read-modify-written under the bank lock — same idiom as
CLOG's bit-packing, but at byte granularity. [verified-by-code]
(`multixact.c:943-956`).

## GetMultiXactIdMembers — two-stage lookup

The lookup is the inverse of the write:

1. **Local cache check** — `mXactCacheGetById(multi)`. Each backend keeps a
   per-process cache of recently-seen MultiXactIds; if hit, return without
   touching SLRU. [verified-by-code] (`multixact.c:1196-1203`).
2. **Visibility filter** — `MultiXactIdSetOldestVisible()` publishes
   `MyOldestVisibleMXactIdSlot()` so vacuum sees us holding a reference. If
   `isLockOnly && multi < oldestVisible`, the multi is unreachable and we
   return -1. [verified-by-code] (`multixact.c:1205-1219`).
3. **Wraparound sanity** — read `oldestMXact` and `nextMXact` under
   `MultiXactGenLock SHARED`; raise hard error if `multi` is outside that
   range. [verified-by-code] (`multixact.c:1235-1252`).
4. **Read my offset** — exclusive-lock the offsets bank, read
   `offsets[multi]` → `offset`. If `offset == 0`, raise corruption error
   (means the next-mxact sentinel was never written — typically a crash
   after `GetNewMultiXactId` but before `RecordNewMultiXact`).
   [verified-by-code] (`multixact.c:1264-1276`).
5. **Read next-mxact's offset** — possibly bank-hop. The "next" handles
   wraparound via `NextMultiXactId(multi) = multi == MaxMultiXactId ?
   FirstMultiXactId : multi+1`. Result: `nextMXOffset`. Sanity check
   `nextMXOffset != 0 && nextMXOffset > offset && nextMXOffset − offset ≤
   INT32_MAX`. [verified-by-code] (`multixact.c:1278-1336`).
6. **Length = `nextMXOffset − offset`**. Allocate `length × sizeof(MultiXactMember)`
   and loop reading members from the members SLRU, bank-hopping as needed.
   [verified-by-code] (`multixact.c:1337-1388`).
7. **Cache the result** — `mXactCachePut(multi, length, ptr)` so the next
   lookup of the same multi is a cache hit. [verified-by-code]
   (`multixact.c:1391-1397`).

The bank-hop pattern (steps 5 and 6) is the same as in `RecordNewMultiXact`:
compare new vs old lock pointer, release-then-acquire if different. Note
**neither path holds two SLRU locks simultaneously** — this matches the
"avoid holding more than one of these locks at a time" rule from the shared
state comment (`multixact.c:130-133`). [from-comment] (`multixact.c:1290-1305`,
`multixact.c:1355-1370`).

## WAL discipline — different from CLOG

CLOG uses async-commit LSN tracking on SLRU pages because a heap tuple's
visibility depends on its CLOG entry being durable. MultiXact intentionally
**does not** enforce write-WAL-before-data:

> XLOG interactions: this module generates a record whenever a new OFFSETs
> or MEMBERs page is initialized to zeroes, as well as an
> XLOG_MULTIXACT_CREATE_ID record whenever a new MultiXactId is defined.
> This module ignores the WAL rule "write xlog before data," because it
> suffices that actions recording a MultiXactId in a heap xmax do follow
> that rule.

[from-comment] (`multixact.c:27-37`).

The argument: a multixact only matters when some `t_xmax` references it.
The heap-page WAL record carrying that `t_xmax` provides the LSN interlock
via the normal buffer manager — i.e. the heap page can't go to disk
without its WAL record. If the SLRU member/offset data hits disk first,
fine; the heap page hasn't been written yet, so on crash no `t_xmax`
references that multi and the data is unreachable. If the SLRU data hits
disk *later* than the heap page's WAL, replay reads the
`XLOG_MULTIXACT_CREATE_ID` record (whose content "completely rebuilds the
data entered since the last checkpoint") and reconstructs the SLRU pages.

So MultiXact's SLRUs set `nlsns = 0` (no `group_lsn[]` array) and the
[[slru-page-replacement]] write path skips its WAL-flush dance for them.
[verified-by-code] (`multixact.c:1785-1813` — no `.nlsns` parameter, defaults to 0).

## TruncateMultiXact — the order matters

`TruncateMultiXact(newOldestMulti, newOldestMultiDB)` is called from
vacuum (driven by `pg_class.relminmxid` aggregation through `pg_database`
into pg_control's `oldestMultiXactId`). The flow:

1. **`MultiXactTruncationLock` exclusive** — only one truncation at a time
   ("otherwise parts of members might vanish while we're doing lookups").
   [from-comment] (`multixact.c:2689-2694`).
2. Snapshot `nextMulti`, `nextOffset`, `oldestMulti` under MultiXactGenLock
   SHARED.
3. Early-out if `newOldestMulti <= oldestMulti` (backward motion guard).
4. Compute `newOldestOffset` via `find_multixact_start(newOldestMulti)`.
   If that lookup fails (the multi exists in counters but not on disk —
   "rare corner case due to bugs"), skip truncation with a LOG message.
5. **Critical section + `DELAY_CHKPT_START`** — once started, the truncate
   record + the truncation must be atomic w.r.t. checkpoints. If a
   checkpoint were to happen between WAL log and disk delete, replay could
   skip the truncate record and leave dead segments around.
6. `WriteMTruncateXlogRec(newOldestMultiDB, newOldestMulti, newOldestOffset)`
   — WAL log with the trio.
7. **Update in-memory limits** under MultiXactGenLock EXCLUSIVE
   (`oldestMultiXactId`, `oldestMultiXactDB`, `oldestOffset`). Must happen
   *before* disk truncation so concurrent lookups don't try to read a
   page we're about to delete. Must be inside the critical section so a
   crash after the update + before the disk truncate makes the next
   truncation idempotent rather than lookup-error.
8. **`PerformMembersTruncation(newOldestOffset)` FIRST**, then
   **`PerformOffsetsTruncation(newOldestMulti)` SECOND**. Order matters:
   if offsets were truncated first and we crashed, the next
   `find_multixact_start` for `newOldestMulti` would fail and we'd be
   stuck. With members-first, a crash before the offsets truncation just
   leaves orphan offset-pages that the next truncation cleans up.
9. Clear `DELAY_CHKPT_START`, release locks.

[verified-by-code] (`multixact.c:2755-2800`).

## Page-precedes comparators — different rules

The two SLRUs have different `PagePrecedes` callbacks:

- **Offsets**: `MultiXactOffsetPagePrecedes` uses modular `MultiXactIdPrecedes`
  (32-bit MultiXactId wraparound). Same shape as `CLOGPagePrecedes`.
- **Members**: `MultiXactMemberPagePrecedes` is just `page1 < page2`.
  "There is no 'invalid offset number' and members never wrap around, so
  use the numbers verbatim." [from-comment] (`multixact.c:2826-2835`).

The members area uses a 64-bit offset that monotonically grows for the
lifetime of the cluster. Truncation moves the cutoff *forward* and disk
space is reclaimed by segment-file deletion — there is no logical
wraparound to defend against in the comparator. Only the 32-bit
**MultiXactId** wraps, and that maps to the offsets SLRU.

`SlruPagePrecedesUnitTests` is called only for the offsets SLRU at startup:

```c
/* multixact.c:1817-1823 */
SlruPagePrecedesUnitTests(MultiXactOffsetCtl, MULTIXACT_OFFSETS_PER_PAGE);
/* members SLRU doesn't call SimpleLruTruncate() or meet criteria for unit tests */
```

…because `PerformMembersTruncation` doesn't call `SimpleLruTruncate` (it
goes through a custom path; members are bulk-deleted by segment files via
the directory scan with `SlruScanDirCbDeleteCutoff` under a plain `<`
comparator). [verified-by-code] (`multixact.c:1819-1823`).

## Wraparound counters and the no-go zone

`GetNewMultiXactId` enforces three escalating limits (`multixact.c:1000-1110`):

- `multiWarnLimit` — start emitting WARNINGs.
- `multiVacLimit` — start forcing autovacuum cycles.
- `multiStopLimit` — refuse to assign new MultiXactIds (ERROR).
- Member-space twin: `MULTIXACT_MEMBER_LOW_THRESHOLD = 2 × 10^9` and
  `MULTIXACT_MEMBER_HIGH_THRESHOLD = 4 × 10^9` trigger more aggressive
  freezing when the **members** area (not MultiXactId space) gets large.
  [verified-by-code] (`multixact.c:99-100`).

These mirror the regular XID wraparound limits in `varsup.c`. The
multixact-specific need is that a member's TransactionId references must
also stay within frozen-safe range — if a member XID is older than the
table's `relfrozenxid`, it must already be frozen. Vacuum's
`MultiXactCutoffForRelation` computation balances both axes.
[unverified — exact computation in `vacuum.c`].

## Local cache (per-backend memo)

`mXactCacheGetById` / `mXactCachePut` is a per-backend hashtable that
remembers recently-resolved `(multi → members[])` mappings. The cache is
allocated in `TopMemoryContext` and freed at backend exit; its size cap is
not heap-pressure-aware — it just grows. The motivation: the same multi
is queried repeatedly during a heap scan because every visible row's
xmax may name the same locker set. [verified-by-code]
(`multixact.c:1196-1203`, `multixact.c:1391-1393`).

## Invariants and races

1. **`offsets[multi] == 0` means "not yet written, or being written"**. A
   read of zero is either a not-yet-initialized slot (during create-window
   race) or a corruption indicator. The caller distinguishes via the
   wraparound bound check that precedes the read. [from-comment]
   (`multixact.c:1273-1276`).
2. **`offsets[multi+1]` is the length sentinel.** Length =
   `offsets[multi+1] − offsets[multi]`. [verified-by-code]
   (`multixact.c:1337`).
3. **Never hold two SLRU bank locks at once.** All bank-hops are
   release-then-acquire. [from-comment] (`multixact.c:130-133`).
4. **Members truncate before offsets** — survives crash mid-truncate.
   [verified-by-code] (`multixact.c:2791-2796`).
5. **Truncation runs in a critical section with `DELAY_CHKPT_START`** —
   prevents the truncation WAL record from being skipped by an
   intervening checkpoint. [from-comment] (`multixact.c:2766-2772`).
6. **The local mXactCache is not invalidated on truncation.** Backends are
   expected to drop their visibility (via `MultiXactIdSetOldestVisible`)
   before a multi can be truncated, so a stale cache entry is impossible.
   [inferred].
7. **MultiXact ignores write-WAL-before-data** because the heap-page LSN
   interlock provides indirection. The `XLOG_MULTIXACT_CREATE_ID` record
   carries the full create-payload for redo-reconstruction.
   [from-comment] (`multixact.c:27-41`).

## Useful greps

```bash
# All MultiXact entry points (creates, expansions, reads):
grep -nE "MultiXactIdCreate|MultiXactIdExpand|GetMultiXactIdMembers" \
       source/src/backend/access/transam/multixact.c

# Bank-lock dance call sites:
grep -n "SimpleLruGetBankLock(MultiXact" \
       source/src/backend/access/transam/multixact.c

# The single-mxact-on-page write idiom in heapam:
grep -rn "MultiXactIdSetOldestVisible\|MultiXactIdExpand" \
       source/src/backend/access/heap/

# Where the heap freezing code touches multixact horizons:
grep -rn "relminmxid\|MultiXactCutoff\|FreezeMultiXactId" \
       source/src/backend/access/heap/
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/transam/multixact.c`](../files/src/backend/access/transam/multixact.c.md) | 1 | file banner: "two SLRU areas … this trick allows us to store variable length arrays of TransactionIds." |
| [`src/backend/access/transam/multixact.c`](../files/src/backend/access/transam/multixact.c.md) | 816 | RecordNewMultiXact (writes both offsets + the member rows; bank-hops as needed) |
| [`src/backend/access/transam/multixact.c`](../files/src/backend/access/transam/multixact.c.md) | 1171 | GetMultiXactIdMembers (two-stage lookup, length = next-offset − offset) |
| [`src/backend/access/transam/multixact.c`](../files/src/backend/access/transam/multixact.c.md) | 1785 | SimpleLruRequest for both SLRUs; members uses long_segment_names = true |
| [`src/backend/access/transam/multixact.c`](../files/src/backend/access/transam/multixact.c.md) | 2677 | TruncateMultiXact (members-first, then offsets, in a critical section) |
| [`src/backend/access/transam/multixact.c`](../files/src/backend/access/transam/multixact.c.md) | 2810 | MultiXactOffsetPagePrecedes (modular) vs MultiXactMemberPagePrecedes (plain <) |
| [`src/include/access/multixact.h`](../files/src/include/access/multixact.h.md) | 36 | MultiXactStatus enum (ForKeyShare … Update) |
| [`src/include/access/multixact.h`](../files/src/include/access/multixact.h.md) | 55 | MultiXactMember { xid; status } |
| [`src/include/access/multixact_internal.h`](../files/src/include/access/multixact_internal.h.md) | 26 | offsets-page macros (MULTIXACT_OFFSETS_PER_PAGE = BLCKSZ/8) |
| [`src/include/access/multixact_internal.h`](../files/src/include/access/multixact_internal.h.md) | 52 | members-page macros (MULTIXACT_MEMBERGROUP_SIZE = 20, MULTIXACT_MEMBERGROUPS_PER_PAGE = 409) |
| [`src/include/access/multixact_internal.h`](../files/src/include/access/multixact_internal.h.md) | 93 | MXOffsetToFlagsOffset / MXOffsetToMemberOffset / MXOffsetToFlagsBitShift |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->

## Cross-references

- [[slru-page-replacement]] — buffer cache + bank-lock dance under both SLRUs.
- [[clog-slru]] — single-SLRU sibling with fixed 2-bit-per-XID encoding.
- [[tuple-locking-modes]] — heapam's view of the `MultiXactStatus` enum.
- [[xmin-horizon-management]] — vacuum aggregates `relminmxid` into the global cutoff driving `TruncateMultiXact`.
- `knowledge/subsystems/access-transam.md` §"MultiXact" — subsystem-level overview that points here.
