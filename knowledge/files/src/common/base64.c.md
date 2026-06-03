---
path: src/common/base64.c
anchor_sha: 4b0bf0788b0
loc: 242
---

# base64.c

- **Source path:** `source/src/common/base64.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 242

## Purpose

Strict base64 codec without whitespace tolerance — the SCRAM
on-wire/on-disk variant. Distinct from
`src/backend/utils/adt/encode.c::pg_b64encode/decode` (which accepts
whitespace and serves the SQL `encode('base64')` user-visible
function). [from-comment, base64.c:3-4]

## Role in PG

Linked into both libpq and the backend. Consumers:
- `scram-common.c::scram_build_secret` (encodes salt + StoredKey +
  ServerKey into `pg_authid.rolpassword`).
- `auth-scram.c` (encodes/decodes the SCRAM nonces, salt, proof on
  the wire).
- `fe-auth-scram.c` (frontend mirror).
- `pgcrypto`'s base64 path (probably).

## Key functions

- `pg_b64_encode(src, len, dst, dstlen)` (base64.c:48): packs 3 input
  bytes into 4 chars; on each output overflow check emits an
  `error:` that does `memset(dst, 0, dstlen)` and returns -1
  (base64.c:103-105). Handles 1- and 2-byte tails with `'='`
  padding (base64.c:85-98).
- `pg_b64_decode(src, len, dst, dstlen)` (base64.c:115): looks up
  each char via `b64lookup[]` table (128 entries, -1 for invalid).
  - **Rejects whitespace** — any `' '`, `'\t'`, `'\n'`, `'\r'` hits
    the `error:` exit (base64.c:132-133).
  - `'='` only legal in `end == 1` (2 padding chars) or `end == 2`
    (1 padding char) positions; anything else errors
    (base64.c:135-152).
  - On error: `memset(dst, 0, dstlen)` then return -1
    (base64.c:210-212).
  - Trailing-buffer state-machine catches missing padding
    (`pos != 0` at end → error, base64.c:198-205).
- `pg_b64_enc_len(srclen) = (srclen + 2) / 3 * 4`.
- `pg_b64_dec_len(srclen) = (srclen * 3) >> 2`.

## State / globals

- `_base64[]` — the encode alphabet `"ABCD...wxyz0123456789+/"`
  (base64.c:27).
- `b64lookup[128]` — decode table indexed by ASCII (base64.c:30-39).
- Both are read-only.

## Concurrency

Reentrant.

## Phase D notes

- **Strict-mode codec is the correct one for SCRAM.** A whitespace-
  tolerant decoder on the wire would create parser ambiguity for
  the SCRAM message framing. The strict mode here is load-bearing
  for protocol security.
- **`memset(dst, 0, dstlen)` on error** (base64.c:104, 211) is a
  defensive scrub — partial writes don't leak through to the
  caller. **Positive Phase D pattern.** Useful precedent for a
  `SecretBuf` API: zero-on-failure.
- The standard alphabet (`+/` not the URL-safe `-_`) is fine for
  SCRAM (RFC mandates standard). No fuzz target known.

## Potential issues

- **[ISSUE-dos: decode does not bound the lookup-table indirection on
  c > 127]** `base64.c:158-159` — the `if (c > 0 && c < 127)` gate
  prevents the lookup, mapping high-bit / NUL to -1 / error. OK.
- **[ISSUE-correctness: padding state machine accepts "X=" but not
  "X==" without the leading pad-eligible char]** Edge case — the
  state-machine relies on `pos == 2` / `pos == 3` for legal pads.
  Probably OK for SCRAM inputs (always a multiple-of-4 encoding) but
  worth a fuzz target. Severity: nit.
- **[ISSUE-side-channel: decode is *not* constant-time]**
  `base64.c:127-196` — short-circuits on first error char. For SCRAM
  this is mostly fine (decoded nonces are public on the wire) but if
  someone uses `pg_b64_decode` for an HMAC tag, they'd leak
  position-of-first-bad-char timing. Severity: nit.
- **[ISSUE-undocumented-invariant: caller must pre-size `dst` via
  `pg_b64_{enc,dec}_len`]** No assert on `dstlen` at entry — overflow
  causes a clean -1 return, but a too-small `dst` for a successful
  decode silently corrupts. `pg_nodiscard` on the API (base64.h:14)
  is the trip-wire. Severity: nit.

## Cross-refs

- Public API: `knowledge/files/src/include/common/base64.h.md`.
- Primary consumer: `knowledge/files/src/common/scram-common.c.md`.
- Looser non-common variant: `src/backend/utils/adt/encode.c`.

## Tally

`[verified-by-code]=10 [from-comment]=1 [inferred]=1`
