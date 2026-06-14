---
name: patch-submission
description: Prepare a PostgreSQL change for upstream submission to pgsql-hackers — git format-patch the series, write the cover letter, register a CommitFest (CF) entry, run pgindent / check-world / docs build, and stage the v1 patchset for mailing. Thin wrapper; the review machinery lives in `pg-patch-review` (--self mode) and the commit-message format in `commit-message-style`. Use proactively whenever the user wants to send a PG patch upstream, format-patch for pgsql-hackers, land a change on master, or register a CF entry. Do NOT trigger for GitHub PRs, npm/crate releases, LKML kernel patches, or generic "open source contribution" questions.
when_to_load: Format-patch + cover letter + CF registration for a PG patch about to go to pgsql-hackers; v(N+1) re-submission after review cycle.
companion_skills:
  - pg-patch-review
  - review-checklist
  - commit-message-style
  - coding-style
  - testing
---

# patch-submission — thin wrapper for the upstream mail

This skill is the **mechanics** of sending a PG patch upstream:
format-patch, cover letter, CF entry, review-cycle bookkeeping. The
**review content** (build, tests, design fit, completeness, style) lives
in two other skills:

- **`pg-patch-review --self`** — runs the 5-critic fan-out + Phase 0
  reflex gates + REJECT-track decision against your own diff. Run this
  BEFORE format-patching. Any blocking finding = stop, fix, re-run.
- **`commit-message-style`** — the upstream PG commit-message format
  (no `Co-Authored-By`, imperative title, Author / Reviewed-by /
  Discussion / Backpatch-through trailer block).

Don't re-derive their rules here.

## Method — six steps

### 1. Self-review gate (REQUIRED first)

Run `pg-patch-review` in `--self` mode against the local branch.

- Stage 3 returns Ready-for-Committer → proceed to step 2.
- Waiting-on-Author / Needs-info / REJECT-A/B → fix and re-run.
- REJECT-C → escalate to user (your verdict probably needs revision).

### 2. Rebase onto current upstream master

```bash
git fetch origin && git rebase origin/master
git log --oneline master..HEAD             # confirm the series
git diff --check master..HEAD              # whitespace clean
```

A v(N) that doesn't apply against current master is the most common
reason a CF entry gets bounced back without review.

### 3. Format-patch the series

```bash
git format-patch -v1 master..HEAD          # first send
git format-patch -v3 master..HEAD          # nth re-submission
```

Filenames: `vN-NNNN-<subject>.patch`. Verify each commit message
follows `commit-message-style` before generating the patches; the
subject line of each patch becomes the email subject.

### 4. Compose the cover email

Send to **pgsql-hackers@lists.postgresql.org**, **plain text only**,
patches as attachments (not inline). Body covers:

- One-paragraph summary of the problem.
- One paragraph on the solution / why this approach.
- Target branch (`master`).
- Confirmation it builds + `ninja test` passes.
- Platforms tested.
- Performance notes if relevant.
- Link to prior discussion via `https://postgr.es/m/<message-id>`.
- Tag: **WIP** (want shape feedback) or **ready for review**.

If replying to an existing thread (v(N+1)), **reply** — don't start a
new thread.

### 5. Register the CommitFest entry

After sending, go to <https://commitfest.postgresql.org/> and add an
entry to the **open** CF:

- Title (mirror the patch subject).
- Authors.
- Target version (`master` / next major).
- Topic — pick the closest backend subsystem.
- Thread Message-Id (URL of your -hackers post on
  `https://www.postgresql.org/message-id/<id>`).

Then **review at least one other patch** in the same CF — the
bartering norm. Skipping it is noticed.

### 6. Review-cycle loop

When a reviewer responds, CF flips to **Waiting on Author**:

1. Address every point. For disagreements, explain in the reply
   rather than silently ignoring.
2. **Fold fixes into the right logical commit via `git rebase -i
   master`** — don't ship a "fix review comments" commit on top. v(N+1)
   should be a clean rewrite of v(N) with the asks applied.
3. Re-run `pg-patch-review --self` against the rebased branch.
4. `git format-patch -v<N+1>` + reply on the same thread.
5. Flip CF entry back to **Needs Review**.

## Email anti-checklist (will get the patch bounced)

- HTML email — never. Plain text only.
- Top-posted reply — never. Reply inline under quoted lines.
- Patch pasted into email body instead of attached.
- Patch that doesn't apply cleanly to current master.
- Corporate confidentiality footer.

The `pg-patch-review --self` step covers test / doc / catversion gaps;
not duplicated here.

## After commit

The committer runs pgindent / pgperltidy, writes the final commit
message with `Author:` / `Reviewed-by:` / `Discussion:` trailers,
decides on backpatch (bug fixes only — see versioning policy), and
commits. Your CF entry flips to **Committed**. Done.

## Cross-references

- `.claude/skills/pg-patch-review/SKILL.md` — `--self` mode for the review content this skill no longer duplicates.
- `.claude/skills/review-checklist/SKILL.md` — eight-phase scaffold (Phase 0 REJECT-track + reflex gates) that `pg-patch-review --self` invokes.
- `.claude/skills/commit-message-style/SKILL.md` — upstream PG format for the per-commit messages this skill format-patches.
- `.claude/skills/coding-style/SKILL.md` — pgindent + warnings check that the self-review walks.
- `.claude/skills/testing/SKILL.md` — `make check` / `ninja test` flavor selection.
- `knowledge/community/patch-workflow.md` — long-form workflow reference.
- `knowledge/community/review-patterns.md` — how reviewer comments are structured (so you can address them well).
- [wiki: Submitting a Patch](https://wiki.postgresql.org/wiki/Submitting_a_Patch)
- [wiki: CommitFest](https://wiki.postgresql.org/wiki/CommitFest)
