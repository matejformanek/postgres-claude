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

- The opaque-context design naturally containerises any internal
  secret state and `pg_cryptohash_free` is documented (in both impls)
  to `explicit_bzero` before free. Good — but the *caller's* digest
  buffer (the `dest` of `_final`) is not the context's responsibility.
- API has no "compute-and-compare in constant time" helper; every
  user of HMAC/digest tags has to remember `timingsafe_bcmp` itself.

## Cross-refs

- Fallback impl: `knowledge/files/src/common/cryptohash.c.md`.
- OpenSSL impl: `knowledge/files/src/common/cryptohash_openssl.c.md`.
- Caller idioms: `pg_md5_hash` in `src/common/md5_common.c`,
  `scram_H` in `src/common/scram-common.c`.

## Tally

`[verified-by-code]=3 [inferred]=1`
