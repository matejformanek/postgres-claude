# Session — A16 src/include/{common,port} enrichment + port finishing (foreground)

**Date:** 2026-06-09 (continuing after A15 finishing pass)
**Phase:** A — corpus completeness + issue surfacing
**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Branch:** `ft_corpus_a16_include_common_port`

## Scope

The **`src/include/{common,port}` API-layer Phase D anchor pass.**
50 common headers were already covered by A5 (2026-06-03) + cloud
sweeps but had THIN Phase D notes. A16 enriched them with
header-anchored ISSUE tags + cross-corpus links. 22 port top-level
headers were genuinely uncovered — A16 added them as NEW docs.

| Sub-tree | Pre-A16 | New | Enriched | Post-A16 | Coverage |
|---|---:|---:|---:|---:|---:|
| `src/include/common` | 50 | 0 | 50 | 50 | 100% (was already 100% — A16 enriched) |
| `src/include/port` (top-level) | 0 | 22 | 0 | 22 | 100% top-level (25 subdir files deferred to cloud) |
| **Total** | **50** | **22** | **50** | **72** | — |

## Method

Standard A-sweep pattern. **4 parallel agents:**

- **A16-1** common crypto/hash/secret (14 headers enriched: acl→openssl→oauth-common→base64 family)
- **A16-2** common file/parse/string (19 headers enriched: archive, blkreftable, controldata, file_utils, pg_lzcompress, percentrepl, etc.)
- **A16-3** common types/unicode/json (17 headers enriched: jsonapi, int, int128, shortest_dec, unicode_*)
- **A16-4** port (22 NEW: atomics, simd, pg_pthread, pg_iovec, pg_lfind, pg_bitutils, pg_bswap, pg_crc32c, pg_cpu, pg_numa, pg_getopt_ctx + 11 platform-specific shims)

Wall time ~13 min. **Zero misdirection. 16th A-sweep in a row.**

## Output

**Per-file docs:**
- 22 NEW under `knowledge/files/src/include/port/*` (full top-level coverage)
- 50 ENRICHED under `knowledge/files/src/include/common/*` (net +1,049 lines, -99 lines = +950 lines of new Phase D content)

**Subsystem issue registers** (2 new files, ~130 entries):
- `knowledge/issues/include-common.md` — ~105 entries
- `knowledge/issues/include-port.md` — ~25 entries

**Progress ledgers updated:**

- `progress/files-examined.md` — +22 rows (port headers; common rows already present from A5)
- `progress/coverage.md` — 1,777→**1,799 docs (69.3%→70.2%)**; src/include 67.3%→**69.9%**
- `progress/coverage-gaps.md` — src/include section refreshed (common DONE, port top-level DONE); attack order extended to #16 (this) + #17
- `progress/STATE.md` — last-activity narrative

## Honest accounting

**A16 is an enrichment-heavy sweep, not a coverage-heavy sweep.** The 50 common headers were already documented by A5 (2026-06-03 commit `e51232a` "document 109 common files (A5 sweep)"). What was MISSING was the header-anchored Phase D notes that surface the A5/A11 findings AT THE API LAYER (not just in the .c companions). A16 added those.

22 NEW docs (port headers) is the actual coverage delta. Still a meaningful sweep — port headers are load-bearing for backend concurrency, atomics, SIMD, NUMA.

## Confidence rollup

Aggregate ~80% `[verified-by-code]`, ~15% `[from-comment]`, ~5%
`[inferred]`, **0% `[unverified]`**. Honest reporting per the brief.

## Headlines

### 🚨 jsonapi recursive-parser frontend SIGSEGV

`jsonapi.h:174` — `pg_parse_json` (recursive) depends on
`check_stack_depth()` which is a NO-OP in libpq/psql/pg_dump
frontend builds. Only `pg_parse_json_incremental` has explicit
`JSON_TD_MAX_STACK=6400` cap. Frontend callers of recursive entry
SIGSEGV on adversarial deeply-nested JSON. **A5 finding at API
layer.**

### `cryptohash.h` is the SecretBuf template

Both `_free` impls call `explicit_bzero(ctx, sizeof(*ctx))` —
`source/src/common/cryptohash.c:243` + analogous in
`cryptohash_openssl.c`. The header NEVER tells the caller this.
A5's proposed `secretbuf.h` + `secretbuf.c` would generalize this
pattern for 10+ caller-owned secret buffers.

### No constant-time compare helpers anywhere in tree

Every HMAC/digest/MD5/base64 consumer needing constant-time
comparison hand-rolls `timingsafe_bcmp`. pgcrypto (A11) does NOT.
A `pg_cryptohash_compare_constant_time` helper would standardize.

### SCRAM iteration cap absent

`scram-common.h:50` — `SCRAM_SHA_256_DEFAULT_ITERATIONS = 4096`
is the RFC floor. OWASP-2026 recommends ≥600,000. No
`SCRAM_SHA_256_MAX_ITERATIONS` constant — malicious server can
coerce client into very long PBKDF2.

### `pg_prng.h` exposes `s0/s1` raw with no security warning

`pg_prng.h:1-62` — extensions can write `s0`/`s1` directly via
exposed struct. Zero-seed makes xoroshiro produce zero forever.
The header has NO "NOT FOR SECURITY" warning. A5 finding (DSM
control-handle uses pg_prng_uint32 not pg_strong_random).

### OpenSSL 3.0 EVP_*_fetch shims not yet in tree

`openssl.h:17-41` — grep over the slice confirms zero hits. A11
pgcrypto modernization ("ERR_get_error never called" + "BN_FLG_
CONSTTIME missing") would land in this header or new `common/
evp.h`.

### `percentrepl.h` does NO shell escaping

`percentrepl.h:16` — `replace_percent_placeholders` flows to
`system()` / `OpenPipeStream()` with no escape contract.
**A5 + A8 + A14 cluster header anchor.**

### `controldata_utils.h` torn-write at API layer

`controldata_utils.h:18-19` — `update_controlfile` advertises
atomic update; the .c does single 8 KiB write with no shadow
file. A5 finding at API layer.

### `atomics.h` u64 fallback invisible at call sites

`atomics.h:460-462` — `pg_atomic_*_u64` silently becomes a
spinlock array on platforms lacking native 64-bit atomics.
**The load-bearing concurrency primitive for the whole backend
has no in-source way to detect the perf cliff.**

### CRC32C trust-boundary cluster echo (A11/A13/A14)

`pg_crc32c.h:38` — `pg_crc32c` is trivially collidable but the
type name and header give no "untrusted-input-unsafe" signal.
Cross-trust uses (WAL from untrusted archive, 2PC state files,
replication frames) need audit.

### `pg_numa_query_pages(pid>0, ...)` is a privacy probe

`pg_numa.h:18` — accepts non-zero pid at the C level; SQL layer
is the only gate. A14 pg_buffercache NUMA finding's dispatch-
layer echo.

### Windows durability narrative split

`win32_port.h:82-83` defines `fsync = _commit` (weak). Proper
`pg_NtFlushBuffersFileEx` is in `win32ntdll.h:24-32`. Neither
cross-references the other; durability semantics on Windows
non-obvious.

## NEW Phase D pitch candidates from A16

1. **`secretbuf.h` + `secretbuf.c`** — A5's proposal now has its
   header template (`cryptohash.h`'s `_free` pattern). Phase-D
   patch series: generalize for 10+ caller-owned secret buffers.
2. **`pg_cryptohash_compare_constant_time` helper** — closes
   timing-attack gaps across HMAC/digest consumers tree-wide.
3. **SCRAM iteration cap GUC** — `SCRAM_SHA_256_MAX_ITERATIONS`
   constant + check-hook to reject malicious-server long PBKDF2.
4. **`pg_openssl_error_drain` + `pg_openssl_bn_set_consttime`** —
   close A11 pgcrypto "discarded OpenSSL errors" + "non-constant-
   time RSA/Elgamal" findings centrally.
5. **`appendStringInfoQuotedIdentifier` + `appendStringInfoShellQuoted`**
   (carryover from A15) — close A7+A13+A14 cluster centrally.
6. **Per-process keying in `hashfn.h`** — hash-flood DoS defense
   for dynahash tables on attacker-controlled keys.

## Cross-corpus reinforcement

- **A5 common.md** (124 entries) gets header-layer companion
  `include-common.md` (~105 entries).
- **A11 pgcrypto.md** (~80 entries) modernization candidates now
  have concrete header sites (`openssl.h`, `cryptohash.h`, `hmac.h`).
- **A5 jsonapi finding** gets API-layer anchor (`jsonapi.h`).
- **A13/A14 GiST signature-collision cluster** gets generic-hash
  anchor (`hashfn.h`, `pg_crc32c.h`).
- **A14 storage-aio** gets iovec anchor (`pg_iovec.h`).
- **A14 pg_buffercache NUMA** gets dispatch anchor (`pg_numa.h`).
- **A4/A5 secret-scrub cluster** gets header anchors
  (`fe_memutils.h`, `string.h`, `cryptohash.h`).
- **A8 archive_command + A14 basebackup_to_shell** cluster gets
  header anchors (`percentrepl.h`, `archive.h`).

## What this sweep did NOT do

- Did NOT add new docs for the 25 `src/include/port` subdirectory
  headers (`atomics/*.h`, `win32/*.h`, `win32_msvc/*.h`) —
  arch-specific atomic implementations + Windows compat shims,
  better filled by cloud routine.
- Did NOT cover remaining ~33 `src/include/executor/nodeXxx.h`
  1-line decl headers (carryover from A15).
- Did NOT refresh source anchor (`4b0bf0788b0` is ~9 days stale).

## Position

**~70.2% coverage; gap ~765 files.** Cumulative since 2026-06-02:
16 A-sweeps shipped, +882 docs, +~2,415 issues. **16 sweeps in a
row with zero misdirection.**

Next foreground candidates: **refresh source anchor** (first-class
candidate — ~9 days stale) OR pivot toward Phase B (developer
personas mined from pgsql-hackers + commits) OR finish the 25
port subdir files + 33 executor nodeXxx.h via cloud.
