# Session 2026-06-11/12 — Phase A close + Phase B (4/5 done)

**Duration:** ~2 working days (most of 2026-06-11 + first hours of 2026-06-12, with sleeps + compaction breaks between).
**Source pin throughout:** `e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa`.

## Headline

Two phase transitions in one session:

1. **Phase D was paused** mid-execution at 6 staged patches. None sent to pgsql-hackers; all live under `patches/<slug>/` + COVER.md drafts. Parked in `knowledge/phase-d-pitches.md` with an explicit "resume after A+B+C" notice.

2. **Phase A finished** at substantive 100% (~2132 docs, 83.6% of the 2550 `.c/.h` substantive target). Remaining ~418 uncovered files are the explicitly-deferred mechanical bucket (src/interfaces 166, snowball 112, src/test 74, src/port + include/port/atomics 50+, jit 10, pch 3, utils/mb/conversion_procs 22).

3. **Phase B reached 4/5 deliverables** — all the substantive ones. Personas now exist for the top 20 PG committers + cross-cut maps of who-commits-where and who-reviews-where. Only the optional pgsql-hackers archive mining (deliverable #2) remains.

## What landed on main (chronological, by PR)

### Phase D quick-win delivery (then paused)
- **#118 SP7** — tablefunc.connectby identifier quoting (CB2 SQL injection)
- **#120 SP6** — pg_prewarm autoprewarm REVOKE-from-PUBLIC (CB5)
- **#127 SP2** — pg_str*lower/upper/title/fold MaxAllocSize cap (A7/A15/A16 cross-finding)
- **#128 CB7** — ltree parse_lquery cross-level amplification cap (~100 GB scratch DoS)
- **#129 CB1** — pgcrypto decompression bomb cap at MaxAllocSize
- **#130 CB8** — hstore HS_FLAG_NEWVERSION trust gap (OOB read via forged datum)

All six: format-patch + COVER.md drafts in `patches/<slug>/`. **Not sent upstream.** The decision: don't pile up unsent patches.

### Phase pivot
- **#131** — pivot commit: STATE.md scope refinement, Phase D parked, scope clarified to "substantive 100% ≈ ~240 files" with the ~416 mechanical files deferred to cloud routines.

### Phase A close (substantive 100%)
- **#132 A19** — backend tails: utils + access + storage + commands + statistics + include/storage + include/postmaster (47 docs)
- **#133 A20** — src/pl + src/bin tails (48 docs)
- **#134 A21** — contrib remainder, mostly PG18 new contribs `pg_plan_advice` + `pg_stash_advice` (52 docs)
- **#135 A22** — substantive closing sweep: top-level `src/include/*.h` core headers + include subdirs + backend lib/nodes/exec/foreign + backup/replication/partitioning (77 docs); honest reframe of what "substantive 100%" really meant + final STATE.md declaration.

**Total Phase A close: +224 docs, +50 issue registers, 0 regressions. Coverage 74.4% → 83.6%.**

### Phase B
- **#137 #1** — committer map (`knowledge/personas/committer-map.md`, 279 lines). 59 lifetime committers, 33 active in 24mo. Per-subsystem heatmap. Identified rising-star Richard Guo (optimizer), Melanie Plageman (vacuum), Jacob Champion (OAuth).
- **#139 #5** — contributor + reviewer trailer map (`contributor-map.md`, 452 lines). **857 distinct people** in trailers vs only 33 committers — 26× larger contributor base than `%an` shows. Top reviewers, top reporters, committer-reviewer pairings.
- **#147 #4** — domain-ownership map (`domain-ownership.md`, 321 lines) + `## Owners` blocks prepended to all 20 `knowledge/subsystems/*.md` files. Per-subsystem top committers + reviewers, ownership clusters, **bus-factor flags**.
- **#148 #3** — 20 per-committer deep persona docs (~3,461 lines total). Top 20 committers, each with activity profile, domain ownership, style patterns, common reviewer partners, "what to expect on a patch they would review" (calibrated for Phase C), landmark commits.

## Key findings carried forward

### From Phase A close
The Phase D backlog gained ~50 new issue tags from these closing sweeps (auto_explain log_parameter_max_length=-1 default, pg_logicalinspect A14-class missing perm check, vacuumlo TOCTOU, refint.c strcmp(SPI_getvalue, SPI_getvalue) wrong for NUMERIC/JSONB/BYTEA, scripts/common.c SQLi via --table, pg_resetwal control-file-before-WAL-unlink race, pg_ctl execl /bin/sh shell injection via postmaster.opts, fmgr_hook no-chaining, varatt_external SIGBUS hazard, FdwRoutine no version field, etc.). All live in per-subsystem `knowledge/issues/<x>.md` registers. Phase D will surface them when it resumes.

### From Phase B
- **Peter Eisentraut has ZERO backpatches in 24mo** across 719 commits. Tom/Michael/Nathan/Heikki all backpatch 17-25%. Phase D implication: don't route a back-patch-needed correctness fix to Peter as the landing committer.
- **Andres Freund only appears as `%an` 3× in 24mo** despite 227 "committer" commits. Virtually all his work is in `Author:` trailers. Cleanest committer-vs-author gotcha in the corpus.
- **Amit Kapila's Fujitsu/EDB reviewer subteam is the most concentrated in PG** — 8 names cover virtually all logical-rep patches. Expect 3+ to weigh in on any logical-rep submission.
- **Richard Guo: 0 → 111 commits in 24mo, 2.1× lead over Tom Lane in optimizer.** Optimizer ownership has effectively transferred.
- **Peter Geoghegan bus-factor confirmed HIGH:** 78/92 24mo commits in nbtree, no second-tier shadow.
- **Chao Li** is in the top-4 reviewers of 11/20 subsystems despite only ~10 months active. Will likely overtake Tom Lane as #1 reviewer next cycle.
- **`Discussion:` URL on 93% of recent commits** — the "every change has a thread" norm is near-universal.

### Operational gotcha
The shell harness silently caps `git log --oneline` at 50 lines (the `rtk` token-saver). All Phase B counts had to use `/usr/bin/git` directly or `rtk proxy git ...`. Future Phase B-style git-mining work should canonize this — don't trust the default `git log` output for count-heavy queries.

## Worktree state

Started: 29 worktrees (mix of A1-A17 + Phase D + cloud-only). Ended: clean — only `main`. Removed 26 merged worktrees during the pivot housekeeping (#131); each subsequent sweep cleaned up after itself.

Cloud routines kept running autonomously through this whole session; no manual interaction needed. They merged some glossary + extension-anthropologist + community-pulse content into main interleaved with the sweeps, but no conflicts.

## What's left

### Phase B remainder (optional)
- **#2 pgsql-hackers archive mining** — external fetching from `postgresql.org/list/pgsql-hackers/`. Recovers mailing-list-only signals (people who participate in threads but don't appear in any trailer). Cost: 1-2 hours wall, WebFetch-dependent. Marginal value is smaller now that #5 + #3 are done — defer unless completeness is the goal.

### Phase C kickoff (next)
Phase C is **planner + review-pipeline calibration against the staged Phase D patches.** The Phase B personas are exactly the input it needs: when a hypothetical patch touches subsystem X, the calibrated review skill should expect comments from {Y, Z, W} with characteristic styles {a, b, c}. Concrete first deliverable could be a `knowledge/calibration/` directory + per-patch calibration runs against the 6 staged Phase D patches.

### Phase D resumption (after C)
The 6 staged patches are ready to send. Decision-point: when to actually engage pgsql-hackers. Probably need the user to commit time to managing review threads, since the 6 are all real DoS / SQLi / privilege fixes and reviewers will respond seriously.

## Compaction note for next conversation

If this session is compacted before continuing:
- **Worktree state:** clean, only main + this `ft_corpus_phaseB_close` worktree pending.
- **Last commit on main:** the merge of #148 (Phase B #3).
- **Open PRs:** none expected after this session's close commit lands.
- **User signaled next move:** after compaction, they want to "continue" — most likely Phase C kickoff, possibly with Phase B #2 first if completeness matters.
- **Don't re-litigate the pivot.** Phase D stays parked; don't send patches upstream without explicit re-authorization.

## Cross-references

- `progress/STATE.md` — receives a closing entry in the same PR as this session log.
- `knowledge/personas/` — full set of 4 cross-cutting + 20 per-person docs.
- `knowledge/subsystems/*.md` — all 20 now have `## Owners` blocks (date 2026-06-12).
- `knowledge/phase-d-pitches.md` — PARKED status visible at the top.
- `patches/<slug>/` — 6 ready-to-send Phase D patches + COVER drafts.
