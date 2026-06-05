# Session — A11 contrib top-4 sweep (foreground)

**Date:** 2026-06-04 (late afternoon, continuing from A10 plperl/
plpython/pltcl sweep earlier the same day)
**Phase:** A — corpus completeness + issue surfacing
**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Branch:** `ft_corpus_a11_contrib_top`

## Scope

**THE four highest-Phase-D-value contrib/ modules** — the first
foreground sweep into `contrib/` after 10 sweeps in `src/`. 36
source files totalling **~35 650 LOC**:

| Module | Files | LOC | Docs | Trust class |
|---|---:|---:|---:|---|
| pg_stat_statements | 1 | 2 913 | 1 | query telemetry (privileged data exposure) |
| dblink | 1 | 3 272 | 1 | cross-cluster query bridge (older) |
| postgres_fdw | 6 | 16 916 | 6 | cross-cluster FDW (newer, stricter) |
| pgcrypto | 28 | ~12 549 | 25 | crypto primitives + OpenPGP |
| **Total** | **36** | **~35 650** | **33** | |

## Method

Standard A-sweep parallel-agent pattern. **4 general-purpose
subagents fired in parallel**, each with an explicit slice:

- **A11-1** — pg_stat_statements + dblink (both single-file)
- **A11-2** — postgres_fdw (6 files; FDW core + connection +
  deparser + options + shippable + header)
- **A11-3** — pgcrypto core (~14 files: crypto primitives, OpenSSL
  backend, mbuf, crypt-{blowfish,des,md5,sha,gensalt}, px/px-crypt/
  px-hmac)
- **A11-4** — pgcrypto PGP (~16 files: pgp/pgp-{pgsql,armor,cfb,
  compress,decrypt,encrypt,info,mpi,mpi-openssl,pubdec,pubenc,pubkey,
  s2k})

Each agent's brief included the standard A-sweep guardrails plus
**explicit Phase D context** per slice (loopback-bypass-RLS for the
FDW class, decompression bombs for the crypto class, query-text
exposure for telemetry class).

Wall time ~14 min from launch to last agent. **Zero misdirection**
— all 33 docs landed in correct relative paths. **11th A-sweep in a
row** with no path drift.

## Output

**Per-file docs** (33 docs, 36 source files):

`knowledge/files/contrib/pg_stat_statements/` (1 doc):
- `pg_stat_statements.c.md`

`knowledge/files/contrib/dblink/` (1 doc):
- `dblink.c.md`

`knowledge/files/contrib/postgres_fdw/` (6 docs):
- `postgres_fdw.c.md`, `connection.c.md`, `deparse.c.md`,
  `option.c.md`, `shippable.c.md`, `postgres_fdw.h.md`

`knowledge/files/contrib/pgcrypto/` (25 docs covering 28 files):
- `pgcrypto.md`, `px.md`, `px-crypt.md`, `px-hmac.md`, `openssl.md`,
  `mbuf.md`, `crypt-blowfish.md`, `crypt-des.md`, `crypt-md5.md`,
  `crypt-sha.md`, `crypt-gensalt.md` (core, 11 docs)
- `pgp.md`, `pgp-pgsql.md`, `pgp-armor.md`, `pgp-cfb.md`,
  `pgp-compress.md`, `pgp-decrypt.md`, `pgp-encrypt.md`,
  `pgp-info.md`, `pgp-mpi-openssl.md`, `pgp-mpi.md`,
  `pgp-pubdec.md`, `pgp-pubenc.md`, `pgp-pubkey.md`, `pgp-s2k.md`
  (PGP, 14 docs)

**Subsystem issue registers** (4 files, ~208 entries total):

- `knowledge/issues/pg_stat_statements.md` — 9 entries
- `knowledge/issues/dblink.md` — 12 entries
- `knowledge/issues/postgres_fdw.md` — 61 entries
- `knowledge/issues/pgcrypto.md` — 126 entries (70 core + 56 PGP,
  combined since same module). **Second-largest single register
  after A7 utils' 310.**

**Progress ledgers updated:**

- `progress/files-examined.md` — +36 rows
- `progress/coverage.md` — 1 433→1 466 docs (55.9%→**57.2%**);
  contrib row 0%→15.7%; gap 1 131→1 098
- `progress/coverage-gaps.md` — contrib row updated; suggested
  attack order's #10 marked DONE; numbering refreshed
- `progress/STATE.md` — last-activity narrative + work-queue refresh

## Confidence rollup

Across the 4 agents (aggregate ~22 000 source lines read in depth):

- A11-1: ~85% verified, ~10% from-comment, ~5% inferred, 0 unverified
- A11-2: ~80% verified, ~15% from-comment, ~5% inferred, 0 unverified
- A11-3: ~85% verified, ~10% from-comment, ~5% inferred, 0 unverified
- A11-4: dominant verified, ~13% from-comment, minimal inferred,
  0 unverified

Aggregate ~83% `[verified-by-code]`, ~12% `[from-comment]`, ~5%
`[inferred]`, **0% `[unverified]`** — discipline holds across all
11 sweeps.

## Headlines

The full headlines live at the top of each subsystem register; the
top 5 are repeated here.

### 1. 🚨 CRITICAL: pgcrypto decompression bomb

`pgp_sym_decrypt(small_compressed_blob, pw)` has **NO output-size
ceiling** (`pgp-compress.c:278-310`). A 10 KB attacker ciphertext
can decompress to multi-GB plaintext, OOMing the backend. Same
class as A5's `pg_lzcompress` finding — but **reachable via a
public SQL API with attacker-controlled bytea**. HIGHEST severity
issue in the entire A11 sweep.

### 2. pgcrypto EFAIL surface still reachable

Legacy `SYMENCRYPTED_DATA` (tag 9) ciphertexts accepted without MDC
at `pgp-decrypt.c:1141-1152`. Only mitigation is delayed-error
reporting (Mister-Zuccherato CFB attack). `disable-mdc=1` SQL
option produces no-MDC ciphertext **with NO WARNING**. MDC uses
SHA-1. Combined with **uncapped attacker-controlled S2K iteration
count** (`pgp-s2k.c:270` — ~65M iter ceiling, no SQL-level cap),
cumulative CPU DoS is straightforward.

### 3. pgcrypto non-constant-time RSA/Elgamal secret-exponent ops

`pgp-mpi-openssl.c:266,183` uses generic `BN_mod_exp` for
`pgp_rsa_decrypt` and `pgp_elgamal_decrypt`, **without setting
`BN_FLG_CONSTTIME`**. Classic Brumley-Boneh 2003 timing-attack
surface. **One-line fix.** Paired with PKCS#1 v1.5 padding short-
circuit (`pgp-pubdec.c:42-67`) which gives a Bleichenbacher-style
oracle distinguishing "bad pad" from "good pad, wrong cksum" by
timing.

### 4. postgres_fdw `password_required` two-layered defense is the GOLD STANDARD

`option.c:194` (CREATE-time superuser check) + `connection.c:759`
(`check_conn_params` pre-connect) + `connection.c:446`
(`pgfdw_security_check` post-connect cross-checking
`PQconnectionUsedPassword`). **The canonical loopback-bypass-RLS
attack requires the superuser to have explicitly set
`password_required=false` on a USER MAPPING.** SCRAM passthrough
adds a third allowed path (`require_auth=scram-sha-256` enforced).
**This is the discipline that dblink lacks.**

### 5. pg_stat_statements password-cleartext in stat file

`track_utility = on` (DEFAULT TRUE) captures `CREATE/ALTER USER ...
PASSWORD '...'` cleartext into `pg_stat_tmp/pgss_query_texts.stat`
(`pg_stat_statements.c:1202`) exposed via the `pg_stat_statements`
view to `pg_read_all_stats`. **Exact A4 psql-history cycle
repeated at cluster scope.** Combined with A7's `pg_read_server_files`
filesystem bypass, the protected-view's role-ACL filter does NOT
extend to the underlying file. **Confirmed at a second concrete
site.**

## New corpus-wide clusters from A11

1. **pgcrypto modernization patch series** — single coherent
   OpenSSL-3.0-era refresh. Components:
   - `EVP_CIPHER_fetch` migration to OpenSSL 3.0 idiom
   - AEAD modes (GCM/CCM/ChaCha20-Poly1305)
   - `explicit_bzero` adoption (closes ~12 sites currently using
     LTO-elidable `px_memset`)
   - `BN_FLG_CONSTTIME` on RSA/Elgamal secret-exponent ops
   - S2K iter cap GUC
   - Decompression-bomb ceiling
   - AEAD-friendly HMAC compare primitive (constant-time)

2. **Cross-cluster trust-boundary discipline ranking** —
   postgres_fdw (two-layered `password_required` + SCRAM
   passthrough, gold standard) > dblink (credentials-only check,
   no host enforcement). Propose `knowledge/idioms/
   cross-cluster-trust.md`.

## Cross-corpus reinforcement

- **A5 `pg_lzcompress` decompression-bomb gap** finds its full
  expression in A11's PGP decompression bomb — the SQL-triggerable
  attack version. Single patch series closes both.
- **A7 `genfile.c` bypass** is now confirmed at a **2nd concrete
  site** (pg_stat_statements stat file). The pattern is
  "protected-view ACL doesn't extend to underlying file."
- **A2 + A5 `explicit_bzero` secret-scrub cluster**: pgcrypto's
  wrapped legacy algorithms (bcrypt, sha-crypt, md5-crypt) DO
  scrub their stack — **they're MORE disciplined than the
  SQL-boundary surrounding them**. The discipline exists in-tree;
  the SQL boundary just doesn't adopt it.
- **NAME-vs-OID Phase D pattern** now spans **7 sweeps**
  (A3+A6+A7+A8+A9+A10+A11) with postgres_fdw shippable +
  postgres_fdw aggregate pushdown + dblink connection-cache as new
  sites.

## Surprises / drift

- **postgres_fdw's `password_required` enforcement is stronger
  than I expected.** A11-2 traced the three-layer defense and
  confirmed CVE-2023-5869-era hardening is intact. The
  loopback-bypass-RLS pattern requires an explicit
  `password_required=false` decision. Worth highlighting this as
  the gold-standard pattern in a future idiom doc.
- **pgcrypto's wrapped legacy algorithms are more disciplined than
  the SQL boundary** — Solar Designer's crypt-blowfish.c, Drepper's
  crypt-sha.c, P-H Kamp's crypt-md5.c all scrub their stack state.
  The SQL boundary just doesn't.
- **A11-3 surfaced that `pgcrypto.builtin_crypto_enabled`** GUC has
  a misleading name — it only gates `crypt`/`gen_salt`, not
  `digest`/`hmac`/`encrypt`. Worth a docs hf.
- **A11-4 found the EFAIL surface is still reachable in 2026**
  despite the Mister-Zuccherato delayed-error mitigation — the
  `disable-mdc=1` SQL option has no warning. Worth at least a
  WARNING.

## What this sweep did NOT do

- No commits to `dev/` — A11 is corpus work only.
- No new idiom docs written — the new clusters (pgcrypto
  modernization + cross-cluster trust ranking) are seeded as
  proposals only.
- No update to `knowledge/glossary.md` — `PgFdwRelationInfo`,
  `OSSLCipher`, `PGP_PubKey`, `S2K`, MDC, EFAIL, Brumley-Boneh are
  glossary candidates but deferred.
- **Did NOT sweep contrib/ second-tier modules** — that's A12.
  btree_gin/btree_gist/amcheck/file_fdw/pageinspect/pgstattuple +
  the datatypes (hstore/ltree/intarray) are next.

## Next

`merge it and continue` will trigger **A12 selection**. Natural
next targets ordered by Phase D value:

- **contrib/amcheck** — verification toolkit, security-relevant for
  catalog-integrity checks (~5 files)
- **contrib/file_fdw** — file-system FDW, path-traversal class (~2 files)
- **contrib/pageinspect + contrib/pgstattuple** — low-level
  page/tuple introspection, security-sensitive but
  superuser-restricted (~12 files)
- **contrib/btree_gin + contrib/btree_gist** — index AMs (~20 files)
- **contrib/hstore + contrib/ltree + contrib/intarray + contrib/citext** —
  classic datatypes (~30 files)
- **contrib/auth_delay + contrib/sepgsql + contrib/sslinfo** —
  security-themed auxiliary modules (~10 files)

A12 candidate: bundle amcheck + file_fdw + pageinspect + pgstattuple
+ auth_delay/sepgsql/sslinfo as a "security-themed" sweep (~30 files).

**Cumulative since 2026-06-02:** 11 A-sweeps shipped, +549 docs /
+1 510 issues. **57.2% coverage; 43% remaining.**
