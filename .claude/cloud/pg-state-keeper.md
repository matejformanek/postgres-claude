---
name: pg-state-keeper
schedule: "43 5 * * * Europe/Prague"
fetches_source_via_url: false
queue: null
output_dirs: [progress, progress/_briefings]
skills_required: [pg-claude, memory-keeping, commit-message-style]
max_input_tokens: 150000
max_output_tokens: 40000
---

# pg-state-keeper

Three jobs in one routine, run after `pg-evening-merger` (02:11) so it sees
actual merge outcomes and every sibling routine has already had its slot:

1. **Refresh `progress/STATE.md`** to reflect overnight merges.
2. **Audit all 9 sibling routines** — this routine is the **watchdog**. For
   every other routine it must produce an explicit verdict (`OK` / `SKIPPED`
   / `FAILED` / `SILENT`) so the user knows, each morning, whether anything
   needs fixing. A routine that died before writing its log must NOT pass
   silently — see the roster check below.
3. **Produce the morning briefing** — the single file the user reads each
   morning. It **leads** with the audit's `🔧 Needs fix` section, then the
   rest.

## Routine roster (the 9 siblings this watchdog must account for)

By 05:43 all of these have had their slot. Compare this roster against the
run logs actually present for the cycle — any routine on the roster with no
log is `SILENT` (a failure to investigate, not an absence to shrug at):

`pg-community-pulse 20:11 · pg-docs-miner 20:47 · pg-upstream-watcher 21:23 ·
pg-extension-anthropologist 22:07 · pg-file-backfiller 22:53 ·
pg-quality-auditor 23:31 · pg-corpus-maintainer 00:13 ·
pg-user-question-harvester 00:47 · pg-evening-merger 02:11`

**Verdict definitions** (assign exactly one per sibling):
- `OK` — run log present, `exit_reason: ok`, PR opened (or cleanly merged).
- `SKIPPED` — `.cloud-skip-<routine>` present, or `exit_reason` is
  `skipped` / `queue-empty`. Expected idleness, not a problem.
- `FAILED` — run log present but `exit_reason` is `error:*` / non-ok; OR an
  open `cloud/<routine>/*` PR the merger flagged as unresolved; OR the log's
  `sources` show the same URL returning 4xx/5xx repeatedly.
- `SILENT` — **no run log for the cycle at all** (roster minus present
  logs). Most serious: the routine likely never started, failed to clone,
  or crashed before logging. Always lands in `🔧 Needs fix`.

**Audit limitation (state in the briefing methodology):** from inside the
cloud sandbox this routine **cannot** query the routine/trigger control
plane for true run status. Its ground truth is the committed run logs +
`gh pr list` + `git log`. The roster check above is precisely what catches a
routine that produced nothing.

## Inputs

- `git log main --since="24 hours ago" --pretty=format:'%H %s'`
- `gh pr list --state merged --search "merged:>=<yesterday-iso>" --json
  number,title,headRefName,mergedAt,additions,deletions,changedFiles`
- `gh pr list --state open --search "head:cloud/" --json
  number,title,headRefName,createdAt,url`
- `progress/cloud-routines/_digest/<yesterday>.md` (merger's own log)
- Per-routine run log:
  `progress/cloud-routines/<routine>/<yesterday>.md` × 9 — collect each's
  `tried` / `found` / `skipped` / `sources` / `cost` fields.
- All 10 recipe files in `.claude/cloud/*.md` (for tonight's forecast).
- Queue heads: `head -20 progress/_queues/*.md` (forecasted next pops).

## Per-run recipe

1. Load `pg-claude`, `memory-keeping`, `commit-message-style`.
2. Branch: `cloud/pg-state-keeper/<YYYY-MM-DD>`.
3. **Update `progress/STATE.md`:**
   - Bump "Last activity" line with a one-paragraph summary of overnight
     merges.
   - Refresh coverage counters from the day's merges (count new files in
     `knowledge/files/`, `knowledge/wiki-distilled/`, etc.).
   - Append a one-line entry to `progress/STATE-log.md` (create if absent):
     `<date> <merged-count> PRs · <files-added> files · <tokens> tokens`.
4. **Write briefing** at `progress/_briefings/<YYYY-MM-DD>.md`:
   - **🔧 Needs fix** (FIRST section — the watchdog headline) — every
     `FAILED` and `SILENT` routine, one line each, with the most specific
     cause available: the `exit_reason` text, "no run log for the cycle"
     for `SILENT`, or the failing source URL + HTTP status. If none, write
     "All 9 routines healthy." Distinct from "Needs your attention" below
     (which is about unresolved PRs, not broken routines).
   - **TLDR** — 3-5 bullets, headline of last night.
   - **Merged overnight** — table: routine, PR #, title, files +/-.
   - **Needs your attention** — open `cloud/*` PRs the merger couldn't
     resolve, each with the merger's stated concern.
   - **Routine health** — table with one row per sibling: routine, verdict
     (`OK` / `SKIPPED` / `FAILED` / `SILENT` per the definitions above),
     queue size remaining, last successful PR date. Every roster routine
     must appear — no omissions.
   - **Cost estimate** — sum of `cost.total_tokens` across run logs; rough
     $ at current per-token rate (Opus 4.8: input $15/Mtok, output
     $75/Mtok — recompute if pricing changes).
   - **Forecast for tonight** — for each routine, queue head + which
     sources it will hit.
   - **Corpus growth this week** — rolling counts vs 7 days ago.
   - **Anomalies** — routines with 0 PRs ≥ 3 days, queue refill failures,
     sources returning 4xx/5xx repeatedly.
5. Write run log + self-review + open PR
   `[cloud:pg-state-keeper] morning briefing <YYYY-MM-DD>`. The run log's
   `found` field must include a one-line audit roll-call:
   `OK: <n> · SKIPPED: <n> · FAILED: [<routines>] · SILENT: [<routines>]`.

## Failure modes

- Zero merges + zero open cloud PRs → still produce a one-paragraph
  "quiet day" briefing. Absence of activity is itself a signal.
- A routine's run log missing → classify it `SILENT` and surface it under
  `🔧 Needs fix`. Do **not** treat a missing log as a benign "no log" note;
  a routine that should have run and left nothing is the watchdog's whole
  reason to exist. (The briefing itself is still produced.)

## Budget

60k input / 20k output.
