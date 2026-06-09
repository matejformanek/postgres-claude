# `src/include/access/bufmask.h`

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**33 lines.**

## Role

Buffer-content masking primitives used during WAL replay verification
(`wal_consistency_checking`). Header lines 4-8 spell it out: "mask
certain bits in a page which can be different when the WAL is generated
and when the WAL is applied. This is really the job of each individual
rmgr, but we make things easier by providing some common routines to
handle cases which occur in multiple rmgrs."
[verified-by-code] `source/src/include/access/bufmask.h:1-15`

## Public API

One constant + five extern functions:

- `MASK_MARKER` = 0 — the byte value substituted into masked regions
  (line 24).
- `mask_page_lsn_and_checksum(page)` — wipe LSN + page checksum.
- `mask_page_hint_bits(page)` — clear non-WAL'd hint bits (e.g.
  `HEAP_XMIN_COMMITTED`, `LP_DEAD` on index leaves).
- `mask_unused_space(page)` — zero pd_lower..pd_upper hole.
- `mask_lp_flags(page)` — clear `lp_flags` bits that aren't WAL'd.
- `mask_page_content(page)` — full content mask (used by `heap_mask`
  for FROZEN/ALL_VISIBLE pages whose content is fully described by the
  VM page).
  [verified-by-code] lines 23-30.

## Invariants

- **INV-mask-deterministic:** after masking, two pages — one from the
  master and one from the standby replay — must compare byte-for-byte
  equal if replay is correct. Any per-rmgr `*_mask` that fails to mask
  a legitimately-divergent byte produces false-positive PANICs under
  `wal_consistency_checking`.
- **INV-mask-marker-fixed:** the marker is 0, not a "poison" pattern.
  This means accidentally-unmasked zero bytes look fine; bugs surface
  only when one side has a non-zero byte the other doesn't.
- Hint bits and LSN are NOT WAL'd in the redo record itself, hence the
  mask. The per-rmgr `*_mask` is registered via `PG_RMGR(..., mask, ...)`
  in `rmgrlist.h`.

## Notable internals

The header pulls only `storage/block.h` and `storage/bufmgr.h` — no
heap-specific or index-specific knowledge. All per-AM nuance lives in
the consumer (e.g. `heap_mask`, `btree_mask`).

## Trust-boundary / Phase D surface

Masking is page-format-sensitive: any change to the on-page layout
(new flag bit, new `lp_flags` value, new page header field) must
update the masking discipline or `wal_consistency_checking` will start
panicking on legitimate replays. This is a Phase-D-relevant
**robustness surface**: a Phase-D-style hardening that adds new
hint-like state to a page MUST extend `mask_page_hint_bits` or
introduce a per-rmgr mask. Otherwise standbys under
`wal_consistency_checking = all` will FATAL.

The helpers do not validate that the page actually has a valid header
before reading `pd_lower`/`pd_upper` — a corrupt WAL record producing
an invalid post-replay page can crash the masker.

## Cross-refs

- `access/rmgrlist.h` — registers per-rmgr `*_mask` slots.
- `src/backend/access/heap/heapam.c` (heap_mask), `nbtree/nbtdesc.c`
  (btree_mask), etc. — the consumers.
- `storage/bufpage.h` — page header layout the maskers depend on.

## Issues

- **ISSUE-cite**: header references `wal_consistency_checking` only by
  implication ("the WAL is generated and ... applied"). A direct
  cross-reference would help.
