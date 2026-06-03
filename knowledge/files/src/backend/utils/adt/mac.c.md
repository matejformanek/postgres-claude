---
path: src/backend/utils/adt/mac.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 430
depth: deep
---

# mac.c

- **Source path:** `source/src/backend/utils/adt/mac.c`
- **Lines:** 430
- **Depth:** deep
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Companion files:** `src/include/utils/inet.h` (`macaddr` struct = 6 `unsigned char` fields `a`..`f`, `PG_GETARG_MACADDR_P`/`PG_RETURN_MACADDR_P`, `DatumGetMacaddrP`), `src/include/utils/sortsupport.h` (`ssup_datum_unsigned_cmp`, `DatumBigEndianToNative`), `src/common/hashfn.h`

## Purpose
Implements the `macaddr` SQL type: a 6-byte EUI-48 MAC address. Provides flexible text input accepting seven punctuation/grouping notations `[verified-by-code: mac.c:60-79]`, fixed colon-separated `%02x` output `[verified-by-code: mac.c:117]`, binary I/O (six raw bytes MSB-first), the full comparison/btree/hash opclass surface, abbreviated-key sortsupport, bitwise NOT/AND/OR, and `macaddr_trunc` (zero the lower 3 bytes to compare by manufacturer OUI) `[verified-by-code: mac.c:329-345]`. All entry points are fmgr V1.

## Public symbols
| Symbol | file:line | Role |
| --- | --- | --- |
| `macaddr_in` | mac.c:43 | Text input; tries 7 `sscanf` formats, range-checks octets |
| `macaddr_out` | mac.c:109 | Output as `aa:bb:cc:dd:ee:ff` |
| `macaddr_recv` / `macaddr_send` | mac.c:128 / 149 | Binary I/O, 6 bytes MSB-first |
| `macaddr_cmp` | mac.c:185 | btree 3-way compare via `macaddr_cmp_internal` |
| `macaddr_lt/le/eq/ge/gt/ne` | mac.c:198-250 | Comparison operators |
| `hashmacaddr` / `hashmacaddrextended` | mac.c:255 / 263 | hash opclass over `hash_any`(`sizeof(macaddr)`) |
| `macaddr_not` / `macaddr_and` / `macaddr_or` | mac.c:275 / 291 / 308 | Bitwise ops, field by field |
| `macaddr_trunc` | mac.c:329 | Zero bytes d/e/f (keep 24-bit OUI) |
| `macaddr_sortsupport` | mac.c:351 | Installs abbreviated-key path |

## Internal landmarks
- **Parser** (`macaddr_in`, mac.c:60-84): cascade of `sscanf` attempts, each with a trailing `%1s` into `junk` so any trailing non-whitespace garbage makes `count != 6` and the format is rejected `[from-comment: mac.c:58]`. Formats: `x:x:...`, `x-x-...`, `xxxxxx:xxxxxx`, `xxxxxx-xxxxxx`, `xxxx.xxxx.xxxx`, `xxxx-xxxx-xxxx`, and bare `xxxxxxxxxxxx` `[verified-by-code: mac.c:60-79]`.
- **Range check** (mac.c:86-91): each parsed `%x` is an `int`; values must be 0..255, else `ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE`. The `< 0` arm matters because `%x` into a signed int could read a sign elsewhere; the guard is explicit.
- **Comparison key construction** (`hibits`/`lobits` macros, mac.c:28-32): packs bytes a/b/c into one `unsigned long`, d/e/f into another, compared high-then-low in `macaddr_cmp_internal` `[verified-by-code: mac.c:170-183]`. This is unsigned-numeric ordering equivalent to lexicographic byte order.
- **Byte-order in abbreviation** (`macaddr_abbrev_convert`, mac.c:403-430): zero an 8-byte Datum, `memcpy` the 6 bytes, then `DatumBigEndianToNative` so the unsigned 3-way comparator orders correctly on little-endian; two trailing zero pad bytes are least-significant `[from-comment: mac.c:394-401]`.
- **Abort never fires** (`macaddr_abbrev_abort`, mac.c:388-392): always returns false because 6 bytes fit entirely in a 64-bit Datum, making the abbreviated key authoritative `[from-comment: mac.c:383-387]`.

## Invariants & gotchas
- **`sizeof(macaddr)` == 6 with no padding** — the struct is six contiguous `unsigned char` fields (inet.h:94-102), so `hash_any((unsigned char *) key, sizeof(macaddr))` hashes exactly the 6 value bytes with no uninitialized padding `[verified-by-code: mac.c:260; inet.h:94-102]`. Equal macaddrs always hash equally.
- **Comparison is unsigned numeric, equivalent to MSB-first byte lexicographic** (mac.c:170-183): `macaddr_trunc` zeroing d/e/f keeps the OUI ordering stable, which is the whole point of grouping by manufacturer `[verified-by-code: mac.c:329-345]`.
- **Bitwise NOT writes `~x` into an `unsigned char` field** (mac.c:282-287): the `int` result of `~addr->a` is truncated to 8 bits on assignment; correct, but relies on implicit narrowing.
- **Input is lenient, output is canonical** — round-tripping any of the 7 accepted forms yields the single colon form (mac.c:117). The abbreviation pad bytes are never compared as data because the full comparator breaks ties.

## Cross-references
- Sibling 8-byte type: [[knowledge/files/src/backend/utils/adt/mac8.c]] (EUI-64; macaddr<->macaddr8 conversions live there).
- Sibling adt I/O types: [[knowledge/files/src/backend/utils/adt/pg_lsn.c]], [[knowledge/files/src/backend/utils/adt/uuid.c]].
- Abbreviated-key sortsupport machinery shared with `uuid.c`: `src/include/utils/sortsupport.h`.
- fmgr V1 conventions: [[knowledge/idioms/fmgr-and-spi]].

## Potential issues
- None surfaced. The all-`char` struct means `sizeof(macaddr)`-based hashing and the 8-byte abbreviation `memcpy` are both padding-safe (`mac.c:260,417`; `inet.h:94-102`).

## Confidence tag tally
- verified-by-code: 8
- from-comment: 4
- inferred: 0
- unverified: 0
