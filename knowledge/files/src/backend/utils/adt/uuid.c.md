---
path: src/backend/utils/adt/uuid.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 779
depth: deep
---

# uuid.c

- **Source path:** `source/src/backend/utils/adt/uuid.c`
- **Lines:** 779
- **Depth:** deep
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Companion files:** `src/include/utils/uuid.h` (`pg_uuid_t`, `UUID_LEN == 16`, `PG_GETARG_UUID_P`/`PG_RETURN_UUID_P`, `UUIDPGetDatum`/`DatumGetUUIDP`), `src/port/pg_strong_random.c` (CSPRNG), `src/include/utils/sortsupport.h` + `skipsupport.h`, `src/backend/lib/hyperloglog.c`

## Purpose
Implements the built-in `uuid` type: text/binary I/O, the six comparison operators (byte-lexicographic via `memcmp`), btree comparator, hash and extended-hash, abbreviated-key sortsupport with HyperLogLog abort heuristics, btree skipsupport (increment/decrement), and the generators `gen_random_uuid` (v4), `uuidv7`/`uuidv7_interval` (v7 per RFC 9562), plus `uuid_extract_timestamp`/`uuid_extract_version`. `[verified-by-code]` `uuid.c:3-4,203-206,523,655`. All SQL entry points are fmgr V1.

## Public symbols
| Symbol | file:line | Role |
| --- | --- | --- |
| `uuid_in` / `uuid_out` | `uuid.c:77` / `88` | text I/O; out is canonical `8-4-4-4-12` lowercase |
| `uuid_recv` / `uuid_send` | `uuid.c:180` / `191` | binary I/O (raw 16 bytes) |
| `uuid_lt/le/eq/ge/gt/ne` | `uuid.c:209`–`261` | comparison ops over `uuid_internal_cmp` |
| `uuid_cmp` | `uuid.c:264` | btree 3-way comparator |
| `uuid_sortsupport` | `uuid.c:276` | installs `uuid_fast_cmp` + abbreviated-key path |
| `uuid_skipsupport` | `uuid.c:469` | btree skip scan: min `00..`, max `FF..`, `uuid_increment`/`uuid_decrement` |
| `uuid_hash` / `uuid_hash_extended` | `uuid.c:488` / `496` | hash opclass over `hash_any`/`hash_any_extended` |
| `gen_random_uuid` | `uuid.c:523` | UUID v4 (all-random except version/variant) |
| `uuidv7` | `uuid.c:654` | UUID v7 at current time |
| `uuidv7_interval` | `uuid.c:666` | UUID v7 at current time shifted by an `interval` |
| `uuid_extract_timestamp` | `uuid.c:710` | timestamp from v1 or v7 UUID, else NULL |
| `uuid_extract_version` | `uuid.c:766` | version nibble if RFC 9562 variant, else NULL |

## Internal landmarks
- **Parser** (`string_to_uuid`, `uuid.c:130-178`): optional `{...}` wrapping, 16 bytes each from a 2-hex-digit pair via `strtoul`, optional `-` separators accepted only after an odd-indexed byte and not at the end (`uuid.c:157`). `isxdigit` validates each char; trailing content errors. Uses soft errors (`ereturn(escontext,,...)`, note the empty value arg at `uuid.c:174`).
- **RNG usage**: both generators use `pg_strong_random` (the CSPRNG), NOT the weak PRNG. v4 fills all 16 bytes then overwrites version/variant (`uuid.c:528,537`); v7 fills only bytes 8..15 with strong random (`uuid.c:625`). `[verified-by-code]`
- **Byte-order / abbreviation** (`uuid_abbrev_convert`, `uuid.c:387-417`): packs the first `sizeof(Datum)` bytes into a Datum, then `DatumBigEndianToNative` so `ssup_datum_unsigned_cmp` orders correctly on little-endian. HLL cardinality estimation feeds `uuid_abbrev_abort` (`uuid.c:327-378`).
- **v7 sub-ms encoding** (`generate_uuidv7`, `uuid.c:600-649`): 48-bit ms timestamp in bytes 0..5; 12-bit sub-ms fraction (`increased_clock_precision`, `uuid.c:618`) in bytes 6..7 ("rand_a"); on 10-bit-precision platforms (`__darwin__`/`_MSC_VER`, `SUBMS_MINIMAL_STEP_BITS == 10`) the low 2 sub-ms bits are XORed with CSPRNG bits (`uuid.c:639`).
- **Monotonicity source** (`get_real_time_ns_ascending`, `uuid.c:547-582`): `static int64 previous_ns` per backend; forces each call at least `SUBMS_MINIMAL_STEP_NS` above the last. Uses `clock_gettime(CLOCK_REALTIME)` (or `gettimeofday` under MSVC).
- **Timestamp extraction byte order differs by version** (`uuid.c:724-755`): v1 reassembles a 60-bit 100-ns Gregorian count from scattered bytes with the v1 layout; v7 reads the big-endian 48-bit ms field. Both adjust to `TimestampTz` (Postgres epoch).

## Invariants & gotchas
- **Generators MUST use `pg_strong_random`** (`uuid.c:528,625`): switching to `pg_prng_*` would make v4/v7 predictable — a security regression. Both call sites `ereport(ERROR)` on RNG failure rather than returning a weak fallback. `[verified-by-code]`
- **v7 monotonicity is per-backend, not global** (`uuid.c:550`): the `previous_ns` static is backend-local. Two concurrent backends can emit out-of-order v7 UUIDs in the same millisecond; monotonicity is only guaranteed within a single backend's call sequence. `[verified-by-code]`
- **`SUBMS_MINIMAL_STEP_NS` must keep the step above the bit the XOR perturbs** (`uuid.c:57,630-640`): on 10-bit platforms the low 2 sub-ms bits are randomized; the minimal step is sized so the 12-bit fraction still advances despite that, preserving monotonicity. Changing either constant in isolation breaks the guarantee. `[from-comment]` (`uuid.c:634-637`)
- **Comparison is raw `memcmp` over 16 bytes** (`uuid.c:203-206`): byte-lexicographic, so v7's time-ordered prefix makes v7 UUIDs sort roughly by creation time; v4 sorts randomly. Skipsupport min/max (`00*`/`FF*`, `uuid.c:476-477`) rely on this same total order. `[verified-by-code]`
- **Variant check gates both extractors** (`uuid.c:719,773`): `(data[8] & 0xc0) != 0x80` => NULL. A UUID with a non-RFC-9562 variant yields NULL version/timestamp even if other bytes look v1/v7-shaped. `[verified-by-code]`
- **abbrev convert reads `sizeof(Datum)` bytes of a 16-byte value** (`uuid.c:394`): only the leading 8 bytes form the abbreviated key; the full comparator (`uuid_fast_cmp`) is authoritative for ties. Intentional. `[from-comment]` (`uuid.c:381-385`)

## Cross-references
- Sibling adt I/O types: [[knowledge/files/src/backend/utils/adt/pg_lsn.c]], [[knowledge/files/src/backend/utils/adt/mac.c]], [[knowledge/files/src/backend/utils/adt/mac8.c]].
- `pg_strong_random` (CSPRNG) in `src/port/pg_strong_random.c`; contrast the weak PRNG `pg_prng_*` in `src/common/pg_prng.c`.
- Abbreviated-key sortsupport machinery: `src/include/utils/sortsupport.h`, `src/backend/lib/hyperloglog.c`.
- fmgr V1 conventions: [[knowledge/idioms/fmgr-and-spi]].

## Potential issues
- **[ISSUE-question: per-backend v7 monotonicity not surfaced to users]** `uuid.c:550` — `previous_ns` is `static` (backend-local). The header comments promise monotonicity "on this backend" (`uuid.c:545`), which is accurate, but consumers expecting globally-ordered v7 keys across connections will not get them. Worth a cross-link in any v7 user doc. Severity: nit (documentation/expectation, not a code bug).

## Confidence tag tally
- `[verified-by-code]`: 8
- `[from-comment]`: 3
- ISSUE: 1 (question, nit)
