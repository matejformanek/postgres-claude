# Persona: Amit Kapila

- Last verified: 2026-06-12
- Source pin: e18b0cb7344
- Method: `git log` mining of `source/` (committer-filtered, 24 months) + cross-cut against `knowledge/personas/committer-map.md`, `contributor-map.md`, `domain-ownership.md`.

## Role + email(s)

- Committer email: `akapila@postgresql.org`
- Personal/review email (appears on Reviewed-by trailers): `amit.kapila16@gmail.com`
- Major committer on PG since the 9.x era; affiliation: Fujitsu (the Hyderabad logical-replication / streaming-rep team).
- Effective ranking: #16 lifetime committer by all-time commit count (689) and one of the most active in the 24mo window (185 commits, 8th overall — see `committer-map.md`).
- Owns logical replication end-to-end (publications, subscriptions, apply workers, slot sync, conflict detection, sequence sync).

## Activity profile (last 24mo) — trailer counts

| Metric | Count | Source |
|---|---:|---|
| Commits as committer (24mo) | 185 | `committer-map.md`; verified by `/usr/bin/git -C source/ log --since='2024-06-12' --committer='Amit Kapila'` |
| Commits authored (`Author:` trailer or `--author=`, 24mo) | 50 | `git log --author='Amit Kapila' --since='2024-06-12'` |
| Reviewed-by trailers (24mo) | 179 + 8 (self in his own commits) | `contributor-map.md` row "Amit Kapila" |
| Commits with at least one Reviewed-by trailer | 149/185 (80.5%) | `committer-map.md` Reviewer-style section |
| Self-Reviewed-by count | 91 (from current 24mo window query) / 114 (committer-map table; window cutoff differs slightly) | `git log --pretty='%B' | grep -i '^Reviewed-by: Amit Kapila'` |

**Subsystem footprint (24mo, his commits only — top dirs):**

| Path | Touched files-count | Notes |
|---|---:|---|
| `src/backend/replication/` | 148 | Logical apply worker, slot sync, conflict detection, reorderbuffer, subscriber |
| `doc/src/sgml/` | 131 | Catalog + config + logical-rep docs (he doc-stamps almost every feature he lands) |
| `src/test/subscription/` | 61 | TAP tests for logical rep |
| `src/test/regress/` | 51 | Regress add-ons (publications, sequences) |
| `src/include/catalog/` | 49 | `pg_subscription_rel`, `pg_subscription`, slot-sync columns |
| `src/backend/utils/` | 36 | Slot-related GUCs and cache |
| `src/include/replication/` | 32 | Public replication headers |
| `src/backend/commands/` | 31 | `subscriptioncmds.c`, `publicationcmds.c` |
| `src/backend/catalog/` | 30 | Catalog mutations for sub/pub features |
| `src/bin/pg_dump/` | 27 | Dump support for new pub/sub options |

The shape is sharply concentrated: `replication/` + adjacent test/doc/catalog dirs account for >80% of file touches. Outside that lane he is essentially absent.

## Domain ownership

- **Logical replication (publications + subscriptions + apply workers).** Primary committer. Own files: `src/backend/replication/logical/{worker.c, tablesync.c, applyparallelworker.c, slotsync.c, conflict.c, reorderbuffer.c}` and command files `subscriptioncmds.c` / `publicationcmds.c`. He lands the multi-month feature series and reviews almost every adjacent patch.
- **Replication slot sync (standby slot synchronization on the subscriber).** Owner. The slotsync worker, `pg_sync_replication_slots()`, and the failover-slot mechanism all flow through him. Sample 24mo commits: `788ec96d591` (refactor slotsync), `04396eacd3f` (LOCK_TIMEOUT handling), `85c17f612af` (idle slotsync logging), `851f6649cc1` (prevent invalidation of newly synced slots).
- **Conflict detection for logical replication.** Owner of the new (PG 18+) conflict-tracking machinery: `pg_conflict_detection` slot, `retain_conflict_info` subscription option, commit-ts retention. Landmark: `228c370` "Preserve conflict-relevant data during logical replication" — introduced the slot and the launcher-side xmin aggregation.
- **Sequence synchronization for logical replication.** Owner of the new `sequencesync` worker (PG 18+). Landmark: `5509055` (Aug 2025), follow-ups `1ba3eee89a7` (concurrent sequence drops), `2bf6c9ff71c` (double table_close fix), `f67dbd8398c` (BF follow-up).
- **`pg_createsubscriber` tool.** Co-owner with the broader subteam. Landed `pg_createsubscriber` features (e.g. `85ddcc2f4` "Support existing publications", `6b5b7eae3a` "-l/--logdir option", `d6628a5ea0` "module-specific logging functions").
- **Publication clause syntax extensions.** Owner of the PG 19-devel `EXCEPT TABLE` clause series: `fd366065e06` (initial), `5984ea868ee` (syntax change), `493f8c6439c` (ALTER), `6b0550c45d1` (misc fixes), `a49b9cfd72d` (error-message wording).

## Style + patterns (from his own commits + the patches he applies)

- **Long descriptive commit bodies.** Big-feature commits (`228c370`, `5509055`, `7054186`) routinely have 30-50 line bodies that explain the data model, the new catalog entries, the wire-protocol changes, and follow-up work. Small fixes still get a paragraph — almost no one-line commits in the feature window.
- **`Discussion: https://postgr.es/m/...` trailer is non-negotiable.** Every substantive commit links the pgsql-hackers thread. Spot-checked across 10 landmark commits — present on all 10.
- **Heavy Reviewed-by stacking.** 5+ Reviewed-by trailers on landmark commits is normal. `228c370` lists 5; `5509055` lists ≥5. He also Reviewed-by-credits himself when he did substantive review of a teammate-authored patch (91 of 185 commits in the 24mo window).
- **Tight feature series.** A new feature lands as 3-15 small follow-up commits over the following weeks: e.g. the `EXCEPT TABLE` series spans 5 commits across ~2 weeks; the slot-sync work has 20+ commits over a year. He buys cleanups + BF fixes + doc improvements as separate commits rather than amending.
- **Doc + test discipline.** Every behavior change includes a `doc/src/sgml/` hunk (131 files touched in 24mo) and a `src/test/subscription/` or `src/test/regress/` hunk (61 + 51 file-touches). Almost no "code-only" commits in the feature work.
- **No squash, no fixup.** Follow-up fixes get their own SHA and the original commit is referenced by hash in the body ("Fix BF failure introduced in commit 2bf6c9ff71." → 2bf6c9ff71 is from 2 days earlier).

## Common reviewer / collaborator partners

This is the most distinctive thing about Kapila's commit stream — **the tightest reviewer subteam in the entire PG project** (confirmed in `contributor-map.md` and `domain-ownership.md` §2).

Top reviewers credited on his 185 24mo commits:

| Reviewer | R-by count on his commits | Affiliation |
|---|---:|---|
| Amit Kapila (self) | 91 | Fujitsu |
| shveta malik | 34 | Fujitsu (Hyderabad) |
| Peter Smith | 32 | Fujitsu (Australia) |
| Hayato Kuroda | 27 | Fujitsu (Japan) |
| Chao Li | 21 | Independent / new reviewer 2025 |
| vignesh C / Vignesh C | 25 (combined) | Independent (ex-EnterpriseDB) |
| Masahiko Sawada | 15 | (Sawada is himself a committer) |
| Dilip Kumar | 15 | Fujitsu |
| Nisha Moond | 12 | Fujitsu |
| Zhijie Hou / Hou Zhijie | 17 (combined) | Fujitsu (also top author — see below) |
| Shlok Kyal | 6 | Fujitsu |

Top authors of patches Kapila commits (not just reviews):

| Author | Authored count (in his 185 commits) |
|---|---:|
| Zhijie Hou (`houzj.fnst@fujitsu.com`) | 19 |
| vignesh C | 18 |
| Shlok Kyal | 17 |
| Hayato Kuroda | 16 |
| Peter Smith | 12 |
| Nisha Moond | 7 |

**Reading:** the logical-rep / slot-sync work is a Fujitsu-internal feature funnel. Kapila is the committer for ~12 distinct Fujitsu engineers' work; 6 of those engineers also do the cross-review. The "Reviewed-by: Amit Kapila" self-credit on 91/185 commits is consistent with him being lead reviewer on team-internal patches before pushing.

Cross-cut to `domain-ownership.md`: of the 331 total `src/backend/replication/` commits in 24mo, Kapila committed 87 (26%) and Reviewed-by'd 107 (32%). The next nearest committer (Peter Eisentraut, 39) does mostly mechanical doc/header work — substantive logical-rep work is essentially Kapila + subteam.

## What to expect on a patch he would review

1. **You will get multiple reviewers from the Fujitsu logical-rep subteam.** Posting a logical-rep patch to pgsql-hackers will typically draw responses from at least 3 of {Kapila, Peter Smith, shveta malik, Hayato Kuroda, Vignesh C, Zhijie Hou, Nisha Moond} within a few rounds. Expect coordinated review (they often comment on each other's review points).
2. **Behavior changes will be challenged on conflict, slot-sync, and upgrade-compat axes.** Kapila routinely asks "what happens during pg_upgrade?" and "does this break slot sync to a standby?" — both are tracked invariants for him. Source: the upgrade-handling paragraph in `228c370` ("During upgrades, if any subscription...") and `851f6649cc1`'s framing.
3. **Doc + test patches expected in the same commit.** A code-only logical-rep patch will be sent back for tests in `src/test/subscription/` and SGML changes in `doc/src/sgml/logical-replication.sgml` / `catalogs.sgml`. He doesn't relax this for "small" patches.
4. **Discussion link is mandatory.** No `Discussion:` trailer → he will ask for the thread before applying.
5. **Multi-round review with named follow-ups is normal.** A 5-revision patchset becoming 3-5 separate commits (initial + cleanups + BF fixes) is the standard shape. Do not expect a feature to land as one squashed commit.

## Landmark commits (last 12mo)

1. **`228c3708685` — Preserve conflict-relevant data during logical replication** (2025-07-23). The foundational PG 18+ patch for `update_deleted` / `update_origin_differs` conflict detection. Introduces `pg_conflict_detection` slot, per-apply-worker non-removable XID tracking, and the `retain_conflict_info` subscription option. Author: Zhijie Hou; 5 Reviewed-by trailers. Sets up the data-retention machinery for the rest of the conflict-detection feature arc.
2. **`5509055d695` — Add sequence synchronization for logical replication** (2025-08; touched 60+ files). Introduces the `sequencesync` worker, `pg_subscription_rel` INIT/READY states for sequences, and the CREATE/ALTER/REFRESH-SUBSCRIPTION paths for sequence sync. Closes a 10+ year gap in logical replication.
3. **`fd366065e06` — Allow table exclusions in publications via EXCEPT TABLE** (2026-Q1). New publication syntax `FOR ALL TABLES EXCEPT TABLE x, y`. Followed by `5984ea868ee` (syntax change), `493f8c6439c` (ALTER support), `6b0550c45d1` (misc fixes), `a49b9cfd72d` (error-message wording) — classic 5-commit follow-up tail.
4. **`7054186c4eb` — Replicate generated columns when `publish_generated_columns` is set** (Mar 2025). Added publication-level option to ship generated stored columns. Followed by `87ce27de696` (require columns when in column-list), `8fcd80258bc` (better errors), `6252b1eaf82` (doc).
5. **`788ec96d591` — Refactor slot synchronization logic in slotsync.c** (recent). Pre-feature refactor to make subsequent slot-sync work (LOCK_TIMEOUT handling, retain_dead_tuples, invalidation prevention) tractable. Representative of his pattern: refactor commit first, then feature commits land cleanly on top.

## Notes / hedges

- All trailer counts above use `/usr/bin/git` directly because the default `git` in this shell is wrapped by a token-saving proxy that truncates `log` output to 50 lines. Counts run through `--no-pager` or via a file redirect confirm the committer-map's 185/24mo number.
- The Fujitsu affiliation for individual reviewers (shveta malik, Peter Smith, Hayato Kuroda, etc.) is inferred from email domain (`@fujitsu.com`) where present in trailers and from publicly available pgsql-hackers history; `[inferred]` for any reviewer whose email isn't visibly Fujitsu in trailers (e.g. Vignesh C uses `vignesh21@gmail.com`).
- Self-Reviewed-by counts vary slightly depending on whether the 24mo window starts 2024-06-12 (current sweep, 91) or matches the committer-map's earlier sweep (114). Both numbers are correct for their respective windows; the pattern (~50-60% of his commits credit himself) holds.
- Zhijie Hou appears under two spellings (`Zhijie Hou` and `Hou Zhijie`) in trailers — same person, ~36 combined Author counts across his commits. No `.mailmap` entry merges them.
