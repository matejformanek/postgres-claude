---
path: src/common/sha1.c
anchor_sha: 4b0bf0788b0
loc: 369
---

# sha1.c

- **Source path:** `source/src/common/sha1.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 369

## Purpose

In-tree fallback SHA-1 (FIPS PUB 180-1, RFC 3174). WIDE Project /
itojun lineage. Implements `pg_sha1_init / _update / _final` over the
`pg_sha1_ctx` defined in `sha1_int.h`. Selected only in non-OpenSSL
builds. [from-comment, sha1.c:1-51]

## Role in PG

Reachable only via the `pg_cryptohash_*` dispatch (`PG_SHA1`).
No direct callers outside `cryptohash.c`. SHA-1 is not used for
SCRAM (which is SHA-256) or for any password storage; it surfaces in
WAL summarisation, sslcert hashing, and a few utility paths.

## Key functions

- `pg_sha1_init(ctx)` (sha1.c:316): zeros the ctx, seeds the five
  IV words (`0x67452301`, ..., `0xc3d2e1f0`).
- `pg_sha1_update(ctx, data, len)` (sha1.c:332): buffers up to a
  64-byte block, calls `sha1_step` per block. Updates the bit-count
  in `ctx->c.b64[0]`.
- `pg_sha1_final(ctx, dest)` (sha1.c:365): `sha1_pad(ctx)` then
  `sha1_result(dest, ctx)`.
- Static `sha1_step(ctx)` (sha1.c:89): the 80-round transform. On
  little-endian it byte-swaps the message block into a stack
  `pg_sha1_ctx tctx` copy first (sha1.c:101-168, the verbose
  manually-unrolled swap). Loops over four 20-round phases with
  rotating F0..F3 mix-ins and K[t/20] constants.
- `sha1_pad` (sha1.c:233): pads with `0x80` then zeros and the
  64-bit bit-count.
- `sha1_result` (sha1.c:276): byte-swaps the output on little-endian.

## OpenSSL vs fallback dispatch

Build-time. Peer is `cryptohash_openssl.c::EVP_sha1()`.

## State / globals

- `_K[4]` — the four SHA-1 round constants (sha1.c:64). Read-only.

## Concurrency

Reentrant.

## Phase D notes

- **No `explicit_bzero`** in this file. The `tctx` stack copy made
  during little-endian swap (sha1.c:102) is a complete duplicate of
  the message block — survives until frame teardown. Not a leak in
  the SCRAM-secret sense (SHA-1 isn't used for SCRAM) but adds to the
  list of unscrubbed hash-state stack copies.
- The ctx is unioned into `pg_cryptohash_ctx.data.sha1` so
  `pg_cryptohash_free` does scrub it on free. Discipline is at the
  dispatcher level, not here.
- WIDE-project licence preserved; structure layout pinned by the
  union aliases in `pg_sha1_ctx`.

## Potential issues

- **[ISSUE-secret-scrub: `sha1_step`'s stack `tctx` not bzero'd]**
  `sha1.c:102`. Holds a byte-swapped copy of the current message
  block. Severity: nit (low sensitivity — SHA-1 isn't used for
  passwords).
- **[ISSUE-dead-code (eventual): SHA-1 fallback exists only for
  no-OpenSSL builds]** Same parity story as MD5. Severity: nit.

## Cross-refs

- Internal header: `knowledge/files/src/common/sha1_int.h.md`.
- Public constants: `knowledge/files/src/include/common/sha1.h.md`.
- Dispatch facade: `knowledge/files/src/common/cryptohash.c.md`.

## Tally

`[verified-by-code]=6 [from-comment]=2`
