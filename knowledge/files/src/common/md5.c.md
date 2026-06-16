---
path: src/common/md5.c
anchor_sha: 4b0bf0788b0
loc: 436
---

# md5.c

- **Source path:** `source/src/common/md5.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 436

## Purpose

In-tree fallback MD5 (RFC 1321). Implements `pg_md5_init`,
`pg_md5_update`, `pg_md5_final` over the `pg_md5_ctx` defined in
`md5_int.h`. Buffers every input byte before computing — a simple
implementation, not optimised. WIDE Project / KAME provenance.
[from-comment, md5.c:1-19]

## Role in PG

Selected only when PG is built without OpenSSL. Even then it's only
reachable through `pg_cryptohash_*` (cryptohash.c routes `PG_MD5` to
`pg_md5_*`). The historic `pg_md5_hash` / `pg_md5_encrypt` helpers in
`md5_common.c` go through the same indirection — there is no direct
caller of `pg_md5_init/_update/_final` outside cryptohash.c.

## Key functions

- `pg_md5_init(ctx)` (md5.c:382): zeroes counters, seeds state with
  the standard MD5 IVs `0x67452301 / 0xefcdab89 / 0x98badcfe /
  0x10325476`, clears the 64-byte buffer.
- `pg_md5_update(ctx, data, len)` (md5.c:400): buffers up to a block
  boundary, calls static `md5_calc` per full 64-byte block, stashes
  trailing bytes. Updates `md5_n` (bit count).
- `pg_md5_final(ctx, dest)` (md5.c:432): `md5_pad(ctx)` then
  `md5_result(dest, ctx)`.
- Static helpers:
  - `md5_calc(b64, ctx)` (md5.c:154): the 64-round transform. On
    big-endian builds it byte-swaps the input block into a stack
    `X[16]` first; on little-endian it casts directly. Uses the four
    `ROUND1..4` macros with `T[]` of `floor(2^32 * |sin(i)|)`
    constants (md5.c:119-140).
  - `md5_pad(ctx)` (md5.c:310): standard MD5 padding (0x80 then
    zeros then 8-byte bit-length).
  - `md5_result(digest, ctx)` (md5.c:348): byte-swaps output on
    big-endian.

## OpenSSL vs fallback dispatch

Build-time: this file is in `libpgcommon` only when `USE_OPENSSL` is
unset (or, more precisely, when the meson build elects the fallback;
the actual gating is in `src/common/meson.build`). [inferred]

## State / globals

- `T[65]` — read-only sin-magic constants (md5.c:119).
- `md5_paddat[MD5_BUFLEN]` — read-only `0x80, 0, 0, ...` padding
  template (md5.c:142).

## Concurrency

Reentrant. The two globals are read-only.

## Phase D notes

- **MD5 deprecation status:** still wired up because some platforms
  build PG without OpenSSL. There is no `#pragma` or `[deprecated]`
  attribute on the symbols — deprecation lives at the *protocol* layer
  in `crypt.c::md5_password_warnings`, not here.
- **No `explicit_bzero` here** — the assumption is that
  `pg_cryptohash_free` scrubs the union (cryptohash.c:243). If
  someone instantiated a `pg_md5_ctx` directly on stack and forgot to
  `explicit_bzero` at end-of-scope, the state would persist longer
  than necessary. But that's not how callers use this file.
- **Hot path on small inputs** when MD5 used for `pg_md5_encrypt`
  (`md5...` password derivation): allocate-init-update-final-free
  through cryptohash.c for every login. Comparable cost to OpenSSL's
  EVP for small inputs.

## Potential issues

- **[ISSUE-stale-todo: comment says "needs every input byte to be
  buffered before doing any calculations"]** `md5.c:7-8` — calls out
  itself as a simple impl. Not a perf concern (MD5 is deprecated)
  but documented. Severity: nit.
- **[ISSUE-dead-code (eventual): MD5 fallback exists only for
  no-OpenSSL builds]** Modern PG always builds OpenSSL by default.
  This file may be removable in a future PG once MD5 password
  support is fully removed from `crypt.c`. Track alongside the
  `MD5_PASSWD_*` constants in `md5.h`. Severity: nit.

## Cross-refs

- Internal header: `knowledge/files/src/common/md5_int.h.md`.
- Public API: `knowledge/files/src/include/common/md5.h.md`.
- Dispatch facade: `knowledge/files/src/common/cryptohash.c.md`.
- Password derivation: `knowledge/files/src/common/md5_common.c.md`.

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->

## Tally

`[verified-by-code]=8 [from-comment]=2 [inferred]=1`
