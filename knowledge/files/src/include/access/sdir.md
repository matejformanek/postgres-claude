# `access/sdir.h` — ScanDirection enum

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/access/sdir.h`)

## Role
Tiny header defining the three-valued scan direction used by every
table-AM and index-AM scan: `BackwardScanDirection = -1`,
`NoMovementScanDirection = 0`, `ForwardScanDirection = 1`.

## Public API
- `ScanDirection` enum (`sdir.h:24`-`29`).
- `ScanDirectionCombine(a, b)` macro (`sdir.h:36`) — multiplies; relies on
  ±1 encoding.
- `ScanDirectionIsValid(direction)` (`sdir.h:42`).
- `ScanDirectionIsBackward(direction)` (`sdir.h:50`).
- `ScanDirectionIsNoMovement(direction)` (`sdir.h:54`).
- `ScanDirectionIsForward(direction)` (`sdir.h:58`).

## Invariants
- The numeric values **must** stay ±1/0 — `ScanDirectionCombine` depends
  on it. `[from-comment]` (`sdir.h:19`-`23`, `:33`-`35`).
- `NoMovementScanDirection` is **never** passed to actual scan callbacks;
  Assert at `table_scan_getnextslot` enforces this. `[verified-by-code]`
  (`tableam.h:1101`-`1102`).

## Notable internals
- The "mathematical trick" of multiplying directions is used to compose
  cursor MOVE FORWARD/BACKWARD with index scan directions; e.g., MOVE
  BACKWARD on a backward cursor gives forward.

## Trust-boundary / Phase D surface

None. Constants only; no attacker input.

## Cross-refs
- `knowledge/files/src/include/access/tableam.h` — direction passed to
  `scan_getnextslot`.
- `knowledge/files/src/include/access/genam.h` — passed to
  `index_getnext_tid` / `index_getnext_slot`.

## Issues
(none)
