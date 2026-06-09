# Session — A15 src/include finishing pass (foreground)

**Date:** 2026-06-09 (continuing after A13 + A14 contrib closure)
**Phase:** A — corpus completeness + issue surfacing
**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Branch:** `ft_corpus_a15_include_finishing`

## Scope

The **`src/include/` finishing pass** — the API-layer Phase D pass.
115 header files across 4 sub-trees, all the load-bearing headers
that were still uncovered post-A8/A11/A14.

| Sub-tree | Pre-A15 | New | Post-A15 | Coverage |
|---|---:|---:|---:|---:|
| `src/include/utils` | 28 | 70 | 98 | 100%+ |
| `src/include/storage` | 39 | 22 | 61 | 88.4% |
| `src/include/lib` | 0 | 15 | 15 | **100% (FULL DIR)** |
| `src/include/executor` | 20 | 8 | 28 | 45.9% (33 thin nodeXxx.h deferred to cloud) |
| **Total** | **87** | **115** | **202** | — |

## Method

Standard A-sweep pattern. **4 parallel agents:**

- **A15-1** utils sec/locale/GUC (18 headers: acl, aclchk_internal, rls, usercontext, pg_locale, pg_locale_c, ascii, formatting, tzparser, guc, guc_hooks, guc_tables, conffiles, ps_status, pidfile, injection_point, help_config, regproc)
- **A15-2** utils types + memory + datum (~30 headers: array, builtins, bytea, cash, datetime, datum, dsa, expanded*, float, fmgrtab, freepage, funccache, geo_decls, hsearch, inet, json, jsonfuncs, memdebug, multirangetypes, numeric, pg_crc, pg_lsn, rangetypes, sampling, uuid, varbit, varlena, xid8, xml)
- **A15-3** utils backend-state + relations + stats + executor support (~28 headers: backend_progress, backend_status, pg_rusage, pgstat_internal, pgstat_kind, portal, queryenvironment, rel, relfilenumbermap, relmapper, relptr, reltrigger, resowner, ruleutils, index_selfuncs, selfuncs, sharedtuplestore, skipsupport, timeout, wait_classes, wait_event, spi, tqueue, execAsync, execParallel, execScan, execdebug, hashjoin, instrument_node)
- **A15-4** lib (15 headers, FULL DIR) + storage core (~22 headers: bufmgr, read_stream, lmgr, lockdefs, locktag, lwlocklist, predicate, predicate_internals, condition_variable, procnumber, pg_shmem, pg_sema, s_lock, spin, io_worker, relfilelocator, block, buf, off, itemid, large_object, indexfsm)

Wall time ~16 min. **Zero misdirection. 15th A-sweep in a row.**

## Output

**Per-file docs** (115 docs / 115 source headers): under
`knowledge/files/src/include/{utils,storage,lib,executor}/...`.

**Subsystem issue registers** (4 new files, ~188 entries):
- `knowledge/issues/include-utils.md` — ~163 entries
- `knowledge/issues/include-storage.md` — ~14 entries
- `knowledge/issues/include-lib.md` — ~11 entries
- `knowledge/issues/include-executor.md` — ~11 entries

**Progress ledgers updated:**

- `progress/files-examined.md` — +115 rows (slugs `include-finishing-a15-{1,2,3,4}`)
- `progress/coverage.md` — 1,662→**1,777 docs (64.8%→69.3%)**; src/include 53.7%→**67.3%**
- `progress/coverage-gaps.md` — src/include section refreshed; attack order extended to #15 (this) + #16
- `progress/STATE.md` — last-activity narrative

## Confidence rollup

Aggregate ~80% `[verified-by-code]`, ~15% `[from-comment]`, ~5%
`[inferred]`, **0% `[unverified]`**. Headers tend to surface fewer
code-level bugs than `.c` files — most flagged issues are
invariant-documentation gaps, undocumented assumptions, and
API-shape concerns. Genuinely exploitable code-level bugs in this
slice: 4 (PS-title leak, USE_INJECTION_POINTS prod build, view
security-clause loss, MCV-leak per-estimator gate).

## Headlines

### 🚨 PS title leaks SQL text to other OS users

`ps_status.h:32` — `update_process_title=on` (Unix default) means
the current SQL query text appears in `ps` / `top` for any OS user.
Literal password strings in `ALTER USER ... PASSWORD '...'`
sessions are visible. Echoes A11 pg_stat_statements + A4 psql
history password-capture cycle at OS-process level.

### 🚨 `USE_INJECTION_POINTS` in production = arbitrary dlopen

`injection_point.h:30,49` — deferred dlopen at first hit hides
attach-time failures; `InjectionPointAttach` superuser requirement
not at header level. Production-build gate is the sole defense.

### 🚨 `spi.h` is THE canonical text-to-SQL injection sink

Joins the A9/A10/A13 5-sweep cluster (plpgsql EXECUTE + plperl
spi_exec_query + plpython plpy.execute(text) + pltcl spi_exec +
tablefunc.connectby_text). Six SPI functions take TEXT + execute
SQL; six take prepared plan + Datum. Header gives zero guidance
steering callers to the safe family. SECURITY DEFINER + SPI is one
of PG's most common security gotchas — privilege/search_path
inheritance is invisible from this header.

### 🚨 `stringinfo.h` is the central injection sink for A7/A13/A14

`appendStringInfo(s, "%s", untrusted)` is the canonical PG SQL/
shell injection footgun:
- A13 tablefunc.connectby_text — 5 of 6 identifier args raw
- A14 basebackup_to_shell — %X substitution model fragile
- A7 to_char — 50 MB format → 600 MB palloc
- A14 cube cubeparse — 16 MB palloc upstream of dim cap

Header carries NO warning. **Phase D candidate:** API-level quoting
helpers `appendStringInfoQuotedIdentifier` + `appendStringInfoShellQuoted`.

### `pg_str*` ICU casemap uncapped

`pg_locale.h:183-194` + `formatting.h:21-24` — `pg_str{lower,upper,
fold,title}` accept caller-supplied srclen; ICU casemap multiplies
up to 3×; no `MaxAllocSize` cap. Direct echo of A7's 50 MB→600 MB
to_char at API layer. Affects citext (A13), pg_trgm (A14), every
text comparison path.

### `pg_get_viewdef` loses view security clauses

`ruleutils.h:54` + `rel.h:426-485` — A7 cross-finding confirmed at
header layer. `get_reloptions` exists; view-option macros
(`security_barrier` / `security_invoker` / `check_option`) exist;
but `pg_get_viewdef()` does NOT re-emit them. `pg_dump` rescues
itself via direct `pg_class.reloptions` read; SQL callers silently
lose security clauses.

### MCV-leak per-estimator gate

`selfuncs.h:99-100,165` — `acl_ok` + `statistic_proc_security_check`
gate is enforced per-estimator with NO single chokepoint. New
estimators routinely miss it (well-known CVE class). Also: `get_
relation_stats_hook` / `get_index_stats_hook` let an FDW silently
override stats per query without audit trail (A11 echo).

### `bloomfilter.h` = 5-implementation Bloom cluster

`bloomfilter.h:16-25` — the in-tree generic Bloom. Contrib `bloom`-
AM + `hstore_gin` + `ltree_gist` + `intarray_gist` + `pg_trgm_gist`
each ship their own ad-hoc multi-hash. 5 implementations, no shared
abstraction. Default seed=0 in all internal callers.

### `execParallel.h` security-envelope concentration

Workers inherit leader's: user identity, search_path,
SecurityRestrictionContext, snapshot, PARAM_EXEC values. The whole
security envelope rests on parallel-safe / parallel-restricted
function labels being honest. Header is silent about this contract.

### NaN/EPSILON cluster at API layer

`float.h:236-241` (PG-only NaN==NaN sort) vs `geo_decls.h:30-32`
(EPSILON intransitive, FALSE on NaN). Mixing in one opclass = the
recurring family observed in A13 btree_gist + A14 cube + seg.

### `bufmgr.h` silent-corruption-tolerant reads

`READ_BUFFERS_IGNORE_CHECKSUM_FAILURES` + `RBM_ZERO_ON_ERROR` =
two read paths that silently swallow corruption. Must remain
superuser-only wherever exposed via SQL. `EB_SKIP_EXTENSION_LOCK`
3-case correctness contract documented only in comment.

### `lwlocklist.h` 3-file silent coupling

Adding/removing a built-in LWLock requires THREE coordinated edits
(header + `wait_event_names.txt` + `generate-lwlocknames.pl`). No
CI cross-check. Silent gaps in `pg_stat_activity` wait reporting
the production hazard.

### `radixtree.h` no lock-held Asserts

`RT_SET`/`RT_DELETE` (`radixtree.h:1707-1712,2617-2624`) only have
magic+root asserts; no Assert that per-tree rwlock is held in
`RT_SHMEM` mode. Header TODO at lines 83-87 acknowledges current
rwlock sub-optimal for high-concurrency mixed read-write.

## New cross-corpus connections from A15

- **A7 utils.md (310 entries)** gets a header-layer companion register:
  `include-utils.md` (~163 entries). datetime, xml, formatting, acl,
  ruleutils, regproc all have header-level cross-refs now.
- **A11/A13/A14 signature-collision cluster** (5 modules) gets the
  in-tree generic anchor: `bloomfilter.h`.
- **A13/A14 NaN cluster** gets the header anchors: `float.h` +
  `geo_decls.h`.
- **5-sweep text-to-SPI injection sinks cluster** (A9+A10+A13) gets
  the API host: `spi.h`.
- **A7+A13+A14 text-injection cluster** gets the API host:
  `stringinfo.h` — Phase D candidate for quoting-helper API.
- **NAME→OID cluster** (A3+A6+A7+A8+A9+A10) gets the header
  anchors: `regproc.h` + `guc_hooks.h`.
- **Monitoring-as-extraction cluster** (A7+A11+A12+A14) gets
  `backend_status.h` (st_activity_raw) + `predicate.h`
  (per-session predicate-TID leak) + `pg_locks` (per-tuple
  locktag leak) header-layer echoes.

## Phase D pitch candidates surfaced

1. **StringInfo quoting-helper API** — `appendStringInfoQuotedIdentifier`
   + `appendStringInfoShellQuoted` would close A7+A13+A14 cluster at
   the source.
2. **MCV-leak central chokepoint refactor** — single
   `statistic_proc_security_check` enforcement point replacing 20+
   per-estimator call sites.
3. **lwlocklist CI cross-check** — assert `lwlocklist.h` IDs match
   `wait_event_names.txt` entries.
4. **`pg_str{lower,upper}` MaxAllocSize cap** — single header
   change, defense in depth for A13/A14 text paths.
5. **`pg_get_viewdef` security-clause round-trip** — emit
   `WITH (security_barrier=...)` etc. (single 20-line fix).
6. **`execParallel` security-envelope documentation upgrade** —
   header-level contract for what's shipped to workers.
7. **`appendStringInfo` callsite audit** — corpus-wide grep for
   `appendStringInfo(.*, "%s",` with untrusted arg.

## What this sweep did NOT do

- Did NOT cover `src/include/common` (50 headers — cryptohash,
  scram, blkreffile — A5's `.c` companion, future candidate).
- Did NOT cover `src/include/port` (47 headers — platform shims;
  pg_iovec, pg_pthread).
- Did NOT cover ~33 `src/include/executor/nodeXxx.h` plan-node
  headers (1-line `ExecXxx`/`InitXxx` declarations — better
  filled by cloud routine).
- Did NOT refresh source anchor (`4b0bf0788b0` is ~9 days stale).

## Position

**~69.3% coverage; gap ~787 files.** Cumulative since 2026-06-02:
15 A-sweeps shipped, +860 docs, +~2,285 issues. **15 sweeps in a
row with zero misdirection.**

Next foreground candidates: **refresh source anchor** (~9 days
stale; ~29-50 master commits accumulated) OR
`src/include/common` (50 headers) OR `src/include/port` (47
headers) OR `src/interfaces/ecpg` (~127 files, low Phase D) OR
`src/test` regress framework selectively.
