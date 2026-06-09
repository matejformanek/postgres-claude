# Issues — `src/include/common`

Per-subsystem issue register for the **common header layer** — cryptography/hash/secret APIs, file/parse/string helpers, type-system + unicode primitives. 50 headers / ~105 entries surfaced 2026-06-09 by A16 (slices A16-1 crypto/hash, A16-2 file/parse, A16-3 types/unicode).

**Parent docs:** `knowledge/files/src/include/common/*` (50 docs — full directory coverage; pre-existing from A5's 2026-06-03 sweep, enriched by A16 with header-anchored Phase D notes).

**Sibling registers:** `knowledge/issues/common.md` (A5's `src/common/*.c` 124 entries — the impl companion).

## Headlines

1. **🚨 jsonapi recursive-parser frontend SIGSEGV** — `pg_parse_json` (recursive) depends on `check_stack_depth()` which is a NO-OP in libpq/psql/pg_dump frontend builds. Only `pg_parse_json_incremental` has explicit `JSON_TD_MAX_STACK=6400` cap. Frontend callers of recursive entry can SIGSEGV on adversarial deeply-nested JSON. **A5 finding at API layer.**
2. **`cryptohash.h` is the SecretBuf template** — both `_free` impls call `explicit_bzero(ctx)` but the header NEVER tells the caller this. A5's proposed `secretbuf.h` would generalize for 10+ caller-owned secret buffers.
3. **No constant-time compare helpers** — every HMAC/digest/MD5/base64 consumer hand-rolls `timingsafe_bcmp`; pgcrypto (A11) does NOT. A `pg_cryptohash_compare_constant_time` helper would standardize.
4. **`scram-common.h` has no iteration-count cap** — `SCRAM_SHA_256_DEFAULT_ITERATIONS = 4096` is the RFC floor; OWASP-2026 says ≥600k. No `_MAX_ITERATIONS` constant — malicious server can coerce client into long PBKDF2.
5. **`pg_prng.h` exposes `s0/s1` raw with NO "NOT FOR SECURITY" warning** — A5 finding (DSM control-handle uses pg_prng not pg_strong_random). Header makes pg_prng look interchangeable with `pg_strong_random`.
6. **OpenSSL 3.0 EVP_*_fetch shims NOT yet in tree** — A11 pgcrypto modernization (ERR_get_error drain, BN_FLG_CONSTTIME helper) would land in `openssl.h` or new `common/evp.h`.
7. **`percentrepl.h` does NO shell escaping** — A5 + A8 + A14 cluster header anchor. `replace_percent_placeholders` is the canonical injection sink.
8. **`pg_lzcompress.h` no input/output ratio bound** — A5 decompression-bomb echoes A11 pgcrypto pgp-compress.
9. **`controldata_utils.h` single 8 KiB write to pg_control with no shadow file** — A5 torn-write window at API layer.
10. **`pg_abs_s64(PG_INT64_MIN)` is the only safe signed-abs on INT64_MIN** — A7 numeric integer-overflow surface header anchor.
11. **Unicode-case-table regeneration invalidates citext/pg_trgm indexes** — A13/A14 collation-pinning hazard at `unicode_case.h` header layer.
12. **`pg_strip_crlf` only strips trailing CRLF** — embedded controls slip through (A4/A5 log-injection cluster echo).
13. **`durable_rename` has no O_NOFOLLOW** — A5/A6/A14 TOCTOU cluster header anchor (`file_utils.h`).
14. **`pg_dir_create_mode` / `pg_file_create_mode` are PGDLLIMPORT mutable globals** — extension can flip 0600→0640 mid-cluster (`file_perm.h`).
15. **OAuth validator-module mechanism is a trust-boundary surface** — `oauth-common.h` doesn't cross-reference validator-loader contract (dlopen cluster echo).

## Entries — A16-1 (crypto / hash / secret, 14 headers)

### cryptohash.h, hmac.h, sha1.h, sha2.h, md5.h
- [ISSUE-documentation: `_free` explicit_bzero contract NOT documented at header level (likely)] — `cryptohash.h:36`, `hmac.h:27`
- [ISSUE-api-shape: no constant-time digest-compare helper — every HMAC/digest consumer hand-rolls timingsafe_bcmp (maybe)] — `cryptohash.h:35`, `hmac.h:26`
- [ISSUE-documentation: `_create` OOM behaviour differs between fallback (NULL) and OpenSSL (ereport ERROR); not noted (nit)] — `cryptohash.h:32`
- [ISSUE-defense-in-depth: `pg_cryptohash_error` returns OpenSSL diagnostics verbatim; client error leaks library internals (nit)] — `cryptohash.h:37`
- [ISSUE-api-shape: caller's `dest` in `_final` is not scrubbed by `_free` — A5 SecretBuf candidate (likely)] — `cryptohash.h:35`
- [ISSUE-documentation: no deprecation note that SHA-1 is broken for collision resistance (nit)] — `sha1.h:1-21`
- [ISSUE-documentation: `*_STRING_LENGTH` variants are hex-output sizes used only by md5_common.c; presence here invites confusion (nit)] — `sha2.h:21-30`
- [ISSUE-documentation: no deprecation note in md5.h for legacy-SCRAM-only (likely)] — `md5.h:1-38`
- [ISSUE-api-shape: pg_md5_encrypt's output buf is caller-owned plain char[]; SecretBuf candidate (likely)] — `md5.h:33-35`
- [ISSUE-api-shape: no constant-time pg_md5_equal helper — strcmp on hex digests leaks timing (maybe)] — `md5.h:29-32`

### scram-common.h, saslprep.h
- [ISSUE-defense-in-depth: no SCRAM_SHA_256_MAX_ITERATIONS upper bound; malicious server coerces client into long PBKDF2 (likely)] — `scram-common.h:50`
- [ISSUE-documentation: `SCRAM_SHA_256_DEFAULT_ITERATIONS = 4096` is RFC floor; OWASP-2026 ≥600k. No MIN/MAX guidance (likely)] — `scram-common.h:50`
- [ISSUE-api-shape: scram_SaltedPassword takes pg_cryptohash_type but impl only accepts PG_SHA256 (nit)] — `scram-common.h:52`
- [ISSUE-defense-in-depth: scram password/salted_password params raw `const char *`; no SecretBuf variant (likely)] — `scram-common.h:52-64`
- [ISSUE-documentation: pg_saslprep output-allocator (palloc vs malloc) FE/BE context-dependent, not at header (likely)] — `saslprep.h:28`
- [ISSUE-defense-in-depth: no input-length bound on pg_saslprep; large passwords normalized in full (nit)] — `saslprep.h:28`
- [ISSUE-api-shape: normalized password output is plain `char *`; SecretBuf candidate (maybe)] — `saslprep.h:28`

### hashfn.h, hashfn_unstable.h, pg_prng.h
- [ISSUE-documentation: hashfn.h doesn't declare "stable, on-disk safe" contract (likely)] — `hashfn.h:1-119`
- [ISSUE-audit-gap: no header distinction between security-grade vs general-purpose hash (maybe)] — `hashfn.h:91-117`
- [ISSUE-defense-in-depth: no per-process keying in hashfn; hash-flood DoS surface on dynahash tables (maybe)] — `hashfn.h:23`
- [ISSUE-correctness: fasthash_accum_cstring_aligned reads up to 7 bytes past NUL; PointerIsAligned is sole gate (maybe)] — `hashfn_unstable.h:259-291`
- [ISSUE-documentation: "unstable" guarantee only in leading comment; easy to copy a prototype into persisting context (nit)] — `hashfn_unstable.h:1-13`
- [ISSUE-documentation: pg_prng header has no "NOT FOR SECURITY" warning (likely)] — `pg_prng.h:1-62`
- [ISSUE-audit-gap: extensions can write s0/s1 directly; zero-seed → xoroshiro produces zero forever (maybe)] — `pg_prng.h:19-23`
- [ISSUE-security: A5 finding — DSM control-handle uses pg_prng_uint32 not pg_strong_random (maybe)] — `pg_prng.h:55`

### link-canary.h, openssl.h, oauth-common.h, base64.h
- [ISSUE-documentation: link-canary header lacks pointer to where this gets checked (nit)] — `link-canary.h:15`
- [ISSUE-audit-gap: no header-level helper to drain `ERR_get_error()` into errstr; A11 pgcrypto discarded-error fix would land here (likely)] — `openssl.h:17-41`
- [ISSUE-audit-gap: no header-level `pg_openssl_bn_set_consttime` helper; A11 non-constant-time RSA/Elgamal fix candidate (likely)] — `openssl.h:17-41`
- [ISSUE-audit-gap: PG18 OAuth validator-module is trust boundary; header doesn't cross-reference validator-loader (likely)] — `oauth-common.h:13-19`
- [ISSUE-documentation: base64.h doesn't explain why two base64 codecs exist (common vs encode.c) (nit)] — `base64.h:14-17`
- [ISSUE-defense-in-depth: no constant-time base64 decode helper for SCRAM ServerSignature paths (nit)] — `base64.h:15`

## Entries — A16-2 (file / parse / string, 19 headers)

### percentrepl.h, archive.h, blkreftable.h, parse_manifest.h
- [ISSUE-security: `replace_percent_placeholders` does NO shell escaping; output to system()/OpenPipeStream (likely, A5+A8+A14)] — `percentrepl.h:16`
- [ISSUE-security: `BuildRestoreCommand` return fed to system() with no shell-escape contract (likely, A5+A8+A14)] — `archive.h:16-19`
- [ISSUE-security: `BlockRefTableSetLimitBlock` accepts attacker-controlled limit_block; hostile BRT silently drops blocks (likely, A5)] — `blkreftable.h:54-57`
- [ISSUE-correctness: report_error_fn "must not return" comment-only; no noreturn (maybe)] — `blkreftable.h:44-47`
- [ISSUE-security: SHA-256 in per_file_cb payload is integrity not authenticity (likely, A5)] — `parse_manifest.h:29-32`
- [ISSUE-correctness: incremental JSON parser is recursive; deeply nested manifests exhaust stack (likely, A8 echo)] — `parse_manifest.h:52-54`

### file_utils.h, file_perm.h, controldata_utils.h
- [ISSUE-security: `update_controlfile` advertises atomic; impl is single 8 KiB write, no shadow (likely, A5)] — `controldata_utils.h:18-19`
- [ISSUE-correctness: `*crc_ok_p` must be checked before trusting ControlFileData; no enforcement (nit)] — `controldata_utils.h:15-17`
- [ISSUE-security: `durable_rename` has no O_NOFOLLOW; TOCTOU symlink window (likely, A5+A6+A14)] — `file_utils.h:41`
- [ISSUE-security: `get_dirent_type` look_through_symlinks flag, no header guidance on safe usage (maybe, A6)] — `file_utils.h:45-48`
- [ISSUE-defense-in-depth: `pg_dir_create_mode`/`pg_file_create_mode` PGDLLIMPORT mutable; extension can flip mid-cluster (maybe)] — `file_perm.h:44-45`
- [ISSUE-correctness: pg_authid hash files persist with mode active at write time; toggling doesn't chmod existing (nit, A6)] — `file_perm.h:44-45`

### pg_lzcompress.h, restricted_token.h, compression.h, checksum_helper.h
- [ISSUE-security: pglz_decompress has no input/output ratio bound (likely, A5 + A11 echo)] — `pg_lzcompress.h:88-89`
- [ISSUE-security: get_restricted_token returns void; Windows fail-open privilege drop (likely, A5+A6)] — `restricted_token.h:17`
- [ISSUE-correctness: `$PG_RESTRICT_EXEC` env var skips privilege drop, undocumented (nit)] — `restricted_token.h:17`
- [ISSUE-correctness: pg_compress_specification level/workers accept untrusted values without validate (maybe)] — `compression.h:32-40`
- [ISSUE-defense-in-depth: checksum_type enum mixes fast-integrity (CRC32C) and crypto-strong (SHA512) (maybe)] — `checksum_helper.h:29-37`

### connect.h, ip.h, relpath.h, logging.h
- [ISSUE-api-shape: ALWAYS_SECURE_SEARCH_PATH_SQL must run after auth but before any other query (nit)] — `connect.h:25-26`
- [ISSUE-defense-in-depth: pg_hba hostname matching trusts ip.h wrappers under poisoned DNS (maybe, A2)] — `ip.h:23-31`
- [ISSUE-correctness: FORKNAMECHARS=4 hard-coded; new fork name >4 chars overflows RelPathStr (nit)] — `relpath.h:97-113`
- [ISSUE-correctness: relpathbackend macro evaluates rlocator three times (maybe)] — `relpath.h:140-152`
- [ISSUE-security: pg_log_error callsites with PQerrorMessage(conn) leak secrets verbatim (maybe, A4 echo)] — `logging.h:108-115`

### string.h, fe_memutils.h, username.h, config_info.h
- [ISSUE-security: pg_strip_crlf only strips trailing CRLF; embedded controls slip through (maybe, A4+A5 log-injection)] — `string.h:31`
- [ISSUE-defense-in-depth: simple_prompt returns malloc'd buffer with no scrubbing wrapper (nit, A4 secret-scrub)] — `string.h:41-43`
- [ISSUE-defense-in-depth: no pg_free_secure / pg_explicit_bzero symbol; every secret-bearing free leaves heap residue (maybe, A5 SecretBuf cluster)] — `fe_memutils.h:42`
- [ISSUE-defense-in-depth: OS↔PG namespace overlap (peer auth) carries no header-level warning (nit, A2+A6 echo)] — `username.h:12`
- [ISSUE-defense-in-depth: get_configdata leaks build paths (nit)] — `config_info.h:18-19`

## Entries — A16-3 (types / unicode / json, 17 headers)

### jsonapi.h, int.h, int128.h, shortest_dec.h
- [ISSUE-security: `pg_parse_json` (recursive) depends on `check_stack_depth()` NO-OP in frontend; SIGSEGV on adversarial nested JSON (likely, A5 finding at API layer)] — `jsonapi.h:174`
- [ISSUE-correctness: `pg_abs_s64(PG_INT64_MIN)` is only safe signed-abs on INT64_MIN; bare `abs()`/`-x` on user int64 = UB (likely, A7 anchor)] — `int.h:352`
- [ISSUE-correctness: `0x5EED` sentinel + caller-must-check-bool convention; no Assert catches use-without-check (nit)] — `int.h:76`
- [ISSUE-correctness: portable INT128 struct byte layout must match native __int128 for test_int128 memcpy cross-checks; padding/reorder silently breaks test (nit)] — `int128.h:42`
- [ISSUE-correctness: `int128_div_mod_int32` unsafe on div-by-zero and INT128_MIN/-1 (maybe)] — `int128.h:308`
- [ISSUE-api-shape: `*_bufn` Ryu variants do NOT NUL-terminate; only the `n` distinguishes (nit)] — `shortest_dec.h:11`

### unicode_*.h
- [ISSUE-correctness: NFKC table-version skew between mismatched libpq + server can cause SCRAM auth failure on exotic codepoints (maybe)] — `unicode_norm.h:33`
- [ISSUE-correctness: regenerating unicode_case_table.h across major upgrade can change case fold; invalidates citext/pg_trgm indexes built against DEFAULT_COLLATION_OID. REINDEX is the only fix (maybe, A13+A14 echo)] — `unicode_case.h:23`

### keywords.h, kwlookup.h
(thin headers; no Phase-D issues — perfect-hash keyword lookup is auto-generated)

## Cross-sweep references

- **A5 common.md** (124 entries) — the `.c` companion register; every header here has a .c partner there.
- **A7 utils.md** (310 entries) — int.h numeric-overflow surface, jsonapi.h backend recursion, formatting cross-link.
- **A11 pgcrypto.md** (~80 entries) — openssl.h + cryptohash.h + hmac.h are the modernization candidate anchors.
- **A11/A13/A14 signature-collision cluster** — hashfn.h is the in-tree non-security-grade anchor.
- **A13 citext + A14 pg_trgm** DEFAULT_COLLATION pin → unicode_case.h header echo.
- **A14 basebackup_to_shell + basic_archive** + A8 archive_command → percentrepl.h + archive.h header anchors.
- **A4/A5 secret-scrub cluster** → fe_memutils.h + string.h + cryptohash.h headers.
- **A6 pg_upgrade + pg_rewind** → file_utils.h + file_perm.h + restricted_token.h headers.
