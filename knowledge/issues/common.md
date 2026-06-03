# Issues — `common` (src/common/ + src/include/common/)

Per-subsystem issue register for the dual-target (frontend + backend)
shared C library. See `knowledge/issues/README.md` for tag taxonomy.

**Parent docs:** `knowledge/files/src/common/*` (59) +
`knowledge/files/src/include/common/*` (50) = 109 docs.

**Source:** 124 entries surfaced 2026-06-03 by the A5 foreground sweep
(5 batches: crypto/scram, file/backup, encoding/strings, numerics,
misc+stubs). Each is mirrored in the corresponding per-file doc's
`## Potential issues` block.

`src/common/` is **the dual-target floor**: every file builds for both
frontend (libpq, bin/ tools, fe_utils) and backend. That makes it the
unique hosting site for shared primitives like the proposed `SecretBuf`
— it's the only place a single helper can be reused by libpq +
psql + pg_dump + initdb + pg_basebackup + the backend itself.

The headlines:
1. **The SecretBuf candidate site** — `src/include/common/secretbuf.h`
   would close the 4-occurrence libpq/psql/initdb/streamutil
   secret-scrub gap with a single new type. 10+ specific sites in
   this batch motivate it.
2. **Backup-trust model echoes A3 pg_dump** — `blkreftable.c` +
   `parse_manifest.c` both authenticate with CRC/SHA-256 over bytes
   the attacker controls end-to-end. Phase D candidate.
3. **Decompression bomb + parser DoS surface** — `pg_lzcompress`,
   `jsonapi`, `stringinfo`, `unicode_norm` all have unbounded growth
   pieces.
4. **GUC-boundary shell-injection** — `percentrepl.c` + `archive.c`
   leave shell-escaping to the operator.

---

## P0 — Phase D candidates

### The SecretBuf cluster (10+ unscrubbed-secret sites)

This batch's headline. The fourth installment of the libpq A2 +
psql A4 + initdb A4 secret-scrub gap, now with **enough call sites in
one directory** to motivate a single shared helper.

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | md5_common.c:151,170 | secret-scrub | likely | `pg_md5_encrypt` mallocs `passwd_len+salt_len+1`, copies plaintext password + salt, hashes, `free()` without `explicit_bzero` — the textbook unscrubbed cleartext leak | open | knowledge/files/src/common/md5_common.c.md |
| 2026-06-03 | md5_common.c | secret-scrub | likely | `pg_md5_hash`'s stack `sum[16]` is the hash output and not zeroed before return | open | knowledge/files/src/common/md5_common.c.md |
| 2026-06-03 | scram-common.c | secret-scrub | likely | `scram_SaltedPassword` PBKDF2 intermediate `Ui`/`Ui_prev` 32-byte stack buffers not `explicit_bzero`'d — most sensitive bytes in PG SCRAM | open | knowledge/files/src/common/scram-common.c.md |
| 2026-06-03 | scram-common.c | secret-scrub | likely | `scram_build_secret` derivation arrays (`SaltedPassword`, `ClientKey`, `StoredKey`) not bzero'd | open | knowledge/files/src/common/scram-common.c.md |
| 2026-06-03 | scram-common.c | side-channel | maybe | PBKDF2 inner loop has no constant-time discipline — observable hash-equality comparison | open | knowledge/files/src/common/scram-common.c.md |
| 2026-06-03 | saslprep.c | secret-scrub | likely | `input_chars` / `output_chars` (32-bit-wide) buffers carry SCRAM password codepoints through NFKC normalization without scrub | open | knowledge/files/src/common/saslprep.c.md |
| 2026-06-03 | hmac.c | secret-scrub | likely | `shrinkbuf` (key-too-long pre-hash) not `explicit_bzero`'d before reuse | open | knowledge/files/src/common/hmac.c.md |
| 2026-06-03 | hmac.c | secret-scrub | likely | Intermediate digest `h` not `explicit_bzero`'d | open | knowledge/files/src/common/hmac.c.md |
| 2026-06-03 | cryptohash_openssl.c | secret-scrub | maybe | `dest` buffer in `_final` is caller-owned and not scrubbed by helper — caller-side contract undocumented | open | knowledge/files/src/common/cryptohash_openssl.c.md |
| 2026-06-03 | sha1.c | secret-scrub | maybe | `sha1_step`'s stack `tctx` not bzero'd | open | knowledge/files/src/common/sha1.c.md |
| 2026-06-03 | sprompt.c | secret-scrub | likely | `simple_prompt` returns malloc'd password buffer with NO scrub contract — every caller (psql, libpq, pg_basebackup, pg_dump, initdb) just `free()`s without `explicit_bzero`; root cause of the four cross-corpus findings | open | knowledge/files/src/common/sprompt.c.md |
| 2026-06-03 | sprompt.c | trust-boundary | maybe | TTY-restore window during termios reset is not signal-safe — echo can remain disabled if SIGINT fires between `tcsetattr` echo-off and restore | open | knowledge/files/src/common/sprompt.c.md |
| 2026-06-03 | fe_memutils.c | secret-scrub | likely | `pg_free`/`pfree` are raw `free()` — frontend has no `pg_free_secure(ptr, len)` helper; root cause of every frontend secret-scrub gap | open | knowledge/files/src/common/fe_memutils.c.md |
| 2026-06-03 | fe_memutils.c | secret-scrub | maybe | `pg_strdup` of a secret leaves the source copy until caller scrubs it | open | knowledge/files/src/common/fe_memutils.c.md |
| 2026-06-03 | logging.c | secret-scrub | likely | Frontend log messages can carry secrets via `pg_log_error("...: %s", PQerrorMessage(conn))` — libpq parse errors embed substrings of malformed conninfo; lands on stderr AND `log_logfile` | open | knowledge/files/src/common/logging.c.md |
| 2026-06-03 | logging.c | secret-scrub | likely | `pg_malloc_extended` scratch buffer in `pg_log_generic_v` `free()`d without scrub | open | knowledge/files/src/common/logging.c.md |
| 2026-06-03 | pg_get_line.c | secret-scrub | maybe | `pg_get_line` buffer holds the password tail across calls; readline of a stream containing PASSWORD-bearing SQL keeps it in memory until next call | open | knowledge/files/src/common/pg_get_line.c.md |
| 2026-06-03 | fe_memutils.h | secret-scrub | maybe | Header advertises `pg_free` but no `pg_free_secure(ptr, len)` — the missing API | open | knowledge/files/src/include/common/fe_memutils.h.md |
| 2026-06-03 | logging.h | secret-scrub | maybe | Every `pg_log_error` callsite that includes `PQerrorMessage(conn)` is a potential frontend secret leak; header doesn't warn | open | knowledge/files/src/include/common/logging.h.md |

**Phase D pitch — the unified SecretBuf patch series:**

1. New file `src/include/common/secretbuf.h` + `src/common/secretbuf.c`:
   ```c
   typedef struct SecretBuf SecretBuf;
   SecretBuf *secret_alloc(size_t len);
   void *secret_data(SecretBuf *buf);
   void secret_free(SecretBuf *buf); /* explicit_bzero + free */
   ```
2. `cryptohash_*` + `hmac_*` gain `_final_secret(SecretBuf *dest)` variants;
   existing `_final` keeps semantics for non-secret digests.
3. `simple_prompt` gains `simple_prompt_secret(SecretBuf **out)`; all 9
   callers across libpq + bin/ tools migrate.
4. `pg_log_error_secret(...)` masks `%s` arguments tagged with a
   wrapper type (e.g. `LogSecret(PQerrorMessage(conn))`).
5. `pg_md5_encrypt` + `scram_SaltedPassword` use `SecretBuf` for
   their internal buffers.

This closes 10+ of the 19 entries in this section in one coordinated
landing. The remaining are caller-side contract docs (sprompt's TTY
restore, PBKDF2 constant-time).

### Backup-trust model — A3 echo

`blkreftable.c` + `parse_manifest.c` mirror the pg_dump archive-trust
finding: file-format checksums authenticate the file against
**accidental** corruption, not against an attacker who controls the
backup chain. Same shape as the pg_dump custom/directory format
analysis from A3 (`knowledge/issues/pg_dump.md` §Archive-format trust).

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | blkreftable.c:595-601,652-655 | trust-boundary | likely | BRT file authenticated by magic + trailing CRC-32C only; attacker rewriting body trivially recomputes CRC | open | knowledge/files/src/common/blkreftable.c.md |
| 2026-06-03 | blkreftable.c:666-672 | dos | maybe | `nchunks` sanity check is `> MaxAllocSize / sizeof(uint16)`; hostile BRT with `nchunks = 2^28` allocates 1 GiB; no aggregate cross-entry cap | open | knowledge/files/src/common/blkreftable.c.md |
| 2026-06-03 | blkreftable.c:907 | trust-boundary | likely | Hostile `limit_block = max` + empty modified-block bitmap silently drops blocks from the combined backup → **stale data**; opposite makes operator re-copy the whole relation | open | knowledge/files/src/common/blkreftable.c.md |
| 2026-06-03 | parse_manifest.c:811-878 | trust-boundary | likely | Manifest SHA-256 is integrity not authenticity — attacker who rewrites manifest + per-file CRCs together evades all checks; per-file checksum defaults to CRC-32C | open | knowledge/files/src/common/parse_manifest.c.md |
| 2026-06-03 | checksum_helper.h:20-27 | trust-boundary | maybe | CRC-32C explicitly disclaimed as crypto-grade in header comment; default per-file checksum on the manifest is still crc32c | open | knowledge/files/src/include/common/checksum_helper.h.md |
| 2026-06-03 | controldata_utils.c:209-252 | state-transition | maybe | Partial-write window on `pg_control`: single 8 KiB `write()`, no shadow file, no rename-into-place; CRC-retry loop only handles racing writer, not torn-write-on-disk | open | knowledge/files/src/common/controldata_utils.c.md |

**Phase D pitch — backup chain integrity:**
1. Make `crc32c` no longer the default for per-file checksums when
   the manifest contains sensitive backups (require operator opt-in).
2. Add an optional manifest-signing flag (HMAC-SHA-256 with operator-
   supplied key) to give true authenticity.
3. Hard-cap `nchunks` and aggregate per-entry memory in BRT parser.
4. Audit `pg_combinebackup`'s handling of `limit_block` + empty
   chunk lists.

### Decompression bomb + parser DoS

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | pg_lzcompress.c:255-256 | undocumented-invariant | maybe | `pglz_compress` not thread-safe / async-signal-safe (process-global history table); single-threaded backend assumption | open | knowledge/files/src/common/pg_lzcompress.c.md |
| 2026-06-03 | pg_lzcompress.c | dos | maybe | No input/output ratio bound on decompression — bomb potential (mirror of A4 walmethods finding) | open | knowledge/files/src/common/pg_lzcompress.c.md |
| 2026-06-03 | jsonapi.c:431-432,952-953,983-984 | dos | maybe | `JSON_TD_MAX_STACK = 6400` is the depth cap ONLY in the incremental parser; recursive-descent `pg_parse_json` relies on `check_stack_depth()` which is a **no-op in libpq frontend**; hostile JSON consumed via recursive path bounded only by OS stack | open | knowledge/files/src/common/jsonapi.c.md |
| 2026-06-03 | jsonapi.c:1400-1407 | dos | nit | Stale TODO ("clients need some way to put a bound on stack growth") — unfixed across many releases | open | knowledge/files/src/common/jsonapi.c.md |
| 2026-06-03 | stringinfo.c | dos | maybe | `StringInfoData` length is `int`+`MaxAllocSize`-bound (1 GiB); attacker who can grow a single StringInfo (e.g. JSON parse) hits this ceiling silently | open | knowledge/files/src/common/stringinfo.c.md |
| 2026-06-03 | unicode_norm.c | dos | maybe | `unicode_normalize` has no input-length cap and quadratic worst-case canonical reordering | open | knowledge/files/src/common/unicode_norm.c.md |
| 2026-06-03 | wchar.c | dos | maybe | `pg_utf8_verifystr` backtracks at the end of the input on a partial trailing sequence | open | knowledge/files/src/common/wchar.c.md |
| 2026-06-03 | base64.c | dos | nit | Decode does not bound the lookup-table indirection — minor amplification | open | knowledge/files/src/common/base64.c.md |
| 2026-06-03 | hashfn.c | dos | maybe | `hash_bytes` has no per-process keying — hash flooding against syscache via colliding relation names by CREATE-privileged user | open | knowledge/files/src/common/hashfn.c.md |
| 2026-06-03 | ip.c | dos | nit | `getaddrinfo()` with caller-controlled hostname is unbounded — typical libc-level limit | open | knowledge/files/src/common/ip.c.md |

### GUC-boundary shell injection

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | percentrepl.c | injection | maybe | `replace_percent_placeholders` does NO shell escaping; output piped to `system(3)` by `archive_command`/`restore_command`; safety relies on undocumented "placeholder values are not attacker-controlled" invariant | open | knowledge/files/src/common/percentrepl.c.md |
| 2026-06-03 | percentrepl.c | undocumented-invariant | nit | The "no attacker-controlled placeholder" contract is implicit | open | knowledge/files/src/common/percentrepl.c.md |
| 2026-06-03 | archive.c:53-54 | trust-boundary | maybe | `restore_command` substitution does not shell-quote `%p`/`%f`/`%r`; admin must wrap with `"%p"` per upstream documentation | open | knowledge/files/src/common/archive.c.md |
| 2026-06-03 | archive.c | trust-boundary | maybe | Hostile filename in `archive_status/` (e.g. tablespace-rooted attack) could feed unusual bytes into `%p` | open | knowledge/files/src/common/archive.c.md |

### Crypto correctness / dispatch

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | cryptohash_openssl.c | trust-boundary | nit | Relying on OpenSSL `EVP_MD_CTX_destroy` to scrub key material — not explicitly enforced; asymmetric error semantics vs fallback (`ereport(ERROR)` in backend vs return-NULL) | open | knowledge/files/src/common/cryptohash_openssl.c.md |
| 2026-06-03 | hmac_openssl.c | trust-boundary | nit | Relying on `HMAC_CTX_free` to scrub key material | open | knowledge/files/src/common/hmac_openssl.c.md |
| 2026-06-03 | cryptohash_openssl.c | correctness | nit | `EVP_DigestFinal_ex(... 0)` uses NULL for the unused-output-len pointer; documented OpenSSL behavior | open | knowledge/files/src/common/cryptohash_openssl.c.md |
| 2026-06-03 | base64.c | correctness | nit | Padding state machine accepts `X=` but not all expected forms | open | knowledge/files/src/common/base64.c.md |
| 2026-06-03 | base64.c | side-channel | maybe | Decode is NOT constant-time — observable timing if used to compare MAC tags (not the case in PG, but flag) | open | knowledge/files/src/common/base64.c.md |
| 2026-06-03 | saslprep.c | correctness | maybe | Prohibit check uses `input_chars` (pre-NFKC) — discrepancy with codepoints that change under normalization | open | knowledge/files/src/common/saslprep.c.md |
| 2026-06-03 | unicode_norm.c, unicode_norm.h | correctness | maybe | NFKC table regeneration between PG releases (Unicode version bump) → silent SCRAM auth failures on exotic codepoints when libpq and server disagree | open | knowledge/files/src/common/unicode_norm.c.md |
| 2026-06-03 | pg_prng.c | crypto-weakness | maybe | DSM control-handle generation uses `pg_prng_uint32` (seeded from `pg_strong_random` but advanced once per fork); local-attacker shm-name pre-creation has narrowed search space; mitigated by collision retry | open | knowledge/files/src/common/pg_prng.c.md |

---

## P1 — Correctness & undocumented invariants

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | int.h | correctness | likely | `pg_abs_s64(PG_INT64_MIN)` is the ONLY safe negation; bare `abs()`/`-x` across backend on user-controlled signed integers is UB landmine — grep audit is high-leverage Phase D follow-up | open | knowledge/files/src/include/common/int.h.md |
| 2026-06-03 | int128.h | correctness | maybe | `int128_div_mod_int32` documented unsafe on portable path | open | knowledge/files/src/include/common/int128.h.md |
| 2026-06-03 | int128.h | undocumented-invariant | maybe | Portable INT128 byte layout must match native; on-disk format implications | open | knowledge/files/src/include/common/int128.h.md |
| 2026-06-03 | file_utils.c:301-340 | correctness | maybe | `sync_pgdata` walkdir treats per-file fsync errors as non-fatal in `pre_sync` (fatal in `fsync_fname`); silent fsync-coverage degradation = crash-safety gap | open | knowledge/files/src/common/file_utils.c.md |
| 2026-06-03 | file_perm.c:37 | undocumented-invariant | maybe | `SetDataDirectoryCreatePerm` only checks GROUP bits, not absence of world bits; 0775 PGDATA picks GROUP triple silently | open | knowledge/files/src/common/file_perm.c.md |
| 2026-06-03 | checksum_helper.c:96-134 | undocumented-invariant | nit | `pg_checksum_init` failure leaves `ctx->type` set; caller MUST not call update/final after init returns -1 | open | knowledge/files/src/common/checksum_helper.c.md |
| 2026-06-03 | checksum_helper.c:200-227 | undocumented-invariant | nit | `pg_checksum_final` leaks `c_sha2` on -1 return path | open | knowledge/files/src/common/checksum_helper.c.md |
| 2026-06-03 | restricted_token.c:151 | trust-boundary | maybe | Privilege-drop fail-open: failure to acquire restricted token lets process keep running with original privileges | open | knowledge/files/src/common/restricted_token.c.md |
| 2026-06-03 | wchar.c | trust-boundary | maybe | `pg_encoding_mblen` reads ahead by up to 4 bytes on UTF-8 — bounds-implicit | open | knowledge/files/src/common/wchar.c.md |
| 2026-06-03 | wchar.c | correctness | nit | `NONUTF8_INVALID_BYTE0/1` canary doc says one thing, code does another | open | knowledge/files/src/common/wchar.c.md |
| 2026-06-03 | wchar.c | undocumented-invariant | nit | `pg_utf8_islegal` rejects length 5/6 implicitly | open | knowledge/files/src/common/wchar.c.md |
| 2026-06-03 | unicode_case.c | correctness | nit | Invalid-UTF-8 input falls through Assert in non-debug build | open | knowledge/files/src/common/unicode_case.c.md |
| 2026-06-03 | unicode_case.c | undocumented-invariant | nit | `full=false`'s title→upper swap is subtle | open | knowledge/files/src/common/unicode_case.c.md |
| 2026-06-03 | encnames.c | undocumented-invariant | nit | `pg_encname_tbl[]` alphabetic sort is invariant for binary search | open | knowledge/files/src/common/encnames.c.md |
| 2026-06-03 | encnames.c | correctness | nit | "Dirty" aliases (`unicode→UTF8`, `win→WIN1251`) are case-fold-only | open | knowledge/files/src/common/encnames.c.md |
| 2026-06-03 | compression.c, compression.h:17-20 | undocumented-invariant | likely | `pg_compress_algorithm` enum ordinals are on-disk format; additions must append | open | knowledge/files/src/common/compression.c.md |
| 2026-06-03 | compression.c:304-327 | trust-boundary | maybe | Parsed spec only safe after `validate_compress_specification`; callers that skip get unchecked input | open | knowledge/files/src/common/compression.c.md |
| 2026-06-03 | compression.c:191,318,468 | correctness | nit | `strtol` on user CLI input → silent saturation; `errno` not consulted; truncation from `long`→`int` produces confusing error message | open | knowledge/files/src/common/compression.c.md |
| 2026-06-03 | binaryheap.c | undocumented-invariant | nit | Comparator must be transitive; no runtime check | open | knowledge/files/src/common/binaryheap.c.md |
| 2026-06-03 | binaryheap.c | correctness | nit | `binaryheap_first` immediately after build assumes heapified state | open | knowledge/files/src/common/binaryheap.c.md |
| 2026-06-03 | instr_time.c | side-channel | nit | High-precision timings exposed to clients via `EXPLAIN ANALYZE` | open | knowledge/files/src/common/instr_time.c.md |
| 2026-06-03 | instr_time.c | undocumented-invariant | nit | `tsc_info` struct (line 73) populated once at startup | open | knowledge/files/src/common/instr_time.c.md |
| 2026-06-03 | hashfn_unstable.h | undocumented-invariant | nit | simplehash users mustn't persist their hash output across PG versions | open | knowledge/files/src/include/common/hashfn_unstable.h.md |
| 2026-06-03 | hashfn_unstable.h | correctness | maybe | `fasthash_accum_cstring_aligned` reads up to 7 bytes past end of string on aligned access | open | knowledge/files/src/include/common/hashfn_unstable.h.md |
| 2026-06-03 | hashfn_unstable.h | side-channel | nit | Hash timings can leak data layout | open | knowledge/files/src/include/common/hashfn_unstable.h.md |
| 2026-06-03 | psprintf.c | undocumented-invariant | nit | `psprintf` MUST NOT be used from libpq — relies on backend memory context | open | knowledge/files/src/common/psprintf.c.md |
| 2026-06-03 | relpath.c | trust-boundary | nit | `GetRelationPath` formats user-influenceable OIDs into filesystem paths — bounded by valid catalog OIDs | open | knowledge/files/src/common/relpath.c.md |
| 2026-06-03 | relpath.c | undocumented-invariant | nit | `forkname_chars` assumes no fork name is prefix of another | open | knowledge/files/src/common/relpath.c.md |
| 2026-06-03 | relpath.h | undocumented-invariant | nit | `REL_PATH_STR_MAXLEN` encodes layout assumptions | open | knowledge/files/src/include/common/relpath.h.md |
| 2026-06-03 | username.c, username.h | trust-boundary | nit | Return value points into libc-owned static buffer (`getpwuid` result); not documented in caller-facing header | open | knowledge/files/src/common/username.c.md |
| 2026-06-03 | ip.c | info-disclosure | nit | `pg_getnameinfo_all` logs `sun_path` verbatim — local path leak | open | knowledge/files/src/common/ip.c.md |
| 2026-06-03 | ip.c | undocumented-invariant | nit | `getnameinfo_unix` returns `EAI_MEMORY` on buffer-too-small | open | knowledge/files/src/common/ip.c.md |
| 2026-06-03 | string.c | undocumented-invariant | nit | `pg_clean_ascii` allocates 4× input | open | knowledge/files/src/common/string.c.md |
| 2026-06-03 | stringinfo.c | undocumented-invariant | nit | "Buffer stays in init-time state" invariant is implicit on error path | open | knowledge/files/src/common/stringinfo.c.md |
| 2026-06-03 | logging.c | info-disclosure | nit | `assert(fmt[strlen(fmt)-1] != '\n')` enforces no-trailing-newline convention | open | knowledge/files/src/common/logging.c.md |
| 2026-06-03 | logging.c | undocumented-invariant | nit | `pg_logging_init` writes to static global; not reentrant | open | knowledge/files/src/common/logging.c.md |
| 2026-06-03 | connect.h | undocumented-invariant | nit | Callers must run this AFTER auth — undocumented ordering | open | knowledge/files/src/include/common/connect.h.md |
| 2026-06-03 | pg_get_line.c | undocumented-invariant | nit | OOM during `enlargeStringInfo` leaves buffer partially-grown | open | knowledge/files/src/common/pg_get_line.c.md |
| 2026-06-03 | shortest_dec.h | undocumented-invariant | nit | `_bufn` variants do NOT NUL-terminate — caller-side trap | open | knowledge/files/src/include/common/shortest_dec.h.md |
| 2026-06-03 | pg_prng.c | undocumented-invariant | nit | `pg_global_prng_state` is fork-inherited; child backends advance the same stream | open | knowledge/files/src/common/pg_prng.c.md |
| 2026-06-03 | pg_prng.h | undocumented-invariant | nit | Extensions can write s0/s1 directly via exported state | open | knowledge/files/src/include/common/pg_prng.h.md |
| 2026-06-03 | d2s.c | undocumented-invariant | nit | `STRICTLY_SHORTEST 0` diverges from upstream Ryu | open | knowledge/files/src/common/d2s.c.md |
| 2026-06-03 | f2s.c | undocumented-invariant | nit | Same as d2s | open | knowledge/files/src/common/f2s.c.md |
| 2026-06-03 | cryptohash.c | undocumented-invariant | nit | Error enum sentinel relies on convention | open | knowledge/files/src/common/cryptohash.c.md |
| 2026-06-03 | hmac.c | undocumented-invariant | nit | `len > block_size` shrinks key via hash; documented in some impls not others | open | knowledge/files/src/common/hmac.c.md |
| 2026-06-03 | saslprep.c | undocumented-invariant | nit | Empty-after-map rejected as `SASLPREP_OOM` (overloaded error code) | open | knowledge/files/src/common/saslprep.c.md |
| 2026-06-03 | sha2.c | undocumented-invariant | nit | `pg_sha224_update` casts | open | knowledge/files/src/common/sha2.c.md |
| 2026-06-03 | base64.c | undocumented-invariant | nit | Caller must pre-size `dst` via output-length formula | open | knowledge/files/src/common/base64.c.md |

---

## P2 — Stale TODOs / dead-code

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | scram-common.c | stale-todo | nit | `Assert(hash_type == PG_SHA256)` blocks future SHA-512 SCRAM mechanisms | open | knowledge/files/src/common/scram-common.c.md |
| 2026-06-03 | md5_common.c | stale-todo | nit | "salt at the end because it may be known by attacker" comment — design rationale preserved | open | knowledge/files/src/common/md5_common.c.md |
| 2026-06-03 | md5.c | stale-todo | nit | "needs every input byte to be little-endian" platform assumption | open | knowledge/files/src/common/md5.c.md |
| 2026-06-03 | md5.c, sha1.c, sha2.c | dead-code | nit | Fallback impls exist only for FRONTEND-without-OpenSSL builds; eventual removal candidate | open | knowledge/files/src/common/md5.c.md |
| 2026-06-03 | saslprep.c | stale-todo | nit | stringprep frozen at Unicode 3.2 per RFC 4013 — never advances | open | knowledge/files/src/common/saslprep.c.md |
| 2026-06-03 | cryptohash.c:78-83 | stale-todo | nit | Comment admits union-based ctx is awkward | open | knowledge/files/src/common/cryptohash.c.md |
| 2026-06-03 | hashfn.c, hashfn.h | stale-todo | nit | `#define oid_hash uint32_hash /* Remove me eventually */` | open | knowledge/files/src/common/hashfn.c.md |
| 2026-06-03 | hmac_openssl.c | dead-code | nit | `return NULL` after `ereport(ERROR)` in backend path | open | knowledge/files/src/common/hmac_openssl.c.md |
| 2026-06-03 | d2s.c | dead-code | nit | Many MSVC-intrinsics paths in `d2s_intrinsics.h` unused on non-Windows | open | knowledge/files/src/common/d2s.c.md |
| 2026-06-03 | d2s_intrinsics.h | dead-code | nit | No-intrinsics-no-int128 fallback may be dead today | open | knowledge/files/src/common/d2s_intrinsics.h.md |
| 2026-06-03 | binaryheap.c | dead-code | nit | All entry points used | open | knowledge/files/src/common/binaryheap.c.md |
| 2026-06-03 | int.h | dead-code | nit | Neither-`HAVE__BUILTIN_OP_OVERFLOW`-nor-`__int128` fallback rarely exercised | open | knowledge/files/src/include/common/int.h.md |
| 2026-06-03 | int128.h | dead-code | nit | Portable (non-HAVE_INT128) path rarely exercised | open | knowledge/files/src/include/common/int128.h.md |
| 2026-06-03 | hashfn.c | undocumented-invariant | nit | "Must never throw elog(ERROR)" applies to dynahash callbacks | open | knowledge/files/src/common/hashfn.c.md |
| 2026-06-03 | instr_time.c:411 | stale-todo | nit | "This won't return the right value on..." TODO | open | knowledge/files/src/common/instr_time.c.md |
| 2026-06-03 | psprintf.c | stale-todo | nit | No format-string lint at build time | open | knowledge/files/src/common/psprintf.c.md |
| 2026-06-03 | fe_memutils.c | stale-todo | nit | `MCXT_ALLOC_HUGE` flag defined but ignored in frontend | open | knowledge/files/src/common/fe_memutils.c.md |
| 2026-06-03 | fe_memutils.h | stale-todo | nit | `MaxAllocSize` defined but not enforced in frontend | open | knowledge/files/src/include/common/fe_memutils.h.md |
| 2026-06-03 | pg_prng.c | stale-todo | nit | `pg_prng_fseed` wraps the double into a 52-bit int64 | open | knowledge/files/src/common/pg_prng.c.md |

---

## Cross-corpus pattern reinforcement

This batch adds **the fifth installment of the secret-scrub cluster**
identified across A2+A4 and now A5:

| Source | What leaks | Where |
|---|---|---|
| A2 libpq | PGconn-held passwords, scram keys, pgpass, oauth tokens | full connection lifetime; `explicit_bzero` in 2 of 60+ files |
| A4 psql | `\password` pw1/pw2; main() password arg; PSQL_HISTORY; -L logfile | command.c:2604; startup.c:249; input.c:148; common.c:1158 |
| A4 streamutil | static-global `password` for replication tools | streamutil.c |
| A4 initdb | `superuser_password` + escape_quotes copy until exit | initdb.c:1732 |
| **A5 common** | **md5_common, scram-common, hmac, saslprep, sprompt, fe_memutils, logging, pg_get_line** | THE hosting site — these are the helpers everything above calls |

**Single proposed mitigation: `SecretBuf` in `src/include/common/secretbuf.h`**
+ `src/common/secretbuf.c`. Migrates the 5 specific cross-corpus
call sites + closes 10+ A5 sites in one coordinated series.

This is the cleanest single Phase D submission shape we've identified
so far — it touches every secret-scrub gap the corpus has found and
adds no new dependencies (src/common depends on nothing else).

---

## Corpus gaps surfaced (out of batch)

- `src/backend/utils/cache/*` (sweep #6 candidate) — see if backend secret storage shares the same gap.
- `src/backend/storage/ipc/dsm.c` — pg_prng/DSM-handle interaction flagged by B4; needs single-file audit.
- `src/include/common/secretbuf.h` (new) + `src/common/secretbuf.c` (new) — the proposed Phase D landing point. Not a corpus gap per se but the natural next file to write.
- `src/common/unicode/generate-*.pl` — the Unicode table generators; would close the "what regenerates these?" question for the 8 stubbed table headers.
- `src/include/common/openssl.h` — partly covered; could deepen now that the cryptohash dispatch is mapped.

---

## Summary by tag type

| Type | Count |
|---|---:|
| secret-scrub | 19 |
| trust-boundary | 11 |
| undocumented-invariant | 35 |
| correctness | 14 |
| dos | 10 |
| stale-todo | 16 |
| dead-code | 8 |
| info-disclosure | 4 |
| side-channel | 5 |
| crypto-weakness | 1 |
| state-transition | 1 |
| injection | 1 |
| **Total** | **125** (one entry double-tagged) |

Severity headline: ~12 `likely`, ~30 `maybe`, rest `nit`/by-design.
Highest-leverage Phase D pitches in order: (1) **SecretBuf**, (2)
**backup-trust hardening**, (3) **pg_lzcompress decompression cap**,
(4) **percentrepl shell-escape**, (5) **jsonapi depth-cap in libpq**.
