---
path: src/common/pg_lzcompress.c
anchor_sha: 4b0bf0788b0
loc: 887
depth: surface
---

# pg_lzcompress.c

- **Source path:** `source/src/common/pg_lzcompress.c`
- **Lines:** 887
- **Last verified commit:** `4b0bf0788b0`
- **Companion file:** `common/pg_lzcompress.h`.

## Purpose

PG's in-tree LZ77-style compressor — was the default TOAST compressor before LZ4 became available. Produces 2-3 byte back-reference tags with a max offset of 4095 and a max length of 273. Output format is fully self-contained (no separate dictionary). The header comment (lines 56-220) is essentially the format spec. [from-comment, pg_lzcompress.c:1-220]

## Role in PG

Both frontend (TOAST dumping via pg_dump uses it for unTOAST'ing) and backend (`detoast_external_attr` → `pglz_decompress`, plus the `default_toast_compression = pglz` write path).

## Key functions

- `pglz_compress(source, slen, dest, *strategy)` (508-…) — applies `strategy` thresholds (`min_input_size`, `max_input_size`, `min_comp_rate`, `first_success_by`) and runs the encoder. Returns dest length or -1 if the output would not be ≥ 4 bytes smaller than the input. [verified-by-code, pg_lzcompress.c:508-…]
- `pglz_decompress(source, slen, dest, rawsize, check_complete)` (691-839) — the operationally interesting function for Phase D. See below.
- `pglz_maximum_compressed_size(rawsize, total_compressed_size)` (856-887) — `((rawsize * 9 + 7) / 8) + 2`, capped at `total_compressed_size`. Uses `int64` intermediate to avoid overflow on `int32` inputs. [verified-by-code, pg_lzcompress.c:856-887]
- Helpers: `pglz_find_match` (399, inline), `hist_start`/`hist_entries` (file-scope arrays — see globals).

## State / globals

- `static int16 hist_start[PGLZ_MAX_HISTORY_LISTS]` (line 255) and `static PGLZ_HistEntry hist_entries[PGLZ_HISTORY_SIZE + 1]` (line 256) — the **encoder's history table is process-global, single-instance.** This makes `pglz_compress` **NOT reentrant** — a signal handler that tries to compress would corrupt an interrupted compression. PG's backend is single-threaded per-fork, so this is fine in current use but worth noting. [verified-by-code, pg_lzcompress.c:255-256] [ISSUE-undocumented-invariant: pglz_compress is not thread-safe / not async-signal-safe; relies on PG's single-threaded backend model (maybe-low)]
- `static const PGLZ_Strategy strategy_default_data` (223), `strategy_always_data` (239) — the strategies pointed to by the public `PGLZ_strategy_default`/`PGLZ_strategy_always`. [verified-by-code, pg_lzcompress.c:223-244]

## Phase D notes — decompressor bounds

The decompressor is the trust-boundary surface (TOAST data may have been written by an older buggy PG, or recovered from corrupted disk).

- **Match-tag bounds checks at lines 735, 743, 756.** `sp + 2 > srcend` rejects a tag header that would over-read the input. The 18-extension byte read at line 743 (`sp >= srcend`) catches that case. The `off == 0 || off > (dp - dest)` check at line 756 prevents reading before the output buffer start (which would otherwise OOB-read uninitialized stack/heap). [verified-by-code, pg_lzcompress.c:735-758]
- **`len = Min(len, destend - dp)` at line 763** clamps the output to caller's `rawsize`. Combined with the `dp < destend` loop condition (line 705), this prevents OOB-write. [verified-by-code, pg_lzcompress.c:705,763]
- **`check_complete` flag** (line 832) is the "did we consume exactly the input and produce exactly the output we expected?" check. Callers that read only a TOAST prefix (`pg_get_line` style) pass `false` — those callers are responsible for not trusting unprocessed input. [verified-by-code, pg_lzcompress.c:832]
- **Decompression bomb?** `rawsize` is caller-supplied. A compressed payload of N bytes can expand to whatever `rawsize` the caller passes — but the caller has already allocated a `rawsize`-byte `dest`. The classic decompression-bomb attack is "tiny compressed → huge decompressed" — here that means the caller has to have requested the huge allocation up front. **PG's TOAST layer treats `rawsize` as authoritative from the toast-pointer header**; an attacker who can plant a toast pointer with `rawsize=1GB` makes us allocate 1GB. That's a separate issue, in `detoast.c`. [inferred] [maybe — Phase D]
- **Overlapping-copy idiom is non-trivial.** The `while (off < len) { memcpy(dp, dp - off, off); … off += off; }` pattern at lines 774-810 is the documented LZ77 RLE-via-overlap. The comment at lines 783-806 explains it. Bug here would be subtle but bounds are checked above so worst case is wrong-data, not OOB. [from-comment, pg_lzcompress.c:783-810]
- **`pglz_maximum_compressed_size` uses `int64` intermediate** (line 859) precisely to avoid `int32 * 9` overflow. [verified-by-code, pg_lzcompress.c:856-887]

## Cross-references

- TOAST writer: `src/backend/access/common/detoast.c`, `src/backend/access/common/toast_compression.c`.
- LZ4 alternative: `src/backend/access/common/toast_compression.c` selects via `default_toast_compression` GUC.

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->

## Confidence tag tally
`[from-comment]=2 [verified-by-code]=10 [inferred]=1 [maybe]=2`
