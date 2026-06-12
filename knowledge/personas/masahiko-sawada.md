# Persona: Masahiko Sawada

- Last verified: 2026-06-12
- Source pin: e18b0cb7344
- Method: git log mining of source/ + cross-cut against committer-map.md,
  contributor-map.md, domain-ownership.md.

## Role + email(s)

- Committer.
- Author/committer email: `Masahiko Sawada <msawada@postgresql.org>`.
  All 155 historical author entries point at this address; no email
  drift detected. [verified-by-code]

## Activity profile (last 24mo)

| Vector                                              | Count |
|-----------------------------------------------------|------:|
| Commits as author (24mo)                            | 113   |
| `Reviewed-by: Masahiko Sawada` in others' commits   | 95    |
| `Reviewed-by:` trailers in his own commits, top reviewer (Chao Li) | 14 |

Counts via `rtk proxy git -C source/ log --since='24 months ago'
--author='Sawada' --oneline`. [verified-by-code]

### Subsystem footprint (file touches, 24mo, top areas)

| Path                            | Touches |
|---------------------------------|--------:|
| src/backend/replication         | 61      |
| doc/src/sgml                    | 42      |
| src/test/regress                | 34      |
| src/backend/utils               | 29      |
| src/backend/access              | 28      |
| src/bin/pg_upgrade              | 24      |
| src/include/replication         | 22      |
| src/backend/commands            | 22      |
| src/include/catalog             | 21      |
| src/bin/pg_basebackup           | 16      |
| src/include/commands            | 11      |
| src/bin/psql                    | 10      |

Replication (backend + include) dominates; pg_upgrade and
pg_basebackup form a secondary cluster tied to logical-replication
slot handling across upgrades. [verified-by-code]

## Domain ownership

- **Logical replication + replication slots.** 61 commits in
  `src/backend/replication/` + 22 in `src/include/replication/`
  over 24mo. Themes (from subjects):
  - Race conditions in logical decoding activation / slot
    initialization (e.g. ffeda04259bb-equivalent commits: "Fix race
    when logical decoding activation is concurrently interrupted",
    "Fix race condition in XLogLogicalInfo and ProcSignal
    initialization").
  - Replication-origin plumbing — multi-commit refactor:
    "Consolidate replication origin session globals into a single
    struct", "Refactor replication origin state reset helpers",
    "Standardize replication origin naming to use `ReplOrigin`".
  - Pub/sub feature additions (e.g. `target_relid` parameter to
    `pg_get_publication_tables()`).
- **Parallel vacuum / autovacuum.** Headline commit "Allow
  autovacuum to use parallel vacuum workers" (2026-04-06), plus
  observability ("Add parallel vacuum worker usage to VACUUM
  (VERBOSE) and autovacuum logs", "Add dead items memory usage to
  …"), plus correctness fixups ("Fix assertion failure in
  parallel vacuum with minimal `maintenance_work_mem`"). 7+
  vacuum-related subjects in 24mo. [verified-by-code]
- **pg_upgrade for logical replication.** 5 pg_upgrade subjects
  including "Add `--set-char-signedness`", "Preserve default char
  signedness", and slot detection / caught-up checks. He is
  the natural owner of the pg_upgrade ↔ logical-slot seam.
  [verified-by-code]
- **COPY support.** "Fix attribute mapping for COPY TO on
  partitioned tables", "Add base32hex support to encode()/decode()"
  (adjacent area); 5 COPY-touching subjects in 24mo.
  [verified-by-code]
- Outside these areas: ProcSignal infrastructure
  ("Fix race between `ProcSignalInit()` and `EmitProcSignalBarrier()`"),
  tidstore, palloc_object/palloc_array sweeps. The recurring
  theme is shared-state races and post-commit hardening.

## Style + patterns

- **Title style:** imperative, often subsystem-prefixed
  ("pg_upgrade: …", "doc: …", "psql: …"). Heavy on "Fix race in X"
  and "Allow Y to do Z". [verified-by-code]
- **Heavy doc-and-test coupling:** 42 doc/src/sgml touches in the
  24mo — he routinely updates docs in the same commit as the code,
  or in an immediate follow-up. Same for test scaffolding (34
  src/test/regress touches). [verified-by-code]
- **Refactor-then-extend pattern.** The replication-origin work is
  three small refactor commits in 2026-01-28 followed by feature
  use, mirroring Geoghegan's style but on a different subsystem.
  [verified-by-code]
- **Race-condition-finder.** A large share of his commits land
  fixes for races in shared-state initialization, signal handling,
  and slot activation. Treat any patch touching those areas as
  likely to come under his lens.

## Common reviewer/collaborator partners

`Reviewed-by:` trailers inside his own commits (24mo):

| Reviewer            | Count |
|---------------------|------:|
| Chao Li             | 14    |
| Amit Kapila         | 10    |
| Noah Misch          | 5     |
| Michael Paquier     | 5     |
| Hayato Kuroda       | 5     |
| Álvaro Herrera      | 4     |
| Sami Imseih         | 4     |
| Peter Smith         | 4     |
| Ashutosh Bapat      | 4     |
| vignesh C           | 3     |
| Zhijie Hou          | 3     |
| Yugo Nagata         | 3     |
| Kirill Reshke       | 3     |

The strong Chao Li / Amit Kapila / Peter Smith / Hayato Kuroda /
Zhijie Hou cluster is the **logical-replication review community**;
he is embedded in it. [verified-by-code]

Going the other direction (95 commits cite `Reviewed-by: Masahiko
Sawada`): he is a high-fan-out reviewer for the replication and
vacuum communities.

## What to expect on a patch he would review

- He'll review **replication (logical + slots), parallel vacuum,
  pg_upgrade-slot interactions, and ProcSignal/shared-state
  initialization paths**.
- Strong attention to **races in shared-state initialization** —
  if your patch sets up shmem, registers a slot, or starts
  decoding, expect questions about what's atomic and what's not.
- Likes **doc + test in the same patch**. If you change a
  GUC or add a SQL function, an SGML hunk and a regress hunk are
  expected.
- Embedded in the **Amit Kapila / Peter Smith / Hayato Kuroda
  review chain** — patches he reviews often get a second pass from
  one of them, and vice-versa. Routing a logical-replication
  patch his way effectively reaches that whole cluster.
- For **VACUUM / autovacuum** patches, he is one of the few
  committers actively shipping features (parallel autovacuum
  workers). Expect substantive design feedback rather than
  rubber-stamping.

## Landmark commits (last 12mo)

- **"Allow autovacuum to use parallel vacuum workers"** (2026-04-06).
  Headline feature: parallel workers under autovacuum, not just
  manual `VACUUM (PARALLEL N)`. Followed by observability commits
  exposing worker counts in `VACUUM (VERBOSE)` and autovacuum
  logs. [verified-by-code]
- **"Fix race when logical decoding activation is concurrently
  interrupted"** (2026-06-09). Latest in a long line of decoding-
  activation race fixes. [verified-by-code]
- **"Fix race condition in XLogLogicalInfo and ProcSignal
  initialization"** (2026-05-07) + **"Fix race between
  `ProcSignalInit()` and `EmitProcSignalBarrier()`"** (2026-05-27).
  Pair of ProcSignal initialization-ordering fixes. [verified-by-code]
- **Replication-origin consolidation series** (2026-01-28):
  three commits — naming standardization, helper refactor, struct
  consolidation. Canonical refactor-then-extend slice.
  [verified-by-code]
- **pg_upgrade slot work**: "Optimize logical replication slot
  caught-up check" (2026-02-04) + "Fix detection of invalid
  logical replication slots" (2026-04-22). The pg_upgrade ↔ slot
  seam. [verified-by-code]
- **"Add base32hex support to encode() and decode()"**
  (2026-03-25). Off-domain side quest; rare for him to touch
  pure encoding code. [verified-by-code]

## Notes / hedges

- His 113 commits and his 95 `Reviewed-by` mentions are
  near-symmetric — he is approximately as much a reviewer as he
  is a committer, unusual relative to a Richard Guo (heavy
  author) or a Tom Lane (heavy committer of others' work).
  [verified-by-code]
- The **vacuum / parallel vacuum** work in 2026 is a notable
  expansion of his scope; historically he was logical-replication
  first. domain-ownership.md flags him as a replication
  specialist; the parallel-vacuum series suggests he is
  positioning as the second-tier owner for vacuum infrastructure
  alongside the existing committers. [inferred]
- The reviewer cluster (Chao Li, Amit Kapila, Peter Smith, Hayato
  Kuroda, Zhijie Hou) is unusually East-Asia heavy, reflecting
  the logical-replication community's center of gravity. Useful
  when routing patches by time zone. [inferred]
- No bus-factor concern: logical replication has multiple senior
  committers (Amit Kapila on the upstream side, Álvaro on
  publish/subscribe, Tomas Vondra historically); Sawada is one of
  several owners, not the sole owner. [from-domain-ownership]
