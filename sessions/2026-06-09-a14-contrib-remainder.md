# Session — A14 contrib remainder cleanup sweep (foreground)

**Date:** 2026-06-09 (continuing the contrib/ campaign immediately
after A13 datatypes sweep — branched pre-A13 because PR #100 still
open at sweep start)
**Phase:** A — corpus completeness + issue surfacing
**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Branch:** `ft_corpus_a14_contrib_remainder`

## Scope

The **contrib remainder cleanup** bundle — every remaining contrib
module not covered by A11 (top-4) / A12 (security-themed) / A13
(datatypes + index-AMs). 44 source files / ~22.7 K LOC across 23
modules:

| Module | Files | LOC | Docs |
|---|---:|---:|---:|
| pg_visibility | 1 | 933 | 1 |
| pg_buffercache | 1 | 873 | 1 |
| pg_freespacemap | 1 | 53 | 1 |
| pg_prewarm | 2 | 1 290 | 2 |
| pgrowlocks | 1 | 280 | 1 |
| pg_walinspect | 1 | 865 | 1 |
| pg_surgery | 1 | 421 | 1 |
| pg_overexplain | 1 | 945 | 1 |
| basebackup_to_shell | 1 | 376 | 1 |
| basic_archive | 1 | 298 | 1 |
| tsm_system_rows | 1 | 342 | 1 |
| tsm_system_time | 1 | 356 | 1 |
| lo | 1 | 114 | 1 |
| bloom | 7 | 1 759 | 7 |
| isn | 9 | 2 442 | 3 (EAN/ISBN/ISMN/ISSN/UPC headers combined) |
| seg | 2 | 1 136 | 2 |
| cube | 2 | 1 999 | 2 |
| earthdistance | 1 | 108 | 1 |
| unaccent | 1 | 502 | 1 |
| dict_xsyn | 1 | 264 | 1 |
| dict_int | 1 | 119 | 1 |
| pg_trgm | 5 | 5 364 | 5 |
| fuzzystrmatch | 3 | 2 819 | 3 |
| **Total** | **44** | **~22 658** | **40** |

## Method

Standard A-sweep pattern. **4 parallel agents:**

- **A14-1** introspection/surgery cluster (9 files; pg_visibility,
  pg_buffercache, pg_freespacemap, pg_prewarm×2, pgrowlocks,
  pg_walinspect, pg_surgery, pg_overexplain)
- **A14-2** storage/archive/sampling/index cluster (19 files;
  basebackup_to_shell, basic_archive, tsm_system_rows,
  tsm_system_time, lo, bloom×7, isn×9)
- **A14-3** geometric + dictionary cluster (8 files; seg×2, cube×2,
  earthdistance, unaccent, dict_xsyn, dict_int)
- **A14-4** text-similarity / fuzzy-matching cluster (8 files;
  pg_trgm×5, fuzzystrmatch×3 — the largest slice by LOC)

Wall time ~15 min. **Zero misdirection. 14th A-sweep in a row.**

## Output

**Per-file docs** (40 docs, 44 source files): under
`knowledge/files/contrib/<module>/...` for each of the 23 modules.

**Subsystem issue registers** (23 files, ~90 entries) — one register
per module, all new under `knowledge/issues/<module>.md`.

**Progress ledgers updated:**

- `progress/files-examined.md` — +44 rows (slug `contrib-remainder-a14`)
- `progress/coverage.md` — 1 569→1 609 docs (61.2%→**62.7%** in this
  worktree, branched pre-A13; after A13 PR #100 merges adds another
  ~2.1pp); contrib row 29.0%→**48.1%** (post-A13-merge → ~73.3%)
- `progress/coverage-gaps.md` — contrib section refreshed with A13 +
  A14 completions; attack order extended to #14 + #15
- `progress/STATE.md` — last-activity narrative

**Branch note:** the worktree was created from `main` (pre-A13)
because PR #100 (A13) was still open at sweep start. The progress-
file numbers reflect 1 569 + 40 = 1 609 baseline. After A13 + A14
both land, expected combined totals: 1 622 + 40 = 1 662 docs;
contrib 154 / 210 = 73.3%; cumulative coverage ~64.8%. The merge
conflicts at landing time will be confined to top-line numbers in
`coverage.md`, `coverage-gaps.md`, `STATE.md`, and append-only rows
in `files-examined.md`.

## Confidence rollup

Aggregate ~85% `[verified-by-code]`, ~12% `[from-comment]`, ~3%
`[inferred]`, **0% `[unverified]`**. Discipline holds across all 14
sweeps.

## Headlines

### 🚨 `pg_walinspect.show_data=true` = RLS / column-priv bypass

`pg_walinspect.c:377-409,425-467` — returns raw FPI page bytes from
WAL including DELETE'd + pre-UPDATE tuple contents. Gated only by
`pg_read_server_files` grant, no per-relation check. **Most
sensitive A14 finding.** Direct echo of A12 `tuple_data_split`
+ A11 pg_stat_statements password capture + A7 genfile.c.

### 🚨 `pg_prewarm` autoprewarm controls are PUBLIC

`autoprewarm.c:814,846` — `autoprewarm_start_worker` /
`autoprewarm_dump_now` have NO REVOKE in any install script and NO
C-side check. Any logged-in user triggers a full `NBuffers` dump +
contends for buffer-header spinlocks.

Dump-file path (`autoprewarm.c:53,322,737-738`) is unvalidated
PGDATA-relative. `<<N>>` block count parsed as signed `%d`
(`autoprewarm.c:339,346`); negative N silently propagated → `dsm_create(20*N)`
OOM. Per-DB worker connects with `InvalidOid` user — cached blocks
survive role-perm changes across restart.

### 🚨 `pg_surgery.heap_force_freeze` resurrects aborted tuples

`heap_surgery.c:289-308` — silently makes aborted-xact tuples
visible to ALL snapshots, including prior ones that already
observed them as aborted. Documented only as "potentially-garbled
data" — the snapshot-violation is unnamed.

HOT-chain root freezes leave dangling successors. Accepts system
catalog OIDs (only `object_ownercheck` gate; no `IsCatalogRelation`
reject — `heap_surgery.c:111-127`).

### `basebackup_to_shell` substitution model is fragile

`basebackup_to_shell.c:211-217` — `%d` is alphanumeric-only because
target's the only allowed escape today. A future `%X` sourced from
client-controlled data would silently bypass the safety check.
`required_role` defaults empty (`:67-68,104-115`) → ANY REPLICATION
role can fire the operator's shell command out of the box.

### `cube` 16 MB palloc upstream of `CUBE_MAX_DIM` check

`cubeparse.y:154-166` + `cubescan.l:17` — `YY_READ_BUF_SIZE =
16777216` and the list-builder palloc's `scanbuflen+1` BEFORE the
`dim > CUBE_MAX_DIM` rejection. Attacker can force ~16 MB palloc
before the limit fires.

### NaN/Inf coords defeat cube_cmp / seg_cmp

`cube.c:944-1021,1131-1236` + `seg.c:744-855` — breaks `EXCLUDE
USING gist (val WITH =)`. Inf coords → `Inf*0=NaN` in `rt_cube_size`
→ NaN penalty → degenerate GiST tree. Direct echo of A13 btree_gist
float NaN divergence.

### `pg_trgm.trgm_regexp.c` has ZERO `CHECK_FOR_INTERRUPTS()`

Entire regex-to-NFA pipeline (~2 100 LOC) relies on static
`MAX_EXPANDED_STATES=128 / MAX_EXPANDED_ARCS=1024 / MAX_TRGM_COUNT=256
/ COLOR_COUNT_LIMIT=256`. `pg_regcomp` itself is unbounded upstream
of trgm boundary (`trgm_regexp.c:737-741`). Direct echo of A13 ltree
`checkCond` catastrophic backtracker.

### Signature-collision cluster grows to 5 modules

`pg_trgm/trgm.h:85` — `HASHVAL = trgm % 95` at default siglen=12;
adversary text engineers trigram→bit collisions saturating internal
GiST nodes to ALLISTRUE → leaf scan + recheck.

`bloom/blutils.c:266-293` — `signValue` uses deterministic
Park-Miller LCG (NOT `pg_prng_*`) for on-disk stability; attacker-
crafted collisions inflate FP rate (heap recheck closes the leak
gap, DoS amplification stands).

Joins A13's cluster: **hstore CRC32 + ltree CRC32 + intarray mod-
hash + pg_trgm mod-hash + bloom LCG = 5-module signature-design
vulnerability cluster.**

### `fuzzystrmatch.dmetaphone` no length cap, no CFI in main loop

`dmetaphone.c:143,172` (no cap) + `:437` (no CFI). Unlike classical
metaphone (255-byte cap at `fuzzystrmatch.c:278`), dmetaphone
accepts 1 GB text. Adversary input designed to never grow
primary/secondary code stalls O(input_length) with no cancel point.

### SELECT-grantable text-content oracles

`pg_trgm.show_trgm` + `similarity` + soundex/metaphone/dmetaphone/
daitch_mokotoff are SELECT-grantable (`trgm_op.c:1171,1339`,
`fuzzystrmatch.c:719-805`, `dmetaphone.c:132,161`,
`daitch_mokotoff.c:122`). Accelerate cracking of hashed/encrypted
text columns vs direct equality. **NEW Phase D cluster: phonetic/
similarity functions as side-channel primitives.**

### Same A12 "REVOKE-only" pattern repeats

pg_visibility (8 entrypoints), pg_buffercache, pg_freespacemap,
pgrowlocks — all have NO C-side privilege check; install-script
REVOKE-from-PUBLIC is sole gate. Counter-example: pg_surgery DOES
use `object_ownercheck`.

### `isn.weak` GUC + `accept_weak_input` SQL function

`isn.c:1126-1136` — `accept_weak_input(bool)` SQL function mutates
session GUC `isn.weak` (PGC_USERSET). Any role opts in their own
session to accept bad ISBN check digits. By design but worth
tracking for integrity-sensitive applications.

## New corpus-wide clusters from A14

1. **5-module signature-collision cluster** (A13 hstore + ltree +
   intarray + A14 pg_trgm + bloom). Phase D pitch: hash-collision
   audit + per-module mitigation (siglen GUC raises, salt mix,
   defensive recheck).

2. **Monitoring-as-extraction extended to 7+ sites** (A7 genfile +
   A11 pg_stat_statements + A12 amcheck/pageinspect/pgstattuple +
   A14 pg_walinspect / pg_visibility / pg_buffercache / pgrowlocks).
   Phase D pitch: per-role + per-relation gate for monitoring/
   integrity functions; RLS-aware mode.

3. **Phonetic / similarity-as-side-channel** (A14 pg_trgm `show_trgm`
   + soundex/metaphone/dmetaphone/daitch_mokotoff). Phase D pitch:
   defang via per-role gate; document the side-channel posture in
   the per-function reference docs.

## Cross-corpus reinforcement

- **A13 btree_gist float NaN divergence** gets 2 new echo sites:
  A14 cube + seg (same NaN-poison family).
- **A13 ltree `checkCond` catastrophic backtracker** gets 1 new
  echo: A14 pg_trgm `pg_regcomp` upstream of NFA bounds.
- **A8 archive_command "load arbitrary code from untrusted name"**
  gets 2 new echoes: A14 basebackup_to_shell + basic_archive.
- **A12 amcheck "no C-side checks"** gets 4 new echoes: A14
  pg_visibility + pg_buffercache + pg_freespacemap + pgrowlocks.
- **A13 citext `DEFAULT_COLLATION_OID`** gets 2 new echoes: A14
  pg_trgm + dict_xsyn (locale-pin family).
- **A5 jsonapi recursive parser** gets 1 echo: A14 cube `cubeparse.y`.

## What this sweep did NOT do

- No commits to `dev/`.
- No new idiom docs written — the 3 new clusters seeded as
  proposals.
- Did NOT touch `contrib/intagg` legacy stub (the one remaining
  contrib module post-A14).
- Did NOT refresh source anchor (`4b0bf0788b0` is now ~9 days
  stale; explicit pending task).

## Position

**~62.7% coverage in this worktree** (branched pre-A13; gap 955 of
2 564). After A13 + A14 both land: ~64.8% / contrib 73.3%. Cumulative
since 2026-06-02: 14 A-sweeps shipped, +732 docs, +~2 095 issues.
**14 sweeps in a row with zero misdirection.**

Next foreground candidates: **refresh source anchor** (`4b0bf0788b0`
is ~9 days stale; ~29-50 master commits accumulated) OR
`src/interfaces/ecpg` (~127 files, low Phase D priority) OR
`src/include` finishing pass (utils=70, storage=34, executor=41
remaining) OR `src/port` shims (the ~22 `win32*.c` remaining).
