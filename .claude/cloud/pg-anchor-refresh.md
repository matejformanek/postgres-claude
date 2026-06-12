---
name: pg-anchor-refresh
schedule: "37 3 * * * Europe/Prague"
fetches_source_via_url: true
queue: null
output_dirs: [progress, progress/_queues, knowledge]
skills_required: [pg-claude, memory-keeping]
max_input_tokens: 250000
max_output_tokens: 50000
---

# pg-anchor-refresh

The 11th cloud routine. Closes the drift question: every night, fetch
the latest upstream `master`, compute what changed since the corpus
anchor, identify which corpus docs are now potentially stale, queue
them for `pg-quality-auditor` re-verification, and bump the anchor in
`progress/STATE.md` to current master.

## Why this exists (separate from `pg-upstream-watcher`)

`pg-upstream-watcher` already fetches new commits daily and writes
`knowledge/upstream-deltas/<date>.md`. Its step 9 anchor-bump rule
fires **only** when zero corpus-known paths are touched — which is
almost never (real PG work lands daily). The anchor sits stuck.

`pg-anchor-refresh` is the **intentional drift acknowledgment**: it
ALWAYS bumps the anchor, and the cost of doing so is paid by queuing
the affected docs for audit. The two routines are complementary:

| Routine | Job |
|---|---|
| `pg-upstream-watcher` | Explain new commits + buildfarm — narrative output |
| `pg-anchor-refresh` | Move the anchor + queue impact — bookkeeping output |

Scheduled at 03:37 (right after `pg-evening-merger` at 02:11) so the
new anchor is in main when `pg-state-keeper` runs its 05:43 briefing.

## Inputs

- Current anchor: read from `progress/STATE.md` (the
  `Source commit at last verification:` line, or the `Phase:` line's
  closest SHA).
- `git fetch origin master` data via WebFetch on the GitHub API:
  `https://api.github.com/repos/postgres/postgres/commits?sha=master&
   since=<anchor-commit-timestamp>&per_page=100` (paginated).
- Per-commit touched-files via:
  `https://api.github.com/repos/postgres/postgres/commits/<sha>`
  (limit fetch to commits the orchestrator selects as "interesting"
  to avoid burning budget).

## Per-run recipe

1. Load `pg-claude`, `memory-keeping`.
2. Branch: `cloud/pg-anchor-refresh/<YYYY-MM-DD>`.
3. **Read current anchor.** From `progress/STATE.md`, find the most
   recent `e<7+ hex>` SHA labelled as "anchor" or "Source commit at
   last verification". If none found, log "anchor unknown" and exit
   `error: anchor-unparseable`.
4. **Fetch commit list since anchor.** Use the GitHub commits API
   `since=<anchor-timestamp>`; paginate via `Link: rel="next"` up
   to 5 pages (500 commits / ~10 days of upstream churn — well
   beyond a daily refresh window).
5. **Compute the touched-paths set.** For each commit in the range,
   fetch its `/commits/<sha>` detail to get the `files` array.
   Aggregate path → committers/dates list. Cap to top 200 paths if
   the range is unusually long.
6. **Cross-reference against the corpus.** For each touched path
   `src/<sub>/<x>.c`, check whether `knowledge/files/src/<sub>/<x>.c.md`
   exists. Build two sets:
   - `IMPACTED` — paths with an existing per-file doc (audit candidates)
   - `UNTRACKED` — paths without a per-file doc (already on the
     coverage queue or in the deferred-mechanical bucket)
7. **Queue impacted docs for `pg-quality-auditor`.** Append each
   `IMPACTED` path to `progress/_queues/audits.md` with the new entry
   format:
   ```
   [pending] knowledge/files/<path>.md  reason=anchor-bump <YYYY-MM-DD>:<old-anchor>..<new-anchor>
   ```
   Skip paths already `[pending]` in the queue (idempotent).
8. **Identify subsystem impact.** For each `IMPACTED` path, find its
   `knowledge/subsystems/<x>.md` parent. If a subsystem has ≥ 5
   impacted files in this run, queue the subsystem doc itself for
   audit (the "Owners" block + `## Invariants` may need refresh).
9. **Write the run log.**
   `progress/cloud-routines/pg-anchor-refresh/<YYYY-MM-DD>.md` with:
   - tried: anchor refresh
   - found: `<old-anchor>` → `<new-anchor>` (N commits)
   - sources: GitHub API URLs + HTTP status
   - cost: token usage
   - exit_reason: ok
   - **subsystem-impact-table**: one row per touched subsystem with
     impacted-file count + top author.
10. **Write the state-log entry** (per `_loader.md` §5.5):
    `progress/cloud-routines/_state-log/pg-anchor-refresh-<YYYY-MM-DD>.md`:
    ```
    **pg-anchor-refresh** <YYYY-MM-DD> — anchor <old> → <new>; <N>
    commits; <K> docs queued for audit (PR #<n>).
    ```
11. **Bump the anchor in `progress/STATE.md`.** Edit the
    "Phase:"-area `e<7-hex>` SHA in-place (NOT a prepend — per
    `_loader.md` §5.5 the only file that gets head-prepended is via
    the merger's consolidated line; STATE.md anchor lives mid-file).
    If the SHA appears in multiple places (Phase line + Source-commit
    line), update all of them.
12. **Self-review + open PR**
    `[cloud:pg-anchor-refresh] anchor <old>..<new> · <K> docs queued`.
    Body lists the impacted subsystems + their file counts + a
    representative-commit cite per subsystem.

## Failure modes

- **Anchor unparseable** → run log `error: anchor-unparseable`,
  exit non-zero, no PR. `pg-state-keeper` will surface it.
- **GitHub API 403/429** → log status, exit `error: rate-limited`,
  no PR. Anchor unchanged. Retry next night.
- **Zero commits since anchor** (caught up) → write run log
  "anchor current — zero new commits", **no PR**, exit `ok`.
- **>500 commits since anchor** (routine missed multiple days) →
  process up to 500, log "partial: <N> processed, <M> remain", PR
  with what was done. Next night picks up the residue.
- **`progress/_queues/audits.md` doesn't exist** → create it from
  the template, log "queue file created", proceed.
- **A path's doc was deleted between anchor + now** → mark as
  `[skipped:doc-removed]` in the queue, note in run log.

## Budget

250k input / 50k output. Commit-list pages are ~5-15k each;
per-commit detail fetches ~3-8k each. Targeting up to 100 commits
typical, ~50 detail fetches → ~150k input. Output is the queue
append + run log + PR body → ~10-20k. Comfortably within budget.

## Interaction with other routines

- **`pg-quality-auditor`** is the primary consumer. Its
  `progress/_queues/audits.md` head grows with each refresh; the
  audit routine processes it in priority order.
- **`pg-upstream-watcher`** runs at 21:23. Its commit-explainer
  output becomes additional context for the morning's
  `pg-state-keeper` briefing; this routine's anchor-bump is the
  *bookkeeping* side. They don't race because they touch different
  files.
- **`pg-state-keeper`** at 05:43 reads STATE.md + the state-log.
  The new anchor is visible to the morning briefing.
- **`pg-evening-merger`** at 02:11 runs *before* this routine. The
  merger handles same-night PRs; this routine's PR lands in the
  next-day merger.

## Roll-out

Day 1 after merge: trigger manually to seed the queue. The
`pg-quality-auditor` will pick up the impacted docs on its 23:31
run.

Day 2+: routine fires nightly. Steady-state: ~10-50 new commits/day,
~5-15 impacted docs/day (most days), ~30-60 docs queued per week.
`pg-quality-auditor` at its current 7-doc/night audit cadence is
exactly sized to keep up (~50 audits/week target after #151's
recipe bump pushes it from 6-10 toward the budgeted 10-15).

## Cross-references

- `.claude/cloud/_loader.md` §5.5 — STATE.md write discipline
- `.claude/cloud/pg-upstream-watcher.md` — sibling routine (narrative)
- `.claude/cloud/pg-quality-auditor.md` — consumer of the audit queue
- `.claude/cloud/pg-state-keeper.md` — reads the new anchor each morning
- `progress/STATE.md` — anchor source-of-truth
- `progress/_queues/audits.md` — queue this routine writes to
