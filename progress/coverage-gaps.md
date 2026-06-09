# Coverage gaps — Phase A work queue

The per-directory undocumented-file map. This is the **work queue** the
`pg-file-backfiller` cloud routine + foreground interactive sweeps pull
from until Phase A closes (100% coverage of `src/` + `contrib/`).

**Refreshed:** 2026-06-04 (post A11 src/fe_utils sweep), source pin `4b0bf0788b0`.
**Top-line:** ~1 451 / 2 564 docs (≈56.6% coverage). **Gap: ~1 113 files.**
(A9 plpgsql +8, A10 pl-other +18, A11 src/fe_utils +18 since the 54.9%
snapshot below; the per-subdir tables below predate A9–A11 except where noted.)

Numbers below count `.c` + `.h` files. The doc count exceeds source count
in some dirs because docs include companion files (Makefiles, .y, .l, .dat,
sub-dir overviews); flagged with `>100%`.

---

## src/backend — 627 / 906 docs (69.2%)

### Done or near-done (skip in foreground sweeps; pg-file-backfiller fills the last gaps)

| Subdir | Source | Docs | Coverage | Notes |
|---|---:|---:|---:|---|
| backup | 14 | 14 | 100.0% | done |
| catalog | 34 | 35 | 102.9% | done (>100%) |
| executor | 65 | 64 | 98.5% | 1 file left |
| nodes | 16 | 15 | 93.8% | 1 file left |
| optimizer | 52 | 52 | 100.0% | done |
| parser | 22 | 25 | 113.6% | done (>100%) |
| postmaster | 16 | 15 | 93.8% | 1 file left |
| regex | 13 | 14 | 107.7% | done (>100%) |
| replication | 27 | 29 | 107.4% | done (>100%) |
| rewrite | 8 | 8 | 100.0% | done |
| tcop | 7 | 7 | 100.0% | done |
| tsearch | 15 | 15 | 100.0% | done |
| access | 157 | 139 | 88.5% | 18 left — last gaps |
| commands | 56 | 46 | 82.1% | 10 left |
| storage | 59 | 47 | 79.7% | 12 left |

### High-priority gaps (foreground sweep candidates — large + load-bearing)

| Subdir | Source | Docs | Coverage | Why prioritize |
|---|---:|---:|---:|---|
| **utils** | 233 | 202 | 86.7% | **A7 closed cache + adt** (104 docs, 310 issues; `knowledge/issues/utils.md`). Remaining: error/, fmgr/, hash/, init/, mb/, misc/, mmgr/, resowner/, sort/, time/, activity/ subdirs |
| ~~libpq~~ | 17 | 17 | 100.0% | **DONE 2026-06-03 (A2 libpq-stack sweep, PR #41)** — all 17 `.c` covered (`knowledge/issues/libpq.md`). The "0/17" that stood here through 2026-06-07 was **stale** (contradicted the A2 STATE entry); corrected 2026-06-08 after the queue refill mistakenly re-targeted it. |
| ~~storage/aio~~ | 10 | 10 | 100.0% | **DONE 2026-06-08 (cloud/pg-file-backfiller)** — PG18 AIO engine; 10 `.c` + 4 `src/include/storage/aio*.h` headers; 11 issues in `knowledge/issues/storage-aio.md`; top `knowledge/subsystems/storage-aio.md` candidate |
| statistics | 8 | 4 | 50.0% | Half-done; finish the rest |

### Low-priority gaps (small dirs or low strategic value)

| Subdir | Source | Docs | Coverage | Notes |
|---|---:|---:|---:|---|
| snowball | 56 | 0 | 0.0% | Mostly generated stemmer code; check if worth documenting at all |
| port | 10 | 0 | 0.0% | Platform shims; mechanical |
| lib | 9 | 0 | 0.0% | Generic data-structure utility code |
| jit | 5 | 0 | 0.0% | LLVM bridge; small but specialized |
| partitioning | 3 | 0 | 0.0% | Tiny; quick win |
| archive | 1 | 0 | 0.0% | Single file |
| bootstrap | 1 | 0 | 0.0% | Single file |
| foreign | 1 | 0 | 0.0% | Single file |
| main | 1 | 0 | 0.0% | postmaster entry; tiny |

---

## src/include — 568 / 844 docs (67.3%, +207 from A15)

Headers are the API surface and the principal source of invariant
documentation (struct field comments, INV-* anchors). Coverage here
matters as much as `.c` files.

### Done or near-done

| Subdir | Source | Docs | Coverage |
|---|---:|---:|---:|
| optimizer | 28 | 28 | 100.0% |
| ~~lib~~ | 15 | 15 | 100.0% (DONE 2026-06-09, A15) |
| postmaster | 15 | 14 | 93.3% |
| storage | 69 | 61 | 88.4% (post-A15) |
| rewrite | 9 | 7 | 77.8% |
| commands | 43 | 33 | 76.7% |
| nodes | 24 | 18 | 75.0% |
| utils | 97 | 98 | 100%+ (post-A15) |
| parser | 23 | 16 | 69.6% |
| access | 94 | 63 | 67.0% |
| tcop | 9 | 6 | 66.7% |

### Mid gaps

| Subdir | Source | Docs | Coverage |
|---|---:|---:|---:|
| executor | 61 | 28 | 45.9% (post-A15; ~33 thin nodeXxx.h headers deferred to cloud) |
| tsearch | 7 | 2 | 28.6% |
| statistics | 4 | 1 | 25.0% |
| regex | 5 | 1 | 20.0% |

### Done or near-done (post A1, A2)

| Subdir | Source | Docs | Coverage | Notes |
|---|---:|---:|---:|---|
| **catalog** | 85 | 87 | 102.4% | A1 sweep landed 72 docs 2026-06-02 evening. |
| **libpq** (src/include) | 20 | 20 | 100.0% | A2 sweep landed all 20 backend headers 2026-06-03. |

### A15 landings (2026-06-09)

- **utils** 28→98 docs (~73 new) via 3 parallel slices: A15-1 sec/locale/GUC (18); A15-2 types+memory+datum (~30); A15-3 backend-state (~25). 4 new registers: `knowledge/issues/include-utils.md` (~163 entries).
- **storage** 39→61 docs (~22 new). Register: `knowledge/issues/include-storage.md` (~14 entries).
- **lib** 0→15 docs (FULL DIR). Register: `knowledge/issues/include-lib.md` (~11 entries).
- **executor** 20→28 docs (~8 SPI/parallel/async support); deferred ~33 `nodeXxx.h` plan-node 1-line decl headers to cloud. Register: `knowledge/issues/include-executor.md` (~11 entries).

### Big absolute gaps (high-priority foreground sweep candidates)

| Subdir | Source | Docs | Coverage | Why |
|---|---:|---:|---:|---|
| ~~**common**~~ | 50 | 50 | 100.0% | **DONE 2026-06-03 (A5) + 2026-06-09 (A16-1/2/3 enrichment)** — 105 entries in `knowledge/issues/include-common.md` (Phase D anchor pass surfaced 130 new ISSUE tags). |
| **port** | 47 | 22 | 47% | A16 top-level done (22/22). 25 subdir files (atomics/, win32/, win32_msvc/) deferred to cloud routine. |
| ~~**replication**~~ | 22 | 23 | 104.5% | **DONE 2026-06-04 (A8 sweep)** — 22 docs + 1 pre-existing headers.md; 98 issues in `knowledge/issues/include-replication.md`; output-plugin dlopen primitive identified |
| ~~**lib**~~ | 15 | 15 | 100.0% | **DONE 2026-06-09 (A15 sweep)** — all 15 docs; 11 issues in `knowledge/issues/include-lib.md`. Headline: stringinfo is the central injection sink for A7/A13/A14 cluster. |
| ~~**fe_utils**~~ | 16 | 16 | 100.0% | **DONE 2026-06-05 (headers sweep, cloud/pg-file-backfiller)** — all 16 `src/include/fe_utils/*.h` docs; +3 header-level issues in `knowledge/issues/fe_utils.md` |

### Low-priority

| Subdir | Source | Docs | Coverage |
|---|---:|---:|---:|
| snowball | 56 | 0 | 0.0% | Generated stemmer code |
| backup | 6 | 1 | 16.7% | Small |
| jit | 5 | 0 | 0.0% | LLVM bridge |
| partitioning | 4 | 0 | 0.0% | Small |
| pch | 3 | 0 | 0.0% | Precompiled-header glue |
| archive | 2 | 0 | 0.0% | API surface for archive modules |
| foreign | 2 | 0 | 0.0% | FDW API |
| mb | 2 | 0 | 0.0% | Multibyte encoding |
| portability | 2 | 0 | 0.0% | Portability shims |
| bootstrap | 1 | 0 | 0.0% | BKI bootstrap |
| datatype | 1 | 0 | 0.0% | Datatype headers |

---

## src/common — 59 / 62 docs (95.2%)

Cross-backend + frontend shared helpers — cryptography, encoding,
scram-auth, file utilities. **DONE 2026-06-03 evening (A5 sweep)**:
59 .c + .h files documented; 124 issues into `knowledge/issues/common.md`.
Headline: **SecretBuf hosting site identified** at the proposed
`src/include/common/secretbuf.h` — closes A2-libpq + A4-psql/streamutil/initdb
+ A5-common secret-scrub findings in one coordinated Phase D series.
Remaining 3 source-counted entries are subdirs (unicode/, etc.) not in scope.

## src/port — 0 / 64 docs (0.0%)

Platform shims: pg_pthread, pg_iovec, copyfile, dirmod, getaddrinfo,
inet_aton, pgcheckdir, pgmkdirp, pgsleep, pg_localtime, etc. Mostly
mechanical; lower strategic priority. Cloud routine can chew through.

## src/interfaces — 0 / 166 docs (0.0%)

libpq client (~120 files) + ecpg (~46 files). **High priority for the
data-leak project**: SSL handshake, GSSAPI, SCRAM, MD5 fallback, error
formatting (info leaks). libpq is the most-attacked piece of the
codebase in the wild.

## src/timezone — 7 / 7 docs (100.0%) — DONE (2026-06-07, cloud/pg-file-backfiller)

Imported IANA tzcode + PG glue. **DONE 2026-06-07** (cloud/pg-file-backfiller):
`pgtz.c`/`pgtz.h`/`tzfile.h` landed 2026-06-06; `private.h`/`localtime.c`/
`strftime.c`/`zic.c` this run → `knowledge/files/src/timezone/*.md`. 4 issues
(all nit) into new `knowledge/issues/timezone.md`. **Headlines:** `localtime.c`
is the runtime TZif loader+converter — `tzloadbody` hard-validates every field
against `TZ_MAX_*` (load-side is the real TZif security boundary, since a
hand-crafted file bypasses `zic`); `pg_tz_acceptable` rejects leap-second
zones; `pg_localtime`/`pg_gmtime` share one static result buffer (non-reentrant);
`malloc`-not-`palloc` because the file builds frontend+backend. `zic.c` is a
build-time-only frontend compiler with its own `namecheck` path-traversal gate.

## src/test — 0 / 74 docs (0.0%)

Test infrastructure (regress/, isolation/, ssl/, kerberos/, ldap/,
recovery/, modules/). **High priority for review skills + Phase B
personas** — test conventions are visible here.

## src/bin — 115 / 160 docs (71.9%)

User-facing utilities. **Done:** pg_dump (36, A3), psql (29, A4),
pg_basebackup (12, A4), initdb (2, A4), pg_upgrade (22, A6),
pg_rewind (13, A6), pg_amcheck (1, A6). **Remaining:** pg_ctl,
pg_resetwal, pg_test_fsync, pg_test_timing, pg_waldump,
pg_combinebackup, pg_verifybackup, pg_walsummary, pg_archivecleanup,
pg_controldata, pg_checksums, scripts/. Mostly small mechanical tools
suitable for cloud-routine backfill.

## src/fe_utils — 18 / 18 docs (100.0%) — DONE (A11, 2026-06-04)

Frontend-shared utilities (cancel handling, conditional, mbprint,
parallel slot, recovery_gen, simple_list, string_utils, the astreamer
backup-stream chain, print). **DONE 2026-06-04 (A11 sweep,
cloud/pg-file-backfiller):** all 18 .c files documented; 20 issues into
`knowledge/issues/fe_utils.md`. **Headlines:** (1) `string_utils.c` is
the identifier-quoting chokepoint (`fmtId` shared static buffer +
`appendShellString` allowlist + `processSQLNamePattern`) the A4 sweep
flagged as a gap — now closed; (2) `astreamer_tar.c` IS the A4
"trust-the-stream" boundary (server-supplied tar name/size/mode drive
local writes; mitigated by `path_is_safe_for_extraction` + hard
`pg_fatal` on PAX headers); (3) `recovery_gen.c` is the canonical
secret-to-disk site (cleartext password into `primary_conninfo`),
extending the secret-scrub cluster; (4) the gzip/lz4/zstd astreamers
are streaming with fixed output buffers — NO RAM decompression bomb,
only a cumulative-output/disk dimension. **Next-up:** the 16 companion
`src/include/fe_utils/` headers (queued).

## src/pl — 26 / 39 docs (66.7%, all 4 PLs covered)

**Procedural languages — ALL 4 PLs documented as of A10 (2026-06-04):**
~~plpgsql~~ (A9, 8 docs / 9 files), ~~plperl~~ (A10-1, 3 docs / 3
files; `ppport.h` skipped as vendored Devel::PPPort), ~~plpython~~
(A10-2/3/4, 14 docs / 26 files; most .c/.h pairs combined into module
docs), ~~pltcl~~ (A10-4, 1 doc / 1 file). The 13 "missing" docs are
all .c/.h pair-combined into module docs — file-coverage is
effectively 100% modulo `ppport.h`. **Cross-PL trust-gate ranking
(THE A10 headline):** Tcl Safe (C-dispatch level) ≥ Perl opcode-mask
(NOT Safe.pm — docs hand-wave) > nothing (plpgsql, language has no
I/O) > N/A (plpython untrusted-only — `import`/ctypes vectors make
Safe.pm-equivalent impossible).

## contrib — 154 / 210 docs (73.3%, top-4 + security-themed + datatypes/index-AMs + remainder cleanup all complete)

In-tree extensions, ~40 modules. **A11 (2026-06-04)** landed the
top-4 highest-Phase-D-value modules: ~~pg_stat_statements~~,
~~dblink~~, ~~postgres_fdw~~ (6 docs), ~~pgcrypto~~ (25 docs / 28
files). **A12 (2026-06-09)** landed the security-themed bundle:
~~auth_delay~~, ~~sslinfo~~. **A13 (2026-06-09, PR #100)** landed
contrib datatypes + index-AMs: ~~hstore~~ (7 docs), ~~ltree~~ (12
docs), ~~btree_gist~~ (24 docs / 27 files), ~~intarray~~ (7 docs),
~~tablefunc~~, ~~citext~~, ~~btree_gin~~ (53 docs / 56 source
files). **A14 (2026-06-09, PR #101)** landed the contrib remainder
cleanup bundle: ~~pg_visibility~~, ~~pg_buffercache~~,
~~pg_freespacemap~~, ~~pg_prewarm~~, ~~pgrowlocks~~,
~~pg_walinspect~~, ~~pg_surgery~~, ~~pg_overexplain~~,
~~basebackup_to_shell~~, ~~basic_archive~~, ~~tsm_system_rows~~,
~~tsm_system_time~~, ~~lo~~, ~~bloom~~, ~~isn~~, ~~seg~~,
~~cube~~, ~~earthdistance~~, ~~unaccent~~, ~~dict_xsyn~~,
~~dict_int~~, ~~pg_trgm~~, ~~fuzzystrmatch~~ (40 docs / 44 source
files / 23 modules). **Only `contrib/intagg` legacy stub remains.**
**A12 critical Phase D findings:** sepgsql 3 confirmed
security-class bugs; pageinspect cross-table read primitive;
amcheck zero C-side permission checks; auth_delay timing oracle;
file_fdw single-layer trust; sslinfo unverified-cert leak.
**A13 critical Phase D findings:** 🚨 tablefunc.connectby_text SQL
injection; ltree parse_lquery 400000× memory amplification +
checkCond catastrophic backtracker + crc32 locale-change breaks
GiST signatures; hstore forged HS_FLAG_NEWVERSION → OOB-read;
btree_gist NaN divergence; intarray signature collisions; citext
collation asymmetry. **A14 critical Phase D findings:**
🚨 pg_walinspect `show_data=true` confirmed RLS/column-priv bypass;
🚨 pg_prewarm autoprewarm PUBLIC (no REVOKE); 🚨 pg_surgery
heap_force_freeze resurrects aborted tuples; basebackup_to_shell
%-escape model fragile; cube palloc's 16 MB upstream of dim cap;
pg_trgm trgm_regexp.c zero CHECK_FOR_INTERRUPTS; pg_trgm/bloom
join the 5-module signature-collision cluster (hstore CRC32 + ltree
CRC32 + intarray mod-hash + pg_trgm mod-hash + bloom LCG).

---

## Suggested attack order (post A3)

0. ~~**Foreground sweep #1** — `src/include/catalog/`~~ — **DONE 2026-06-02 evening** (72 docs, 68 issues; `knowledge/issues/catalog.md`).
1. ~~**Foreground sweep #2** — libpq stack~~ — **DONE 2026-06-03 morning** (69 docs, 227 issues; `knowledge/issues/libpq.md`).
2. ~~**Foreground sweep #3** — pg_dump~~ — **DONE 2026-06-03 afternoon** (36 docs, 80 issues; `knowledge/issues/pg_dump.md`). pg_dump.c alone is ~17k LOC; B2's "trust the archive source" finding is the headline.
3. ~~**Foreground sweep #4** — psql + pg_basebackup + initdb~~ — **DONE 2026-06-03 evening** (43 docs, 146 issues; `knowledge/issues/{psql,pg_basebackup,initdb}.md`). 5 parallel agents; 0 misdirection. Headlines: psql secret-scrub cluster (history+logfile+password buffers); pg_basebackup backup-stream trust (server-controlled `spclocation` + `data_directory_mode`); initdb `--pwfile` stale-TODO ("paranoia for now" never resolved).
4. ~~**Foreground sweep #5** — src/common + src/include/common~~ — **DONE 2026-06-03 evening** (109 docs, 124 issues; `knowledge/issues/common.md`). 5 parallel agents; 0 misdirection. **Headlines:** SecretBuf hosting site at `src/include/common/secretbuf.h` (proposed) closes 10+ A5 sites + 4 prior cross-corpus sites in one coordinated patch series; backup-trust echo of A3 in `blkreftable.c` + `parse_manifest.c` (CRC/SHA-256 over attacker-controlled bytes); `pg_lzcompress` decompression-bomb potential; `percentrepl.c` GUC-boundary shell-injection; `controldata_utils` torn-write window.
5. ~~**Foreground sweep #6** — pg_upgrade + pg_rewind + pg_amcheck~~ — **DONE 2026-06-03 late evening** (36 docs, 170 issues; `knowledge/issues/{pg_upgrade,pg_rewind,pg_amcheck}.md`). 5 parallel agents; 0 misdirection. **Headlines:** (1) **pg_upgrade `check_loadable_libraries` RCE** — actually `LOAD`s old-cluster-named `.so` files into the NEW cluster (concrete privilege-escalation primitive); (2) **pg_rewind zero `O_NOFOLLOW` everywhere** + server-supplied symlink targets accepted unchecked + null-bytea-from-source = unlink-target-file primitive; (3) **pg_amcheck fail-open at per-database level** (silent skip on missing extension); (4) **pg_upgrade `pg_authid` hash file persists** under pg_dir_create_mode in new pgdata until cleanup. **Past corpus halfway point at 50.0%.**
6. ~~**Foreground sweep #7** — src/backend/utils/cache + adt~~ — **DONE 2026-06-03 night** (104 docs, 310 issues; `knowledge/issues/utils.md`). 6 parallel agents; 0 misdirection. **Headlines:** (1) genfile.c is server-side trust target pg_rewind (A6) extracts; `pg_read_server_files` membership = total bypass + `Log_directory`-escape vector; (2) xml.c uses custom XXE defense via `xmlSetExternalEntityLoader` returning empty string instead of `XML_PARSE_NONET` (works today; libxml2 changes could regress); (3) pg_upgrade_support.c is catalog-corruption-primitive battery gated by single `IsBinaryUpgrade` bool; (4) acl.c PUBLIC-friendly defaults (DATABASE→CONNECT, FUNCTION→EXECUTE); (5) formatting.c to_char has no input-length cap (50 MB format → 600 MB palloc); (6) binary recv DoS surface (tsvectorrecv 16M lexemes, multirange_recv 100 MB pre-alloc, record_recv lacks check_stack_depth); (7) extended-stats deserializers only `Assert`-validate `nattributes`. **What's working:** gen_random_uuid uses pg_strong_random; ri_triggers fully safe; quote_literal safe due to encoding allowlist; datetime parser-DoS defenses intact; JSON backend recursion stack-guarded.
7. ~~**Foreground sweep #8** — `src/include/replication/`~~ — **DONE 2026-06-04** (22 docs, 98 issues; `knowledge/issues/include-replication.md`). 3 parallel agents; 0 misdirection. **Headlines:** (1) **output_plugin dlopen primitive** confirmed (A6 echo) — `pg_create_logical_replication_slot('name', 'arbitrary_so')` gates only on `has_rolreplication`, `_PG_init` runs via dlopen side effect BEFORE missing-symbol check; this is the FIFTH "load arbitrary code" primitive in the corpus; (2) `pg_logical_emit_message` is EXECUTE PUBLIC by default; (3) subscriber resolves target table by publisher-supplied `nspname.relname` not OID; (4) `max_slot_wal_keep_size = -1` default → unbounded WAL retention DoS; (5) `primary_conninfo` plaintext window in WalRcv shared memory between RequestXLogStreaming and post-connect memset; (6) reorderbuffer disk-bomb (memory cap only); (7) REPLICATION role reads all databases' WAL bypassing per-DB CONNECT.
8. ~~**Foreground sweep #9** — `src/pl/plpgsql/`~~ — **DONE 2026-06-04** (8 docs covering 9 source files, 87 issues; `knowledge/issues/plpgsql.md`). 4 parallel agents; 0 misdirection. **Headlines:** (1) **trusted-PL boundary enforced exactly twice** in `pl_handler.c` (`CheckFunctionValidatorAccess` silent-no-op + `variable_conflict` PGC_SUSET); everything else delegated to fmgr/`pg_language` ACL — once you call a plpgsql function, the trust boundary is gone; (2) **EXECUTE has zero injection defenses for the query body** (USING params parameterized, body never); (3) **WHEN OTHERS swallows everything except QUERY_CANCELED + ASSERT_FAILURE**; (4) **COMMIT-in-procedure breaks one-snapshot-per-command** (fresh snapshot via EnsurePortalSnapshotExists); (5) **two never-invalidated session caches**: `cast_expr_hash` + simple-expr plancache trust; (6) `variable_conflict` policy **baked at first-compile-in-this-backend** — later SET has no effect on cached function; (7) `%TYPE`/`%ROWTYPE` NAME→OID **baked at compile** with `NoLock` — joins corpus-wide NAME-vs-OID Phase D pattern (now A3+A6+A7+A8+A9); (8) grammar admits known-fragile heuristics in its own comments (INTO disambiguation, integer-FOR `..` lookahead, PERFORM strlen-equality rewrite); (9) `PLpgSQL_function` struct **intentionally never freed** to keep external `fn_extra` pointers valid.
9. ~~**Foreground sweep #10** — `src/pl/{plperl,plpython,tcl}`~~ — **DONE 2026-06-04 mid-day** (18 docs covering 30 source files, ~92 issues; `knowledge/issues/{plperl,plpython,pltcl}.md`). 4 parallel agents; 0 misdirection. **Headlines (the cross-PL trust-gate comparison sweep):** (1) **plperl uses opcode-mask + opcode-redirect, NOT Safe.pm despite docs hand-wave** — `grep Safe plperl.c` = 0 matches; the mechanism is `PL_op_mask = plperl_opmask` generated from Perl's Opcode.pm; drift-prone as new ops get added; (2) **plpython is untrusted-only by design** — no `plpython3` trusted variant because Python's `import`/`__builtins__`/getattr/ctypes vectors make a Safe.pm analogue impossible; the entire defense is `superuser = true` at `CREATE EXTENSION plpython3u`; (3) **pltcl uses Tcl Safe (C-dispatch level), structurally strongest** — dangerous commands (`exec`, `socket`, `open`, `file delete`, `load`) NOT PRESENT in the safe interp's command table at all; (4) **`PLy_cursor_plan` missing `is_PLyPlanObject` check** that `PLy_spi_execute` has — text-fallback `"O|O"` parse accepts any PyObject as a "plan" (most concrete Phase D candidate from A10); (5) **one Python interpreter per backend, never finalized** — `sys.modules` patches + ctypes loads persist for backend lifetime; amplified by transaction-poolers; (6) **`plpy.execute(text)` injection surface = plpgsql injection ∪ every PG type's `_in()`** — scalar-return path runs every type's input function; (7) **`plpy.subtransaction()` swallows Python `try/except` and COMMITS subxact** — opposite of plpgsql `EXCEPTION` rollback semantics (cross-PL footgun); (8) **plperl one Perl interpreter per `(trusted?user_id:0)`, never evicted** — long-lived pooled backends accumulate. **NEW corpus-wide cluster: cross-PL trust-gate ranking** (Tcl Safe ≥ Perl opcode-mask > plpgsql nothing > plpython N/A). **NEW corpus-wide cluster: PL dynamic-SQL injection quad** (plpgsql EXECUTE + plperl spi_exec_query + plpython plpy.execute(text) + pltcl spi_exec).
10. ~~**Foreground sweep #11** — contrib/ top 4 modules~~ — **DONE 2026-06-04 afternoon** (33 docs covering 36 source files, ~208 issues — second-largest after A7; `knowledge/issues/{pg_stat_statements,dblink,postgres_fdw,pgcrypto}.md`). 4 parallel agents; 0 misdirection. **Headlines:** (1) **🚨 CRITICAL: pgcrypto decompression bomb** — `pgp_sym_decrypt(small_compressed_blob, pw)` has NO output-size ceiling (`pgp-compress.c:278-310`); 10 KB ciphertext → multi-GB plaintext → backend OOM; reachable via public SQL API with attacker-controlled bytea; same class as A5 `pg_lzcompress` finding but with SQL trigger; (2) **pgcrypto EFAIL surface still reachable** — legacy SYMENCRYPTED_DATA tag-9 ciphertexts accepted without MDC (`pgp-decrypt.c:1141-1152`); only mitigation is delayed-error reporting (Mister-Zuccherato); `disable-mdc=1` SQL option produces no-MDC ciphertext with NO WARNING; (3) **pgcrypto non-constant-time RSA/Elgamal secret-exponent ops** — `BN_mod_exp` called without `BN_FLG_CONSTTIME` for `pgp_rsa_decrypt`/`pgp_elgamal_decrypt` (`pgp-mpi-openssl.c:266,183`); Brumley-Boneh 2003 timing attack; one-line fix; paired with PKCS#1 v1.5 padding short-circuit (`pgp-pubdec.c:42-67`) = Bleichenbacher oracle; (4) **pgcrypto S2K iter byte uncapped** — attacker controls iter via `pgp_sym_decrypt`/`pgp_pub_decrypt` bytea args (`pgp-s2k.c:270`); ~65M digest ops per call; cumulative DoS; (5) **pgcrypto OpenSSL error stack silently discarded everywhere** — `ERR_get_error()` never called; every EVP failure collapses to 3 PXE codes (`px.c:42-84`); (6) **pgcrypto memory hygiene weaker than core PG** — `px_memset` (LTO-elidable) instead of `explicit_bzero`; wrapped legacy algorithms (bcrypt, sha-crypt) DO scrub stack — they're MORE disciplined than the SQL-boundary surrounding them; (7) **pgcrypto weak-by-default password hashing** — `crypt(pw, 'aa')` returns DES (no warning); `gen_salt('bf')` defaults to cost=5 (OWASP min 12); shacrypt accepts ~hour-long DoS; (8) **pgcrypto `encrypt(data, key, 'aes-cbc')` no-IV form silently uses all-zero IV** — confirmed; two encryptions of same plaintext = identical ciphertext; (9) **pgcrypto: no AEAD modes in 2026** (no GCM/CCM/ChaCha20-Poly1305); raw HMAC tags + SQL `=` = timing-attackable; (10) **postgres_fdw `password_required` two-layered defense** is the GOLD STANDARD — `option.c:194` (CREATE-time superuser check) + `connection.c:759` (`check_conn_params` pre-connect) + `connection.c:446` (`pgfdw_security_check` post-connect cross-checking `PQconnectionUsedPassword`); canonical loopback-bypass-RLS requires EXPLICIT `password_required=false`; SCRAM passthrough adds third allowed path; (11) **postgres_fdw stats-import + ANALYZE-as-table-owner enlarge attack surface** — ANALYZE opens remote conn as `relowner`; hostile remote can plant decoy MCVs via `restore_stats=true`; (12) **postgres_fdw TLS not enforced** — default `sslmode=prefer` allows MITM downgrade; **Phase D candidate: `postgres_fdw.min_sslmode` GUC**; (13) **postgres_fdw cross-cluster semantic mismatch silent** — shippable functions/aggregates resolved by NAME at remote; same-named aggregate with different semantics = silently wrong result; (14) **dblink conninfo-trust has zero host-restriction enforcement** — canonical loopback-to-bypass-RLS / privilege-escalation surface; `dblink_security_check` correctly gates credentials but NOT host; (15) **pg_stat_statements track_utility=on (DEFAULT TRUE) captures CREATE/ALTER USER PASSWORD cleartext** in `pg_stat_tmp/pgss_query_texts.stat` exposed to `pg_read_all_stats` — exact A4 psql-history cycle at cluster scope; (16) **pg_stat_statements stat file readable by `pg_read_server_files`** — confirms A7 genfile.c bypass at a second concrete site. **NEW corpus-wide Phase D pitch cluster (pgcrypto modernization patch series): EVP_CIPHER_fetch migration + AEAD modes + `explicit_bzero` adoption + `BN_FLG_CONSTTIME` + S2K iter cap GUC + decompression-bomb ceiling — single coherent OpenSSL-3.0-era refresh.**
11. **Cloud routine** — keep grinding. ~~`src/fe_utils` (18 files)~~ DONE (A11 + headers); ~~`src/timezone` (7 files)~~ DONE 2026-06-07; `src/port` security+broadly-used shims done 2026-06-06 (the ~22 `win32*.c` shims remain deferred); ~~`src/backend/libpq` (17 files)~~ was ALREADY DONE by A2 (the queue's "0/17" was stale — see 2026-06-08 queue audit); ~~`src/backend/storage/aio` (10 .c + 4 headers)~~ DONE 2026-06-08 (PG18 AIO subsystem). **Next cloud target: `src/include/utils` (70 headers, biggest single remaining gap) or `src/include/storage` aio companions + the rest (34 headers); also `src/backend/access/rmgrdesc` (22, WAL-desc) and `src/include/executor` (41).** Recompute the genuine gap from the GitHub tree at anchor before refilling — `coverage-gaps.md` per-subdir 0% rows have proven unreliable (libpq was wrong).
12. ~~**Foreground sweep #12** — contrib/ security-themed bundle~~ — **DONE 2026-06-09 (PR #99)** (28 docs / 30 files, ~153 issues; `knowledge/issues/{amcheck,pageinspect,pgstattuple,sepgsql,file_fdw,auth_delay,sslinfo}.md`). 4 parallel agents; 0 misdirection. Headlines summarized inline at "## contrib" above.
13. ~~**Foreground sweep #13** — contrib/ datatypes + index-AMs~~ — **DONE 2026-06-09 (PR #100 — pending merge at A14 branch time)** (53 docs / 56 files, ~155 issues; `knowledge/issues/{hstore,ltree,btree_gist,intarray,tablefunc,citext,btree_gin}.md`). 4 parallel agents; 0 misdirection. **Headlines:** (1) **🚨 `tablefunc.connectby_text` SQL injection** — 5 of 6 identifier args interpolated raw via `appendStringInfo`; (2) **ltree `parse_lquery` ~400000× memory amplification** + `checkCond` regex-class catastrophic backtracker + `crc32.c` locale-change silently breaks GiST signatures; (3) **hstore forged `HS_FLAG_NEWVERSION` bypasses ALL validation** → controllable OOB-read; (4) **btree_gist float4/float8 NaN divergence vs nbtree** — `EXCLUDE USING gist (val WITH =)` permits duplicate NaN rows; (5) **intarray signature-tree trivial bit-collisions** (mod-hash siglen*8); (6) **citext collation asymmetry** (`=` DEFAULT-collation vs `<` INPUT-collation). **NEW corpus-wide clusters:** GiST-collision attacks on attacker data (4-module); text-to-SPI injection sinks (5-sweep cluster).
14. ~~**Foreground sweep #14** — contrib/ remainder cleanup~~ — **DONE 2026-06-09 (this sweep)** (40 docs / 44 files, ~90 issues across 23 modules; `knowledge/issues/{pg_visibility,pg_buffercache,pg_freespacemap,pg_prewarm,pgrowlocks,pg_walinspect,pg_surgery,pg_overexplain,basebackup_to_shell,basic_archive,tsm_system_rows,tsm_system_time,lo,bloom,isn,seg,cube,earthdistance,unaccent,dict_xsyn,dict_int,pg_trgm,fuzzystrmatch}.md`). 4 parallel agents; 0 misdirection. **14 sweeps in a row.** Headlines summarized inline at "## contrib" above.
15. ~~**Foreground sweep #15** — src/include finishing pass~~ — **DONE 2026-06-09 (PR #102)** (115 docs / 115 files, ~188 issues across 4 sub-trees; 4 parallel agents; zero misdirection; 15 sweeps in a row). Slices: A15-1 utils sec/locale/GUC (18 headers); A15-2 utils types+memory+datum (~30 headers); A15-3 utils backend-state + executor support (~28 headers); A15-4 lib (15, FULL DIR) + storage core (~22). Headlines: PS title leaks SQL (incl passwords) to other OS users; `USE_INJECTION_POINTS` in prod = arbitrary dlopen + symbol execute; spi.h is the canonical text-to-SQL injection sink (A9/A10/A13 cluster); stringinfo.h is the central injection sink for A7/A13/A14; ruleutils `pg_get_viewdef` loses view security clauses (A7 cross-finding confirmed at API layer); `pg_str{lower,upper}` 3x ICU casemap uncapped (A7 echo); MCV-leak gate per-estimator; bloomfilter.h is the in-tree generic Bloom — contrib AMs each ship their own (5 implementations); execParallel workers inherit leader's whole security envelope. Registers: `knowledge/issues/include-{utils,executor,lib,storage}.md`.
16. ~~**Foreground sweep #16** — src/include/{common,port} enrichment + port finishing~~ — **DONE 2026-06-09 (PR #103)** (22 NEW port docs + 50 enriched common docs; ~130 new ISSUE tags; 2 new registers; 4 parallel agents; zero misdirection; 16 sweeps in a row). Slices: A16-1 common crypto/hash/secret (14 enriched); A16-2 common file/parse/string (19 enriched); A16-3 common types/unicode/json (17 enriched); A16-4 port (22 NEW top-level + 11 platform-specific shims). Headlines: jsonapi recursive-parser frontend SIGSEGV (A5 at API layer); cryptohash.h is the SecretBuf template; no constant-time compare helpers anywhere in tree; SCRAM iter cap absent; pg_prng exposes s0/s1 raw with no "NOT FOR SECURITY"; OpenSSL 3.0 EVP_*_fetch shims not yet in tree (A11 modernization); percentrepl.h does no shell escaping (A5+A8+A14); atomics.h u64 fallback invisible at call sites; CRC32C trivially collidable (A11/A13/A14 cluster echo); pg_numa cross-pid query is privacy probe. Registers: `knowledge/issues/{include-common,include-port}.md`. **25 port subdir files (atomics/*.h, win32/*.h, win32_msvc/*.h) deferred to cloud routine.**
17. **Next foreground candidates:** **refresh source anchor** (`4b0bf0788b0` ~9 days stale; ~29-50 master commits accumulated) — first-class candidate; OR `src/include/executor` remaining ~33 thin `nodeXxx.h` plan-node decl headers (low value, cloud-fillable); OR `src/interfaces/ecpg` (~127 files, low Phase D); OR `src/test` regress framework selectively; OR pivot toward **Phase B** (developer personas mined from pgsql-hackers + commits).
18. **Defer** — `snowball/` (generated), `timezone/` (imported tzcode), `pch/` (precompiled-header glue), `po/` (translations), ecpg (127 files; embedded SQL — low Phase D priority).

---

## Maintenance

Refresh this file whenever per-file doc count moves by ≥50, when a
top-level dir crosses a 10% coverage boundary, or after any major
foreground sweep. Run:

```bash
SRC=/Users/matej/Work/postgres/postgres-claude/source
DOCS=knowledge/files
# (per-subdir counts — see the meson recipe at the bottom)
```

(A small `progress/_gap-script.sh` will be added in a follow-up if this
becomes painful to recompute; for now it's an ad-hoc bash invocation.)
