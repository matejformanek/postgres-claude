# `src/include/storage/itemid.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 184

## Role

**Line-pointer (LP) definition** — the 4-byte
`ItemIdData` that lives in the linp[] array of every buffer page,
plus the macros to read/write its bitfields. The fundamental
on-disk indirection from a (block, offset) TID to a tuple's bytes
on the page.

## Bit layout

`ItemIdData` is a 32-bit struct (lines 25-30):

```
lp_off : 15  (offset to tuple from start of page; 0..32767)
lp_flags : 2 (LP_UNUSED=0 / LP_NORMAL=1 / LP_REDIRECT=2 / LP_DEAD=3)
lp_len : 15  (byte length of tuple; 0 if no storage)
```

Total: 4 bytes (the compiler packs the 15+2+15 bitfield into a
single `unsigned`).

## State machine

[verified-by-code] `source/src/include/storage/itemid.h:35-42`

- `LP_UNUSED` (0) — slot is free for reuse; `lp_len == 0`
- `LP_NORMAL` (1) — points at valid tuple; `lp_len > 0`,
  `lp_off` points at heap tuple
- `LP_REDIRECT` (2) — HOT redirect; `lp_len == 0`, `lp_off`
  holds the OffsetNumber of the next line pointer in the HOT
  chain
- `LP_DEAD` (3) — dead, may or may not have storage; used as a
  hint-bit by index scans

## Invariants

- INV-1: `lp_len == 0` for every state EXCEPT `LP_NORMAL` (and
  `LP_DEAD` which "may or may not"). [from-comment] lines 17-23
  and 38-41.
- INV-2: `ItemIdSet*` macros multiply-evaluate `itemId` — caller
  must not pass side-effectful expressions. [from-comment]
  lines 126, 138, 150, 161.
- INV-3: `ItemIdMarkDead` is **race-free for hint use** in
  indexes — "multiple processors can do this in parallel and
  get the same result". [from-comment] lines 175-177. Other
  ItemId state transitions are NOT race-safe and require buffer
  content lock.
- INV-4: `lp_off` is 15 bits so max 32 767 — fits ≤ BLCKSZ=32K.
  Larger BLCKSZ values would overflow. [inferred from bitfield
  layout]

## Trust boundary (Phase D)

- Bitfield layout is on-disk. **Any change here requires WAL
  format change + pg_upgrade story.**
- `ItemIdSetRedirect(itemId, link)` stores the link OffsetNumber
  in `lp_off` (line 152-157). If `link > MaxOffsetNumber`,
  follow-up HOT-chain walk reads junk. Verify via
  `OffsetNumberIsValid(link)` before the macro.
- 15-bit `lp_off` is precisely 32K-1: an Assert
  `lp_off < BLCKSZ` would catch bitfield overflow at write time,
  but the cast inside the macro silently truncates. Site:
  `source/src/include/storage/itemid.h:140-145`
  (`ItemIdSetNormal`). [unverified — no current overflow bug]

## Cross-refs

- `knowledge/subsystems/storage-buffer.md` — page layout
- `knowledge/files/src/include/storage/bufpage.h.md` (existing) —
  the `PageHeaderData + linp[] + tuples` layout
- `knowledge/files/src/include/storage/off.h.md`

## Issues

- ISSUE-DESIGN: `ItemIdSetNormal(itemId, off, len)` silently
  truncates `off` to 15 bits and `len` to 15 bits via bitfield
  assignment. An Assert
  `(off < BLCKSZ && len <= BLCKSZ)` at the macro entry would
  catch overflow during development. (Low — current callers
  always derive `off` from in-page positions.)
