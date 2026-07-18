# `src/include/storage/bufpage.h`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~520

## Purpose

The on-disk page format. *Every block of every relation on disk
follows this layout.* Defines `PageHeaderData`, the access macros
that read/write its fields safely, the `PD_*` flag bits, and the page
version constant `PG_PAGE_LAYOUT_VERSION`.

## Top of file (lines 24–78)

ASCII diagram of the page: header → linp1..N (growing forward),
free space, tupleN..tuple1 (growing backward), special space at the
end. Plus the rules: linps are 1-indexed (`FirstOffsetNumber = 1`),
tuples are placed "backwards" so the linp can be reordered without
moving tuple bodies. The special space is AM-specific (btree opaque,
hash opaque, etc.).

## Types

- `PageData = char`, `Page = PageData *` (lines 80–81).
- `LocationIndex = uint16` (line 90) — byte offset within a page;
  effective max 2^15 due to `ItemIdData.lp_off` being 15 bits.
- `PageXLogRecPtr` (lines 101–136) — endianness-aware 64-bit LSN
  store/load; legacy two-word layout.
- `PageHeaderData` (lines 184–197): `pd_lsn`, `pd_checksum`,
  `pd_flags`, `pd_lower`, `pd_upper`, `pd_special`,
  `pd_pagesize_version`, `pd_prune_xid`, then flexible
  `pd_linp[FLEXIBLE_ARRAY_MEMBER]` of `ItemIdData`.

## Flag bits (`pd_flags`)

- `PD_HAS_FREE_LINES` — hint, recyclable linps somewhere.
- `PD_PAGE_FULL` — hint, page nearly full (used by HOT).
- `PD_ALL_VISIBLE` — set during VACUUM, used for index-only scans
  & visibility map sync.
- `PD_VALID_FLAG_BITS` — mask of all defined bits.

## Page version

- `PG_PAGE_LAYOUT_VERSION` is currently 4. (Constant defined here.)

## Accessor inline functions

`PageGetItemId`, `PageGetItem`, `PageGetMaxOffsetNumber`,
`PageGetPageSize`, `PageGetSpecialPointer`, `PageGetSpecialSize`,
`PageGetLSN`, `PageSetLSN`, `PageIsNew`, `PageIsEmpty`,
`PageHasFreeLinePointers`, `PageSetHasFreeLinePointers`,
`PageClearHasFreeLinePointers`, etc.

## Tag tally

`[verified-by-code]` 2 / `[from-comment]` 4.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/storage-buffer.md](../../../../subsystems/storage-buffer.md)
