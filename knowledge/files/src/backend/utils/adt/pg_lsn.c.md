---
path: src/backend/utils/adt/pg_lsn.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 307
depth: deep
---

# pg_lsn.c

- **Source path:** `source/src/backend/utils/adt/pg_lsn.c`
- **Lines:** 307
- **Depth:** deep
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Companion files:** `src/include/utils/pg_lsn.h` (the `XLogRecPtr`/`PG_GETARG_LSN`/`PG_RETURN_LSN` macros, `LSN_FORMAT_ARGS`), `src/backend/utils/adt/numeric.c` (`numeric_pg_lsn`, the actual range-check for `+`/`-`)

## Purpose
Implements the SQL `pg_lsn` type, which wraps the 64-bit WAL byte position `XLogRecPtr`. Provides text/binary I/O in the canonical `%X/%08X` form, the full six comparison operators plus btree/hash opclass support, and arithmetic: LSN minus LSN yields a `numeric` byte-distance, and LSN plus/minus a `numeric` byte count yields a new LSN. `[verified-by-code]` `pg_lsn.c:3-4,52,81`. All entry points are fmgr V1.

## Public symbols
| Symbol | file:line | Role |
| --- | --- | --- |
| `pg_lsn_in_safe` | `pg_lsn.c:31` | Soft-error-capable parser; returns `XLogRecPtr`, reports via `escontext` |
| `pg_lsn_in` | `pg_lsn.c:63` | fmgr input; delegates to `pg_lsn_in_safe` with `fcinfo->context` |
| `pg_lsn_out` | `pg_lsn.c:74` | fmgr output; `snprintf("%X/%08X", LSN_FORMAT_ARGS(lsn))` |
| `pg_lsn_recv` / `pg_lsn_send` | `pg_lsn.c:86` / `97` | binary I/O via `pq_getmsgint64`/`pq_sendint64` |
| `pg_lsn_eq/ne/lt/gt/le/ge` | `pg_lsn.c:112`–`164` | comparison operators (plain `uint64` compare) |
| `pg_lsn_larger` / `pg_lsn_smaller` | `pg_lsn.c:166` / `175` | max/min, for aggregates |
| `pg_lsn_cmp` | `pg_lsn.c:185` | btree 3-way comparator |
| `pg_lsn_hash` / `pg_lsn_hash_extended` | `pg_lsn.c:200` / `207` | hash opclass; forwards to `hashint8`/`hashint8extended` |
| `pg_lsn_mi` | `pg_lsn.c:218` | LSN - LSN -> numeric (signed byte distance) |
| `pg_lsn_pli` | `pg_lsn.c:245` | LSN + numeric bytes -> LSN |
| `pg_lsn_mii` | `pg_lsn.c:279` | LSN - numeric bytes -> LSN |

## Internal landmarks
- **Parser** (`pg_lsn.c:31-61`): two `strspn` scans over `[0-9a-fA-F]`, each component 1..`MAXPG_LSNCOMPONENT`(8) chars, separated by exactly one `/`, with `'\0'` terminator required. Decodes each half with `strtoul(..., 16)` and assembles `((uint64) id << 32) | off`.
- **Range / byte-order**: components are masked to `uint32` (`pg_lsn.c:50-51`) so a >8-hex-digit component is rejected by the length check before `strtoul`, not by overflow. Binary I/O is whatever `pq_getmsgint64`/`pq_sendint64` define (network byte order).
- **`pg_lsn_mi` overflow note** (`pg_lsn.c:226`): comment states the difference "could be as large as plus or minus 2^63 - 1"; result is stringified into a 256-byte buffer then fed to `numeric_in`, so the numeric type absorbs the magnitude. No native-int overflow because the branch (`lsn1 < lsn2`) subtracts the smaller from the larger as unsigned.
- **`pg_lsn_pli` / `pg_lsn_mii`** (`pg_lsn.c:245`, `279`): reject NaN explicitly (`numeric_is_nan`), convert the LSN to numeric, add/subtract, then funnel through `numeric_pg_lsn` (`pg_lsn.c:272,306`) which is where the actual out-of-`[0, 2^64-1]` range error is raised. This file does not itself bound-check the result.

## Invariants & gotchas
- **Add/subtract overflow is delegated, not local** (`pg_lsn.c:272,306`): the only thing protecting `pg_lsn + numeric` from wrapping past `FFFFFFFF/FFFFFFFF` or below `0/0` is `numeric_pg_lsn` in numeric.c. Anyone refactoring must keep that conversion as the final step; replacing it with a raw cast would silently wrap. `[verified-by-code]`
- **Component length, not value, gates the parse** (`pg_lsn.c:42,46`): `MAXPG_LSNCOMPONENT == 8` means each side is at most 8 hex digits = 32 bits; this is what prevents `strtoul` overflow per half. `[verified-by-code]`
- **Output is always zero-padded low half but not high half** (`pg_lsn.c:81`): `%X/%08X` — the high 32 bits print without leading zeros, the low 32 bits are always 8 digits. Round-trips because the parser accepts 1..8 digits per side. `[verified-by-code]`
- **Hash reuses int8 hashing** (`pg_lsn.c:200-211`): `pg_lsn` and `bigint` with the same bit pattern hash identically; intentional, but means hash-partition co-location semantics are shared. `[from-comment]` (`pg_lsn.c:203`)

## Cross-references
- Sibling adt I/O types: [[knowledge/files/src/backend/utils/adt/uuid.c]], [[knowledge/files/src/backend/utils/adt/mac.c]], [[knowledge/files/src/backend/utils/adt/mac8.c]].
- `numeric_pg_lsn`, `numeric_in`, `numeric_add`, `numeric_sub` live in `src/backend/utils/adt/numeric.c` (the real overflow guard for `+`/`-`).
- fmgr V1 conventions: [[knowledge/idioms/fmgr-and-spi]].

## Potential issues
- **[ISSUE-undocumented-invariant: overflow guard lives off-file]** `pg_lsn.c:272` — `pg_lsn_pli`/`pg_lsn_mii` rely entirely on `numeric_pg_lsn` for range enforcement; there is no comment here pointing at that dependency, so a refactor that "simplifies" the numeric round-trip could reintroduce silent wraparound. Severity: maybe (nit-to-likely depending on refactor risk).

## Confidence tag tally
- `[verified-by-code]`: 5
- `[from-comment]`: 1
- ISSUE: 1 (undocumented-invariant, maybe)
