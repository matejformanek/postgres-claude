# PostgreSQL Patch Workflow: idea → commit (→ backpatch)

End-to-end map of how a code change actually reaches the upstream PostgreSQL
tree. The workflow is mailing-list-centric — there is no GitHub PR equivalent.

## 0. Pick the right list

- **pgsql-hackers** — design discussion, patch submission, review.
  All patch traffic lives here. `[from-docs](https://www.postgresql.org/community/lists/)`
- **pgsql-bugs** — bug *reports* (via the bug-report form). Bug *fixes* still
  go to -hackers. `[from-docs](https://www.postgresql.org/community/lists/)`
- **pgsql-docs** — doc-only changes. `[from-docs](https://www.postgresql.org/community/lists/)`
- **pgsql-committers** — read-only commit notifications; **never post here**.
  `[from-docs](https://www.postgresql.org/community/lists/)`
- **pgsql-general / -novice / -sql / -performance / -admin** — user lists, not
  for patches. `[from-docs](https://www.postgresql.org/community/lists/)`

## 1. Discuss before coding (for anything non-trivial)

For non-trivial work, post a design proposal on **pgsql-hackers** *before*
writing the patch. Cover: problem, current behavior, proposed behavior,
rationale. `[from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)`

Why this matters: the community has strong opinions on architecture. A
finished patch built against an approach -hackers will reject is wasted
work. Trivial bug fixes can skip this step.

## 2. Prepare the change

- Branch from current `master` for new features. Bug fixes targeting back
  branches still develop on master first, then committer backpatches.
  `[inferred]` from backpatch policy below.
- Follow PostgreSQL coding conventions; "blend in with the surrounding code."
  `[from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)`
- Include **regression tests** and **doc updates** in the same patch.
  `[from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)`
- Run `git diff --check` (catches whitespace).
  `[from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)`
- Comments should explain *why*, not *what*.
  `[from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)`

## 3. Generate the patch with `git format-patch`

The community convention is a versioned, numbered patch series:

```
git format-patch -v3 master..HEAD
# produces v3-0001-Short-subject.patch, v3-0002-…, etc.
```

`-vN` increments the series version (v1 first submission, v2 after first
round of review, …). For a multi-commit feature, each logical commit becomes
its own `0001-`, `0002-` file. `[from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)`

Patches must use unified or context diff format (i.e. with context lines).
Plain `diff` output without context is **rejected**. `[from-mailing-list](https://www.mail-archive.com/pgsql-hackers@lists.postgresql.org/msg190327.html)` `[from-wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch)`

## 4. Send to pgsql-hackers

Email a new thread (or reply to an existing design thread) with the patch as
an **attachment** (not inline). The opening message should include:
`[from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)`

- Brief description of what the patch does and why
- Whether it's WIP (for discussion) or ready for review/apply
- Target branch (almost always `master`)
- That it compiles and passes `make check` (or meson `ninja test`)
- Platforms tested
- Performance impact (if relevant)
- Design rationale / alternatives considered
- Message-Id link to prior discussion thread, if any

### Mailing-list social norms (load-bearing)

- **Plain text only**, no HTML. `[from-wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F)`
- **No top-posting.** Reply inline, quoting only the relevant lines, then
  responding under each quoted block. Top-posted replies routinely get
  pushback. `[from-wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F)` `[from-mailing-list](http://rhaas.blogspot.com/2024/08/posting-your-patch-on-pgsql-hackers.html)`
- **Keep threading intact.** Reply to the patch email, don't start a new
  thread per revision. `[from-wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch)`
- Strip corporate confidentiality footers before sending.
  `[from-wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F)`
- Discussion style is blunt and technical; not personal. `[from-wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F)`
- Posting a patch grants PGDG non-revocable right to distribute it under the
  PostgreSQL license. `[from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)`

## 5. Register in the CommitFest

After the initial post, add the patch to the **open** CommitFest at
<https://commitfest.postgresql.org/>. `[from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)`

### CommitFest structure

- CommitFests run roughly monthly during the development year, with a
  multi-month hiatus around major-release stabilization.
  `[from-wiki](https://wiki.postgresql.org/wiki/CommitFest)`
- Two-phase model at any moment: one **Open** CF accepting new entries, and
  one **In Progress** CF where the community actively reviews.
  `[from-wiki](https://wiki.postgresql.org/wiki/CommitFest)`
- Each CF entry tracks: title, author(s), reviewers, target branch, thread
  link (Message-Id), and a status. Status values (canonical set):
  `[unverified]` exact wording, but standard:
  - **Needs Review** — waiting for a reviewer
  - **Waiting on Author** — review feedback returned; author's turn
  - **Ready for Committer** — reviewer is satisfied
  - **Returned with Feedback** — closed, author may resubmit later
  - **Rejected** — closed, the approach won't be accepted
  - **Committed** — landed
  - **Moved to next CommitFest** — rolled over

A **CommitFest manager** drives status transitions and nudges stalled
entries. `[from-wiki](https://wiki.postgresql.org/wiki/CommitFest)`

### The review-bartering rule

Every patch submitter is expected to **review at least one other patch** of
similar scope per CF they enter. This is the de facto entry fee.
`[from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)`

### Current CF (as of 2026-06-01)

`PG20-1` is the open CF, accepting submissions through 2026-06-30; its
review period runs 2026-07-01 through 2026-07-31. `PG20-Drafts` accepts
early drafts through Feb 2027. `PG20-2` opens 2026-07-01.
`[from-wiki](https://commitfest.postgresql.org/)`

## 6. Reviewer cycle

A reviewer (signed up via the CF entry) works through the seven review
phases (see `review-patterns.md`). They reply **on the patch thread** —
never a new thread. Typical first review within ~5 days of sign-up.
`[from-wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch)`

Outcomes per round:
- Reviewer marks **Waiting on Author** with concrete asks → author posts
  `v(N+1)-0001-…` in reply, possibly flips back to **Needs Review**.
- Reviewer marks **Ready for Committer** when they're satisfied.

## 7. Committer cycle

A committer does their own review before merging — reviewer sign-off is not
a guarantee of acceptance. `[from-wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch)`

Committer-side checks include:
- `pgindent`, `pgperltidy`, `reformat_dat_files`, `pgperlcritic`
- Update `CATALOG_VERSION_NO`, `PG_CONTROL_VERSION`, `XLOG_PAGE_MAGIC`,
  `PGSTAT_FILE_FORMAT_ID` when catalogs / on-disk formats change
- ABI safety check for back-branches
- Commit message: subject + body explaining why; trailers for `Author:`,
  `Reviewed-by:`, `Discussion: https://postgr.es/m/<message-id>`,
  `Backpatch-through:` where relevant
- Reference other commits by first 9 SHA chars (auto-linkifies in tooling)

`[from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist)`

The commit lands on `master`. A notification appears on **pgsql-committers**.

## 8. Backpatch decision

PostgreSQL supports **5 major versions** at any time (currently 14–18).
Minor releases come out at least quarterly; backpatched changes ride them.
`[from-docs](https://www.postgresql.org/support/versioning/)`

Backpatch is **only** for: `[from-docs](https://www.postgresql.org/support/versioning/)`
1. Frequently-encountered bug fixes
2. Low-risk fixes
3. Security fixes
4. Data-corruption fixes

**Never** new features.

When backpatching, commit messages across branches should be **identical**
so release-note tooling can deduplicate. The committer uses
`git commit --amend --reset-author -C <commit>` to sync messages.
`[from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist)`

ABI rules in back branches: `[from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist)`
- Don't change exported function signatures
- Don't change struct layouts in `src/include/`
- New struct members go at the **end**
- New enum values go at the **end**

## 9. After commit

- CF entry flips to **Committed**.
- Author can now propose follow-ups in subsequent CFs.
- Bug reports against the change come back on -hackers or -bugs.

## Reference: lifecycle diagram

```
idea
 └─→ pgsql-hackers (design thread)         [step 1]
      └─→ code + tests + docs              [step 2]
           └─→ git format-patch -vN        [step 3]
                └─→ post to thread + CF    [steps 4–5]
                     ├─→ Needs Review ↔ Waiting on Author  (loop)
                     └─→ Ready for Committer
                          └─→ Committer review
                               ├─→ pgindent, catversion, msg
                               └─→ commit to master
                                    └─→ optional backpatch (14–18)
                                         └─→ next minor release
```

## Sources

- [Submitting a Patch — wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)
- [Reviewing a Patch — wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch)
- [Committing Checklist — wiki](https://wiki.postgresql.org/wiki/Committing_checklist)
- [CommitFest — wiki](https://wiki.postgresql.org/wiki/CommitFest)
- [So you want to be a developer — wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F)
- [Mailing lists — postgresql.org](https://www.postgresql.org/community/lists/)
- [Versioning policy — postgresql.org](https://www.postgresql.org/support/versioning/)
- [commitfest.postgresql.org](https://commitfest.postgresql.org/)
- [Robert Haas: Posting Your Patch On pgsql-hackers](http://rhaas.blogspot.com/2024/08/posting-your-patch-on-pgsql-hackers.html)
