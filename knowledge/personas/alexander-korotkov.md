# Persona: Alexander Korotkov

- Last verified: 2026-06-12
- Source pin: e18b0cb7344
- Method: `git log` mining of `source/` (committer-filtered, 24 months) + cross-cut against `knowledge/personas/committer-map.md`, `contributor-map.md`, `domain-ownership.md`.

## Role + email(s)

- Committer email: `akorotkov@postgresql.org`
- Major committer since the 9.6 era. Lifetime rank #23 (496 commits per `contributor-map.md`).
- Active feature committer on **access methods (GIN especially), partitioning DDL, optimizer micro-passes, and the new WAIT FOR LSN infrastructure**. He lands large multi-commit feature series in his domain and follows them with weeks of small fixes.
- Affiliation: long-time independent; previously Postgres Pro (Russia).

## Activity profile (last 24mo) — trailer counts

| Metric | Count | Source |
|---|---:|---|
| Commits as committer (24mo) | 141 | `committer-map.md`; verified by `/usr/bin/git -C source/ log --since='2024-06-12' --committer='Alexander Korotkov'` |
| Commits with Reviewed-by trailer | 73 (51%) | `committer-map.md` |
| Self Reviewed-by | 44 | `git log ... | grep -ic '^Reviewed-by: Alexander Korotkov'` |
| Top author across his commits (besides himself) | Xuneng Zhou (26), Andrei Lepikhov (14) | `git log ... | grep -i '^Author:'` |
| Co-authored-by Korotkov (he wrote part himself) | 11 | same query |

**Subsystem footprint (24mo, his commits only — top dirs):**

| Path | Touched files-count |
|---|---:|
| `src/test/regress/` | 71 |
| `src/backend/access/` | 57 |
| `src/test/recovery/` | 33 |
| `src/backend/optimizer/` | 30 |
| `doc/src/sgml/` | 27 |
| `src/backend/utils/` | 26 |
| `src/backend/commands/` | 26 |
| `src/test/modules/` | 21 |
| `src/tools/pgindent/` | 17 |
| `src/test/isolation/` | 13 |

The dominance of `src/test/recovery/` is unusual — driven by his WAIT FOR LSN work (TAP test `049_wait_for_lsn.pl`). The mix of `access/` + `optimizer/` + `commands/` is what `committer-map.md` characterizes as "access (indexes) + partitioning + optimizer."

## Domain ownership

- **WAIT FOR LSN command + xlogwait infrastructure.** Sole owner; this is a large multi-month feature series in the 24mo window. ~20 commits including `7e8aeb9e483` (xlogwait infra: write+flush wait types), `49a181b5d63` (MODE option), `cba67b5b87f` (replay-position floor), `5cdec423193` (subxact-abort cleanup), `a80a593ab63` (memory ordering in wakeup). Touches `src/backend/access/transam/xlogwait.c`, command grammar, and a dedicated TAP suite.
- **ALTER TABLE SPLIT / MERGE PARTITION.** Owner of the PG 18 partitioning DDL extensions. Landmarks `4b3d173629f` (Implement SPLIT PARTITION), `f2e4cc42795` (Implement MERGE PARTITIONS). Plus a long tail of fixes through 2026: `e64a9ba2b4f` (reject degenerate SPLIT with DEFAULT), `9354896920e` (range-bound validation), `83df16f1fa5` (doc clarification), `971017c4959` (hint fix), `713e553e321` (preserve extension deps on indexes during merge/split).
- **Self-Join Elimination (SJE) optimizer pass.** Landed `fc069a3` ("Implement Self-Join Elimination") with Andrei Lepikhov as primary author. Long body, opinionated design explanation. Follow-up `07b7a964d36` (fix for bare Var references in join clauses).
- **GIN index improvements.** Co-owner of `src/backend/access/gin/`. Sample: `fa6f2f624c0` (rework ginScanToDelete to pass Buffers), `c5ae07a90a0` (palloc in MERGE/SPLIT PARTITION code touches GIN paths).
- **MERGE statement fixes.** `177037341a4` "Fix handling of updated tuples in the MERGE statement" — substantive correctness fix.
- **pgindent runs.** `17 files in src/tools/pgindent/` — he frequently runs the indent and commits its output.
- **Cross-cut: he Reviewed-by appears 56 times on others' optimizer/access commits** (per `contributor-map.md`) — meaning he is also a reviewer for Richard Guo's optimizer work and adjacent access-method patches.

## Style + patterns

- **Long technical commit bodies for feature commits.** `fc069a3` (SJE) has 50+ lines describing the transformation, example queries, and follow-up directions. `5509055`-class feature bodies. Small fixes get 1-paragraph bodies.
- **Heavy follow-up commit tail per feature.** WAIT FOR LSN landed as ~20 separate small commits over months — refactor, test, edge-case fix, doc, BF follow-up. SPLIT PARTITION similarly has 10+ trailing fix commits across 2024-2026. He does not amend.
- **Revert-and-resubmit pattern.** Visible in `0392fb900eb` ("Revert 'Reject degenerate SPLIT PARTITION with DEFAULT partition'") followed two days later by `d8af7301003` (same subject — re-landed corrected). Also `e54ce0b2da6` reverts followed by `f30848cb05d` re-land. He prefers a revert + clean re-commit over an amend.
- **`Reviewed-by: Alexander Korotkov` (self) appears 44/141 times.** Lower self-credit rate than Amit Kapila (~50%) but still substantial — consistent with him driving the review of patches he ultimately commits.
- **Top author cross-cut: Xuneng Zhou (26).** Xuneng is flagged in `contributor-map.md` as a "new author 2025" with top reviewer Alexander Korotkov (35) and Michael Paquier (24). The Zhou ↔ Korotkov pairing is the strongest in his 24mo data, suggesting an apprenticing collaboration on test stabilization / small fixes.

## Common reviewer / collaborator partners

Top reviewers credited on his 141 24mo commits:

| Reviewer | R-by count |
|---|---:|
| Alexander Korotkov (self) | 44 |
| Tom Lane | 9 |
| Michael Paquier | 9 |
| Andres Freund | 8 |
| Alvaro Herrera | 8 |
| Xuneng Zhou | 7 |
| Pavel Borisov | 7 |
| Amit Kapila | 7 |
| Heikki Linnakangas | 6 |
| Kyotaro Horiguchi | 5 |
| Chao Li | 5 |
| Alexander Lakhin | 5 |

Top authors of patches he commits (excluding self/Co-authored-by):

| Author | Count |
|---|---:|
| Xuneng Zhou | 26 |
| Alexander Korotkov (self) | 15 + 11 co-authored |
| Andrei Lepikhov | 14 |
| Tender Wang | 6 |
| Chao Li | 5 |
| Teodor Sigaev | 4 |
| Vitaly Davydov | 3 |
| Oleg Tselebrovskiy | 3 |

Pattern: a recurring core of **Russian-affiliated contributors** (Lepikhov, Borisov, Tselebrovskiy, Davydov, Lakhin, Sigaev — Teodor was the co-founder of Postgres Pro) shows up disproportionately in his patches/reviews. This is a real but loose cluster, not a tight subteam like Amit Kapila's Fujitsu lane. The reviewer pool is broader: substantive review also comes from Tom Lane, Michael Paquier, and Heikki Linnakangas — i.e. mainstream committers do step into his feature reviews.

## What to expect on a patch he would review

1. **He will request a long, justified commit body for any feature patch.** His own commit bodies set the bar; a one-line subject + empty body for a feature change will get pushed back.
2. **WAIT FOR LSN / SPLIT-MERGE PARTITION / GIN territory is his.** Expect substantive technical review, including memory-ordering, recovery interaction, and subxact cleanup — those are recurring concerns visible in his own follow-up commits (`a80a593ab63`, `5cdec423193`, `dfb690dd523`).
3. **Tests in the right `src/test/` flavor are required.** WAIT FOR LSN landed with a dedicated TAP suite (`049_wait_for_lsn.pl`); SPLIT PARTITION added regress tests. A patch in his lane without matching tests gets sent back.
4. **He is willing to revert and re-land** rather than amend or layer on increasingly complex follow-ups. Don't be alarmed if a patch is reverted shortly after landing; the typical re-land is within 1-3 days.
5. **He may apply patches authored by lesser-known contributors** (Xuneng Zhou's 26 authored, Tender Wang's 6, Oleg Tselebrovskiy's 3) — he is one of the more accessible committers for new authors in his domain.

## Landmark commits (last 12mo)

1. **`fc069a3a631` — Implement Self-Join Elimination** (Feb 2025). New optimizer pass to remove redundant inner self-joins. Primary author: Andrei Lepikhov; multi-Reviewed-by stack. The kind of standalone "new feature" commit that lands clean and gets a long body.
2. **`4b3d173629f` — Implement ALTER TABLE ... SPLIT PARTITION** + **`f2e4cc42795` — Implement ALTER TABLE ... MERGE PARTITIONS** (paired, PG 18). Big partitioning DDL extension. Followed by 10+ trailing fixes through 2026.
3. **`7e8aeb9e483` — Extend xlogwait infrastructure with write and flush wait types** + **`49a181b5d63` — Add the MODE option to the WAIT FOR LSN command**. The PG-19-devel work that makes WAIT FOR LSN usable for sync-replication scenarios. Paired with `cba67b5b87f` (replay-position floor on standby) and many BF fixes.
4. **`177037341a4` — Fix handling of updated tuples in the MERGE statement**. Substantive MERGE correctness fix, demonstrating his cross-cut into core DML.
5. **`713e553e321` — Preserve extension dependencies on indexes during partition merge/split**. Catalog-correctness follow-up for SPLIT/MERGE, showing the long-tail-after-feature pattern.

## Notes / hedges

- The Russian-affiliated contributor cluster (Lepikhov, Borisov, etc.) is a soft pattern based on names + a known Postgres Pro nexus; treat as `[inferred]` — affiliations are not directly in trailers.
- Xuneng Zhou as his top author is a strong fact from the 24mo data, but Zhou is a new author (flagged in `contributor-map.md` as "new author 2025"); the pattern may shift if Zhou continues developing as an independent contributor.
- The 17 `src/tools/pgindent/` touches are not "feature work" — they are pgindent runs whose output he committed. Should be filtered out of any subsystem-affinity ranking.
- Committer-map's "access, optimizer, utils" footprint is confirmed by the file-touch data but understates the partitioning-DDL and WAIT FOR LSN concentration — those are the actual feature lanes.
