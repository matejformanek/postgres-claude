# PostgreSQL committer map

- **Last verified:** 2026-06-11
- **Source pin:** e18b0cb7344
- **Method:** `git log` mining of the upstream PostgreSQL master branch via the
  read-only `source/` clone. No external network calls.

## What this is

Foundation doc for Phase B (developer personas). For each significant committer
on the PG master tree, this captures: identity, how active, what they work on
(inferred from path-of-files-touched), and a small sample of recent landmark
commits (by lines-changed in the last 24 months).

Phase B follow-up deliverables (NOT in this doc):
- Per-committer deep persona docs (review style, common pushback, patterns).
- Reviewer activity from pgsql-hackers archives.
- Domain-ownership map keyed by subsystem (a tighter version of the heatmap
  below, with rationale per assignment).

## Important caveat up front: this counts COMMITTERS, not all contributors

PostgreSQL uses a strict committer/author distinction. Only the small set of
people with commit bits push changes. Non-committer contributions land via a
committer who picks up the patch from the mailing list and credits the original
author inside the commit message body (`Author:`, `Reviewed-by:` trailers).
That author attribution is NOT visible in `%an`/`%ae`; `git log --pretty=%an`
shows the committer who pushed.

So when this doc says "Tom Lane has 16,794 lifetime commits" it means he pushed
16,794 commits. Many of those embed work by dozens of other contributors. The
true contributor base is much larger than the 59 distinct committer identities
that show up in `%an` (see Long-tail observation below).

Phase B follow-ups will pull `Author:` trailers from commit bodies to surface
the broader contributor base; that's out of scope here.

## Top committers (last 24 months)

Window: 2024-06-11 .. 2026-06-11 (5,752 commits, 33 distinct committers).

Sorted by commits-24mo. "Primary domain" is inferred from the top file paths
touched in the window, not declared. "Notable commits" picks 1-2 large-impact
commits (by lines changed) from the same window — these are landmarks, not
necessarily their most representative work.

| Author | Email | Commits 24mo | Commits 12mo | Primary domain | Top 3 paths touched | Notable commits |
|---|---|---:|---:|---|---|---|
| Michael Paquier | michael@paquier.xyz | 723 | 406 | broad maintenance: utils + access + test infra | src/backend/utils, src/backend/access, src/test | `ba97bf9` Add support for "exprs" in pg_restore_extended_stats; `1b105f9` Use palloc_object()/palloc_array() in backend code |
| Peter Eisentraut | peter@eisentraut.org | 719 | 365 | broad: utils + access + commands + includes; SQL/PGQ owner | src/backend/utils, src/backend/access, src/include | `2f094e7` SQL Property Graph Queries (SQL/PGQ); translation-update batches |
| Tom Lane | tgl@sss.pgh.pa.us | 661 | 313 | broad: utils + executor + optimizer + commands + PL | src/backend/utils, src/backend/snowball, src/backend/commands | `0dca5d6` Change SQL-language functions to use the plan cache; recurring Snowball updates |
| Nathan Bossart | nathan@postgresql.org | 315 | 162 | utils + pg_upgrade + arch-specific (popcount, CRC) + src/port | src/backend/utils, src/bin, src/port | `626d723` pg_upgrade: Add --swap for faster file transfer; `79e232c` Move x86-64-specific popcount code |
| Heikki Linnakangas | heikki.linnakangas@iki.fi | 292 | 154 | storage + postmaster + access; AIO/shmem rework | src/backend/storage, src/backend/access, src/backend/postmaster | `393e0d2` Split WaitEventSet to separate file; `9b5acad` Convert all remaining subsystems to new shmem allocation API; `bd8d9c9` Widen MultiXactOffset to 64 bits |
| Fujii Masao | fujii@postgresql.org | 232 | 169 | replication + psql/docs | src/backend/replication, doc/src, src/test | `a8f45de` Add wal_sender_shutdown_timeout GUC; `4eada20` Add has_largeobject_privilege function |
| Andres Freund | andres@anarazel.de | 227 | 107 | storage; asynchronous I/O (AIO); CI infra | src/backend/storage, src/include, src/test | `da72269` aio: Add core asynchronous I/O infrastructure; `93bc3d7` aio: Add test_aio module; `9c12606` ci: Add GitHub Actions based CI |
| Daniel Gustafsson | dgustafsson@postgresql.org | 192 | 88 | TLS/OAuth/libpq/postmaster + docs | src/backend/utils, src/backend/postmaster, src/backend/libpq | `b3f0be7` Add support for OAUTHBEARER SASL mechanism; `f19c0ec` Online enabling/disabling of data checksums; `4f43302` ssl: Serverside SNI support for libpq |
| David Rowley | drowley@postgresql.org | 187 | 86 | executor + optimizer; performance | src/backend/executor, src/backend/utils, src/backend/access | `c456e39` Optimize tuple deformation; `adf97c1` Speed up Hash Join by making ExprStates support hashing |
| Jeff Davis | jdavis@postgresql.org | 185 | 72 | utils (collations + ICU + Unicode), statistics | src/backend/utils, src/backend/statistics, src/backend/executor | `27bdec0` Optimization for lower/upper/casefold; `286a365` Support Unicode full case mapping and conversion; `4e7f62b` Add Unicode case folding |
| Amit Kapila | akapila@postgresql.org | 185 | 96 | logical replication + publications + sequences sync | src/backend/replication, src/backend/utils, src/backend/commands | `228c370` Preserve conflict-relevant data during logical replication; `5509055` Add sequence synchronization for logical replication; `7054186` Replicate generated columns |
| Álvaro Herrera | alvherre@kurilemu.de | 179 | 171 | commands + replication + parser; constraints/inheritance | src/backend/utils, src/backend/access, src/backend/commands | (Same identity as `alvherre@alvh.no-ip.org`; email changed mid-2024. See note below.) |
| Bruce Momjian | bruce@momjian.us | 168 | 72 | release notes + copyright-year bumps; docs | src/backend/utils, src/backend/access, src/backend/storage | `451c439` Update copyright for 2026; `a724c78` doc: first draft of PG 18 release notes |
| Alexander Korotkov | akorotkov@postgresql.org | 141 | 73 | access (indexes) + partitioning + optimizer | src/backend/access, src/backend/optimizer, src/backend/utils | `4b3d173` Implement ALTER TABLE ... SPLIT PARTITION; `f2e4cc4` Implement ALTER TABLE ... MERGE PARTITIONS; `fc069a3` Implement Self-Join Elimination |
| Melanie Plageman | melanieplageman@gmail.com | 121 | 65 | access (heap + vacuum); read-stream API integration | src/backend/access, src/backend/executor, src/include | `052026c` Eagerly scan all-visible pages to amortize aggressive vacuum; `2b73a8c` BitmapHeapScan uses the read stream API |
| Robert Haas | rhaas@postgresql.org | 117 | 66 | optimizer + planning advice contrib + commands | src/backend/optimizer, contrib/pg_plan_advice, src/backend/commands | `5883ff3` Add pg_plan_advice contrib module; `e8ec19a` Add pg_stash_advice contrib module; `8d5ceb1` pg_overexplain: additional EXPLAIN options |
| Masahiko Sawada | msawada@postgresql.org | 114 | 65 | replication + parallel vacuum + COPY | src/backend/replication, src/backend/utils, src/backend/access | `67c2097` Toggle logical decoding dynamically based on logical slot presence; `1ff3180` Allow autovacuum to use parallel vacuum workers; `7717f63` Refactor COPY FROM to use format callbacks |
| Thomas Munro | tmunro@postgresql.org | 113 | 40 | storage (read stream) + JIT + AIO worker tuning + encoding | src/backend/utils, src/backend/storage, src/backend/jit | `77645d4` Remove MULE_INTERNAL encoding; `d1c01b7` aio: Adjust I/O worker pool automatically; `9044fc1` Monkey-patch LLVM code to fix ARM relocation bug |
| Richard Guo | rguo@postgresql.org | 111 | 63 | optimizer (planner internals) | src/backend/optimizer, src/test, src/backend/utils | `8e11859` Implement Eager Aggregation; `24225ad` Pathify RHS unique-ification for semijoin planning; `383eb21` Convert NOT IN sublinks to anti-joins when safe |
| Andrew Dunstan | andrew@dunslane.net | 105 | 59 | src/bin (pg_dump) + test infra + docs | src/test, src/bin, src/backend | `4e23c9e` Split func.sgml into more manageable pieces; `763aaa0` Add non-text output formats to pg_dumpall; `4a18907` Add built-in fuzzing harnesses for security testing |
| Peter Geoghegan | pg@bowt.ie | 92 | 33 | access (nbtree); index scan; skip scan | src/backend/access, src/include, doc/src | `65d6acb` Relocate _bt_readpage and related functions; `597b1ff` Move nbtree preprocessing into new .c file; `92fe23d` Add nbtree skip scan optimization |
| Noah Misch | noah@leadboat.com | 87 | 20 | utils + access + commands; durability/correctness fixes; security | src/backend/utils, src/backend/access, src/test | `a07e03f` Fix data loss at inplace update after heap_update; `46b4f5c` Fix SQL injection in logical replication origin checks; `aac2c9b` For inplace update durability, make heap_update() callers wait |
| Amit Langote | amitlan@postgresql.org | 82 | 30 | executor + commands + parser; partitioning + FK fast path | src/backend/executor, src/backend/utils, src/backend/commands | `525392d` Don't lock partitions pruned by initial pruning; `b7b27eb` Optimize fast-path FK checks with batched index probes; `2da86c1` Add fast path for foreign key constraint checks |
| Tomas Vondra | tomas.vondra@postgresql.org | 81 | 32 | storage + executor + amcheck + contrib; EXPLAIN IO instrumentation | src/backend/utils, src/backend/storage, contrib/amcheck | `8492feb` Allow parallel CREATE INDEX for GIN indexes; `14ffaec` amcheck: Add gin_index_check; `ba2a3c2` Add pg_buffercache_numa view with NUMA node info |
| John Naylor | john.naylor@postgresql.org | 63 | 43 | utils + src/port + encoding tables + SIMD CRC | src/backend/utils, src/include, src/port | `48566180` Generate EUC_CN mappings from gb18030-2022; `ef3c3cf` Perform radix sort on SortTuples with pass-by-value Datums; `3c6e8c1` Compute CRC32C using AVX-512 instructions where available |
| Jacob Champion | jchampion@postgresql.org | 63 | 54 | libpq + oauth + interfaces | src/interfaces, src/test, doc/src | `b0635bf` oauth: Move the builtin flow into a separate module; `6225403` libpq-oauth: Use the PGoauthBearerRequestV2 API; `b977bd3` oauth: Allow validators to register custom HBA options |
| Álvaro Herrera | alvherre@alvh.no-ip.org | 60 | — | (older identity; merge with `@kurilemu.de`) | (see merged row above) | (merged) |
| Dean Rasheed | dean.a.rasheed@gmail.com | 56 | 33 | parser + optimizer + executor; RETURNING/RLS/numeric | src/test, src/backend/utils, src/backend/executor | `80feb72` Add OLD/NEW support to RETURNING in DML queries; `88327092` Add support for INSERT ... ON CONFLICT DO SELECT; `2242495` Fix security checks in selectivity estimation |
| Alvaro Herrera (ASCII) | alvherre@alvh.no-ip.org | 31 | — | (third spelling of same identity; ASCII without accent) | (see merged row above) | (merged) |
| Etsuro Fujita | efujita@postgresql.org | 21 | 15 | postgres_fdw maintainer | contrib/postgres_fdw, src/backend, src/include | `aa1f93a` postgres_fdw: Replace buffers in RemoteAttributeMapping with pointers; `5107398` Fix deparsing of remote column names in stats import |
| Tatsuo Ishii | ishii@postgresql.org | 19 | 9 | executor + window functions | src/backend, doc/src, src/test | `26269fe` Fix IGNORE NULLS nullness cache for volatile window arguments; `2d7b247` Fix multi WinGetFuncArgInFrame/Partition calls with IGNORE NULLS |
| Magnus Hagander | magnus@hagander.net | 6 | 2 | docs + small psql tweaks (light recent activity) | src/bin, doc/src, src/test | `d3ba50d` docs: Fix protocol version 3.2 message format of CancelRequest |
| Joe Conway | mail@joeconway.com | 4 | 3 | release stamping + pgperltidy + housekeeping | src/test, src/bin, src/include | `2652835` Stamp HEAD as 19devel; `9c5b9a2` Do pre-release housekeeping on catalog data |

**Note on Álvaro Herrera:** appears under three spelling/email combinations in the 24mo window —
`Álvaro Herrera <alvherre@kurilemu.de>` (179), `Álvaro Herrera <alvherre@alvh.no-ip.org>` (60),
and `Alvaro Herrera <alvherre@alvh.no-ip.org>` (31, ASCII spelling). Same person; the email
switch to `@kurilemu.de` happened mid-2024. Effective 24mo commit count: ~270, which would
rank him 11th instead of 12th in the list above. The repo's `.mailmap` only normalises the
accented name with the new email and does not merge the three identities.

## Top committers (all-time, top 30 shown)

59 distinct committer identities total. Top 30:

| Rank | Author | Email | Lifetime commits |
|---:|---|---|---:|
| 1 | Tom Lane | tgl@sss.pgh.pa.us | 16,794 |
| 2 | Bruce Momjian | bruce@momjian.us | 14,103 |
| 3 | Peter Eisentraut | peter_e@gmx.net | 4,193 |
| 4 | Robert Haas | rhaas@postgresql.org | 2,609 |
| 5 | Michael Paquier | michael@paquier.xyz | 2,476 |
| 6 | Peter Eisentraut | peter@eisentraut.org | 2,290 |
| 7 | Alvaro Herrera | alvherre@alvh.no-ip.org | 1,950 |
| 8 | Heikki Linnakangas | heikki.linnakangas@iki.fi | 1,890 |
| 9 | Andres Freund | andres@anarazel.de | 1,547 |
| 10 | Marc G. Fournier | scrappy@hub.org | 1,491 |
| 11 | Thomas G. Lockhart | lockhart@fourpalms.org | 1,078 |
| 12 | Andrew Dunstan | andrew@dunslane.net | 997 |
| 13 | Magnus Hagander | magnus@hagander.net | 928 |
| 14 | Michael Meskes | meskes@postgresql.org | 766 |
| 15 | Fujii Masao | fujii@postgresql.org | 748 |
| 16 | Amit Kapila | akapila@postgresql.org | 689 |
| 17 | Thomas Munro | tmunro@postgresql.org | 641 |
| 18 | Neil Conway | neilc@samurai.com | 616 |
| 19 | David Rowley | drowley@postgresql.org | 576 |
| 20 | Noah Misch | noah@leadboat.com | 552 |
| 21 | Vadim B. Mikheev | vadim4o@yahoo.com | 519 |
| 22 | Peter Geoghegan | pg@bowt.ie | 510 |
| 23 | Alexander Korotkov | akorotkov@postgresql.org | 496 |
| 24 | Daniel Gustafsson | dgustafsson@postgresql.org | 466 |
| 25 | Simon Riggs | simon@2ndQuadrant.com | 453 |
| 26 | Tatsuo Ishii | ishii@postgresql.org | 450 |
| 27 | Nathan Bossart | nathan@postgresql.org | 429 |
| 28 | Jeff Davis | jdavis@postgresql.org | 403 |
| 29 | Teodor Sigaev | teodor@sigaev.ru | 399 |
| 30 | Tomas Vondra | tomas.vondra@postgresql.org | 361 |

Notes:
- **Peter Eisentraut** appears twice (rows 3 and 6) under two distinct email
  addresses, summing to 6,483 — that would put him third overall and place him
  just ahead of Robert Haas.
- The top two (Tom Lane, Bruce Momjian) dominate by a wide margin: together
  they account for ~48% of all-time commit volume on master. Both have been
  active since the late-1990s; their "commit" tally includes a lot of small
  doc/cleanup/whitespace work in addition to feature work.
- Several emeritus / historical committers appear in the top 20 (Marc G.
  Fournier, Thomas G. Lockhart, Neil Conway, Vadim B. Mikheev) but have zero
  commits in the 24mo window.

## Domain-of-activity heatmap

For the active-24mo cohort, top 4 most active committers per subsystem (commit
counts in the 24mo window). "Touched" = the commit modified at least one file
under that subtree. Cross-cutting commits (touching multiple subsystems) count
once per subsystem.

| Subsystem | Top committers (24mo commits touching path) |
|---|---|
| `src/backend/access` | Michael Paquier (101), Peter Geoghegan (87), Melanie Plageman (83), Peter Eisentraut (76), Heikki Linnakangas (51) |
| `src/backend/storage` | Andres Freund (109), Heikki Linnakangas (82), Michael Paquier (51), Peter Eisentraut (42), Thomas Munro (33) |
| `src/backend/executor` | Tom Lane (39), David Rowley (37), Peter Eisentraut (36), Amit Langote (28), Michael Paquier (21) |
| `src/backend/optimizer` | Richard Guo (85), Tom Lane (41), David Rowley (33), Robert Haas (25), Alexander Korotkov (20) |
| `src/backend/replication` | Amit Kapila (86), Peter Eisentraut (38), Fujii Masao (34), Michael Paquier (33), Masahiko Sawada (27) |
| `src/backend/utils` | Michael Paquier (168), Peter Eisentraut (164), Tom Lane (137), Jeff Davis (72), Heikki Linnakangas (55) |
| `src/backend/commands` | Peter Eisentraut (82), Álvaro Herrera (74), Tom Lane (65), Michael Paquier (50), David Rowley (35) |
| `src/backend/parser` | Peter Eisentraut (37), Tom Lane (33), Álvaro Herrera (19), Michael Paquier (14), Amit Langote (14) |
| `src/backend/catalog` | Peter Eisentraut (37), Tom Lane (31), Michael Paquier (28), Amit Kapila (27), Álvaro Herrera (23) |
| `src/backend/libpq` | Peter Eisentraut (24), Daniel Gustafsson (15), Tom Lane (10), Nathan Bossart (6), Michael Paquier (5) |
| `src/backend/postmaster` | Heikki Linnakangas (38), Nathan Bossart (24), Álvaro Herrera (22), Peter Eisentraut (19), Daniel Gustafsson (19) |
| `src/backend/tcop` | Heikki Linnakangas (20), Michael Paquier (14), Peter Eisentraut (12), Álvaro Herrera (9), Tom Lane (7) |
| `src/backend/statistics` | Michael Paquier (28), Jeff Davis (18), Peter Eisentraut (9), Tom Lane (3), Dean Rasheed (3) |
| `src/backend/partitioning` | Alexander Korotkov (9), Peter Eisentraut (6), Amit Langote (4), Tom Lane (3), Michael Paquier (3) |
| `src/backend/nodes` | Peter Eisentraut (17), Álvaro Herrera (8), Tom Lane (8), Michael Paquier (8), David Rowley (6) |
| `contrib` | Peter Eisentraut (90), Michael Paquier (87), Tom Lane (72), Robert Haas (40), Álvaro Herrera (31) |
| `src/bin` | Peter Eisentraut (111), Michael Paquier (96), Tom Lane (92), Nathan Bossart (86), Fujii Masao (53) |
| `src/include` | Peter Eisentraut (196), Michael Paquier (163), Tom Lane (120), Heikki Linnakangas (97), Nathan Bossart (87) |
| `src/interfaces` | Peter Eisentraut (51), Tom Lane (46), Jacob Champion (38), Michael Paquier (30), Daniel Gustafsson (20) |
| `src/test` | Michael Paquier (249), Tom Lane (184), Peter Eisentraut (137), Álvaro Herrera (77), Richard Guo (74) |
| `doc/src/sgml` | Bruce Momjian (156), Michael Paquier (118), Peter Eisentraut (115), Tom Lane (101), Fujii Masao (96) |
| `src/pl` | Tom Lane (43), Peter Eisentraut (39), Michael Paquier (4), Thomas Munro (3), Noah Misch (2) |
| `src/common` | Peter Eisentraut (34), Jeff Davis (12), Tom Lane (9), Michael Paquier (7), Heikki Linnakangas (6) |
| `src/port` | Nathan Bossart (19), Tom Lane (16), John Naylor (16), Peter Eisentraut (12), Thomas Munro (10) |

Sharpest mono-domain ownership (one person disproportionately dominates):
- `src/backend/optimizer` — Richard Guo (85) is nearly 2× the runner-up
  Tom Lane (41). Richard joined as committer in 2024 and his work is
  almost exclusively in the optimizer (155 of his ~208 `src/backend`
  files touched are in `optimizer/`).
- `src/backend/replication` — Amit Kapila (86) is 2.5× runner-up Peter
  Eisentraut (38). Logical replication is clearly his domain.
- `src/backend/storage` — Andres Freund (109) is the top; the recent
  AIO infrastructure (`da7226993fd`, `93bc3d75d8e`) is his.
- `contrib/postgres_fdw` — Etsuro Fujita has 36 of his 41-ish total
  paths in this single directory; he's effectively the FDW maintainer
  even though his 24mo total (21) is modest.

## Recently joined / risen

Committers whose first-ever commit on master is in 2024+ (i.e. new committer
bits) — these are the genuine "rising stars" since 2024:

| Committer | First commit date | First commit | 12mo commits | 24mo commits |
|---|---|---|---:|---:|
| Melanie Plageman | 2024-05-16 | `a3e6c6f9299` BitmapHeapScan: Remove incorrect assert and reset field | 65 | 121 |
| Richard Guo | 2024-06-10 | `3cb19f45a3f` Fix comment about cross-checking the varnullingrels | 63 | 111 |
| Jacob Champion | 2025-04-23 | `005ccae0f2d` oauth: Support Python 3.6 in tests | 54 | 63 |

Each was an active patch-author for years before getting the bit; the timestamp
above is when they began committing under their own name, not when they began
contributing.

Within their active window:
- Melanie's velocity (65 commits in last 12mo of 121 in 24mo) suggests her rate
  has been roughly constant since gaining the bit.
- Richard's pattern is similar (63/111 — i.e. ~60% in the most recent year).
- Jacob received the bit only in April 2025 so the 12mo figure (54) is most of
  his total (63); ramp is steep.

Other notable velocity changes (existing committers with 12mo > 50% of their
24mo, i.e. their second year is busier than their first):
- Álvaro Herrera (under `@kurilemu.de`): 171/179 — ~95% of his 24mo activity is
  in the last 12mo, consistent with the email switch dating to mid-2024 (older
  activity is under the `@alvh.no-ip.org` identity).
- Fujii Masao: 169/232 ≈ 73%.
- Nathan Bossart: 162/315 ≈ 51% (very even).
- Jacob Champion: 54/63 ≈ 86%.

Nobody from the all-time top 20 has gone silent in the 24mo window — the active
committer set is highly stable. Notable lighter recent activity:
- Magnus Hagander (lifetime 928, 24mo only 6).
- Joe Conway (lifetime 123, 24mo only 4).

## Long-tail observation

The committer base is small and almost entirely active. Concrete numbers from
`%an` on `source/` at pin `e18b0cb7344`:

- **59 distinct committer identities** all-time (or 61 if you don't fold the
  three Álvaro Herrera variants and the two Peter Eisentraut variants).
- **33 distinct committers** in the 24mo window.
- **31 distinct committers** in the 12mo window.
- **Only 3 identities have <10 lifetime commits** (Julian Assange — 6, Vince
  Vielhaber — 2, Kris Jurka — 1). These are all from the late-1990s / early-2000s
  era and reflect very early commit-bit experimentation.
- **15 identities have <100 lifetime commits**, most from the pre-2005 era.

In short: there is **no long tail of one-time committers**. PG enforces commit
bits very narrowly, so every name in `%an` is someone who pushed multiple times
and was a sustained project participant. The broader contributor base — patch
authors credited via commit-message trailers — is much larger but invisible to
`%an`.

Phase B follow-ups should mine commit bodies for `Author:` and `Reviewed-by:`
trailers to surface that population.

## Methodology + caveats

- **Source:** `git log` on `/Users/matej/Work/postgres/postgres-claude/source/`
  (read-only PG clone, pinned at `e18b0cb7344`). No mailing-list archives, no
  GitHub API, no external network.
- **`%an` is the committer, not the original author.** PG uses a committer/author
  separation where non-committer contributions land via a committer who credits
  the original author in the commit body (`Author:`, `Reviewed-by:` trailers).
  This doc captures the committer side only. The 59-distinct-author number is
  committers; the true contributor base is much larger.
- **Identity merging is partial.** The repo's `.mailmap` is essentially empty
  (only normalises Álvaro Herrera's name with his new email). Two committers
  appear under multiple `<name, email>` pairs:
  - Álvaro Herrera: 3 variants (`Álvaro` + `@kurilemu.de`, `Álvaro` +
    `@alvh.no-ip.org`, `Alvaro` + `@alvh.no-ip.org`).
  - Peter Eisentraut: 2 variants (`peter_e@gmx.net` historical, `peter@eisentraut.org`
    current).
  These have been called out in the relevant tables but not collapsed into
  single rows, so commit counts for these two are split across rows.
- **"Primary domain" is inferred from path frequency, not declared.** Someone
  who touches `src/backend/utils/` a lot is not necessarily a "utils maintainer"
  — that subtree contains everything from GUC plumbing to error reporting to
  fmgr glue. Read the "Top 3 paths" column for the actual nuance.
- **"Notable commits" was selected by total lines-changed in the 24mo window**
  (insertions + deletions, from `git log --shortstat`). This biases toward
  feature additions, encoding-table regenerations, and Snowball updates; it
  under-represents subtle correctness fixes. The selection should be read as
  "samples of large work" not "most important work."
- **Time windows.** 24mo = `--since="24 months ago"` evaluated on 2026-06-11,
  i.e. 2024-06-11 .. 2026-06-11. 12mo = 2025-06-11 .. 2026-06-11. "Since 2024"
  used for the rising-stars detection means `--since="2024-01-01"`.
- **This doc deliberately does NOT cover:** review style, mailing-list activity,
  social context, employer affiliations, code-review pushback patterns, who
  reviews whom, or anything that requires reading commit-message bodies or
  pgsql-hackers archives. Those are Phase B follow-up deliverables.
