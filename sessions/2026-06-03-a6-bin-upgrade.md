# 2026-06-03 — A6 bin-upgrade sweep (foreground sweep #6)

**Type:** interactive (worktree `ft_corpus_a6_bin_upgrade`).
**Outcome:** 36 new per-file docs across `src/bin/pg_upgrade/` (22) +
`src/bin/pg_rewind/` (13) + `src/bin/pg_amcheck/` (1); **170 issues
consolidated into three new registers** under `knowledge/issues/`
(`pg_upgrade.md`, `pg_rewind.md`, `pg_amcheck.md`).

**Headlines:** (1) **pg_upgrade `check_loadable_libraries` RCE
primitive** — actually LOADs old-cluster-named `.so` files into the
new cluster; (2) **pg_rewind zero `O_NOFOLLOW` + unchecked symlink
targets** = escape-the-data-dir; (3) **pg_amcheck fail-open at
per-database level**; (4) **corpus past halfway point at 50.0%**.

## Why this sweep

Phase A foreground sweep #6 per `progress/coverage-gaps.md`. The user
chose this trio because the security-sensitive bin/ tools remaining
after A4 were specifically pg_upgrade (most security-sensitive — runs
SQL as superuser on both old + new clusters, performs raw file ops,
carries credential material), pg_rewind (data-dir manipulation), and
pg_amcheck (integrity verifier). All Phase D candidate territory.

## What landed

### New files (40 total)

| Path | Count | Role |
|---|---|---|
| `knowledge/files/src/bin/pg_upgrade/*.md` | 22 | All 22 `.c`/`.h` files |
| `knowledge/files/src/bin/pg_rewind/*.md` | 13 | All 13 `.c`/`.h` files |
| `knowledge/files/src/bin/pg_amcheck/*.md` | 1 | The single 68K source file |
| `knowledge/issues/pg_upgrade.md` | 1 | 105-entry register — trust-the-old-cluster cluster (RCE primitive), shell-injection, secret-scrub (pg_authid hash file), state-transitions, correctness |
| `knowledge/issues/pg_rewind.md` | 1 | 53-entry register — `O_NOFOLLOW` gap, server-controlled delete + symlink primitives, no atomicity marker |
| `knowledge/issues/pg_amcheck.md` | 1 | 12-entry register — fail-open at per-database, server text to terminal |
| `sessions/2026-06-03-a6-bin-upgrade.md` | 1 | This log |

### Modified files

| Path | Change |
|---|---|
| `progress/files-examined.md` | +36 rows (source slug `bin-upgrade-a6`) |
| `progress/coverage.md` | 1 245 → 1 281 docs; src/bin 49.4%→71.9%; total 48.6%→**50.0% (halfway)** |
| `progress/coverage-gaps.md` | A6 marked done; #7 unchanged (backend/utils/cache + adt); src/bin remaining is small mechanical tools |
| `progress/STATE.md` | Last-activity bumped; Phase A work queue 1-6 done, 7-11 queued |

## How it was done — 5 parallel agents

Same pattern as A1-A5; sized for 36-file scale:

| Batch | Theme | Files | Issues | Wall time |
|---|---|---:|---:|---:|
| B1 | pg_upgrade heavy core (check.c 83K, info.c 29K, pg_upgrade.c+.h, option.c, relfilenumber.c) | 6 | 54 | ~10 min |
| B2 | pg_upgrade rest (controldata, exec, file, server, multixact rewrite, parallel, slru_io, util, etc.) | 16 | 50 | ~12 min |
| B3 | pg_rewind core (pg_rewind.c+.h, filemap.c+.h, libpq_source.c, rewind_source.h) | 6 | 30 | ~7 min |
| B4 | pg_rewind utility (file_ops, datapagemap, local_source, parsexlog, timeline) | 7 | 22 | ~5 min |
| B5 | pg_amcheck.c solo (68K) | 1 | 8 | ~3 min |
| **Total** | | **36** | **164** (agent-reported) / **170** (grep) | ~12 min wall (parallel max) |

**Zero misdirection.** Six successive sweeps with the explicit
"RELATIVE paths" instruction = zero relocation incidents.

## What the sweep surfaced

### Headline 1: pg_upgrade `check_loadable_libraries` RCE primitive

The single most actionable Phase D finding of this sweep. `check.c`
(B1) calls `check_loadable_libraries` which **actually `LOAD`s every
library referenced by the old cluster's `pg_proc`/extensions ON THE
NEW CLUSTER**. A tampered old catalog with `/tmp/evil.so` reference
triggers `_PG_init` in the just-built new cluster's backend → arbitrary
code execution.

The defense: whitelist `shared_preload_libraries`, reject paths under
`/tmp/`, `..`, or any unsigned path. Single-function patch.

This makes pg_upgrade's "trust the old cluster" gap **concrete and
exploitable**. Every other "old cluster catalog trusted" issue (relname,
spclocation, output_plugin name carried over to slot) is a separate
attack surface but `check_loadable_libraries` is the direct RCE.

### Headline 2: pg_upgrade trusts all old-cluster catalog content

`info.c` reads `relname`/`nspname`/`relfilenode`/`spclocation` from old
cluster with **zero validation**. A relative `spcloc=../../etc/...`
from a tampered `pg_tablespace` would compose a path outside pgdata via
`snprintf("%s/%s", pgdata, spcloc)`. `relfilenumber` flows uint32-raw
into `snprintf` paths. The `output_plugin` of a logical-replication slot
is restored into the new cluster with no whitelist — combined with the
loadable-libraries gap = vector.

### Headline 3: pg_upgrade `pg_authid` hash file persists

`pg_upgrade_dump_globals.sql` contains `ALTER ROLE ... PASSWORD
'<scram-hash>'` lines. Sits in `<new_pgdata>/pg_upgrade_output.d/
<timestamp>/dump/` between dump and psql-restore. **NOT scrubbed**.
Persists until `cleanup_output_dirs()` at end of `main()`. With `-r/
--retain` OR on failure, persists indefinitely at `pg_dir_create_mode`
permissions (0700 strict, 0750 group-readable).

Same conceptual gap as A5's sprompt/logging secret-scrub, but with a
**longer in-disk lifetime** than a typical pg_dumpall run. Sixth
installment of the cross-corpus secret-scrub cluster.

### Headline 4: pg_rewind zero `O_NOFOLLOW` anywhere

The pg_rewind security-posture headline. **All 6 file_ops.c open
sites** — `open_target_file`, `truncate_target_file`,
`remove_target_file`, `create_target_symlink`, `remove_target_symlink`,
`remove_target_dir` — lack `O_NOFOLLOW`. Combined with:

- **`create_target_symlink` writes attacker-influenced link targets
  unchecked**: `entry->source_link_target` (opaque server-supplied
  bytes) flows straight into `symlink(link, dstpath)` — no abs-path
  validation, no `..` check, no length cap beyond MAXPGPATH.
- **`recurse_dir` follows symlinks recursively in `pg_tblspc` and
  `pg_wal`**.

Result: a malicious source can plant arbitrary symlinks the next
pg_rewind run dereferences → escape-the-data-dir primitive across
repeated rewinds.

### Headline 5: pg_rewind server-controlled file delete

`libpq_source.c:562`: `pg_read_binary_file()` returning null bytea =
`remove_target_file(filename, missing_ok=true)`. A hostile source has
**explicit unlink primitive** on target files. Guarded only by
`path_is_safe_for_extraction` inside the unlink helper.

### Headline 6: pg_rewind no atomicity marker

`pg_rewind.c:529` "point of no return" comment explicit: a crash
between the first overwriting write and the final
`update_controlfile()` leaves the target with arbitrary mix of source/
target bytes while `pg_control.state` still claims clean shutdown.
**No way to detect partial rewind on re-run.** Closure: marker file
written before first overwrite, removed after final controlfile update.

### Headline 7: pg_amcheck fail-open at per-database

`pg_amcheck.c:585-594`: `--all` silently skips databases without
amcheck extension installed; `all_checks_pass` and exit code
unaffected. Operators using `pg_amcheck --all` as a scheduled cron
check get exit-0 even if some databases were never verified.

**Critical answer for verifier-as-policy-gate:** exit-0 means
**"everything I touched was clean"**, NOT "the cluster is clean".

Closure: `--require-amcheck` flag for fail-closed posture.

### Cross-cutting observations

- **`patternToSQLRegex` is sibling of `processSQLNamePattern`** —
  pg_amcheck uses the former (regex output via VALUES literals), psql/
  pg_dump use the latter (LIKE output). Same chokepoint discipline,
  same safety guarantee. Both live in `fe_utils/string_utils.c`. Worth
  a single `knowledge/idioms/sql-name-pattern.md` doc covering both.
- **pg_rewind is mirror image of pg_basebackup (A4) but worse** —
  pg_basebackup writes a NEW tar; pg_rewind writes IN-PLACE into
  target data dir, has no `O_NOFOLLOW`, accepts server-supplied
  symlink targets unchecked, has explicit delete primitive.
- **pg_upgrade text-parses popen output of pg_controldata + pg_resetwal
  -n** — different trust shape from A5's controldata_utils binary
  parse, but inherits the torn-write story and adds substring-match
  text parsing as new attack surface.

### What's working well (record)

- **pg_rewind file modes are local-only** — `umask(pg_mode_mask)` at
  `pg_rewind.c:297` then `pg_file_create_mode` at `file_ops.c:68`. No
  server-supplied modes honored. Better posture than pg_basebackup.
- **pg_amcheck is fail-closed at per-relation level** — backend ERROR
  while invoking `verify_heapam`/`bt_index_check` flips
  `all_checks_pass = false` → exit-code 2.
- **pg_rewind has no `simple_prompt` callsite** — credentials come from
  libpq via pgpass/env, no separate cleartext buffer to scrub. Better
  posture than the A4 tools.

## What this commit explicitly does NOT do

- **No subsystem docs.** `knowledge/subsystems/{pg_upgrade,pg_rewind,pg_amcheck}.md`
  syntheses queued.
- **No upstream patches for any of the 170 issues.** Corpus side done;
  patches are Phase D work.
- **No changes to `dev/` or other knowledge/ trees.**
- **Remaining bin/ tools deferred** — pg_ctl, pg_resetwal, pg_waldump,
  pg_combinebackup, pg_verifybackup, pg_controldata, pg_checksums,
  scripts/ are mostly small mechanical tools; suitable for cloud
  routine backfill.

## Followup candidates surfaced

- **Phase D — `check_loadable_libraries` whitelist patch** (the single
  highest-impact concrete pitch from any sweep so far).
- **Phase D — pg_rewind `O_NOFOLLOW` sweep** (6 sites in file_ops.c +
  parsexlog.c WAL segment open).
- **Phase D — pg_rewind atomicity marker** (closes "partial rewind
  invisibly leaves inconsistent target").
- **Phase D — `--require-amcheck` flag** for fail-closed `--all`.
- **Phase D — `SecretBuf` extension to pg_upgrade** for pg_authid
  carryover file + util.c logs.
- **`knowledge/idioms/sql-name-pattern.md`** — single doc covering
  both `processSQLNamePattern` (LIKE) and `patternToSQLRegex` (regex).
- **`knowledge/subsystems/{pg_upgrade,pg_rewind,pg_amcheck}.md`**
  syntheses from this sweep's per-file docs.
- **Foreground sweep #7** — `src/backend/utils/cache/` +
  `src/backend/utils/adt/` (233 utils/ files, the biggest remaining
  backend gap).

## Repository state after this commit

- 36 new files across `knowledge/files/src/bin/{pg_upgrade,pg_rewind,pg_amcheck}/`.
- 3 new files in `knowledge/issues/{pg_upgrade,pg_rewind,pg_amcheck}.md`.
- 1 session log.
- 4 progress files updated.

Total: ~44 files changed, ~4 500 lines added.

## Commit message for this work

```
ft(corpus): document 36 bin upgrade/rewind/amcheck files (A6 sweep) + 170 issues

Sixth foreground sweep of Phase A: cover every .c/.h under
src/bin/pg_upgrade/ (22), src/bin/pg_rewind/ (13), and
src/bin/pg_amcheck/ (1) via 5 parallel general-purpose agents. Wall
time ~12 min; 36 per-file docs landed; 170 [ISSUE-*] tags surfaced
and consolidated into three subsystem registers grouped by Phase D
pattern.

Coverage bumps: 1 245 -> 1 281 docs (48.6% -> 50.0%); src/bin 49.4%
-> 71.9%. **CORPUS PAST HALFWAY POINT.**

THE PHASE D HEADLINES:

1. pg_upgrade check_loadable_libraries RCE: check.c actually LOADs
   every library referenced by old cluster's pg_proc/extensions ON
   THE NEW CLUSTER. A tampered old catalog with /tmp/evil.so reference
   triggers _PG_init on the just-built new cluster = arbitrary code
   execution. The concrete RCE primitive in pg_upgrade. Closure:
   whitelist shared_preload_libraries; reject /tmp/, .., or unsigned.

2. pg_upgrade trust-the-old-catalog: relname/nspname/relfilenode/
   spclocation from old cluster's pg_class/pg_tablespace consumed
   unchecked; relative spcloc=../../etc/... composes path outside
   pgdata via snprintf("%s/%s"). Output plugin name of a logical
   replication slot is carried over with no whitelist (vector when
   combined with loadable-libraries gap).

3. pg_upgrade pg_authid hash file persists: pg_upgrade_dump_globals.sql
   contains ALTER ROLE ... PASSWORD '<scram-hash>' lines, sits in
   <new_pgdata>/pg_upgrade_output.d/<ts>/dump/ until cleanup_output_dirs;
   indefinitely under -r/--retain or failure. Sixth installment of the
   cross-corpus secret-scrub cluster (libpq A2 + psql/streamutil/initdb
   A4 + common A5 + pg_upgrade A6).

4. pg_rewind zero O_NOFOLLOW anywhere: all 6 file_ops.c open sites
   dereference; combined with create_target_symlink accepting server-
   supplied source_link_target unchecked + recurse_dir following
   symlinks in pg_tblspc/pg_wal = real escape-the-data-dir primitive
   across repeated rewinds.

5. pg_rewind null-bytea = unlink: pg_read_binary_file() returning null
   = remove_target_file(missing_ok=true); server-controlled delete
   primitive.

6. pg_rewind no atomicity marker: crash between first overwrite and
   final update_controlfile() leaves target inconsistent; pg_control
   still claims clean shutdown; no detection on retry.

7. pg_amcheck fail-open at per-database: --all silently skips
   databases without amcheck extension; exit-0 means "everything I
   touched was clean", NOT "the cluster is clean". Closure:
   --require-amcheck flag.

Cross-corpus: patternToSQLRegex (pg_amcheck) is sibling of
processSQLNamePattern (psql/pg_dump); both live in fe_utils/
string_utils.c; worth single idiom doc. pg_rewind is mirror image of
pg_basebackup (A4) but worse posture (writes in-place, no O_NOFOLLOW,
server-controlled delete primitive). pg_upgrade text-parses popen
output of pg_controldata/pg_resetwal -n — inherits A5 controldata
torn-write story + adds substring-match parsing.

What's working: pg_rewind file modes are local-only (better than
pg_basebackup); pg_amcheck is fail-closed at per-relation level;
pg_rewind has no simple_prompt callsite.

All 5 agents wrote to correct worktree paths (zero misdirection;
6 successive sweeps with explicit RELATIVE-paths guidance = 0
relocation incidents).

Session: sessions/2026-06-03-a6-bin-upgrade.md
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```
