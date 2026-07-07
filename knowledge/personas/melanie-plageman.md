# Persona: Melanie Plageman

- Last verified: 2026-06-12
- Source pin: e18b0cb7344
- Method: `git log` mining of `source/` (committer-filtered, 24 months + pre-committer window) + cross-cut against `knowledge/personas/committer-map.md`, `contributor-map.md`, `domain-ownership.md`.

## Role + email(s)

- Committer email: `melanieplageman@gmail.com`
- **Recent committer.** First commit-as-committer landed `2024-07-19` (`83c39a1f7f3` "Ensure vacuum removes all visibly dead tuples older than OldestXmin"). The committer-map's 121-commit 24mo count is essentially her entire committer career so far.
- Pre-committer she was a heavy reviewer in the heap/vacuum/IO areas — per `contributor-map.md` she has 62 Reviewed-by trailers (most pre- and post-committership combined) and ~88 Author trailers. Was apprenticing under Andres Freund as a regular co-author on his AIO/read-stream work.
- Affiliation: Microsoft (Postgres team).

## Activity profile (last 24mo) — trailer counts

| Metric | Count | Source |
|---|---:|---|
| Commits as committer (since 2024-07-19) | 121 | `committer-map.md`; verified |
| Commits with Reviewed-by trailer | 65 (54%) | `committer-map.md` |
| Authored by herself (`Author: Melanie Plageman` in her own commits) | 76 (66 + 10 ASCII variant) | `git log ... --pretty='%B' | grep -i '^Author:'` |
| Self Reviewed-by | 8 | `git log ... | grep -ic '^Reviewed-by: Melanie Plageman'` |
| Pre-committer authored commits (2022-06 to 2024-07) | 1 in `--author=` log (suggests the rest were committed by others on her behalf — see below) | `git log --before='2024-07-19' --since='2022-06-12' --author='Melanie Plageman'` |
| Reviews credited *to* her in pre-committer window (2022-06 to 2024-07) | 32 | `git log ... | grep -ci '^Reviewed-by: Melanie Plageman'` |

The 32 pre-committer Reviewed-by appearances confirm `contributor-map.md`'s characterization: she did substantial review work before being granted commit access. The 8 self-Reviewed-by in her own commits is *low* compared to peer committers (Kapila 91, Korotkov 44, Haas higher) — consistent with her preferring to credit external reviewers rather than herself.

**Subsystem footprint (24mo, her commits only — top dirs):**

| Path | Touched files-count |
|---|---:|
| `src/backend/access/` | 144 |
| `src/include/access/` | 41 |
| `src/backend/executor/` | 33 |
| `src/backend/utils/` | 14 |
| `doc/src/sgml/` | 13 |
| `src/test/recovery/` | 11 |
| `src/include/nodes/` | 11 |
| `src/tools/pgindent/` | 9 |
| `src/backend/storage/` | 9 |
| `src/backend/commands/` | 9 |

The concentration in `src/backend/access/` + `src/include/access/` is sharper than any other committer's: ~75% of her file touches are in `access/`, almost all in `heap/` and `vacuum/`. This is one of the narrowest lanes among the active committers.

## Domain ownership

- **Heap-vacuum (`src/backend/access/heap/vacuumlazy.c`, `pruneheap.c`, `visibilitymap.c`).** Owner of the on-access pruning + visibility-map work. From `domain-ownership.md` §access-heap: "Melanie Plageman (75/210) ≈ 35.7% — Vacuum / read-stream / prune work is overwhelmingly hers." This is the largest subsystem concentration in the current committer base. Sample commits: `b46e1e54d07` (allow on-access pruning to set pages all-visible), `01b7e4a46d0` (pruning fast path for all-visible/all-frozen), `dd5716f3c74` (GlobalVisState in vacuum for page-level visibility), `4f7ecca84dd` (detect & fix VM corruption).
- **WAL-side of VM/freeze.** Owner of the new XLOG_HEAP2_PRUNE_VACUUM_SCAN consolidation. `a881cc9c7e8` ("Remove XLOG_HEAP2_VISIBLE entirely"), `a759ced2f1e` + `1252a4ee286` (WAL-log VM setting in PRUNE_VACUUM_SCAN). This is invariant-heavy work — WAL replay correctness + crash-recovery semantics — and she handled the consolidation cleanly.
- **Read-stream API integration into table-access methods.** `2b73a8c` ("BitmapHeapScan uses the read stream API"), `38229cb9051` (Add `read_stream_{pause,resume}()`), `31b0544b32b` (use I/O stats arguments in `FlushUnlockedBuffer()`). Read stream is Thomas Munro's invention; her job has been threading it through scan nodes. Pattern: she absorbed the apprenticeship from Andres Freund / Thomas Munro and now ships the integration work.
- **Scan-API plumbing.** `50eb5faea29` (pass table-modification info to scan nodes), `dcd8cc1c852` (thread flags through begin-scan APIs), `39dcd10a2c4` (remove PlannedStmt->resultRelations in favor of resultRelationRelids), `0f4c170cf3b` (cheap check if relation is modified). These are cross-cut into the executor — adjacent to her main heap lane.
- **PruneState refactoring.** `34cb4254bdb`, `68c2dcb9130`, `59663e4207f`, `bfe5c4bec75` — series of small commits cleaning up the prune-state representation. Refactor-first style.
- **Parallel BitmapHeapScan instrumentation.** `dd78e69cfc3` ("Allocate separate DSM chunk for parallel Index[Only]Scan instrumentation") — cross-listed under `executor` in `domain-ownership.md`.

## Style + patterns

- **Refactor-first, feature-second pattern (strong signal of reviewer apprenticeship).** A typical sequence in her log: refactor commit → helper-introduce commit → fast-path commit → main feature commit → BF/test stabilization commits. Example sequence: `68c2dcb9130` (add `PageGetPruneXid()` helper) → `34cb4254bdb` (rename `all_{visible,frozen}` to `set_*`) → `59663e4207f` (move common context into PruneState) → `01b7e4a46d0` (the actual fast-path feature). She prepares the ground before landing the user-visible change. This is the **classic reviewer-trained discipline** — likely absorbed from Andres Freund's work style.
- **Long-ish technical commit bodies, but mechanical-style.** Tightly bounded — what was changed, why, and what invariant was preserved. Less narrative than Kapila or Korotkov; more like Andres Freund's voice.
- **Heavy reliance on Reviewed-by external reviewers.** Top reviewer on her work is **Andres Freund (33)** — same person she apprenticed under as an author. She does not self-Reviewed-by often (8/121).
- **Test stabilization is a constant.** `62407d26b7c` (stabilize btree_gist test against on-access VM), `85ae8ab0533` (stabilize plancache test), `4a99ef1a0d1` (fix flakiness in pg_visibility VM-only vacuum test), `8519251ee97` (fix test_aio without cassert). She owns the BF response loop for her own work.
- **`pgindent` self-discipline.** 9 file touches in `src/tools/pgindent/` — runs the indent and commits cleanly.


## Scenarios I'd review
<!-- persona-scenarios:auto -->

*Derived from Domain-ownership paths overlapping each scenario's §Files section. If this persona claims a directory and a scenario mentions any file under it, they're a likely reviewer.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

| Scenario | Via path(s) |
|---|---|
| [`add-new-system-catalog-column`](../scenarios/add-new-system-catalog-column.md) | `src/backend/access/heap/vacuumlazy.c` |

<!-- /persona-scenarios:auto -->


## Subsystems I know
<!-- persona-subsystems:auto -->

*Derived from Domain-ownership paths overlapping each subsystem's `## Files owned` block.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

- [`access-heap`](../subsystems/access-heap.md)

<!-- /persona-subsystems:auto -->

## Common reviewer / collaborator partners

Top reviewers credited on her 121 24mo commits:

| Reviewer | R-by count |
|---|---:|
| Andres Freund | 33 |
| Chao Li | 23 |
| Kirill Reshke | 22 |
| Melanie Plageman (self) | 8 |
| Tomas Vondra | 7 |
| Robert Haas | 6 |
| Masahiko Sawada | 6 |
| Daniel Gustafsson | 5 |
| Andrey Borodin | 5 |
| Nazir Bilal Yavuz | 4 |
| Thomas Munro | 3 |
| Robert Treat | 3 |
| Peter Geoghegan | 3 |

Top authors in her commits (i.e. patches she committed but didn't write):

| Author | Count |
|---|---:|
| Melanie Plageman (self) | 76 (66 + 10) |
| Chao Li | 2 |
| Andrey M. Borodin | 2 |
| Thomas Munro | 1 |
| Sergey Tatarintsev | 1 |
| Richard Guo | 1 |

**Pattern: she mostly commits her own patches.** Out of ~80 substantive authored commits, only ~10 came from external authors. This is the *recent-committer shape* — she's still primarily landing her own work rather than gatekeeping a queue of others' patches (contrast Kapila who lands 12+ Fujitsu engineers' work).

**The Andres Freund pairing is the most diagnostic relationship.** Cross-cut to `contributor-map.md`'s "Melanie Plageman" row: her top reviewers (when she was an author) were Melanie Plageman (89) and Andres Freund (43). The author-side data is now mirrored on the committer side (Andres Freund 33 Reviewed-by). She and Andres are operating as a tight 2-person heap/AIO/read-stream loop, with Tomas Vondra and Peter Geoghegan as the next closest substantive reviewers.

## What to expect on a patch she would review

1. **Invariant-aware review on heap, vacuum, VM, and pruning.** She will check that WAL semantics + crash recovery + concurrent-vacuum interactions are preserved. Her own commits routinely call out these invariants in commit bodies (`a759ced2f1e`, `dd5716f3c74`).
2. **She prefers small, well-named refactor commits.** A 3000-line feature patch with no prep will likely get bounced for splitting. Match her own style: helper introduce, refactor, then feature.
3. **Andres Freund will likely co-review** anything heap/AIO/read-stream adjacent. The pairing is consistent.
4. **Tests must be added in the right file.** Heap/vacuum changes need `src/test/regress/sql/vacuum.sql` / `src/test/regress/sql/visibility.sql` updates, or an isolation/recovery TAP. She owns the BF response loop and is meticulous about test stability.
5. **She may merge an outside patch after a fairly long author-review-revise cycle.** With only ~10 external-author commits across 121, expect a thorough back-and-forth before she applies your patch — comparable to her own pre-committer apprenticeship cycle.

## Landmark commits (last 12mo)

1. **`052026c` — Eagerly scan all-visible pages to amortize aggressive vacuum** (from committer-map). The big PG 18 vacuum behavior change. Reduces aggressive-vacuum cost by interleaving work with normal vacuum passes.
2. **`a881cc9c7e8` — Remove XLOG_HEAP2_VISIBLE entirely** + **`a759ced2f1e` / `1252a4ee286` — WAL log VM setting in XLOG_HEAP2_PRUNE_VACUUM_SCAN.** The consolidation of VM-side WAL records into the prune/vacuum record. WAL-on-disk impact — needs careful invariant handling.
3. **`2b73a8c33b7` — BitmapHeapScan uses the read stream API** (from committer-map). Threaded Thomas Munro's read-stream into a major scan node. Substantive perf + cleanup work.
4. **`b46e1e54d07` — Allow on-access pruning to set pages all-visible** + **`01b7e4a46d0` — Add pruning fast path for all-visible and all-frozen pages.** Pair: feature commit + matching fast-path. Demonstrates the refactor-first, helper-introduce, then feature pattern.
5. **`4f7ecca84dd` — Detect and fix visibility map corruption in more cases.** Correctness fix in the most invariant-heavy corner she owns. Adjacent to `046b1a08aa` style durability work.

## Notes / hedges

- The committer-map's note "rising-since-2024" is confirmed by the 2024-07-19 first-commit date.
- The "reviewer-apprenticeship" reading of her refactor-first style is `[inferred]` from the pattern + the fact that her top-reviewer-on-her-own-author-work pre-committer was Andres Freund. The pattern is robust across 121 commits; the apprenticeship attribution is interpretation.
- Microsoft affiliation is `[from-comment]` (well-known publicly); not directly visible in her commit email.
- The 0.66 ratio of "she authored what she commits" is the recent-committer signature; expect this to drop over the next 2-3 years as she absorbs more external patches.
- The Chao Li reviewer entry (23) is noteworthy: Chao Li also appears as a top reviewer on Korotkov's, Eisentraut's, and Paquier's work. New high-volume reviewer 2025 — likely an emerging community voice; `[unverified]` whether substantive or mostly-stylistic.
