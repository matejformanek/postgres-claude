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

The single PR-handling routine. Reviews **every open PR** on the
repo — both sibling cloud routines (`cloud/*` branches) AND the
human-authored corpus / feature PRs (`ft_*`, `hf_*` branches).
Auto-merges on green, attempts auto-fix on yellow, escalates to
"human-needed" comment on red. Prevents the open-PR backlog from
growing past one day.

**Why all PRs (added 2026-06-14):** the prior `head:cloud/`-scoped
behavior let the human-author backlog grow to 59 open PRs across
a single mining arc. The merger now owns the whole queue. Per-class
validation differs (see §3 below), but the lifecycle is the same:
checkout → validate → classify → act.

## Inputs

- `gh pr list --state open --limit 100 --json
  number,title,headRefName,author,createdAt,url,mergeable,mergeStateStatus`.
- No `head:` filter. Iterate all open PRs.
- **Sort:** by `number` ascending (oldest first). FIFO so cross-ref
  forward-refs land in the order they were promised.

## PR class detection

Branch-prefix taxonomy (used to pick the validation track):

| Prefix | Class | Source | Validation track |
|---|---|---|---|
| `cloud/<routine>/<date>` | **cloud** | sibling cron routine | §3.1 — run-log + queue marker + cited URLs |
| `ft_corpus_*` | **corpus** | human mining session | §3.2 — anti-target + cite-resolve + cross-ref + established shape |
| `ft_skills_*` | **skills** | skill-creator pass | §3.3 — rubric items + companion_skills + benchmark non-regression if claimed |
| `ft_session_*` | **session-log** | per-session log | §3.4 — append-only + dated + no protected paths |
| `ft_*` (other) | **feature** | feature work in `dev/` | §3.5 — R10 two-repo separation (no source/ patches in meta-repo PR) |
| `hf_*` | **hotfix** | meta-repo hotfix | §3.6 — single-purpose + named issue |

If the prefix doesn't match any of the above → §3.7 unclassified
(comment + leave open).

## Per-run recipe (per PR)

1. Load `pg-claude`, `memory-keeping`, `review-checklist`,
   `commit-message-style`, `coding-style`, `patch-submission`.
2. Branch: do not enter a new branch — operate on each PR's checkout.
3. For each open PR (oldest first):
   1. `gh pr checkout <N>`.
   2. Detect class via branch prefix (see table above).
   3. Run the class-specific validation track (§3.1–§3.7).
   4. Classify Green / Yellow / Red.
   5. Act:
      - **Green** — `gh pr merge --squash --auto`.
      - **Yellow** (≤ 2 fixable issues) → fix locally on the PR
        branch, push, re-review. If now green → merge. If still
        yellow → comment listing residual issues and leave open.
      - **Red** (architectural concern, cite drift unexplained,
        cross-branch corruption, scope violation) → comment with
        concerns and leave open for the next day's quality-auditor
        or the human.

### 3.1 — cloud class

Existing behavior (preserved verbatim):
- Run `review-checklist` against diff + PR body's stated sources.
  Verify cited URLs returned 2xx (re-fetch HEAD on a couple of
  spot-checks; don't re-fetch everything).
- Verify the routine's run log exists and is well-formed under
  `progress/cloud-routines/<routine>/<YYYY-MM-DD>.md`.
- Verify queue markers were updated correctly (no orphan
  `[in-progress:<branch>]` from a *different* branch).
- On merge: rewrite corresponding queue entry's `[done:<placeholder>]`
  → `[done:<merge-sha>]` (one extra commit to main, log-only).

### 3.2 — corpus class (NEW)

Validation track for `ft_corpus_*` PRs (human mining sessions):
- **Anti-target audit:** `git diff --stat origin/main..HEAD --
  knowledge/calibration knowledge/personas knowledge/files
  patches progress/STATE.md progress/cloud-routines CLAUDE.md
  pg-claude-plan.md` MUST be empty. Non-empty = **Red**.
- **Anchor-cite spot-check:** sample 3–5 file:line cites from
  added docs; verify each resolves in `source/...` at the
  current anchor in `progress/STATE.md` (or the anchor cited in
  the PR body). Drift on any sample = **Yellow** (open a fix
  commit if trivial — `±20` lines and same symbol), else **Red**.
- **Cross-ref resolve:** every `[[name]]` link in added files
  resolves to an existing target or to a still-open sibling PR
  in this batch (forward-refs are explicit). Broken refs to
  non-existent docs = **Yellow** (drop the ref).
- **Established shape:** every new `knowledge/idioms/*.md` /
  `knowledge/data-structures/*.md` opens with anchors block,
  has invariants section, has cross-references section, has
  useful greps section. Missing section = **Yellow**.
- **Scope discipline:** PR touches ≤ 4 doc files (the 3-doc
  cluster norm); >4 = **Yellow** (comment asking to split).
- **No `dev/` or `source/` paths.** Any source-tree edit in a
  meta-repo PR = **Red** (R10 violation).

### 3.3 — skills class (NEW)

Validation track for `ft_skills_*` PRs:
- **Frontmatter:** every edited `.claude/skills/<name>/SKILL.md`
  carries `name`, `description`, `when_to_load`,
  `companion_skills`. Missing any field = **Yellow** (add it).
- **Anchor-cite spot-check** (same as 3.2) for any file:line
  cites added.
- **Companion skills resolve:** every entry in `companion_skills`
  points to a real skill directory. Broken = **Yellow**.
- **Benchmark non-regression** (if the PR body claims one):
  read the cited `benchmark.json` deltas; any eval regressing =
  **Red** (revise before merge).
- **Anti-target audit** same as 3.2.

### 3.4 — session-log class (NEW)

Validation track for `ft_session_*` PRs:
- **Single-file scope:** PR adds exactly one
  `sessions/<YYYY-MM-DD>-*.md` file. Anything else = **Yellow**
  (comment asking to split).
- **No protected paths** (same anti-target audit).
- **Dated filename** matches the date in the body's "session"
  heading. Mismatch = **Yellow**.
- **No new claims about source/** that aren't already cited
  elsewhere. Session logs reference, they don't introduce.

### 3.5 — feature class (NEW)

Validation track for non-corpus `ft_*` PRs (anything that
might be feature work):
- **R10 separation check:** PR MUST NOT contain edits to
  `source/...` paths (that path is read-only). Any such edit =
  **Red**. (Real feature work lives in `dev/`, not in a meta-repo
  PR.)
- **Plan trailer in commits:** every commit message has a
  `Plan: planning/<slug>/plan.md` trailer if it's part of a
  feature implementation. Missing = **Yellow**.
- **Notes log present:** matching `planning/<slug>/notes.md`
  exists and has a section for each phase committed. Missing
  for a feature-implementation PR = **Yellow**.

### 3.6 — hotfix class

Validation track for `hf_*` PRs:
- Single-purpose: PR title names the specific fix; diff
  touches a focused set of files. Sprawl = **Yellow**.
- No new abstractions / refactors bundled in.
- Anti-target audit (same).

### 3.7 — unclassified

Branch prefix doesn't match any of the above:
- Comment: "Branch prefix `<prefix>` not recognized. Expected
  `cloud/`, `ft_corpus_`, `ft_skills_`, `ft_session_`, `ft_`, or
  `hf_`. Please rename or close."
- Leave open. Do not merge.

## Cross-PR coordination (NEW)

When merging in FIFO order, watch for forward-refs:

- A merging PR's `[[name]]` may point to a doc only added by a
  later open PR. That's expected; do NOT block on broken
  forward-refs to other PRs in this batch. The cross-ref audit
  re-runs at the **end** of the batch — by then every promised
  doc should be on main.
- If a forward-ref resolves to nothing even after the batch
  completes, open a `hf_corpus_<name>` follow-up PR with the
  retarget or drop.

## Merge-conflict handling

A PR has merge conflicts with main → check the conflict scope:

- **`progress/STATE.md` ONLY, and both sides are `**Last
  activity:**` prepends to the head of the file** → auto-rebase
  the PR by accepting main's STATE.md and re-prepending the
  sibling's "Last activity" line at the new head. Re-push,
  re-review, merge if now green. This is safe because both sides
  are append-style log entries with no shared state. (Becomes
  obsolete once `_loader.md` §5.5 STATE.md serialization lands
  and siblings stop touching STATE.md.)
- **Same `knowledge/<dir>/MEMORY.md` head-prepend** (when corpus
  PRs both prepend an index entry) → auto-rebase: accept main's
  MEMORY.md, re-prepend the sibling's entry at the head. Re-push,
  re-review, merge if green.
- **Anchor-refresh queue file** — if a `cloud/pg-anchor-refresh/*`
  PR conflicts on `progress/_queues/audits.md` with a sibling
  refresh (only the *most recent* anchor is valid), close the
  older PR with comment "superseded by #<newer>". This is the
  one auto-close case.
- Any other conflict → comment "conflict, rebase needed", leave
  open. Do not auto-rebase.

## Superseded-PR auto-close (NEW)

Some PR types have a natural "only the latest matters" semantic:

- **`cloud/pg-anchor-refresh/*`** — only the most recent date's
  refresh is valid. Older ones get auto-closed with comment
  "superseded by #<newer-PR>".
- **`cloud/pg-state-keeper/*`** — same; only today's briefing
  matters. Yesterday's is superseded.
- **`cloud/pg-corpus-maintainer/*`** — daily; one open at a
  time, older = superseded.

For all OTHER PR types (corpus, skills, session-log, feature,
hotfix), supersession is NOT automatic — they accumulate
independently and must each be merged on their own merit.

## Digest + STATE.md

5. **Consolidated STATE.md prepend (added 2026-06-12, paired
   with `_loader.md` §5.5)**: read every file matching
   `progress/cloud-routines/_state-log/*-<YYYY-MM-DD>.md`,
   synthesise a SINGLE `**Last activity:** <date> (cloud) —
   <one-line per routine, semicolon-separated, max ~3 sentences
   total>` line, and prepend that one line to
   `progress/STATE.md`. This is the only STATE.md prepend of
   the night; sibling routines never touch STATE.md. (Falls
   back gracefully: if no `_state-log/*-<date>.md` files exist —
   e.g. during the rollout window before sibling recipes adopt
   §5.5 — skip the consolidated prepend and let sibling PRs
   continue prepending directly; the auto-rebase in "Merge-
   conflict handling" handles the residual collisions.)
6. Write digest at `progress/cloud-routines/_digest/<YYYY-MM-DD>.md`:
   - **Table:** PR #, class, branch, title, classification,
     action, link.
   - **One-paragraph summary** at top: total seen, merged
     count, yellow count, red count, superseded-closed count,
     per-class breakdown.
7. Commit + push the digest + STATE.md prepend + queue-marker
   rewrites directly to main (no PR — safe because the diff is
   consolidated log-style content, no shared state).
8. Write run log + self-review for this routine itself.

## Failure modes

- `review-checklist` skill fails to load → no merges; digest
  reports the breakage so `pg-state-keeper` surfaces it in the
  morning briefing.
- `gh` 5xx → log + retry once; on second failure, skip and
  continue.
- A PR fails class detection → §3.7 unclassified flow (comment,
  leave open).
- Backlog > 30 PRs at start of run → process in two passes:
  first pass merges the obvious greens (cloud + corpus with
  zero issues); second pass takes yellows. This avoids a
  budget overrun when the queue is deep.
- A PR has `mergeable: CONFLICTING` AND `mergeStateStatus:
  DIRTY` AND is a superseded class (§ Superseded-PR auto-close)
  → close per the rule. Otherwise → "conflict, rebase needed"
  comment.

## Budget

300k input / 60k output (matches frontmatter; reconciled
2026-06-12 — the prior "150k/30k" footer was making the agent
self-cap at half budget). Sees every PR of the day across all
classes; the cap now fits ~9 PRs at ~30k each, leaving
headroom for the auto-rebase path on STATE.md-only conflicts.

When the backlog exceeds 20 PRs, the routine uses the
two-pass strategy (Failure modes ⇧) and may split work across
the next day's run. Digest documents the carry-over.
