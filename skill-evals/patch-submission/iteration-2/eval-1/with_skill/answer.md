# v1 submission walkthrough — autovacuum-aggressiveness GUC

## 0. Pre-flight

Before formatting anything:

- A new GUC affecting autovacuum behavior is **non-trivial**. Has the
  design been discussed on pgsql-hackers? If not, the right next step is
  a design email, not a v1 patch — I can draft that instead. A finished
  patch built against an approach -hackers will reject is wasted work.
- Target branch: `master`. New features never go to back branches.
- Check the archives + open CF for an existing thread covering this knob.
  If one exists, you're producing `vN+1` there, not starting fresh.
- **Decide upfront: WIP or ready-for-review.** For a first-cut new GUC
  where you want shape feedback on naming / semantics / scope
  (`PGC_USERSET` vs `PGC_SIGHUP`), tag it **WIP**. If you're confident
  it's committable modulo nits, tag it **ready for review**. The tag goes
  in the cover email and changes how reviewers triage.

## 1. Completeness check

A "complete" PG patch needs:

- [ ] Code (the GUC + the autovacuum logic that consumes it)
- [ ] **Regression tests** under `src/test/regress` or TAP under
      `src/test/`, exercising the new GUC + boundary cases + interaction
      with existing autovacuum knobs
- [ ] **SGML docs** in `doc/src/sgml/config.sgml` (the autovacuum section)
      with a usable example, not just syntax
- [ ] Comments explain *why*, not *what*
- [ ] If you added any user-facing error messages, conform to the **Error
      Message Style Guide** in `doc/src/sgml/sources.sgml` (the in-repo
      `error-handling` skill summarizes the rules)
- [ ] A pure GUC patch needs no catalog / WAL / pg_control / pgstat
      format-version bumps

Verify in `dev/build-debug/`:

```bash
cd dev/build-debug
ninja                 # clean build, no new warnings
meson test            # or: ninja test
```

## 2. Clean the git history and rebase onto current master

```bash
git log --oneline master..HEAD
git rebase -i master          # squash WIP, split mixed commits
git fetch origin              # then refresh against upstream
git rebase origin/master
```

The community reviews **commits**, not squashed blobs. Each commit
should be a coherent unit. A v1 that doesn't apply against current
master is the most common reason a CF entry gets bounced back without
review.

## 3. Generate the v1 patch series

```bash
git format-patch -v1 master..HEAD
# → v1-0001-Add-autovacuum-aggressiveness-GUC.patch
git diff --check master..HEAD     # whitespace
```

## 4. Cover email — to pgsql-hackers@lists.postgresql.org

**Plain text only**, patches as **attachments** (not inline), no HTML,
no corporate footer. Body should contain:

- One paragraph: the problem (workload where current knobs fall short)
- One paragraph: the solution and why this approach beats alternatives
- Target branch: `master`
- Confirmation it builds + `meson test` / `ninja test` is clean
- Platforms tested (e.g. "Linux x86_64, macOS arm64")
- Performance notes if relevant
- `https://postgr.es/m/<id>` link to the prior design thread, if any
- Explicit **WIP** or **ready for review** tag

If you have a design thread, **reply** to it rather than starting a new
one — keep threading intact.

## 5. Anti-checklist (will get the patch bounced)

- HTML email
- Top-posting
- Patch in body, not attached
- Plain `diff` without context
- Patch doesn't apply cleanly to current master (you just rebased — good)
- No tests
- No doc updates for user-visible changes (a GUC is user-visible)
- Corporate confidentiality footer

## 6. Register on commitfest.postgresql.org

Add an entry to the **open** CF (currently `PG20-1` as of mid-2026):

- Title: mirror your patch subject
- Authors: you
- Target version: master / next major
- Topic: closest backend subsystem — for an autovacuum GUC that's
  `Server / Autovacuum`. Other common values: `SQL Commands`,
  `Replication & Recovery`, `Performance`.
- Thread Message-Id: the URL `https://www.postgresql.org/message-id/<id>`
  of your -hackers post

Then **review at least one other patch** in the same CF — the de facto
entry fee. Skipping it is noticed.

## 7. After that

Reviewer comments → CF flips to **Waiting on Author** → you address
everything (disagreements answered inline, not silently ignored) →
**fold the fixes back into the right logical commit via `git rebase -i
master`** rather than appending a "fix review comments" commit → `git
format-patch -v2 master..HEAD` attached as a reply on the same thread →
flip CF back to **Needs Review**. Repeat until **Ready for Committer**,
then a committer takes over (pgindent, final message with `Author:` /
`Reviewed-by:` / `Discussion:` trailers, commit to master).

Want me to draft the cover email body now?
