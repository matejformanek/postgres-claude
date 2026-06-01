# bufmask.c

- **Source path:** `source/src/backend/access/common/bufmask.c`
- **Lines:** 129
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `bufmask.h`, every per-AM `*_mask` rmgr callback (`heap_mask`, `btree_mask`, `gin_mask`, …) that calls these.

## Purpose

Page-masking helpers used ONLY during WAL consistency checking (`wal_consistency_checking` GUC). When the standby replays a record, the per-rmgr `*_mask` callback runs both the primary's page and the standby's replayed page through these helpers to zero out fields that can legitimately differ (LSN, checksum, hint bits, unused space, dead-line-pointer flags) before bit-comparing. [from-comment, bufmask.c:1-15]

## Top-of-file comment

> "Routines for buffer masking. Used to mask certain bits in a page which can be different when the WAL is generated and when the WAL is applied." [from-comment, bufmask.c:3-7]

## Public surface

- `mask_page_lsn_and_checksum` (31) — Stamp `MASK_MARKER` into `pd_lsn` and `pd_checksum`.
- `mask_page_hint_bits` (46) — Zero `pd_prune_xid`, clear `PD_PAGE_FULL`, `PD_HAS_FREE_LINES`, and (for now) `PD_ALL_VISIBLE`.
- `mask_unused_space` (70) — Fill the gap between `pd_lower` and `pd_upper` with `MASK_MARKER` (the free space region is not WAL-logged and so may differ).
- `mask_lp_flags` (94) — Demote `LP_DEAD` line-pointers to `LP_UNUSED` (hint-bit equivalent; LP_DEAD may be set on the primary asynchronously and not replayed).
- `mask_page_content` (118) — Wipe the entire data area (`(char *)page + SizeOfPageHeaderData ... BLCKSZ` minus the line-pointer area). Used by AMs whose payload is irrelevant during consistency check.

## Key invariants

- Masking is for consistency checking ONLY — it must NEVER run during normal replay or write-out. Callers are gated by `wal_consistency_checking`. [inferred, standard PG pattern]
- `PD_ALL_VISIBLE` masking is preserved here only because the VM bit is set/cleared in subtle race windows that aren't guaranteed identical between primary and standby; the comment notes this is "worth investigating". [from-comment, bufmask.c:55-62]

## Cross-references

- Called from `*_mask` rmgr callbacks listed in `rmgrlist.h`; each AM's `_mask` decides which of these to apply. Example: `heap_mask` (in heapam_xlog.c) calls `mask_page_lsn_and_checksum`, `mask_page_hint_bits`, and `mask_unused_space`.

## Confidence tag tally
`[verified-by-code]=4 [from-comment]=3 [from-readme]=0 [inferred]=1 [unverified]=0`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
