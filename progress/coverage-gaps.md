# Coverage gaps — Phase A work queue

The per-directory undocumented-file map. This is the **work queue** the
`pg-file-backfiller` cloud routine + foreground interactive sweeps pull
from until Phase A closes (100% coverage of `src/` + `contrib/`).

**Refreshed:** 2026-06-04 (post A8 include/replication sweep), source pin `4b0bf0788b0`.
**Top-line:** 1 407 / 2 564 docs (54.9% coverage). **Gap: 1 157 files.**

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
| libpq | 17 | 0 | 0.0% | Backend libpq (auth, be-secure, hba, crypt). Loadbearing for connection security; touched by data-leak threat models |
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

## src/include — 361 / 844 docs (42.8%)

Headers are the API surface and the principal source of invariant
documentation (struct field comments, INV-* anchors). Coverage here
matters as much as `.c` files.

### Done or near-done

| Subdir | Source | Docs | Coverage |
|---|---:|---:|---:|
| optimizer | 28 | 28 | 100.0% |
| postmaster | 15 | 14 | 93.3% |
| rewrite | 9 | 7 | 77.8% |
| commands | 43 | 33 | 76.7% |
| nodes | 24 | 18 | 75.0% |
| parser | 23 | 16 | 69.6% |
| access | 94 | 63 | 67.0% |
| tcop | 9 | 6 | 66.7% |

### Mid gaps (workable in cloud)

| Subdir | Source | Docs | Coverage |
|---|---:|---:|---:|
| storage | 69 | 35 | 50.7% |
| executor | 61 | 20 | 32.8% |
| utils | 97 | 28 | 28.9% |
| tsearch | 7 | 2 | 28.6% |
| statistics | 4 | 1 | 25.0% |
| regex | 5 | 1 | 20.0% |

### Done or near-done (post A1, A2)

| Subdir | Source | Docs | Coverage | Notes |
|---|---:|---:|---:|---|
| **catalog** | 85 | 87 | 102.4% | A1 sweep landed 72 docs 2026-06-02 evening. |
| **libpq** (src/include) | 20 | 20 | 100.0% | A2 sweep landed all 20 backend headers 2026-06-03. |

### Big absolute gaps (high-priority foreground sweep candidates)

| Subdir | Source | Docs | Coverage | Why |
|---|---:|---:|---:|---|
| **common** | 50 | 0 | 0.0% | Cross-backend shared helpers (cryptohash, scram, blkreffile, …) |
| **port** | 47 | 0 | 0.0% | Cross-platform portability headers — `pg_iovec.h`, `pg_pthread.h`, etc. |
| ~~**replication**~~ | 22 | 23 | 104.5% | **DONE 2026-06-04 (A8 sweep)** — 22 docs + 1 pre-existing headers.md; 98 issues in `knowledge/issues/include-replication.md`; output-plugin dlopen primitive identified |
| **lib** | 15 | 0 | 0.0% | binaryheap, dshash, hyperloglog, pairingheap, simplehash, etc. |
| **fe_utils** | 16 | 0 | 0.0% | Frontend-shared helpers |

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

## src/timezone — 0 / 7 docs (0.0%)

Imported tzcode. Mechanical; low priority.

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

## src/fe_utils — 0 / 18 docs (0.0%)

Frontend-shared utilities (cancel handling, conditional, mbprint,
parallel slot, recovery_gen, simple_list, string_utils). Small,
mechanical.

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

## contrib — 0 / 210 docs (0.0%)

In-tree extensions, ~40 modules. Mix: hardly-used (auth_delay,
sslinfo) to load-bearing (pg_stat_statements, pgcrypto, postgres_fdw,
btree_gin, dblink, pgrowlocks). **Important for extension-API surface
documentation**. Touched by the extension-anthropologist cloud routine
already; verify alignment.

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
10. **Cloud routine** — keep grinding through `src/port`, `src/timezone`, `src/fe_utils` (mechanical, low-judgement).
11. **Cloud routine + foreground** — contrib/ top modules (pg_stat_statements, pgcrypto, postgres_fdw, dblink).
12. **Defer** — `snowball/` (generated), `timezone/` (imported tzcode), `pch/` (precompiled-header glue), `po/` (translations), ecpg (127 files; embedded SQL — low Phase D priority).

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
