---
path: src/include/common/pg_lzcompress.h
anchor_sha: 4b0bf0788b0
loc: 93
depth: skim
---

# pg_lzcompress.h

- **Source path:** `source/src/include/common/pg_lzcompress.h`
- **Lines:** 93
- **Last verified commit:** `4b0bf0788b0`
- **Companion file:** `common/pg_lzcompress.c`.

## Purpose

Public surface for PG's in-tree LZ implementation — historically the default toast compression. Defines the `PGLZ_Strategy` knobs, the two pre-baked strategies (`default` for TOAST, `always` for forced compression), and the four functions: `pglz_compress`, `pglz_decompress`, `pglz_maximum_compressed_size`. [from-comment, pg_lzcompress.h:1-92]

## Public surface

- `#define PGLZ_MAX_OUTPUT(dlen) ((dlen) + 4)` — output buffer sizing macro. 4-byte overrun allowance lets the compressor detect "would-grow" before bailing out. [verified-by-code, pg_lzcompress.h:21]
- `struct PGLZ_Strategy { min_input_size; max_input_size; min_comp_rate; first_success_by; match_size_good; match_size_drop; }`. [verified-by-code, pg_lzcompress.h:57-65]
- `PGLZ_strategy_default`, `PGLZ_strategy_always` — global const-pointer strategies. [verified-by-code, pg_lzcompress.h:78-79]
- `pglz_compress(source, slen, dest, *strategy)` — returns dest length or -1 on "didn't shrink". [verified-by-code, pg_lzcompress.h:86-87]
- `pglz_decompress(source, slen, dest, rawsize, check_complete)` — returns dest length or -1 on corrupt/truncated. [verified-by-code, pg_lzcompress.h:88-89]
- `pglz_maximum_compressed_size(rawsize, total_compressed_size)` — for "fetch only N raw bytes" partial-TOAST reads. [verified-by-code, pg_lzcompress.h:90-91]

## Phase D notes

See `pg_lzcompress.c.md` — bounds-checking detail on the decompressor.

## Confidence tag tally
`[from-comment]=1 [verified-by-code]=6`
