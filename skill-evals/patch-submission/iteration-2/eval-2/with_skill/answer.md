# Posting the revised patch after "Waiting on Author"

You're in the standard review cycle. Here's the exact procedure.

## 1. Address every comment

For each reviewer point, either fix it or, if you disagree, write an
inline reply on the thread explaining *why* — never silently ignore.
Reviewers notice ignored items and the entry stalls.

For the two specific items:
- **Wider test case**: add it to the existing test file under
  `src/test/regress` (or TAP under `src/test/`) as part of the same
  patch series.
- **Error-message style**: re-check against the **Error Message Style
  Guide** in `doc/src/sgml/sources.sgml` (the in-repo `error-handling`
  skill summarizes the rules — capitalization, period vs no period,
  primary vs detail vs hint).

## 2. Fold the fixes into the right commits and rebase onto current master

The community reviews commits, not blobs. Do **not** ship v(N) + a "fix
review comments" commit on top — v(N+1) should look like a clean
rewrite with the asks applied.

```bash
git rebase -i master    # fold each fix into the relevant logical commit
git fetch origin
git rebase origin/master
```

The second rebase makes sure the series still applies cleanly to current
upstream master — patches that don't apply are bounced without review.

Re-run the suite before formatting:

```bash
cd dev/build-debug && ninja && meson test
```

## 3. Generate v2

```bash
git format-patch -v2 master..HEAD
# → v2-0001-…patch, v2-0002-…
git diff --check master..HEAD     # whitespace
```

The `-v2` bumps the series version. On the next round it's `-v3`, etc.

## 4. Reply on the *same thread*

**Do not start a new thread.** Reply to the most recent message on the
existing patch thread, **plain text only**, with the v2 patches as
**attachments** (not inline), no HTML, no top-posting (reply inline
beneath the quoted block). In the body:

- Brief summary of what changed since v1 (bullet list mapped to the
  reviewer's asks works well)
- Inline responses to each concrete point, under the quoted text
- Note that it still builds + tests pass; mention platforms re-tested

## 5. Flip the CF entry back to Needs Review

On <https://commitfest.postgresql.org/> open your entry and change
status from **Waiting on Author** to **Needs Review**. This signals the
reviewer (or the CF manager) the ball is back in their court.

Stay responsive: patches that stall for a full CF without author
activity get **Returned with Feedback**. If the reviewer doesn't pick
it back up and the CF closes, the entry usually rolls — **Moved to next
CommitFest** — rather than being rejected.
