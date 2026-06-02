# 2026-06-02 — Cloud routine throughput bump

**Type:** interactive (worktree `ft_cloud_throughput_bump`).
**Outcome:** Pushed all 10 cloud routines to actually use their per-run
budget. Loader gets an explicit "fill the budget" floor; frontmatters
bumped ~3-5× across the board; 6 producer recipes restructured to loop
rather than do one item and exit.

## Why this happened

User feedback after the A1 catalog-headers sweep (~80k tokens for 12-13
docs in 5 min):

> Really the routines make sure to put even more pressure on them we are
> still generating not that much ctx for the limit to be depleted so
> make sure they are really on edge of limits in the routines.

The routines were sized for an over-cautious "do one thing, exit". The
A1 sweep proved that ~12 catalog header docs fit comfortably in 80k
tokens — well within a single Opus 4.8 context. The cloud env should
match that throughput nightly. Sizing too small means:

- Phase A closes in ~18 months at 2-3 files/night via pg-file-backfiller.
- pg-corpus-maintainer's "top-15 glossary terms/night" leaves obvious
  high-frequency terms undefined for weeks.
- pg-quality-auditor's audits queue takes 24+ days to cycle through
  ~24 long-form docs.

Sized properly:

- Phase A closes in **~3-4 months** at 10-20 files/night.
- Glossary grows by 30-50 terms/night.
- Audits queue cycles every 3-5 days.

## Two changes — loader + per-recipe

### Change 1 — `_loader.md` §5 gets a floor

The loader's §5 ("Do the recipe's work") already had a CEILING ("if you
approach the ceiling, stop early and record `exit_reason: budget-capped`").
Missing: a FLOOR.

Added:

- **70% target.** Keep popping queue items / doing passes until
  `output_tokens_so_far ≥ 0.70 * max_output_tokens` OR queue empty.
- **85% soft cap.** Only stop mid-item at 85% to record `budget-capped`.
- **Empty-handed run = process bug.** Exit at <30% budget consumed →
  flag in run log so pg-state-keeper surfaces "routine under-utilization".
- Branched into two paths: **queue-driven** (file-backfiller,
  quality-auditor, extension-anthropologist, user-question-harvester,
  docs-miner) and **sweep-driven** (corpus-maintainer, upstream-watcher,
  community-pulse). Both get loop-until-budget; sweep-driven phrases
  it in terms of growing the pass output (e.g. glossary top-50 not top-15).

### Change 2 — frontmatter bumps (all 10 routines)

| Routine | Input before → after | Output before → after |
|---|---|---|
| pg-file-backfiller | 120k → **400k** | 25k → **100k** |
| pg-corpus-maintainer | 80k → **250k** | 20k → **60k** |
| pg-quality-auditor | 80k → **250k** | 20k → **60k** |
| pg-docs-miner | 60k → **200k** | 20k → **50k** |
| pg-extension-anthropologist | 70k → **250k** | 20k → **60k** |
| pg-upstream-watcher | 80k → **200k** | 25k → **50k** |
| pg-community-pulse | 100k → **250k** | 30k → **60k** |
| pg-user-question-harvester | 70k → **200k** | 15k → **50k** |
| pg-evening-merger | 150k → **300k** | 30k → **60k** |
| pg-state-keeper | 60k → **150k** | 20k → **40k** |
| **Total per cycle** | **850k → 2 450k** | **217k → 590k** |

Headroom: Opus 4.7/4.8 supports 200k context default + a 1M-context
variant. The new per-routine ceilings sit comfortably within the
default; sweep-style routines that fetch many sources (file-backfiller
at 400k input) trend toward needing the 1M variant on high-input
runs, but that's a model-selection knob, not a budget change.

### Change 3 — restructure 6 producer recipes

Loader floor handles most of it, but recipes that explicitly say "pop
one, process, exit" needed structural updates:

- **`pg-file-backfiller`**: "try 2-3 small files" → "10-20 small / 3-5
  medium / 1-2 large; loop until 70% budget or queue empty".
- **`pg-extension-anthropologist`**: "one extension per run" → loop
  3-4 extensions per run.
- **`pg-docs-miner`**: "one wiki + one docs chapter" → loop 6-10
  distillations per run, alternating queues.
- **`pg-quality-auditor`**: "pop head, do one" → "loop 5-10 items in
  primary mode; rotate modes if primary's queue empties".
- **`pg-user-question-harvester`**: "5-8 questions per run" → 20-30.
- **`pg-corpus-maintainer`**: glossary Pass 2 "top-15 terms" → "top-50
  (or however many fit in budget)".

## Expected impact (back-of-envelope)

Phase A closure:

- Old cadence: ~2-3 files/night (pg-file-backfiller) + occasional
  foreground sweep. Gap = 1 575 files (post A1). Time to close ≈ 1.5 yr.
- New cadence: ~12 files/night (pg-file-backfiller) + same foreground
  sweeps. Time to close ≈ **3-4 months**. Maybe faster if foreground
  sweeps continue at A1's pace (~70 files / 30 min).

Glossary:

- Old: top-15/night = 15-week cycle to enumerate 200 baseline terms.
- New: top-50/night = ~4 weeks. Glossary stabilizes by end of June.

Quality audits:

- Old: 1 doc/3 days → 24 docs in 72 days (and each only re-verified
  every ~24 days).
- New: 5-10 docs/day in AUDIT mode → re-verification cycle of 3-5 days.

## What this commit explicitly does NOT do

- **Doesn't change the schedule cron expressions.** Same overnight
  cadence (20:11-05:43 Prague).
- **Doesn't touch the `RemoteTrigger` bootstrap.** The triggers still
  fire the same 2-line "pull main + read loader" prompt; all the new
  behavior lives in repo files that `git pull` brings in.
- **Doesn't change which model the routines use** (claude-opus-4-8 per
  the master plan).
- **Doesn't add any new routines.**
- **Doesn't change the producer set or output_dirs.**

## Followup candidates surfaced

- **Verify the next nightly cycle (2026-06-03 Prague evening).** Watch
  for: (a) routines actually consuming ≥70% budget; (b) any "routine
  under-utilization" notes in the daily briefing; (c) any budget-capped
  exits that suggest budgets should go higher still.
- **If routines hit 85% budget-cap regularly**, bump again — Opus 4.7/4.8
  with the 1M-context variant can absorb 600k+ input easily.
- **Wall-time monitoring.** With 100k output per file-backfiller run,
  wall time will scale; pg-evening-merger schedule (02:11) should still
  give file-backfiller (22:53) a comfortable window. If wall time
  exceeds 60 min per run, consider parallelizing within a single
  routine (multi-agent fan-out like the A1 sweep used).
- **Throughput dashboard.** `pg-state-keeper`'s daily briefing should
  show per-routine output-token consumption % vs budget. Currently it
  shows total cost but not utilization. Small addition.

## Commit message

```
ft(cloud): bump routine throughput (fill the budget; loop don't pop-once)

User feedback after A1 catalog-headers sweep (12 docs/agent in ~80k
tokens): cloud routines were sized for over-cautious one-item-per-run.
Push them to actually use the context they have.

Two changes:

1. `_loader.md` §5 — add the floor. Loop until ≥70% output_tokens
   consumed OR queue empty. Soft cap at 85% to record budget-capped.
   Empty-handed run (<30% consumed) = process bug; flag in run log
   so pg-state-keeper surfaces routine under-utilization.

2. All 10 routine frontmatters bumped ~3-5x:
   pg-file-backfiller 120/25 -> 400/100
   pg-corpus-maintainer 80/20 -> 250/60
   pg-quality-auditor 80/20 -> 250/60
   pg-docs-miner 60/20 -> 200/50
   pg-extension-anthropologist 70/20 -> 250/60
   pg-upstream-watcher 80/25 -> 200/50
   pg-community-pulse 100/30 -> 250/60
   pg-user-question-harvester 70/15 -> 200/50
   pg-evening-merger 150/30 -> 300/60
   pg-state-keeper 60/20 -> 150/40
   Cycle total: 850k/217k -> 2450k/590k.

6 producer recipes restructured to loop rather than pop-once:
file-backfiller (2-3 -> 10-20 files/run), extension-anthropologist
(1 -> 3-4), docs-miner (2 -> 6-10), quality-auditor (1 -> 5-10),
user-question-harvester (5-8 -> 20-30), corpus-maintainer glossary
top-15 -> top-50.

Expected: Phase A closes in ~3-4 months instead of ~18 at the same
nightly cadence; glossary stabilizes in ~4 weeks; audit queue cycles
in 3-5 days vs 24+.

Cron schedule unchanged. RemoteTrigger bootstrap unchanged (all new
behavior lives in the repo + arrives via the next git pull).

Session: sessions/2026-06-02-cloud-throughput-bump.md
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```
