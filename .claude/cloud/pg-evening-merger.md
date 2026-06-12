---
name: pg-evening-merger
schedule: "11 2 * * * Europe/Prague"
fetches_source_via_url: false
queue: null
output_dirs: [progress/cloud-routines/_digest]
skills_required: [pg-claude, memory-keeping, review-checklist, commit-message-style, coding-style, patch-submission]
max_input_tokens: 300000
max_output_tokens: 60000
---

# pg-evening-merger

The single PR-handling routine. Reviews every open `cloud/*` PR, auto-merges
on green, attempts auto-fix on yellow, escalates to "human-needed" comment
on red.

## Inputs

- `gh pr list --state open --search "is:open is:pr head:cloud/" --json
  number,title,headRefName,author,createdAt,url`.

## Per-run recipe (per PR)

1. Load `pg-claude`, `memory-keeping`, `review-checklist`,
   `commit-message-style`, `coding-style`, `patch-submission`.
2. Branch: do not enter a new branch — operate on each PR's checkout.
3. For each open `cloud/*` PR (oldest first):
   1. `gh pr checkout <N>`.
   2. Run the `review-checklist` skill against the diff + the PR body's
      stated sources. Verify cited URLs returned 2xx (re-fetch HEAD on a
      couple of spot-checks; don't re-fetch everything).
   3. Verify the routine's run log exists and is well-formed under
      `progress/cloud-routines/<routine>/<YYYY-MM-DD>.md`.
   4. Verify queue markers were updated correctly (no orphan
      `[in-progress:<branch>]` from a *different* branch).
   5. Classify:
      - **Green** — checklist passes, run log valid, queue clean →
        `gh pr merge --squash --auto`.
      - **Yellow** (≤ 2 fixable issues — typos, missing run-log field,
        unrewritten queue marker) → fix locally on the PR branch, push,
        re-review. If now green → merge. If still yellow → comment listing
        the residual issues and leave open.
      - **Red** (architectural concern, cite verification failed,
        skill-eval drift unexplained, cross-branch corruption) → comment
        with the concerns and leave open for the next day's
        quality-auditor or the human.
4. On every merged PR: rewrite the corresponding queue entry's
   `[done:<placeholder>]` to `[done:<merge-sha>]`. This is one extra commit
   to main (not via PR — safe because it only edits queue files).
5. **Consolidated STATE.md prepend (added 2026-06-12, paired with
   `_loader.md` §5.5)**: read every file matching
   `progress/cloud-routines/_state-log/*-<YYYY-MM-DD>.md`, synthesise
   a SINGLE `**Last activity:** <date> (cloud) — <one-line per routine,
   semicolon-separated, max ~3 sentences total>` line, and prepend that
   one line to `progress/STATE.md`. This is the only STATE.md prepend
   of the night; sibling routines never touch STATE.md. (Falls back
   gracefully: if no `_state-log/*-<date>.md` files exist — e.g.
   during the rollout window before sibling recipes adopt §5.5 — skip
   the consolidated prepend and let sibling PRs continue prepending
   directly; the auto-rebase in "Failure modes" handles the residual
   collisions.)
6. Write digest at `progress/cloud-routines/_digest/<YYYY-MM-DD>.md`:
   - Table: PR #, routine, title, classification, action, link.
   - One-paragraph summary at top.
7. Commit + push the digest + STATE.md prepend + queue-marker rewrites
   directly to main (no PR — safe because the diff is consolidated
   log-style content, no shared state).
8. Write run log + self-review for this routine itself.

## Failure modes

- `review-checklist` skill fails to load → no merges; digest reports the
  breakage so `pg-state-keeper` surfaces it in the morning briefing.
- `gh` 5xx → log + retry once; on second failure, skip and continue.
- A PR has merge conflicts with main → check the conflict scope:
  - **`progress/STATE.md` ONLY, and both sides are `**Last activity:**`
    prepends to the head of the file** → auto-rebase the PR by accepting
    main's STATE.md and re-prepending the sibling's "Last activity" line
    at the new head. Re-push, re-review, merge if now green. This is
    safe because both sides are append-style log entries with no shared
    state. (Becomes obsolete once `_loader.md` §5.5 STATE.md
    serialization lands and siblings stop touching STATE.md.)
  - Any other conflict → comment "conflict, rebase needed", leave open.
    Do not auto-rebase.

## Budget

300k input / 60k output (matches frontmatter; reconciled 2026-06-12 — the
prior "150k/30k" footer was making the agent self-cap at half budget).
Sees every PR of the day; the cap now fits ~9 PRs at ~30k each, leaving
headroom for the auto-rebase path on STATE.md-only conflicts.
