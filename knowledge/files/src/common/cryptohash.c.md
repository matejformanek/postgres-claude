---
path: src/common/cryptohash.c
anchor_sha: 4b0bf0788b0
loc: 273
---

# cryptohash.c

- **Source path:** `source/src/common/cryptohash.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 273

## Purpose

Fallback implementation of the `pg_cryptohash_*` API used when PG is
built without OpenSSL. Glues the in-tree `pg_md5_*`, `pg_sha1_*`,
`pg_sha224..512_*` primitives behind one opaque `pg_cryptohash_ctx`
so callers (`scram_H`, `pg_md5_hash`, WAL summarisation, RANDOM_PAGE
checksums via cryptohash) need not care which algorithm or which
backend (in-tree vs OpenSSL) is in play. [verified-by-code,
cryptohash.c:1-15]

## Role in PG

Linked into `libpgcommon` for both frontend and backend whenever
`USE_OPENSSL` is *not* defined. `cryptohash_openssl.c` defines the
same symbols and is linked in the OpenSSL build instead — meson
selects exactly one. [inferred from build pattern, verified by
identical symbol exports]

## Key functions

- `pg_cryptohash_create(type)` (cryptohash.c:73): allocates one
  `pg_cryptohash_ctx` sized for the largest of the six possible
  sub-ctxs. Backend uses `palloc`, frontend uses `malloc`. `memset(0)`
  before return.
- `pg_cryptohash_init / _update` (cryptohash.c:99-164): dispatches on
  `ctx->type` to the per-algorithm primitive. Always returns 0 (the
  fallback's per-algorithm `_init`/`_update` cannot fail).
- `pg_cryptohash_final(ctx, dest, len)` (cryptohash.c:171-230): the
  only place where a runtime error is possible —
  `PG_CRYPTOHASH_ERROR_DEST_LEN` if `len <` the algorithm's digest
  size. Otherwise calls the per-algorithm `_final` and returns 0.
- `pg_cryptohash_free(ctx)` (cryptohash.c:237-245):
  `explicit_bzero(ctx, sizeof(pg_cryptohash_ctx))` before `pfree` /
  `free`. **Scrub-on-free is built in.** [verified-by-code,
  cryptohash.c:243]
- `pg_cryptohash_error(ctx)` (cryptohash.c:253-273): static
  translated error strings; never allocates.

## OpenSSL vs fallback dispatch

`cryptohash.c` defines the symbols; `cryptohash_openssl.c` is the
peer. Build system picks one. They share the public header
`common/cryptohash.h` and produce identical caller-visible behaviour,
modulo the OpenSSL impl's `EVP_*` error queue surfacing as
`errreason`. [inferred from dual-file identical-symbol pattern]

## State / globals

None. Each context is per-call.

## Concurrency

Reentrant. No globals.

## Phase D notes

- **`explicit_bzero` in `_free` is the cleanest possible discipline.**
  This file is the *positive* model: every callee state lives inside
  the context; `_free` scrubs unconditionally. A `SecretBuf` type
  hosted in `src/common/` should adopt this exact pattern (allocate,
  use, scrub-on-free).
- The OpenSSL peer mirrors the discipline: `cryptohash_openssl.c:153,
  338` both `explicit_bzero` before `FREE`. **Unified contract across
  the two impls.**
- **Caller's `dest` buffer is not scrubbed.** `pg_cryptohash_final`
  writes to caller memory; if that memory holds an HMAC tag or
  digest derived from a secret, the caller must scrub. This is the
  gap a `SecretBuf` would close.

## Potential issues

- **[ISSUE-undocumented-invariant: error enum sentinel relies on
  caller checking return]** Most call sites do
  `if (... < 0) return -1;`. A caller that uses `_final` without
  checking the return would happily emit zeros from a destination
  that was never written into. Severity: nit.
- **[ISSUE-stale-todo: comment at cryptohash.c:78-83 admits the union
  wastes memory for MD5/SHA224/SHA256]** Calls out itself. Severity:
  nit.

## Cross-refs

- Public API: `knowledge/files/src/include/common/cryptohash.h.md`.
- OpenSSL peer: `knowledge/files/src/common/cryptohash_openssl.c.md`.
- Per-algorithm impls: `md5.c`, `sha1.c`, `sha2.c` under
  `src/common/`.

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->

## Tally

`[verified-by-code]=8 [from-comment]=1 [inferred]=2`
