# One-line numeric.c bug fix — do I need the full dance?

Short answer: **yes, you still go through pgsql-hackers + CommitFest**,
but the design-discussion step can be skipped for an obvious bug fix.

## What you skip

- The "post a design proposal first" step from pre-flight. For an
  obvious bug fix, jumping straight to a patch is fine — the diff *is*
  the proposal.

## What you still do

- **Develop the fix on `master`.** Even though it's a bug fix that may
  eventually want backpatching, you submit against master. The committer
  decides whether the fix qualifies for backpatch — the four criteria
  are:
  1. Frequently-encountered bug fixes
  2. Low-risk fixes
  3. Security fixes
  4. Data-corruption fixes
  Never new features. If your fix qualifies, the committer backpatches
  across supported branches (currently 14–18).
- **Include a regression test.** You already have one — good. A bug fix
  without a test is the #1 reason small fixes get bounced.
- **Rebase onto current master** before formatting so the patch applies
  cleanly: `git fetch origin && git rebase origin/master`. Doesn't-apply
  is the most common silent rejection reason.
- **Run the suite** in `dev/build-debug`: `ninja && meson test`.
- **Format the patch**: `git format-patch -v1 master..HEAD`. Convention
  is universal even for one-commit fixes.
- **Send to pgsql-hackers@lists.postgresql.org** — plain text,
  attachment, with a short cover that states the bug, the fix, target =
  master, build + tests pass, platforms tested. Tag it **ready for
  review** (not WIP — you're not asking for shape feedback).
- **Register on commitfest.postgresql.org** under the open CF (currently
  `PG20-1`). Title mirrors the patch subject; paste the Message-Id URL.
  Topic: the closest backend subsystem (for numeric.c that's roughly
  `Server / Numerics & data types`).
- **Review at least one other patch** in the same CF — the bartering
  norm applies even to small fixes.

## The anti-checklist still applies

- No HTML email
- No top-posting on replies
- Patch as attachment, not pasted in body
- `git diff --check master..HEAD` clean (no trailing whitespace)
- No corporate confidentiality footer

## After commit

The committer runs pgindent, writes the final commit message with the
`Author:` / `Reviewed-by:` / `Discussion: https://postgr.es/m/<id>` /
`Backpatch-through:` trailers, and decides on backpatch. You don't
produce per-branch patches yourself unless explicitly asked — backpatch
commit messages should be **identical** across branches so release-note
tooling can deduplicate, which is the committer's job.

So: not the *whole* dance, but format-patch + -hackers + CF is still
mandatory. Mailing directly to a committer bypasses the visible review
trail and is discouraged.
