# PostgreSQL domain-ownership map

- **Last verified:** 2026-06-12
- **Source pin:** `e18b0cb7344` (`source/`, read-only)
- **Inputs:** `knowledge/personas/committer-map.md`,
  `knowledge/personas/contributor-map.md`,
  `knowledge/subsystems/*.md` (20 docs).
- **Window:** last 24 months (2024-06-12 .. 2026-06-12) unless noted; "Recent
  landmark commits" uses the last 12 months.

## What this is

The cross-cut Phase B was always supposed to deliver: for each documented
subsystem in the corpus, **who actually owns it in 2026** — who commits
there, who reviews there, what recent landmark work looks like.

`committer-map.md` answers "who pushes in PG, by global volume." `contributor-
map.md` answers "who reviews / authors / reports, by global volume." Neither
answers the cross-cut question: **"if I touch this directory, whose name shows
up in the trailers?"** This doc does, by intersecting both inputs against the
20 documented subsystems.

Feeds:

- **Phase C** (planner/review skill calibration) — "if a patch touches X,
  expect review from these names; here is the typical cadence."
- **Phase D** (future upstream submission) — CC list selection for
  pgsql-hackers patches, and tone-calibration on what reviewers in that
  domain look for.

## Per-subsystem index

20 rows, one per documented subsystem in `knowledge/subsystems/`. Counts are
24mo commit-count (committers) or 24mo Reviewed-by-trailer appearances
(reviewers) restricted to commits whose `--name-only` diff touched the
subsystem's paths.

"Total 24mo commits" column counts distinct commits that touched any path in
the subsystem's scope. The subsystem-scoped totals sum to MORE than the
all-tree 5,752 because cross-cutting commits (e.g. pgindent, repo-wide const
refactors) get counted into each subsystem they touched.

| Subsystem | Path(s) | Total 24mo | Top committers | Top reviewers | Recent landmark commits |
|---|---|---:|---|---|---|
| access-heap | `src/backend/access/heap/` + `src/include/access/heap*.h`, `htup*.h`, `hio.h`, `visibilitymap.h` | 210 | Melanie Plageman (75), Peter Eisentraut (19), Álvaro Herrera (18), Noah Misch (14) | Andres Freund (42), Chao Li (29), Kirill Reshke (22), Masahiko Sawada (13) | `8b9d42bf6bd (Melanie Plageman): Save prune cycles by consistently clearing prune hints on all-visible pages`; `64bf53dd61e (Noah Misch): Revisit cosmetics of inplace-update invalidations` |
| access-nbtree | `src/backend/access/nbtree/`, `nbtree.h`, `nbtxlog.h` | 140 | Peter Geoghegan (78), Peter Eisentraut (22), Álvaro Herrera (7), Tom Lane (6) | Matthias van de Meent (12), Tomas Vondra (11), Chao Li (9), Peter Geoghegan (6) | `8191937082a (Tom Lane): Add offnum range checks to suppress compile warnings with UBSAN`; `92fe23d (Peter Geoghegan): Add nbtree skip scan optimization` (from committer-map) |
| access-transam | `src/backend/access/transam/` + 16 transam headers (`xact.h`, `xlog*.h`, `clog.h`, `multixact.h`, `twophase.h`, `slru.h`, etc.) | 271 | Michael Paquier (67), Heikki Linnakangas (33), Alexander Korotkov (31), Peter Eisentraut (25) | Chao Li (24), Michael Paquier (23), Andres Freund (19), Bertrand Drouvot (14) | `65f4976189b (Michael Paquier): Add assertion check for WAL receiver state during stream-archive transition`; `03facc1211b (Michael Paquier): Switch to FATAL error for missing checkpoint record without backup_label`; `351265a6c7f (Fujii Masao): Remove recovery.signal at recovery end when both signal files are present` |
| executor | `src/backend/executor/`, `src/include/executor/` | 300 | Tom Lane (41), Peter Eisentraut (37), David Rowley (37), Amit Langote (28) | Andres Freund (25), Tom Lane (21), Chao Li (21), Tomas Vondra (18) | `e6d6e32f424 (Álvaro Herrera): Fix duplicate arbiter detection during REINDEX CONCURRENTLY on partitions`; `dd78e69cfc3 (Melanie Plageman): Allocate separate DSM chunk for parallel Index[Only]Scan instrumentation`; `487cf2cbd2f (Andrew Dunstan): Extend DomainHasConstraints() to optionally check constraint volatility` |
| foreign | `src/backend/foreign/`, `src/include/foreign/` | 16 | Jeff Davis (5), Bruce Momjian (2), Michael Paquier (2), Richard Guo (2) | Ashutosh Bapat (2), Chao Li (2), Michael Paquier (2), Amit Kapila (2) | `28972b6fc3d (Etsuro Fujita): Add support for importing statistics from remote servers`; `f16f5d608ca (Jeff Davis): GetSubscription(): use per-object memory context` |
| headers-wave3 | `src/include/{libpq,port,foreign,jit,partitioning}/` (composite header skim) | 140 | Peter Eisentraut (26), Nathan Bossart (23), Thomas Munro (14), Tom Lane (13) | Tom Lane (19), John Naylor (13), Andres Freund (10), Chao Li (10) | `112faf1378e (Fujii Masao): Log remote NOTICE, WARNING, and similar messages using ereport()`; `fbc57f2bc2e (John Naylor): Compute CRC32C on ARM using the Crypto Extension where available`; `7d8f5957792 (Tom Lane): Create infrastructure to reliably prevent leakage of PGresults` |
| jit | `src/backend/jit/`, `src/include/jit/` | 52 | Thomas Munro (12), Peter Eisentraut (8), Tom Lane (7), David Rowley (7) | Andres Freund (7), Tom Lane (5), Andreas Karlsson (4), Álvaro Herrera (3) | `6911f80379d (David Rowley): Fix incorrect zero extension of Datum in JIT tuple deform code`; `9044fc1 (Thomas Munro): Monkey-patch LLVM code to fix ARM relocation bug` (from committer-map) |
| libpq-backend | `src/backend/libpq/`, `src/include/libpq/` | 106 | Peter Eisentraut (31), Daniel Gustafsson (16), Tom Lane (14), Nathan Bossart (9) | Jacob Champion (11), Daniel Gustafsson (11), Tom Lane (10), Andres Freund (10) | `b3f0be7 (Daniel Gustafsson): Add support for OAUTHBEARER SASL mechanism` (from committer-map); `4f43302 (Daniel Gustafsson): ssl: Serverside SNI support for libpq` |
| main | `src/backend/main/` | 10 | Bruce Momjian (2), Tom Lane (2), Peter Eisentraut (2), Jeff Davis (1) | Peter Eisentraut (3), Heikki Linnakangas (1), Greg Sabino Mullane (1), Álvaro Herrera (1) | `d4baa327a1c (Tom Lane): Avoid possible crash within libsanitizer`; `5e6e42e44fe (Jeff Davis): Force LC_COLLATE to C in postmaster` |
| optimizer | `src/backend/optimizer/`, `src/include/optimizer/` | 281 | Richard Guo (85), Tom Lane (40), David Rowley (33), Robert Haas (25) | Tom Lane (40), David Rowley (23), Andrei Lepikhov (23), Tender Wang (18) | `a1b754558ae (Richard Guo): Consider opfamily and collation when removing redundant GROUP BY columns`; `f41ab51573a (Richard Guo): Teach planner to transform "x IS [NOT] DISTINCT FROM NULL" to a NullTest`; `b8a1bdc458e (Tom Lane): Fix "variable not found in subplan target lists" in semijoin de-duplication` |
| parser-and-rewrite | `src/backend/{parser,rewrite}/`, `src/include/{parser,rewrite}/` | 203 | Peter Eisentraut (51), Tom Lane (36), Álvaro Herrera (20), Michael Paquier (15) | Jian He (24), Peter Eisentraut (14), Álvaro Herrera (14), Tom Lane (13) | `81ce602d48e (Fujii Masao): Make CREATE TABLE LIKE copy comments on NOT NULL constraints when requested`; `5548a969b65 (Dean Rasheed): Fix UPDATE/DELETE ... WHERE CURRENT OF on a table with virtual columns`; `487cf2cbd2f (Andrew Dunstan): Extend DomainHasConstraints() to optionally check constraint volatility` |
| partitioning | `src/backend/partitioning/`, `src/include/partitioning/` | 34 | Alexander Korotkov (9), Peter Eisentraut (7), Amit Langote (4), Tom Lane (3) | Alexander Korotkov (6), Tomas Vondra (4), Robert Haas (4), Jian He (3) | `0392fb900eb (Alexander Korotkov): Revert "Reject degenerate SPLIT PARTITION with DEFAULT partition"`; `4b3d173 (Alexander Korotkov): Implement ALTER TABLE ... SPLIT PARTITION` (from committer-map) |
| port | `src/backend/port/`, `src/include/port/` | 84 | Nathan Bossart (18), Peter Eisentraut (13), Tom Lane (11), John Naylor (11) | John Naylor (12), Tom Lane (8), Heikki Linnakangas (8), Nathan Bossart (7) | `3e2a1496bae (Andrew Dunstan): Rework signal handler infrastructure to pass sender info as argument`; `e2362eb2bd1 (Heikki Linnakangas): Move shmem allocator's fields from PGShmemHeader to its own struct`; `fbc57f2bc2e (John Naylor): Compute CRC32C on ARM using the Crypto Extension where available` |
| replication | `src/backend/replication/`, `src/include/replication/` | 331 | Amit Kapila (87), Peter Eisentraut (39), Fujii Masao (34), Michael Paquier (33) | Amit Kapila (107), Chao Li (44), Masahiko Sawada (32), Hayato Kuroda (30) | `d87d07b7ad3 (Masahiko Sawada): Fix re-distributing previously distributed invalidation messages during logical decoding`; `883a95646a8 (Fujii Masao): Fix stalled lag columns in pg_stat_replication when replay LSN stops advancing`; `50ea4e09b6c (Masahiko Sawada): Use palloc_object/array() in more areas of the logical replication` |
| storage-buffer | `src/backend/storage/buffer/`, `bufmgr.h`, `buf_internals.h`, `buf.h`, `bufpage.h` | 147 | Andres Freund (62), Peter Eisentraut (19), Michael Paquier (12), Noah Misch (7) | Melanie Plageman (22), Andres Freund (20), Noah Misch (13), Matthias van de Meent (8) | `e18b0cb7344 (Michael Paquier): Fix MarkBufferDirtyHint() to not call GetBufferDescriptor() for local buffers`; `c75ebc657ff (Andres Freund): bufmgr: Allow some buffer state modifications while holding header lock`; `ff219c19878 (Andres Freund): bufmgr: Make definitions related to buffer descriptor easier to modify` |
| storage-ipc | `src/backend/storage/ipc/` + 17 IPC headers (`shmem.h`, `ipc.h`, `sinval.h`, `latch.h`, `dsm*.h`, `procsignal.h`, `procarray.h`, `shm_mq.h`, etc.) | 154 | Heikki Linnakangas (50), Peter Eisentraut (17), Nathan Bossart (15), Álvaro Herrera (11) | Andres Freund (22), Chao Li (14), Matthias van de Meent (12), Ashutosh Bapat (12) | `2dd506b859c (Nathan Bossart): Revert "Teach DSM registry to ERROR if attaching to an uninitialized entry"`; `3e2a1496bae (Andrew Dunstan): Rework signal handler infrastructure to pass sender info as argument`; `01a80f06214 (Álvaro Herrera): Revert "Allow logical replication snapshots to be database-specific"` |
| storage-lmgr | `src/backend/storage/lmgr/` + lock/lwlock/proc/predicate/CV headers | 156 | Heikki Linnakangas (49), Peter Eisentraut (16), Michael Paquier (15), Nathan Bossart (14) | Andres Freund (20), Matthias van de Meent (11), Ashutosh Bapat (11), Michael Paquier (10) | `3fd05777282 (Heikki Linnakangas): Refactor PredicateLockShmemInit to not reuse var for different things`; `fd6ecbfa75f (Fujii Masao): Ensure "still waiting on lock" message is logged only once per wait`; `ec317440716 (Álvaro Herrera): Replace literal 0 with InvalidXLogRecPtr for XLogRecPtr assignments` |
| tcop | `src/backend/tcop/`, `src/include/tcop/` | 107 | Heikki Linnakangas (20), Peter Eisentraut (15), Michael Paquier (14), Álvaro Herrera (9) | Tom Lane (12), Michael Paquier (11), Daniel Gustafsson (9), Chao Li (8) | `2c16deee2f7 (Andres Freund): instrumentation: Allocate query level instrumentation in ExecutorStart`; `b63f25bddfe (Michael Paquier): Fix unbounded recursive handling of SSL/GSS in ProcessStartupPacket()`; `910690415b6 (Michael Paquier): Revert "Drop unnamed portal immediately after execution to completion"` |
| utils-cache | `src/backend/utils/cache/` + 13 cache headers (`catcache.h`, `syscache.h`, `relcache.h`, `plancache.h`, `typcache.h`, `inval.h`, etc.) | 127 | Peter Eisentraut (35), Michael Paquier (13), Tom Lane (12), Álvaro Herrera (10) | Tom Lane (13), Andres Freund (11), Michael Paquier (9), Jian He (9) | `0dca5d6 (Tom Lane): Change SQL-language functions to use the plan cache` (from committer-map); `64bf53dd61e (Noah Misch): Revisit cosmetics of "For inplace update, send nontransactional invalidations."` |
| utils-mmgr | `src/backend/utils/mmgr/` + mmgr headers (`palloc.h`, `memutils*.h`, `dsa.h`, `portal.h`, `freepage.h`, `memnodes.h`) | 59 | Tom Lane (14), Peter Eisentraut (11), Michael Paquier (6), Nathan Bossart (6) | Andres Freund (6), Chao Li (4), Michael Paquier (4), Sami Imseih (3) | `7d8f5957792 (Tom Lane): Create infrastructure to reliably prevent leakage of PGresults`; `46593aea0a5 (Tom Lane): Make palloc_array() and friends safe against integer overflow`; `4da2afd01f9 (Michael Paquier): Fix size underestimation of DSA pagemap for odd-sized segments` |

## Subsystem ownership clusters

Grouping subsystems by who actually drives them in the 24mo window. A cluster
is "a set of subsystems with substantially overlapping top-4 committers OR
top-4 reviewers." These groupings are how a patch author should think about
who will weigh in on a change.

### 1. Storage / AIO / shmem cluster — Andres Freund + Heikki Linnakangas

Subsystems: `storage-buffer`, `storage-ipc`, `storage-lmgr`, partly
`access-transam`, partly `access-heap`.

- **Driving committers:** Andres Freund (storage-buffer 62; storage-lmgr 13;
  smaller elsewhere) and Heikki Linnakangas (storage-ipc 50; storage-lmgr
  49; access-transam 33).
- **Recurring reviewers:** Andres Freund himself (when he isn't pushing he
  reviews — 20 on storage-lmgr, 22 on storage-ipc, 25 on executor),
  Melanie Plageman (22 storage-buffer, 42 access-heap), Noah Misch (13
  storage-buffer, 14 access-heap), Matthias van de Meent (8-12 across
  storage-buffer / storage-ipc / storage-lmgr / nbtree), Nazir Bilal Yavuz
  (per `contributor-map.md` — storage + test-modules-heavy).
- **Pattern:** Andres pushes the AIO infrastructure (`da72269`, `93bc3d7`,
  `c75ebc657ff`, `ff219c19878`, `c819d1017dd`) and Heikki pushes the shmem
  rework (`9b5acad`, `e2362eb2bd1`, `3fd05777282`); they cross-review each
  other and have a stable group of secondary reviewers.

### 2. Logical-replication cluster — Amit Kapila + the Fujitsu/EDB pool

Subsystem: `replication` (and some `access-transam` for the WAL-decoding side).

- **Driving committer:** Amit Kapila (87 commits in 24mo on `replication`,
  and 107 Reviewed-by appearances on the SAME subsystem — meaning he reviews
  almost every replication patch he doesn't push, AND most of the ones he
  does push). Secondary committers: Peter Eisentraut (39), Fujii Masao (34),
  Masahiko Sawada (28).
- **Reviewer pool is tight:** Amit Kapila (107), Chao Li (44), Masahiko
  Sawada (32), Hayato Kuroda (30), Peter Smith (30), shveta malik (25).
  Six names cover essentially the whole reviewing in this subsystem — the
  tightest reviewer pool in the corpus.
- **Pattern matches the committer-map's "Amit Kapila's review pool is the
  tightest"** finding: this is a real, tightly-bounded subteam (mostly
  Fujitsu/EDB) — substantively different from how the rest of PG reviews.

### 3. Optimizer cluster — Richard Guo + Tom Lane + David Rowley

Subsystem: `optimizer` (and tendrils into `executor`, `parser-and-rewrite`).

- **Driving committer:** Richard Guo (85 commits in 24mo) — nearly 2× the
  runner-up. Co-leads: Tom Lane (40), David Rowley (33), Robert Haas (25).
- **Reviewer pool:** Tom Lane (40 R-by on optimizer alone — he reviews every
  Richard Guo patch), David Rowley (23), Andrei Lepikhov (23), Tender Wang
  (18), Richard Guo himself (16 — i.e. self-review on his pushed patches).
- **Pattern:** Richard pushes feature-level planner work (Eager Aggregation,
  semijoin de-duplication, GROUP BY collation, IS NULL transforms); Tom
  reviews; David and Andrei provide specialist depth.

### 4. Heap / vacuum cluster — Melanie Plageman

Subsystem: `access-heap`.

- **Driving committer:** Melanie Plageman (75 commits in 24mo) is the clear
  owner; Peter Eisentraut (19) and Álvaro Herrera (18) trail far behind.
- **Reviewer pool:** Andres Freund (42), Chao Li (29), Kirill Reshke (22),
  Masahiko Sawada (13), Tomas Vondra (12).
- **Pattern:** Almost every recent heap/vacuum landmark is hers: read-stream
  integration, aggressive-vacuum eager scanning, prune-hint clearing. Her
  reviewer cluster overlaps strongly with the AIO/storage cluster (Andres,
  Noah Misch, Matthias van de Meent) — consistent with vacuum + read-stream
  being on the AIO boundary.

### 5. nbtree cluster — Peter Geoghegan (single owner)

Subsystem: `access-nbtree`.

- **Driving committer:** Peter Geoghegan (78 commits in 24mo) overwhelmingly
  dominates; second place Peter Eisentraut (22) is mostly mechanical
  const/Datum cleanups.
- **Reviewer pool:** Matthias van de Meent (12), Tomas Vondra (11), Chao Li
  (9), Peter Geoghegan (6 self), Masahiro Ikeda (6), Heikki Linnakangas (5).
- **Pattern:** nbtree is the textbook single-owner subsystem — Peter
  Geoghegan pushes feature work (skip scan, page deletion, preprocessing
  rewrite), and the reviewer pool is small but specialist. See bus-factor
  flag below.

### 6. Cross-cutting infra cluster — Peter Eisentraut + Tom Lane

Subsystems: `parser-and-rewrite`, `utils-cache`, `utils-mmgr`, `executor`,
`headers-wave3`, plus heavy presence in everything else.

- **Pattern:** Peter Eisentraut pushes type-system / const-correctness /
  header refactors (`8a27d418f8f`, `7724cb9935a`, `137d05df2f2`) that touch
  many subsystems; Tom Lane pushes correctness/build fixes (`b8a1bdc458e`,
  `8191937082a`, `46593aea0a5`) similarly broadly. Their joint footprint is
  why Peter and Tom appear in the top-4 committers of 13 of the 20
  subsystems documented here, and Tom appears in the top-4 reviewers of 11.
- **This is the corpus's confirmation that Tom and Peter are the
  universal-coverage maintainers.** The `committer-map.md` lifetime-volume
  view already suggested this (Tom 16,794 lifetime; Peter 6,483 combined);
  this cross-cut shows the per-subsystem mechanism.

### 7. Postmaster / process-startup cluster — small, distributed

Subsystems: `main`, `tcop`, `port`, parts of `libpq-backend`.

- **Pattern:** No single dominant committer. Heikki Linnakangas (20 on tcop,
  + heavy in storage-ipc), Nathan Bossart (18 on port, 15 on storage-ipc),
  Peter Eisentraut as the cross-cut infra contributor. Andrew Dunstan
  appears once with a landmark (`3e2a1496bae`: signal handler rework).
- **Reviewers across this cluster:** Tom Lane is the universal reviewer; John
  Naylor specifically reviews port (12 R-by) and CRC/SIMD work.

### 8. TLS / OAuth / libpq cluster — Daniel Gustafsson + Jacob Champion

Subsystem: `libpq-backend` (and shared parts of `tcop`).

- **Pattern:** Two committers, three combined Reviewed-by counts dominating
  this subsystem (Daniel 16 commits + 11 R-by; Jacob 7 + 11 R-by). Per
  `contributor-map.md`: "Daniel credits Jacob 13× on his pushed commits" —
  i.e. they cross-review each other heavily. This is a coherent 2-person
  subteam, very different from the broader-cluster norm.

## Bus-factor / single-point-of-ownership flags

Subsystems where ONE committer pushes >50% of the 24mo work AND there is no
clear runner-up at >25%:

| Subsystem | Top committer | Their 24mo % | Runner-up % | Risk |
|---|---|---:|---:|---|
| access-nbtree | Peter Geoghegan (78/140) | 55.7% | Peter Eisentraut, 22/140 = 15.7% (mostly mechanical) | **HIGH.** Substantive nbtree work is essentially one person. The reviewer pool (Matthias van de Meent + Tomas Vondra + Heikki Linnakangas) is real but small; if Peter were unavailable, sustaining velocity on skip-scan / preprocessing / dedup work would be hard. |
| replication | Amit Kapila (87/331) | 26.3%; but combined with the rep subteam (Sawada + Kuroda + Smith + shveta + Hou) the cluster reaches ~75% | other clusters trail far behind | **MEDIUM.** No single committer dominates, but a single FUJITSU/EDB-affiliated subteam does. Healthy within the subteam; brittle if it shifted. |
| access-heap | Melanie Plageman (75/210) | 35.7% | Peter Eisentraut 19/210 = 9% (mostly mechanical) | **MEDIUM-HIGH.** Vacuum / read-stream / prune work is overwhelmingly hers. Andres Freund (11 commits) is the only other person doing substantive heap work; he's busy on AIO. |
| storage-buffer | Andres Freund (62/147) | 42.2% | Peter Eisentraut 19/147 = 12.9% (mechanical) | **HIGH.** AIO + buffer-state work is Andres's. Melanie Plageman + Noah Misch + Heikki Linnakangas all review heavily but only Melanie has pushed comparable substantive commits (6). |
| optimizer | Richard Guo (85/281) | 30.2% | Tom Lane 40/281 = 14.2% | **LOW-MEDIUM.** Richard is dominant but Tom + David Rowley + Robert Haas all push real planner work; the reviewer pool is broad. |
| storage-ipc | Heikki Linnakangas (50/154) | 32.5% | Peter Eisentraut 17/154 = 11% (mechanical), Nathan Bossart 15 = 9.7% | **MEDIUM.** Heikki is driving the shmem rework; no single secondary committer is doing comparable work. |
| storage-lmgr | Heikki Linnakangas (49/156) | 31.4% | Peter Eisentraut 16/156 = 10.3% (mechanical) | **MEDIUM.** Same pattern as storage-ipc. |
| jit | Thomas Munro (12/52) | 23.1% | spread evenly | **LOW.** Subsystem is small and stable; no rapid evolution requiring sustained ownership. |

Subsystems with healthy multi-owner pictures (no bus-factor concern):
`access-transam` (Paquier + Linnakangas + Korotkov + Eisentraut all push
substantively), `executor` (Tom + Peter + David + Amit Langote balanced),
`parser-and-rewrite` (Peter + Tom + Álvaro + Paquier balanced).

## Sharp differences vs. the committer-map heatmap

The `committer-map.md` per-subsystem heatmap counted by `src/backend/<X>/`
prefix only. This map narrows to the exact paths each subsystem doc claims.
A few places where the picture differs:

1. **access-heap looks Melanie-dominated in this cut (75/210 = 35.7%); in
   the broader `src/backend/access/` heatmap it's flatter** (Michael Paquier
   101 across all access, Peter Geoghegan 87 across all access, Melanie 83
   across all access). Narrowing to `heap/` specifically reveals Melanie's
   true dominance. The broader heatmap was diluted by nbtree, transam,
   GIN/GiST work.

2. **`storage-ipc` shows Heikki Linnakangas at 50 commits in 24mo;** the
   broader `src/backend/storage/` heatmap counted him at 82 across storage.
   So ~60% of his recent storage work is in the IPC subdir — the shmem
   allocation rewrite (`9b5acad`, `e2362eb2bd1`, `c6d55714ba4`).

3. **`access-transam` puts Michael Paquier (67) ahead of Heikki Linnakangas
   (33);** the broader access heatmap had Michael at 101 across all access.
   Transam is therefore where ~66% of his recent access work lives — WAL
   correctness fixes, recovery signal handling, checkpoint-record errors.

4. **`tcop` reviewer top is Tom Lane (12), but the cluster is small.** Tom's
   universal-reviewer signal is at risk of over-counting any subsystem where
   his absolute review count is small. Same for utils-cache (Tom Lane top
   reviewer at 13). Read these "Tom Lane is the top reviewer of X" lines as
   "Tom Lane reviews everything; he reviewed X this many times in 24mo,"
   not "Tom Lane specifically owns the review of X."

5. **`foreign/` has almost no recent activity** (16 commits in 24mo). The
   subsystem doc's nominal maintainer is Etsuro Fujita per the
   committer-map; but the actual top committer in the 24mo window is Jeff
   Davis (5), with Etsuro at 1. Etsuro is still the FDW substantive owner
   when there IS work; there just isn't much. **postgres_fdw** (in
   `contrib/`, NOT in this subsystem) is where Etsuro's work actually lives
   and that's outside the documented-subsystem set.

## Methodology + caveats

- **Path mapping** is taken from each subsystem doc's front matter
  (`Source path:` / `Header path:` / `Paths:` headers). Where a doc cites
  many headers, all are included. The `headers-wave3` composite covers
  five subsystems' include dirs simultaneously, which is why its top
  committers look like a Peter Eisentraut/Nathan Bossart/Thomas Munro
  smear rather than the per-subsystem committers.
- **Committer counts** are `git -C source/ log --since="24 months ago"
  --no-merges --pretty='%an' -- <paths>` piped through name canonicalization
  (the same Álvaro / Peter Eisentraut / Fujii Masao rollups used in the
  contributor map).
- **Reviewer counts** are `Reviewed-by:` trailer appearances on the
  path-filtered 24mo commits. The same per-commit dedup and multi-name
  trailer splitter from `contributor-map.md`'s parser. **Cross-cutting
  reviewers (Tom Lane, Chao Li) are over-represented on small subsystems**
  — they review across the whole tree, so any subsystem they touched at all
  in the window puts them in the top-4 even when their substantive review
  share is small. The `(self)` quirk (committers listing themselves as
  Reviewed-by) shows through too — Amit Kapila's 107 R-by on replication is
  partly self-credit, exactly as the committer-map's pairings section
  documents.
- **Recent landmark commits** picks the last 12 months of commits touching
  the subsystem, filters out commits whose subject contains
  pgindent/copyright/typedefs/Datum-const/mechanical-refactor markers, and
  takes the 3 with the longest remaining subjects. Where the unfiltered
  pick was dominated by mechanical commits (e.g. nbtree, partitioning, jit,
  utils-cache, libpq-backend), the table reaches back to the
  `committer-map.md` "Notable commits" column for a more representative
  landmark — those are flagged inline.
- **Subsystem-to-path mapping has overlaps.** `access-heap` includes
  `htup.h` which `executor` and `storage-buffer` also touch via includes;
  `storage-buffer` and `storage-ipc` both touch `bufmgr.h` / `shmem.h`
  cross-references. These commits get double-counted into each subsystem.
  This is intentional — a commit that's load-bearing for two subsystems
  *should* show up in both ownership pictures.
- **What this map does NOT capture:**
  - Pre-2024-06 ownership patterns. A subsystem that swapped owners in 2024
    will show the new owner only.
  - Mailing-list ownership signal (people who shape a subsystem on
    pgsql-hackers without committing or being credited in trailers).
  - Review SUBSTANCE. A one-line "LGTM" and a 50-comment deep review are
    one R-by appearance each. Deliverable #3 (per-committer persona deep
    dives) is where review style gets characterized.
  - Anything personality / employer-affiliation. Inferable in places
    (Fujitsu cluster around Amit Kapila is the clearest), but explicit
    affiliation tagging is a separate Phase B follow-up.
  - Contributors who DO submit patches via author-trailers but rarely get
    them credited in the subsystem-path-filtered commits. The
    `contributor-map.md` author/co-author counts catch these globally; this
    map only counts trailer appearances on subsystem-touching commits.
- **Source command (reproducibility):**
  ```bash
  # Per subsystem, with <paths> drawn from each subsystem doc's front matter:
  git -C source/ log --since="24 months ago" --no-merges \
      --pretty='%H%n%B%n==SEP==' -- <paths> > /tmp/<sub>_commits.txt
  # then a Python pass that parses Reviewed-by trailers, splits multi-name
  # values, applies the name-canonicalization rollups, dedups per commit per
  # trailer type, and aggregates.
  ```
  Parser: `/tmp/owner_query.py` (this session). Driver:
  `/tmp/all_owners.py`. Both follow the same trailer-split + name-rollup
  conventions documented in `contributor-map.md`'s Methodology.

## Cross-references

- `knowledge/personas/committer-map.md` — the global committer-volume table
  this map is path-narrowed against.
- `knowledge/personas/contributor-map.md` — the global trailer-mining map
  that supplied reviewer / author / reporter pool data.
- `knowledge/subsystems/*.md` — each subsystem doc now carries an "Owners
  (as of 2026-06-12)" block at the top with the same data narrowed to
  its scope and a back-link here.
- Future Phase B deliverable #3 (per-committer deep personas) will
  characterize review STYLE for the top-cluster names called out above
  (Andres Freund, Tom Lane, Amit Kapila, Heikki Linnakangas, etc.).
