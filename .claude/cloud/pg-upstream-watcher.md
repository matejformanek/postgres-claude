---
name: pg-upstream-watcher
schedule: "23 21 * * * Europe/Prague"
fetches_source_via_url: true
queue: null
output_dirs: [knowledge/upstream-deltas, knowledge/buildfarm-lessons, progress]
skills_required: [pg-claude, memory-keeping, wal-and-xlog, executor-and-planner, locking, coding-style]
max_input_tokens: 200000
max_output_tokens: 50000
---

# pg-upstream-watcher

Explain new upstream commits since the anchor SHA and surface interesting
buildfarm failures. Merges upstream-deltas-explainer + buildfarm-miner.

## Inputs

- Anchor SHA: read from `progress/STATE.md` (line "Source commit at last
  verification:").
- Commit list: `https://api.github.com/repos/postgres/postgres/commits?sha=master&since=<iso-24h-ago>&per_page=100`
  (paginate via `Link: rel="next"` until exhausted; cap at 5 pages).
- Per-commit diff (only for commits selected for deep treatment):
  `https://github.com/postgres/postgres/commit/<sha>.diff`.
- Buildfarm RSS: `https://buildfarm.postgresql.org/cgi-bin/show_failures.pl`.

## Per-run recipe

1. Load skills: `pg-claude`, `memory-keeping`. Lazily load subsystem skills
   (`wal-and-xlog`, `executor-and-planner`, `locking`, `coding-style`) per
   commit area when the diff touches that subsystem's files.
2. Branch: `cloud/pg-upstream-watcher/<YYYY-MM-DD>`.
3. Fetch commit list since anchor SHA's timestamp (or last 24h, whichever is
   smaller). Record each fetch URL + status in run log.
4. For each commit (cap 50/day): one-line explainer with author, subject,
   files touched (top 3), 1-sentence "what changed".
5. Pick up to 5 commits flagged "interesting" (heuristic: touches
   `src/backend/storage`, `src/backend/access`, `src/backend/optimizer`,
   `src/backend/executor`, `src/backend/replication`, or any header in
   `src/include/`). For each: fetch its diff, write a 5-15-line deep
   explainer with file:line cites and `[[link]]` into corpus.
6. Output → `knowledge/upstream-deltas/<YYYY-MM-DD>.md`.
7. If any commits land, also generate a `/refresh-upstream`-style cross-ref
   report at `progress/refresh-<YYYY-MM-DD>.md` listing potentially-impacted
   corpus files (grep `knowledge/files/<changed-path>.md`).
8. **Buildfarm:** fetch RSS, pick 3-5 failures from the last 24h that aren't
   obvious flakes. For each: animal name, branch, stage, failure URL,
   1-paragraph rootcause guess. Output →
   `knowledge/buildfarm-lessons/<YYYY-MM-DD>.md`.
9. **Anchor bump:** if (and only if) the commits explained produce zero
   corpus-impact crossrefs (i.e., none touch a path with an existing
   per-file knowledge doc), bump the anchor SHA in `progress/STATE.md` to
   the newest fetched commit. Otherwise leave the anchor alone — the human
   refresh pass updates it after reviewing corpus impact.
10. Write run log + self-review + open PR
    `[cloud:pg-upstream-watcher] <n> commits · <m> bf failures`.

## Failure modes

- GitHub API 403 / 429 → log, exit `rate-limited`, no PR. (Authenticated
  rate is 5000/h — recommend `GH_TOKEN` env in cloud task.)
- Buildfarm RSS down → write deltas only, skip the buildfarm section.
- Zero new commits AND zero new bf failures → no PR; `exit_reason:
  queue-empty`.

## Budget

80k input / 25k output. Cap each diff fetch at 8k; commit-list pages are
~5-15k each.
