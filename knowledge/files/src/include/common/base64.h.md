---
path: src/include/common/base64.h
anchor_sha: 4b0bf0788b0
loc: 19
---

# base64.h

- **Source path:** `source/src/include/common/base64.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 19

## Purpose

Public API for the strict, no-whitespace base64 codec used by SCRAM
(nonces, salt, StoredKey/ServerKey in `pg_authid.rolpassword`) and by
the OAuth bearer-token path. Distinct from `pg_b64encode` /
`pg_b64decode` in `src/backend/utils/adt/encode.c`, which accept
whitespace. [from-comment, base64.h:3-5]

## Key declarations

- `pg_b64_encode(src, len, dst, dstlen)` — returns encoded length, -1
  on dst-overflow. Marked `pg_nodiscard`.
- `pg_b64_decode(src, len, dst, dstlen)` — returns decoded length, -1
  on malformed-or-overflow. `pg_nodiscard`.
- `pg_b64_enc_len(srclen)` / `pg_b64_dec_len(srclen)` — buffer sizing.

## Phase D notes

- `pg_nodiscard` on encode/decode is the trip-wire for "did the caller
  check the -1 return". Compiler-enforced.
- Strict-whitespace rejection (impl returns -1 on `' '`, `\t`, `\n`,
  `\r`) is a SCRAM/wire-format requirement: the SCRAM messages can
  contain neither padding-stripped nor wrapped base64. See base64.c
  notes for the padding rules.

## Cross-refs

- Impl: `knowledge/files/src/common/base64.c.md`.
- Primary SCRAM consumer: `src/common/scram-common.c`.
- Looser non-common variant: `src/backend/utils/adt/encode.c`.

## Tally

`[verified-by-code]=3 [from-comment]=1`
