---
path: src/common/compression.c
anchor_sha: 4b0bf0788b0
loc: 506
depth: read
---

# compression.c

- **Source path:** `source/src/common/compression.c`
- **Lines:** 506
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `common/compression.h`, `src/bin/pg_dump/compress_io.c` (consumer for archive blocks), `src/bin/pg_basebackup/bbstreamer_gzip.c`/etc. (consumers for backup output).

## Purpose

Two layers of compression-spec parsing:
1. **Algorithm-name layer** (`parse_compress_algorithm`, `parse_tar_compress_algorithm`, `get_compress_algorithm_name`): map names/file suffixes ↔ `pg_compress_algorithm` enum.
2. **Spec-string layer** (`parse_compress_specification`, `validate_compress_specification`, `parse_compress_options`): parse `gzip:9`, `zstd:level=3,workers=4,long`, the bare integer `5`, etc., into a `pg_compress_specification`, then sanity-check the result against the chosen algorithm.

The split lets every CLI tool present "-Z" / "--compress" identically. [from-comment, compression.c:1-21]

## Role in PG

Both frontend and backend (the spec parser is used by `replication/basebackup_*` server-side). Heaviest user is `pg_basebackup` + `pg_dump` / `pg_restore` via `compress_io.c`.

## Key functions

- `parse_tar_compress_algorithm(fname, *algorithm)` (48-72) — suffix sniff: `.tar`/`.tgz`/`.tar.gz`/`.tar.lz4`/`.tar.zst`. Filename-trust boundary. [verified-by-code, compression.c:48-72]
- `parse_compress_algorithm(name, *algorithm)` (78-92) — case-sensitive `strcmp` against `none`/`gzip`/`lz4`/`zstd`. [verified-by-code, compression.c:78-92]
- `get_compress_algorithm_name(algorithm)` (98-115) — enum→string for log messages; `Assert(false)` on out-of-range. [verified-by-code, compression.c:98-115]
- `parse_compress_specification(algorithm, specification, *result)` (136-296) — fills defaults (default level per algorithm; `parse_error` if build doesn't support the algorithm via `#ifdef`), then if `specification` is a bare integer (`strtol` consumes whole string), `level = bare_level`. Otherwise loop over comma-separated `keyword[=value]` pairs: `level=N`, `workers=N`, `long[=yes/no]`. Unknown keyword → `parse_error`. [verified-by-code, compression.c:136-296]
- `expect_integer_value(keyword, value, *result)` (304-327) — `strtol`; requires no garbage after; on failure stores message into `result->parse_error` and returns `-1`. **Does NOT range-check** — accepts negatives, huge values, etc. Range is enforced later in `validate_compress_specification`. [verified-by-code, compression.c:304-327]
- `expect_boolean_value(keyword, value, *result)` (340-364) — `yes/on/1/no/off/0`; bare keyword (no `=value`) is treated as `true` (line 343). [verified-by-code, compression.c:340-364]
- `validate_compress_specification(*spec)` (373-443) — per-algorithm `min_level`/`max_level`/`default_level`; reject NONE-with-level (line 407-411); reject `level` outside `[min,max]` unless it equals `default_level` (line 414-418); reject `workers` for non-zstd, `long` for non-zstd. Returns NULL or a `psprintf` error string. [verified-by-code, compression.c:373-443]
- `parse_compress_options(option, **algorithm, **detail)` (455-505, `#ifdef FRONTEND`) — for `-Z` CLI: bare integer → ("none"/"gzip", maybe detail). Otherwise split on first `:`; left part is algorithm, right part is detail. [verified-by-code, compression.c:455-505]

## State / globals

None.

## Phase D notes

- **Enum order is persisted in archives.** Reordering or inserting a new algorithm at the front of `pg_compress_algorithm` silently changes the meaning of every existing archive's algorithm tag. Comment at compression.h:17-20 makes this explicit. [from-comment, compression.h:17-20] [ISSUE-undocumented-invariant: pg_compress_algorithm enum ordinals are an on-disk format, not just internal — additions must append (maybe-high)]
- **`expect_integer_value` does not range-check.** `level=99999999999` is accepted at parse and only rejected at validate. Two-pass design is fine, but a caller that uses the parsed spec without calling `validate_compress_specification` will pass a bogus level into the compressor library. [verified-by-code, compression.c:304-327] [ISSUE-trust-boundary: parsed spec is only safe after validate_compress_specification; consumers that skip the validate step (any?) get unchecked input (maybe)]
- **`strtol` on user CLI input — no overflow check.** `result = strtol(specification, &endp, 10)` (line 191) for the bare-integer case; out-of-`long` values quietly saturate (`LONG_MAX`/`LONG_MIN` with `errno=ERANGE`) and `errno` is not consulted. Same in `parse_compress_options` (line 468) and `expect_integer_value` (line 318). Result truncates from `long` to `int` at line 326. On 64-bit platforms this means `level=2147483648` becomes `level=-2147483648`. Then `validate_compress_specification` rejects it. So no exploit, but the error message ("expects a level between 1 and 9") is wrong. [verified-by-code, compression.c:191,318,468] [ISSUE-correctness: integer overflow on level= silently truncates from long to int; validate then rejects with a confusing message (maybe-low)]
- **`expect_boolean_value` on bare keyword returns `true`** (line 343). This is intentional — `long` is shorthand for `long=yes`. But it means a typo like `looong` falls through to the `unrecognized compression option` branch instead of being misinterpreted. [verified-by-code, compression.c:343]
- **`parse_compress_options` allocates `palloc` on a user-controlled length** (line 498). `(sep - option) + 1` bytes; `option` comes from the command line so length is bounded by ARG_MAX. Not a DoS vector. [verified-by-code, compression.c:498-501]
- **Build-time downgrade.** If `#ifdef USE_ZSTD` is false, parsing a zstd spec stores `parse_error` but `parse_compress_specification` still runs through the keyword loop. The caller must check `parse_error`. [verified-by-code, compression.c:167-173,289]
- **Comma-separator in keyword/value is not escapable** — a value containing a literal `,` (`level=1,2`) splits at the comma and parses `2` as a new keyword. The comma terminator is hard. [verified-by-code, compression.c:225-227]

## Confidence tag tally
`[from-comment]=2 [verified-by-code]=14 [maybe]=4`
