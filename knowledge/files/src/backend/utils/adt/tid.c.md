---
path: src/backend/utils/adt/tid.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 463
depth: deep
---

# tid.c

- **Source path:** `source/src/backend/utils/adt/tid.c`
- **Lines:** 463
- **Depth:** deep
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Companion files:** `src/include/storage/itemptr.h` (`ItemPointerData`, `ItemPointerSet`, `ItemPointerCompare`, `ItemPointerCopy`, `ItemPointerGet*NoCheck`, `BlockIdData`), `src/include/storage/block.h` (BlockNumber), `src/include/storage/off.h` (OffsetNumber), `src/include/access/tableam.h` (`table_beginscan_tid`, `table_tuple_get_latest_tid`), `src/include/catalog/pg_proc.dat`

## Purpose
SQL type I/O, comparison, and hashing for the `tid` type — a `(block, offset)` tuple identifier (`ItemPointerData`) — plus the `currtid_byrelname` machinery that resolves the latest live version of a tuple given its CTID [from-comment `tid.c:3-4`, verified-by-code `tid.c:50-309`]. The comparison operators all funnel through `ItemPointerCompare` so block-major then offset-minor ordering is consistent [verified-by-code `tid.c:174-235`]. `currtid` also handles views by chasing a single `ctid` Var through the view's SELECT rule down to a base relation [verified-by-code `tid.c:365-438`].

## Public symbols
| Symbol | file:line | Role |
|---|---|---|
| `tidin` | `tid.c:50` | cstring `"(block,offset)"` → tid; soft-error capable |
| `tidout` | `tid.c:117` | tid → `"(block,offset)"` cstring |
| `tidrecv` | `tid.c:137` | binary recv (int32 block + int16 offset) |
| `tidsend` | `tid.c:158` | binary send |
| `tideq`/`tidne` | `tid.c:174`/`183` | (in)equality via `ItemPointerCompare` |
| `tidlt`/`tidle`/`tidgt`/`tidge` | `tid.c:192`/`201`/`210`/`219` | ordering operators |
| `bttidcmp` | `tid.c:228` | btree 3-way compare |
| `tidlarger`/`tidsmaller` | `tid.c:237`/`246` | min/max aggregate support |
| `hashtid` | `tid.c:255` | hash over BlockIdData+OffsetNumber bytes |
| `hashtidextended` | `tid.c:270` | extended (seeded) hash |
| `tid_block` | `tid.c:287` | extract block number as int8 |
| `tid_offset` | `tid.c:302` | extract offset number as int4 |
| `currtid_byrelname` | `tid.c:445` | latest tuple version for CTID, by relation name |

## Internal landmarks
- Delimiter macros `LDELIM`/`RDELIM`/`DELIM` and `NTIDARGS` (=2) [verified-by-code `tid.c:39-42`].
- `tidin` parses two unsigned longs with `strtoul`, with a wide-`unsigned long` guard so block numbers out of `BlockNumber` range are rejected on 64-bit platforms (mirrors `uint32in_subr`) [from-comment + verified-by-code `tid.c:83-95`]; the offset is bounded by `USHRT_MAX` [verified-by-code `tid.c:97-104`].
- `currtid_internal` (static, `tid.c:323`): ACL-checks `ACL_SELECT`, dispatches views to `currtid_for_view`, rejects relkinds without storage, then runs a `table_beginscan_tid` + `table_tuple_get_latest_tid` under a registered latest snapshot [verified-by-code `tid.c:333-356`].
- `currtid_for_view` (static, `tid.c:365`): finds the `ctid` attribute (must be `TIDOID`), requires exactly one SELECT rule, resolves the target Var to a base RTE, opens that relation under `AccessShareLock`, and recurses into `currtid_internal` [verified-by-code `tid.c:375-432`].
- `hashtid`/`hashtidextended` deliberately hash `sizeof(BlockIdData) + sizeof(OffsetNumber)` bytes rather than `sizeof(ItemPointerData)` to avoid hashing compiler struct padding [from-comment `tid.c:260-267`, `tid.c:276-279`].

## Invariants & gotchas
- **tid uses NoCheck accessors on output/extract** because `tidin` permits `InvalidBlockNumber`/`InvalidOffsetNumber`; the checked accessors would reject those valid-on-input values [from-comment `tid.c:292`, `tid.c:307`; verified-by-code `tid.c:125-126`, `tid.c:293`, `tid.c:308`].
- **`tid_block` returns int8, `tid_offset` returns int4** because the unsigned source types (uint32 block, uint16 offset) overflow the signed SQL types one size down [from-comment `tid.c:283-286`, `tid.c:296-300`].
- **Hash must not include struct padding** — relying on `sizeof(ItemPointerData)` would make hashes depend on compiler padding and break hash joins/indexes across builds [from-comment `tid.c:260-267`].
- **Block/offset packing.** `ItemPointerSet(result, block, offset)` is the only sanctioned way to build a tid; the on-disk layout is BlockIdData (two 16-bit halves) + OffsetNumber [verified-by-code `tid.c:108`, `tid.c:150`; layout in `itemptr.h`].
- **currtid snapshot lifetime.** The latest snapshot is registered before the scan and unregistered after — do not reorder; the scan holds a reference [verified-by-code `tid.c:351-355`].
- **currtid view resolution is narrow:** only a single-action SELECT rule whose ctid target is a plain `Var` referencing `SelfItemPointerAttributeNumber` of a non-special varno is followed; anything else `elog(ERROR)`s [verified-by-code `tid.c:398-437`].

## Cross-references
- [[knowledge/data-structures/heap-tuple-layout.md]] — how ItemPointers index heap tuples.
- [[knowledge/subsystems/access-heap.md]] — `table_tuple_get_latest_tid` and HOT-chain latest-version semantics.
- [[knowledge/idioms/fmgr.md]] — V1 calling convention; soft-error `ereturn`/`escontext` pattern in `tidin`.
- [[knowledge/idioms/error-handling.md]] — `ereturn`/`escontext` vs `ereport`/`elog`.
- Sibling adt files: [[knowledge/files/src/backend/utils/adt/xid.c.md]], [[knowledge/files/src/backend/utils/adt/oid.c.md]].

## Potential issues
None surfaced. The NoCheck accessor usage and padding-aware hashing are documented intentional choices.

## Confidence tag tally
- [verified-by-code]: 13
- [from-comment]: 7
- [inferred]: 0
- [unverified]: 0
