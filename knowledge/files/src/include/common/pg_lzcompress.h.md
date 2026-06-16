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

## Issues

[ISSUE-trust-boundary: `pglz_decompress(source, slen, dest, rawsize, check_complete)`
(`pg_lzcompress.h:88-89`) — caller supplies `rawsize` as the
expected output length, but the header documents no upper bound on
the input/output ratio. A5's `common.md` headline: a malicious TOAST
chunk can claim `rawsize` arbitrarily large vs `slen` → decompression
bomb (high)] The header is silent. Cross-link: A11 pgcrypto pgp
decompression bomb is the same family.

[ISSUE-undocumented-invariant: `PGLZ_MAX_OUTPUT(dlen)` macro
(`pg_lzcompress.h:21`) — comment says "4 bytes for overrun before
detecting compression failure", but does not state that this is the
ONLY tolerance — i.e. callers MUST size dest to at least
`PGLZ_MAX_OUTPUT(slen)` or the compressor may step on memory (low)]

[ISSUE-trust-boundary: `check_complete` parameter
(`pg_lzcompress.h:89`) is a bool whose semantics ("error out if
decompression finishes early") are not explained at the header
level (low)] Misuse — passing `false` when the caller actually
needs strict completeness — yields silent truncation, exactly the
class of TOAST-corruption attack `pglz` has been hardened against
historically.

## Cross-refs

- A5 `common.md` — pglz decompression bomb.
- A11 pgcrypto pgp — sibling decompression bomb class.
- Companion: `src/common/pg_lzcompress.c.md`.

<!-- issues:auto:begin -->
- [Issue register — `include-common`](../../../../issues/include-common.md)
<!-- issues:auto:end -->

## Confidence tag tally
`[from-comment]=1 [verified-by-code]=6`
