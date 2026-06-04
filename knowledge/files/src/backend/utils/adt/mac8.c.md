---
path: src/backend/utils/adt/mac8.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 569
depth: deep
---

# mac8.c

- **Source path:** `source/src/backend/utils/adt/mac8.c`
- **Lines:** 569
- **Depth:** deep
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Companion files:** `src/include/utils/inet.h` (`macaddr8` struct = 8 `unsigned char` fields `a`..`h`, and the sibling `macaddr`; `PG_GETARG_MACADDR8_P`/`PG_RETURN_MACADDR8_P`), `src/common/hashfn.h`, `src/backend/utils/adt/mac.c` (the 6-byte sibling)

## Purpose
Implements the `macaddr8` SQL type: an 8-byte EUI-64 MAC address. Accepts both EUI-48 (6-byte) and EUI-64 (8-byte) text/binary input; 6-byte input is widened to EUI-64 by inserting `FF FE` as the 4th/5th bytes `[verified-by-code: mac8.c:198-206]` (the same modified-EUI-64 expansion used in IPv6). Output is always the 8-byte colon form `[verified-by-code: mac8.c:241]`. Provides comparison/btree/hash, bitwise NOT/AND/OR, `macaddr8_trunc` (zero lower 5 bytes), `macaddr8_set7bit` (set the U/L bit for IPv6 modified EUI-64), and casts to/from `macaddr`. Unlike `mac.c`, there is NO sortsupport/abbreviated-key path. All entry points are fmgr V1.

## Public symbols
| Symbol | file:line | Role |
| --- | --- | --- |
| `macaddr8_in` | mac8.c:96 | Text input, byte-pair scanner; 6- or 8-byte accepted |
| `macaddr8_out` | mac8.c:233 | Output as 8-byte `aa:...:hh` |
| `macaddr8_recv` / `macaddr8_send` | mac8.c:253 / 286 | Binary I/O; recv widens 6-byte input to EUI-64 |
| `macaddr8_cmp` | mac8.c:324 | btree 3-way compare via `macaddr8_cmp_internal` |
| `macaddr8_lt/le/eq/ge/gt/ne` | mac8.c:337-389 | Comparison operators |
| `hashmacaddr8` / `hashmacaddr8extended` | mac8.c:394 / 402 | hash opclass over `hash_any`(`sizeof(macaddr8)`) |
| `macaddr8_not` / `macaddr8_and` / `macaddr8_or` | mac8.c:414 / 433 / 453 | Bitwise ops |
| `macaddr8_trunc` | mac8.c:476 | Zero bytes d..h (keep 24-bit OUI) |
| `macaddr8_set7bit` | mac8.c:499 | `a |= 0x02` — modified EUI-64 U/L bit |
| `macaddrtomacaddr8` | mac8.c:523 | Cast macaddr -> macaddr8 (insert FF FE) |
| `macaddr8tomacaddr` | mac8.c:544 | Cast macaddr8 -> macaddr (requires FF FE in bytes d/e) |

## Internal landmarks
- **Hex helper** (`hex2_to_uchar`, mac8.c:58-91): table-driven `hexlookup[128]` mapping; two digits -> one byte, sets `*badhex` if either digit is non-hex or string ends mid-pair. `*ptr > 127` guards the 128-entry table against high bytes `[verified-by-code: mac8.c:65,77]`.
- **Parser** (`macaddr8_in`, mac8.c:96-228): hand-rolled state machine (not `sscanf`). Skips leading whitespace, reads byte pairs into `a`..`h` via a `count`-indexed `switch`, enforces a single consistent spacer (`:`/`-`/`.`) across the whole string (mac8.c:169-181), allows trailing whitespace only after 6 or 8 bytes, and `goto fail` for a 7-byte count or trailing garbage `[verified-by-code: mac8.c:131-208]`.
- **EUI-48 -> EUI-64 widening** (mac8.c:198-206): when `count == 6`, shifts `d/e/f` to `f/g/h` and sets `d=0xFF`, `e=0xFE`. The recv path does the equivalent when `buf->len == 6` (mac8.c:265-274).
- **Comparison key** (`hibits`/`lobits`, mac8.c:33-37): packs a/b/c/d into one `unsigned long`, e/f/g/h into another; compared high-then-low `[verified-by-code: mac8.c:309-322]`.
- **Cast guard** (`macaddr8tomacaddr`, mac8.c:552-559): rejects any macaddr8 whose bytes d/e are not exactly `FF FE`, with an errhint naming the `xx:xx:xx:ff:fe:xx:xx:xx` eligible pattern `[verified-by-code: mac8.c:552-559]`.

## Invariants & gotchas
- **EUI-64 conversion is `FF FE` insertion at bytes 4/5, and the inverse cast requires it.** Widening always inserts `FF FE` (mac8.c:204-205, 534-535); narrowing back to macaddr errors unless those exact bytes are present (mac8.c:552). A macaddr8 not derived from a 6-byte address generally cannot be downcast `[verified-by-code: mac8.c:552-559]`.
- **`sizeof(macaddr8)` == 8 with no padding** — eight contiguous `unsigned char` fields (inet.h:107-117), so `hash_any(..., sizeof(macaddr8))` hashes exactly the 8 value bytes; equal addresses hash equally `[verified-by-code: mac8.c:399; inet.h:107-117]`.
- **All result allocations use `palloc0_object`** (e.g. mac8.c:210,259,420,482,529) — zero-initialized so that, e.g., `macaddr8tomacaddr` filling only 6 of the macaddr's fields cannot leave garbage; the bitwise/trunc ops then overwrite every byte anyway. Consistent defensive choice vs `mac.c`'s plain `palloc_object`.
- **`set7bit` flips only the OUI U/L bit** (`a |= 0x02`, mac8.c:507): used to produce the IPv6 modified-EUI-64 interface identifier; does not touch the FF FE marker.
- **No sortsupport** — `macaddr8` lacks the abbreviated-key path that `macaddr` has; an 8-byte value would fully occupy a 64-bit Datum, but the optimization was simply not added here `[inferred]` (absence in mac8.c vs mac.c:351-430).

## Cross-references
- Sibling 6-byte type: [[knowledge/files/src/backend/utils/adt/mac.c]] (shares `inet.h`, `hibits`/`lobits` idiom).
- Sibling adt I/O types: [[knowledge/files/src/backend/utils/adt/pg_lsn.c]], [[knowledge/files/src/backend/utils/adt/uuid.c]].
- fmgr V1 conventions: [[knowledge/idioms/fmgr-and-spi]].

## Potential issues
- **[ISSUE-correctness: `isspace`/`hexlookup` fed a plain `char`]** `mac8.c:116,186` — `isspace(*ptr)` is called on `*ptr` where `ptr` is `const unsigned char *` (declared mac8.c:101), so this is actually safe here; the high-byte guard `*ptr > 127` (mac8.c:65,77) protects the `hexlookup[128]` table access. No defect — noting only because `<ctype.h>` on a signed `char` is the classic adt pitfall and a future refactor changing `ptr`'s type to `char *` would reintroduce it. Severity: nit.

## Confidence tag tally
- verified-by-code: 9
- from-comment: 0
- inferred: 1
- ISSUE: 1 (correctness, nit — currently non-defect)
