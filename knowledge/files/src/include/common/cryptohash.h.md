---
path: src/include/common/cryptohash.h
anchor_sha: 4b0bf0788b0
loc: 39
---

# cryptohash.h

- **Source path:** `source/src/include/common/cryptohash.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 39

## Purpose

Public API for the generic, multi-algorithm cryptographic hash facade
used by `src/common/scram-common.c`, `pg_md5_hash`, WAL summarisation,
and any other backend/libpq site that wants `pg_cryptohash_*`. Two
implementations sit behind it: `cryptohash.c` (in-tree fallback) and
`cryptohash_openssl.c` (when `USE_OPENSSL` is set). [verified-by-code,
cryptohash.h:14-38]

## Key declarations

- `pg_cryptohash_type` enum — `PG_MD5`, `PG_SHA1`, `PG_SHA224`,
  `PG_SHA256`, `PG_SHA384`, `PG_SHA512` (cryptohash.h:19-27). The
  enum *order* is not on-disk; safe to reorder so long as both impls
  stay in sync. `PG_MD5 = 0` is hard-coded.
- `struct pg_cryptohash_ctx` — opaque, defined privately in each impl.
- API: `pg_cryptohash_create / _init / _update / _final / _free /
  _error` (cryptohash.h:32-37). `_create` returns NULL on OOM in
  frontend; backend `ereport(ERROR)`s on OOM for the OpenSSL impl
  (cryptohash_openssl.c:156-158) but the in-tree impl returns NULL
  (cryptohash.c:85-86). [verified-by-code]

## OpenSSL vs fallback dispatch

Build system picks at most one of `cryptohash.c` or
`cryptohash_openssl.c`; the chosen `.o` defines all six symbols.
There is no per-call dispatch — the API is link-time-resolved.
[inferred from meson.build pattern, verified by symbol duplication]

## Phase D notes

- **Opaque-context = SecretBuf template.** `pg_cryptohash_free` is
  the canonical in-tree example of "an `_free` that scrubs before
  release": both impls call `explicit_bzero(ctx, sizeof(*ctx))` then
  free. [verified-by-code, `source/src/common/cryptohash.c:243`,
  `source/src/common/cryptohash_openssl.c` analogous]. The proposed
  A5 `SecretBuf` (`secretbuf.h` + `secretbuf.c`) would generalise
  this pattern for the 10+ caller-owned secret buffers (see A5
  `knowledge/issues/common.md` "SecretBuf cluster") — `cryptohash.h`
  is the existence proof.
- **Header does NOT document the scrub contract.** Nothing in
  `cryptohash.h:32-37` tells the reader "_free wipes secret bytes";
  callers have to know by reading the impl. `[ISSUE-documentation:
  no header-level note that _free scrubs the ctx (likely)]`.
- **Caller-side `dest` is NOT the context's responsibility.** A caller
  that does `uint8 digest[32]; pg_cryptohash_final(ctx, digest, 32);
  pg_cryptohash_free(ctx);` ends with cleared ctx but live secret in
  `digest`. SCRAM is a frequent offender — see scram-common.c notes.
- **No constant-time compare helper.** Every consumer of HMAC tags or
  hash digests has to hand-roll `timingsafe_bcmp` (libpq does, see
  scram-common.c; pgcrypto does NOT — A11 finding).
  `[ISSUE-api-shape: missing pg_cryptohash_compare_constant_time helper (maybe)]`.
- **OOM behaviour split, undocumented.** `_create` returns NULL on
  OOM for the in-tree fallback (`cryptohash.c:85-86`) but the OpenSSL
  impl `ereport(ERROR)`s under backend
  (`cryptohash_openssl.c:156-158`). Frontend libpq must NULL-check;
  backend must not (would be unreachable). Header `cryptohash.h:32`
  doesn't hint at this split. `[ISSUE-documentation: split OOM
  contract between fallback / OpenSSL impls is not in the header (nit)]`.
- **Error string opacity.** `pg_cryptohash_error` returns
  `const char *` but no enumeration of possible strings — callers
  pass straight through `ereport(ERROR, errmsg("...%s", _error(ctx)))`,
  which means OpenSSL diagnostic strings reach client error logs
  verbatim. Defence-in-depth concern only — not currently exploited.

## Cross-refs

- Fallback impl: `knowledge/files/src/common/cryptohash.c.md`.
- OpenSSL impl: `knowledge/files/src/common/cryptohash_openssl.c.md`.
- Caller idioms: `pg_md5_hash` in `src/common/md5_common.c`,
  `scram_H` in `src/common/scram-common.c`.
- A5 SecretBuf cluster: `knowledge/issues/common.md` (the "SecretBuf
  hosting site").
- A11 pgcrypto: `knowledge/issues/pgcrypto.md` (pgcrypto's `px_memset`
  is weaker than `explicit_bzero`; cryptohash is the model to adopt).

## Issues

1. `[ISSUE-documentation: _free's explicit_bzero contract is NOT
   documented at header level; callers learn it only by reading the
   impl (likely)]` — `source/src/include/common/cryptohash.h:36`.
2. `[ISSUE-api-shape: no constant-time digest-compare helper —
   every HMAC/digest consumer hand-rolls timingsafe_bcmp (maybe)]` —
   `source/src/include/common/cryptohash.h:35`.
3. `[ISSUE-documentation: _create OOM behaviour differs between
   fallback (returns NULL) and OpenSSL backend (ereport ERROR) —
   not noted in header (nit)]` — `source/src/include/common/cryptohash.h:32`.
4. `[ISSUE-defense-in-depth: pg_cryptohash_error returns OpenSSL
   diagnostic strings verbatim; risk of leaking library internals
   into client error messages (nit)]` — `source/src/include/common/cryptohash.h:37`.
5. `[ISSUE-api-shape: caller's dest buffer in _final is not scrubbed
   by _free — A5 SecretBuf candidate site (likely)]` —
   `source/src/include/common/cryptohash.h:35`.

## Tally

`[verified-by-code]=4 [inferred]=2`
