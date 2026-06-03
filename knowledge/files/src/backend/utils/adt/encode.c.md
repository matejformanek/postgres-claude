---
path: src/backend/utils/adt/encode.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 1034
depth: deep
---

# encode.c

- **Source path:** `source/src/backend/utils/adt/encode.c`
- **Lines:** 1034
- **Depth:** deep
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Companion files:** `src/include/utils/builtins.h` (declares `hex_encode`/`hex_decode`/`hex_decode_safe`), `src/include/varatt.h` (VARDATA/SET_VARSIZE), `src/include/port/simd.h` (Vector8 ops), `src/backend/utils/adt/varlena.c` (`byteaout`/`byteain` use the same hex/escape codecs)

## Purpose
Implements the SQL `encode(bytea, text)` and `decode(text, text)` functions and the codec dispatch layer behind them. `[from-comment]` `encode.c:3-4`. A small `struct pg_encoding` vtable (`encode_len`/`decode_len`/`encode`/`decode`) is registered per scheme in `enclist[]`, and `pg_find_encoding()` does a case-insensitive name lookup. `[verified-by-code]` `encode.c:34-40`, `encode.c:979-1034`. Five schemes are supported: `hex`, `base64`, `base64url`, `base32hex`, `escape`. `[verified-by-code]` `encode.c:986-1015`. The `hex_*` codecs are also exported (non-static) because `bytea` I/O uses them directly. `[verified-by-code]` `encode.c:201`, `encode.c:264`.

## Public symbols
| Symbol | file:line | Role |
|--------|-----------|------|
| `binary_encode` | `encode.c:48` | SQL `encode()`: dispatch to `enc->encode_len` then `enc->encode` |
| `binary_decode` | `encode.c:98` | SQL `decode()`: dispatch to `enc->decode_len` then `enc->decode` |
| `hex_encode` | `encode.c:201` | Exported hex encoder (SIMD + scalar fallback), used by bytea out |
| `hex_decode` | `encode.c:264` | Exported hex decoder; thin wrapper over `hex_decode_safe(...,NULL)` |
| `hex_decode_safe` | `encode.c:350` | Soft-error-capable hex decoder (takes `Node *escontext`) |

## Internal landmarks
- **Dispatch struct** `struct pg_encoding` `encode.c:34-40` — four function pointers. The `_len` functions estimate output size; `encode`/`decode` write to `*res` and return the true length. Contract: `_len` may overestimate but never underestimate. `[from-comment]` `encode.c:25-33`.
- **Registry** `enclist[]` `encode.c:979-1022`, NULL-terminated; `pg_find_encoding()` `encode.c:1024-1034` linear-scans with `pg_strcasecmp`.
- **HEX:** `hextbl[512]` `encode.c:156-172` (two ASCII chars per byte value); `hexlookup[128]` `encode.c:174-183` (char→nibble, -1 = invalid). `hex_encode_scalar` `encode.c:185-199`; SIMD `hex_encode` `encode.c:201-248`; `get_hex` `encode.c:250-262`; scalar decode `hex_decode_safe_scalar` `encode.c:270-309` (skips whitespace, errors on odd digit count / bad digit); SIMD `hex_decode_simd_helper` `encode.c:318-347` and `hex_decode_safe` `encode.c:350-388` (falls back to scalar path by resetting `i=0` if the vector path detected any out-of-range byte). Length funcs `hex_enc_len` = `srclen<<1` `encode.c:390-394`, `hex_dec_len` = `srclen>>1` `encode.c:396-400`.
- **BASE64 / BASE64URL:** alphabets `_base64` `encode.c:406-407`, `_base64url` `encode.c:409-410`; `b64lookup[128]` `encode.c:412-421`. `pg_base64_encode_internal` `encode.c:430-489` (inserts `\n` every 76 chars for plain base64 only; base64url omits newlines and `=` padding); `pg_base64_decode_internal` `encode.c:509-607` (maps url `-`/`_` to `+`/`/`, tracks `=` end-sequence state). Length funcs `encode.c:621-658`.
- **ESCAPE:** comment block `encode.c:660-672` explains escaping zero bytes, high-bit bytes, and backslash so output is encoding-safe. `VAL`/`DIG` macros `encode.c:674-675`; `esc_encode` `encode.c:677-714`; `esc_decode` `encode.c:716-762`; length estimators `esc_enc_len` `encode.c:764-783` and `esc_dec_len` `encode.c:785-826` (the decoder and `esc_dec_len` run the *same* validation walk so the codec never hits the "should never get here" branch).
- **BASE32HEX:** `base32hex_table` `encode.c:832`, `b32hexlookup[128]` `encode.c:834-843`; len funcs `encode.c:845-857`; `base32hex_encode` `encode.c:859-894` (5-bit accumulator, RFC 4648 `=` padding to multiple of 8); `base32hex_decode` `encode.c:896-973` (validates first `=` position ∈ {2,4,5,7}, rejects data after padding).

## Invariants & gotchas
- **The estimate-vs-actual contract is a hard safety boundary.** Both `binary_encode` and `binary_decode` palloc `VARHDRSZ + resultlen` where `resultlen` comes from the `_len` estimator, then assert `res <= resultlen` after the real write, escalating to `elog(FATAL, "overflow - ... estimate too small")` on violation. `encode.c:90-91`, `encode.c:140-141`. A `_len` that underestimates is a heap buffer overflow — hence FATAL, not ERROR. `[verified-by-code]`
- **`resultlen` is `uint64` to dodge 32-bit `palloc` overflow.** Explicit `resultlen > MaxAllocSize - VARHDRSZ` check before `palloc`, because on 32-bit `palloc`'s internal size check could be evaded by overflow. `encode.c:76-83`, `encode.c:126-133`. `[from-comment]`
- **`hexlookup`/`b64lookup`/`b32hexlookup` are 128 entries; callers must gate on the byte being < 127/128 before indexing.** `get_hex` checks `c < 127` `encode.c:256`; base64 decode checks `c > 0 && c < 127` `encode.c:559`; base32hex checks `c < 128` `encode.c:945`. Indexing with a high-bit byte would read out of bounds. `[verified-by-code]`
- **`hex_dec_len` truncates (`>>1`), so an odd-length hex string over-allocates by zero and the codec catches the odd count.** Odd digit count is rejected in `hex_decode_safe_scalar` `encode.c:295-298`. `[verified-by-code]`
- **`esc_decode` octal branch requires `src + 3 < end`** `encode.c:727` — i.e. all 3 octal digits must be strictly inside the buffer; this matches `esc_dec_len` `encode.c:795`. The two must stay in lockstep or the FATAL guard trips. `[verified-by-code]`
- **`esc_encode` writes up to 4 bytes per input byte** (`\nnn`), so any caller's buffer must honor `esc_enc_len`. The encoder does the same classification as the len function. `encode.c:688-708` vs `encode.c:770-779`. `[verified-by-code]`
- **base64 plain decode tolerates the `\n` that encode inserts** because whitespace (` \t\n\r`) is skipped at `encode.c:525`. `[verified-by-code]`

## Cross-references
- [[knowledge/files/src/backend/utils/adt/quote.c]] — sibling adt string function file.
- [[knowledge/files/src/backend/utils/adt/ascii.c]] — sibling; also fmgr V1 text codecs.
- `varlena.c` `byteaout`/`byteain` reuse `hex_encode`/`hex_decode` and the escape codec (not yet documented).
- [[knowledge/idioms/fmgr-and-spi]] — `binary_encode`/`binary_decode` are PG_FUNCTION_INFO_V1 entry points; `DirectFunctionCall` is not used here but the V1 convention is.

## Potential issues
- **[ISSUE-question: base64url over-estimates decode length by design; harmless but worth noting]** `encode.c:644-658` — `pg_base64url_dec_len` rounds `srclen` up to a multiple of 4 before `*3/4`, which is a deliberate overestimate (allowed by the contract `encode.c:29`). Not a bug; recorded so a future reader doesn't "tighten" it and risk an underestimate. Severity: nit.
- **[ISSUE-undocumented-invariant: 128-entry lookup tables rely on caller range checks scattered across codecs]** `encode.c:174`, `encode.c:412`, `encode.c:834` — the bounds gate lives at each call site (`encode.c:256`, `encode.c:559`, `encode.c:945`) rather than inside an accessor; correct today but fragile if a new codec indexes a table without the guard. Severity: maybe.

## Confidence tag tally
- `[verified-by-code]`: 11
- `[from-comment]`: 4
- `[from-README]`: 0
- `[inferred]`: 0
- `[unverified]`: 0
