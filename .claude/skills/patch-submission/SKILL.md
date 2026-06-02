---
name: patch-submission
description: Prepare a PostgreSQL change for upstream submission to pgsql-hackers — git format-patch the series, write the cover letter, register a CommitFest (CF) entry, run pgindent / check-world / docs build, and stage the v1 patchset for mailing. Use proactively whenever the user wants to send a PG patch upstream, format-patch for pgsql-hackers, land a change on master, or register a CF entry. Do NOT trigger for GitHub PRs, npm/crate releases, LKML kernel patches, or generic "open source contribution" questions.
---

# Patch Submission Skill

When the user wants to upstream a change, walk this checklist in order.
Don't skip steps — community pushback on missing tests/docs/format is the
biggest source of wasted round-trips.

## 0. Pre-flight — does this even belong upstream?

Before formatting anything, confirm:

- [ ] Has the design been discussed on pgsql-hackers? If non-trivial and the
      answer is **no**, the right next step is a design email, **not** a
      patch. Offer to draft that email instead.
- [ ] Is the target branch `master`? (It almost always is. Bug fixes also
      develop on master; backpatching is the committer's job.)
- [ ] Does an existing CommitFest entry / thread already cover this? If yes,
      we're producing `vN+1` on that thread, not a new submission.
- [ ] Decide upfront: **WIP** (you want shape / design feedback before
      reviewers spend serious cycles) or **ready for review** (you believe
      it's committable modulo nits). The tag goes in the cover email and
      changes how reviewers triage.

## 1. Make sure the change is actually complete

A "complete" patch in PG terms means:

- [ ] Code change itself
- [ ] **Regression tests** (`src/test/regress` or TAP under `src/test/`)
      exercising the new behavior + corner cases
- [ ] **SGML documentation** updated (`doc/src/sgml/`) — with at least one
      usable example, not just syntax
- [ ] Comments explain *why*, not *what*
- [ ] If the patch adds or changes user-facing error messages, conform to
      the **Error Message Style Guide** in `doc/src/sgml/sources.sgml`
      (the in-repo `error-handling` skill summarizes the rules)
- [ ] If catalogs change: `CATALOG_VERSION_NO` bumped in
      `src/include/catalog/catversion.h`
- [ ] If WAL changes: `XLOG_PAGE_MAGIC` bumped
- [ ] If `pg_control` changes: `PG_CONTROL_VERSION` bumped
- [ ] If stats file changes: `PGSTAT_FILE_FORMAT_ID` bumped

Verify with:

```bash
cd $PG_BUILD_DIR
ninja                           # clean build, no new warnings
meson test                      # or: ninja test
# for assertion builds, build was configured with -Dcassert=true
```

If anything fails, fix before formatting the patch.

## 2. Clean up the git history

The community reviews **commits**, not squashed blobs. Split logical steps:

```bash
git log --oneline master..HEAD
git rebase -i master            # squash WIP commits, split mixed ones
```

Each commit should be a coherent unit (e.g. `0001-refactor-X`,
`0002-add-Y-API`, `0003-wire-Y-into-Z`). A single-commit patch is fine for
small fixes.

Before formatting, **rebase onto current upstream master** so the series
applies cleanly:

```bash
git fetch origin
git rebase origin/master
```

A v(N) that doesn't apply against current master is the most common
reason a CF entry gets bounced back without review.

## 3. Generate the patch series

```bash
git format-patch -v1 master..HEAD
# Files: v1-0001-<subject>.patch, v1-0002-..., ...
```

On re-submission after review, bump the version:

```bash
git format-patch -v3 master..HEAD
```

Then verify hygiene:

```bash
git diff --check master..HEAD   # whitespace
# Patch must be unified-diff with context (format-patch handles this).
```

## 4. Compose the cover email

Send to **pgsql-hackers@lists.postgresql.org**, plain text only,
attachments not inline. Include in the body:

- One-paragraph summary of the problem
- One paragraph on the solution / why this approach
- Target branch (`master`)
- Confirmation it builds + `make check` / `ninja test` passes
- Platforms tested
- Performance notes if relevant
- Link to prior discussion via `https://postgr.es/m/<message-id>` if any
- Note whether this is **WIP** (for discussion) or **ready for review**

If you're replying to an existing thread (revision N+1), **reply** —
don't start a new thread.

## 5. Anti-checklist (things that will get the patch bounced)

- [ ] HTML email — never. Plain text only.
- [ ] Top-posted reply — never. Reply inline beneath quoted lines.
- [ ] Patch pasted into email body instead of attached.
- [ ] Plain `diff` output without context.
- [ ] Patch that doesn't apply cleanly to current master.
- [ ] No tests.
- [ ] No doc updates for user-visible changes.
- [ ] Corporate confidentiality footer in the email.

## 6. Register in the CommitFest

After sending the email, go to <https://commitfest.postgresql.org/> and
add an entry to the **open** CF (currently `PG20-1` as of mid-2026):

- Title (mirror the patch subject)
- Authors
- Target version (master / next major)
- Topic — maps to a backend subsystem (Server / Autovacuum, SQL Commands,
  Replication & Recovery, Performance, …). Pick the one closest to the
  patch's primary impact.
- Thread Message-Id (the URL of your -hackers post on
  `https://www.postgresql.org/message-id/<id>`)

Then **review at least one other patch** in the same CF. This is the
community's bartering norm and skipping it is noticed.

## 7. Handling review feedback

Cycle:

1. Reviewer posts comments → CF entry flips to **Waiting on Author**.
2. You address every point. For points you disagree with, explain in the
    reply rather than silently ignoring.
3. **Fold fixes back into the right logical commit via `git rebase -i
    master`** — don't ship a "fix review comments" commit on top. v(N+1)
    should look like a clean rewrite of v(N) with the asks applied, not
    v(N) + fixup. Then re-run `ninja && meson test` before formatting.
4. Generate `vN+1` with `git format-patch -v<N+1>` and attach to a reply
    on the same thread.
5. Flip the CF entry back to **Needs Review**.

If a CF ends and the patch isn't done, it usually rolls to the next CF
(**Moved to next CommitFest**). Be responsive — patches that stall for a
full CF without author activity get **Returned with Feedback**.

## 8. After commit

The committer will:
- Run pgindent / pgperltidy
- Write the final commit message with `Author:`, `Reviewed-by:`,
  `Discussion:` trailers
- Decide on backpatch (only for bug fixes — see versioning policy)
- Commit to master; notification appears on pgsql-committers

Your CF entry flips to **Committed**. Done.

## Quick reference

```bash
# Refresh against upstream before re-formatting
git fetch origin && git rebase origin/master

# Versioned patch series
git format-patch -v3 master..HEAD

# Whitespace check
git diff --check master..HEAD

# Apply someone else's patch series (for review)
git am v3-*.patch

# Drop a patch series cleanly
git reset --hard master
```

## Sources

- [Submitting a Patch — wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)
- [CommitFest — wiki](https://wiki.postgresql.org/wiki/CommitFest)
- knowledge/community/patch-workflow.md
- knowledge/community/review-patterns.md
