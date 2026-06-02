---
name: pg-state-keeper
schedule: "43 5 * * * Europe/Prague"
fetches_source_via_url: false
queue: null
output_dirs: [progress, progress/_briefings]
skills_required: [pg-claude, memory-keeping, commit-message-style]
max_input_tokens: 60000
max_output_tokens: 20000
---

# pg-state-keeper

Two jobs in one routine, run after `pg-evening-merger` so it sees actual
merge outcomes:

1. **Refresh `progress/STATE.md`** to reflect overnight merges.
2. **Produce the morning briefing** — the single file the user reads each
   morning to see what cloud routines did, what needs attention, and
   what's coming.

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
   - **TLDR** — 3-5 bullets, headline of last night.
   - **Merged overnight** — table: routine, PR #, title, files +/-.
   - **Needs your attention** — open `cloud/*` PRs the merger couldn't
     resolve, each with the merger's stated concern.
   - **Routine health** — per-routine status (ran / skipped / failed),
     queue size remaining, last successful PR date.
   - **Cost estimate** — sum of `cost.total_tokens` across run logs; rough
     $ at current per-token rate (Opus 4.7: input $15/Mtok, output
     $75/Mtok — recompute if pricing changes).
   - **Forecast for tonight** — for each routine, queue head + which
     sources it will hit.
   - **Corpus growth this week** — rolling counts vs 7 days ago.
   - **Anomalies** — routines with 0 PRs ≥ 3 days, queue refill failures,
     sources returning 4xx/5xx repeatedly.
5. Write run log + self-review + open PR
   `[cloud:pg-state-keeper] morning briefing <YYYY-MM-DD>`.

## Failure modes

- Zero merges + zero open cloud PRs → still produce a one-paragraph
  "quiet day" briefing. Absence of activity is itself a signal.
- A routine's run log missing → note "no log" under Routine health,
  don't fail the briefing.

## Budget

60k input / 20k output.
