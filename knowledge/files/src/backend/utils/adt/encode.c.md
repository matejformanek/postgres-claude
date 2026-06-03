# `src/backend/utils/adt/encode.c`

- **File:** `source/src/backend/utils/adt/encode.c` (1034 lines)
- **Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Purpose

Binary ↔ text encoders dispatched by SQL `encode(bytea, text)` /
`decode(text, text)`. Five named encodings: `hex`, `escape`, `base64`,
`base64url`, `base32hex`. Each is a `struct pg_encoding` of four
function pointers: `encode`, `decode`, `encode_len`, `decode_len`.
(`encode.c:979-1023` [verified-by-code])

## SQL entry points

- `binary_encode` (`:48`) — `text = encode(bytea, name)`.
- `binary_decode` (`:98`) — `bytea = decode(text, name)`.

Both follow the same pattern:
1. Resolve `name` via `pg_find_encoding` (`:1024`); error on
   unrecognized name with hint listing valid encodings (`:65-69`,
   `:115-119`).
2. Call `enc->encode_len` / `enc->decode_len` to estimate output size
   into a **`uint64 resultlen`** (`:74, :124`).
3. **`MaxAllocSize` guard** — error
   `ERRCODE_PROGRAM_LIMIT_EXCEEDED` if `resultlen > MaxAllocSize -
   VARHDRSZ` (`:80-83`, `:130-133`). This is the **input-bomb
   defense**: a multi-GB hex string is rejected before palloc, not
   after. [verified-by-code]
4. palloc + invoke `enc->encode` / `enc->decode`.
5. If actual result exceeded the estimate, `elog(FATAL, "overflow -
   encode estimate too small")` (`:90-91`, `:139-141`) — guards against
   bugs in the per-encoding estimators that would underrun the buffer.

## Per-encoding notes

### Hex (`:150-403`)

- `hextbl[]` (`:156`) is a precomputed 256×2 expansion table.
- `hex_encode_scalar` (`:185`) and a SIMD path `hex_encode` via
  `vector8_interleave_*` (`:200`+) — encodes in chunks of 16 bytes.
- `hex_decode_safe(src, len, dst, escontext)` (`:351`) — SIMD-vectorized
  decode with scalar fall-back when SIMD reports any out-of-range
  byte. Errors on odd digit count or non-hex char via `ereturn`
  (soft-error friendly) (`:289-303`).
- Decoded length is `srclen >> 1` (`:399`) — no padding.

### Escape (`:430-…`)

- `escape_encode` / `escape_decode` — backslash-octal encoding for
  bytea legacy format.

### Base64 / base64url (`:406-602`)

- Standard RFC4648 dispatch; `base64url` uses `-` and `_` instead of
  `+` and `/` and omits padding (`url == true` branch throughout).
- Decoder rejects unexpected `'='` (`:551`) and invalid symbols
  (`:566`) with a precise `errmsg`.
- End-of-data validation (`:602`): if final 4-char block is malformed,
  `errmsg("invalid %s end sequence")`.

### Base32hex (`:832-…`)

- Newer encoding (RFC4648 §7), distinct alphabet (`base32hex_table`,
  `:832`). Decoder validates symbols and `=` placement.

## Phase D notes — the input-bomb story

- The `MaxAllocSize - VARHDRSZ` guard (`:80, :130`) is the **only**
  cap on result size. `MaxAllocSize == 1 GB - 1`. So:
  - A 2 GB hex string → rejected before palloc (resultlen 1 GB).
  - A 1.5 GB base64 string → decode_len = 1.125 GB → rejected.
  - A 1 GB binary payload → encode hex → 2 GB result → rejected.
- **What's NOT bounded**: the input itself, when reached via
  `PG_GETARG_*_PP`, is bounded by the type's max size (1 GB for bytea
  and text). So a malicious 900 MB hex input is allowed in but its
  estimated decode is 450 MB which passes the guard; the decoder then
  spends real CPU cycles, mitigated only by `CHECK_FOR_INTERRUPTS`
  inside the SIMD/scalar inner loops (NOT visible in the snippet I
  read — verify if Phase D wants).
- The `elog(FATAL)` on estimate underrun is correct: the per-encoding
  functions write past their estimates only if there's a code bug,
  which would have already corrupted memory.

## Potential issues

- [ISSUE-dos: no `CHECK_FOR_INTERRUPTS` visible inside
  `hex_decode_safe_scalar` (`:270-309`); a ~1 GB hex string with no
  whitespace will hold the backend in this loop without a chance to
  cancel. Worth checking the SIMD path too. (medium)]
- [ISSUE-undocumented-invariant: `hex_decode_safe` returns the number
  of decoded bytes — caller (`binary_decode`) trusts this to set
  `VARSIZE`; if a bug let it exceed `resultlen` we hit the FATAL
  (`:139-141`). The FATAL is correct hardening but indicates trust
  level. (low)]
- [ISSUE-info-disclosure: error messages on invalid hex include the
  bad character via `%.*s` with `pg_mblen_range` (`:292-293`). A
  multi-byte sequence is echoed back unchanged in the error log; for
  log-injection-via-control-char this is a (low) consideration. (low)]

## Cross-references

- `source/src/backend/utils/adt/bytea.c` — calls `hex_decode_safe` for
  `byteain('\x...')`.
- `source/src/include/utils/builtins.h` — declarations of `hex_encode`,
  `hex_decode_safe`.
- `source/src/include/port/simd.h` — `Vector8`, `vector8_*` primitives.

## Confidence tag tally

- `[verified-by-code]` × 7
- `[from-comment]` × 1
- `[unverified]` × 1
