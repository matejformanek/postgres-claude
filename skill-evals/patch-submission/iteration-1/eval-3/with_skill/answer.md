# One-line numeric.c bug fix — do I need the full dance?

Short answer: **yes, you still go through pgsql-hackers + CommitFest**,
but you can skip the design-thread step for a trivial bug fix.

## What you skip

- The "post a design proposal first" step from pre-flight. For an obvious
  bug fix, jumping straight to a patch is fine — the diff *is* the
  proposal.

## What you still do

- **Develop the fix on `master`.** Even though it's a bug fix that may
  eventually want backpatching, you submit against master. Backpatch
  decisions and the actual backpatch commits are the committer's job, not
  yours — they decide whether the fix qualifies (frequently-encountered /
  low-risk / security / data-corruption are the four backpatch criteria).
- **Include a regression test.** You already have one — good. A bug fix
  without a test is the #1 reason small fixes get bounced.
- **Run the suite** in `dev/build-debug`: `ninja && meson test`.
- **Format the patch** with `git format-patch -v1 master..HEAD` (yes, even
  for a single-commit fix; the convention is universal).
- **Send to pgsql-hackers@lists.postgresql.org**, plain text, patch as
  attachment, with a short cover that says: what the bug is, what the fix
  does, target = master, builds + tests pass, platforms tested. Mark it
  **ready for review**.
- **Register on commitfest.postgresql.org** under the open CF (currently
  `PG20-1`). Title mirrors the patch subject, paste the Message-Id URL.
- **Review one other patch** in the same CF — the bartering norm applies
  even to small fixes.

## The anti-checklist still applies

- No HTML email
- No top-posting on replies
- Patch attached, not in body
- `git diff --check` clean (no trailing whitespace)
- No corporate confidentiality footer

## After commit

The committer will run pgindent, write the final commit message with the
`Author:` / `Reviewed-by:` / `Discussion:` trailers, and decide on
backpatch. If it qualifies, they backpatch across the supported branches
(currently 14–18). You don't need to produce per-branch patches yourself
unless explicitly asked.

So: not the *whole* dance, but the format-patch + -hackers + CF loop is
still mandatory. Mailing it directly to a committer bypasses the visible
review trail and is discouraged.
