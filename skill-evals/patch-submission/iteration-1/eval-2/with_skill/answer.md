# Posting the revised patch after "Waiting on Author"

You're in the standard review cycle. Here's the exact procedure.

## 1. Address every comment

For each reviewer point, either fix it or, if you disagree, write an inline
reply on the thread explaining *why* — don't silently ignore. Reviewers
notice ignored items and the CF entry stalls.

For the two items you mentioned:
- **Wider test case**: add it under `src/test/regress` (or TAP under
  `src/test/`) as part of the same patch series.
- **Error-message style**: re-check against the project's message style
  guide (the `error-handling` / `coding-style` notes in this repo, and
  `doc/src/sgml/sources.sgml` "Error Message Style Guide").

## 2. Clean up the history again

The community reviews **commits**, not squashed blobs. So:

```bash
git log --oneline master..HEAD
git rebase -i master    # fold the fixup commits into the right logical commits
```

The v2 should look like a clean rewrite of v1 with the requested changes
folded in — not v1 + a "fix review comments" commit on top.

Also rebase onto current master so the patch applies cleanly:

```bash
git fetch upstream
git rebase upstream/master
```

If anything broke, fix and re-run `ninja && meson test` in
`dev/build-debug`.

## 3. Generate v2

```bash
git format-patch -v2 master..HEAD
# → v2-0001-…patch, v2-0002-…
git diff --check master..HEAD     # whitespace
```

The `-v2` bumps the series version. On the next round it's `-v3`, etc.

## 4. Reply on the *same thread*

**Do not start a new thread.** Reply to the most recent message on the
existing patch thread, plain text only, with the v2 patches as attachments
(not inline). In the reply body:

- Brief summary of what changed since v1 (bullet list mapped to the
  reviewer's points works well)
- Inline responses to each of the reviewer's concrete asks, beneath the
  quoted text — no top-posting
- Note that it still builds + tests pass, mention platforms re-tested

## 5. Flip the CF entry back to Needs Review

On <https://commitfest.postgresql.org/> open your entry and change status
from **Waiting on Author** back to **Needs Review**. This is the signal
to the original reviewer (or the CF manager) that the ball is in their
court again.

If the reviewer doesn't pick it back up promptly and the CF is closing,
the patch usually gets **Moved to next CommitFest** rather than rejected
— but stay responsive, because patches that stall for a full CF without
author activity get **Returned with Feedback**.
