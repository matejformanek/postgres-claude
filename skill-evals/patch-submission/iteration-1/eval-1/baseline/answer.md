# Getting your autovacuum GUC feature on pgsql-hackers

Here's how I'd approach upstreaming a new feature like this.

## 1. Make sure it's ready

Before sending anything, make sure:

- It builds cleanly and the test suite passes
- You've added tests for the new behavior (regression tests under `src/test/regress` is the usual home)
- You've updated the docs — for a GUC that means the autovacuum/config docs under `doc/src/sgml/`
- Your commits are reasonably clean (squash WIP commits)

## 2. Generate patches with git format-patch

PostgreSQL uses an email-based workflow, so you produce patches with:

```bash
git format-patch -v1 master..HEAD
```

This creates `v1-0001-....patch` files. The `-v1` is the version of the patch series; if you have to revise after review, you'll bump to `-v2`, `-v3`, etc.

## 3. Send to pgsql-hackers

Send to **pgsql-hackers@lists.postgresql.org**. A few things to know about that list:

- Plain text email only — no HTML
- Patch as an attachment, not pasted in
- Include a short description of what the patch does, why, target branch (master), and confirmation it builds and passes tests
- Mention platforms tested and any performance considerations

For a non-trivial feature like a new autovacuum knob, you may want to start with a **design discussion** on -hackers before sending the patch, because the community has strong opinions and might prefer a different shape. If you've already had that conversation, just go ahead with the patch.

## 4. Register in the CommitFest

After the email goes out, register the patch at <https://commitfest.postgresql.org/>. You'll need:

- A title
- The message-id link to your email on the list
- Target version

The CommitFest is where review gets tracked.

## 5. Be responsive to review

Once a reviewer engages, they'll leave feedback. Address each point (or argue back if you disagree), then post `v2` as a reply to the same thread. Don't start a new thread for each revision.

It can be slow — a non-trivial feature may go through several CommitFests before landing.

That's the gist. Want help drafting the cover email?
