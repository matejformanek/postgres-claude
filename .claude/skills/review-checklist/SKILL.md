---
name: review-checklist
description: The seven-phase PostgreSQL patch review checklist from the wiki — applies to reviewing someone else's pgsql-hackers/CommitFest submission OR self-reviewing your own patch before mailing it. Covers apply/build, regress + check-world, pgindent, design fit, docs, comments, and committer-readiness. Use proactively whenever the user says "review this patch", "is it ready to send to hackers", "CF entry NNNN review", or "pre-submission review". Do NOT trigger for generic GitHub PR review, Terraform/Python/Rust code review, or app security review.
---

# Review Checklist Skill

Reviewing in PostgreSQL is structured into **seven phases** per the wiki.
Run them in order — the cheap checks first, the deep ones last. The same
checklist applies pre-submission (review our own work) and post-submission
(review someone else's CF entry).

## Phase 1 — Submission review (5 minutes)

Cheap, mechanical checks. If any fail, kick back to author immediately
(`Waiting on Author`) — don't waste cycles on later phases.

- [ ] Patch is in unified or context diff format (with context lines).
- [ ] Applies cleanly to current `master`:
      ```bash
      cd $PG_SOURCE && git checkout master && git pull
      git am --abort 2>/dev/null
      git am /path/to/vN-0001-*.patch  # ... and the rest
      ```
- [ ] Filename follows `vN-0001-…patch` convention.
- [ ] Includes tests (look for changes under `src/test/`).
- [ ] Includes doc updates (look for changes under `doc/src/sgml/`) — or
      explicit justification for none (e.g. internal refactor).

## Phase 2 — Usability review

Does the patch do what it claims?

- [ ] Read the cover email's stated goal. Does the diff match?
- [ ] If it adds SQL syntax: does it align with SQL standard / existing
      PG conventions?
- [ ] Does it need `pg_dump` support? If new schema objects, **yes**.
- [ ] Does it interact with other features sensibly (extensions,
      logical replication, parallel query, …)?
- [ ] Are GUC names / catalog column names / function names well-chosen
      and consistent with neighbors?

## Phase 3 — Feature test

Build and exercise it.

```bash
cd $PG_BUILD_DIR
# configure with -Dcassert=true -Ddebug=true if not already
ninja
meson test
```

- [ ] Clean build, no new warnings.
- [ ] All existing tests still pass.
- [ ] New tests actually fail without the code change (sanity: revert
      just the code part and re-run the new tests — they should fail).
- [ ] Exercise corner cases the author didn't test: empty input,
      max-length input, NULL, encoding edges, concurrent calls, etc.
- [ ] Crash-test under assertion build.

## Phase 4 — Performance review

- [ ] Does it slow down anything currently fast? (Run `pgbench` baseline
      + new build comparison for any hot-path change.)
- [ ] If the patch claims a speedup, does it deliver? Reproduce.
- [ ] Any new O(N²) or unbounded loops? Acceptable only with rationale.
- [ ] Memory: any new per-tuple / per-row allocation? Should it use a
      short-lived MemoryContext?

## Phase 5 — Coding review

Read the diff line by line.

- [ ] Style matches the surrounding module (CamelCase vs snake_case).
- [ ] No long lines that could reasonably be wrapped.
- [ ] Comments explain *why*; no noise comments.
- [ ] Uses existing infrastructure: `ereport`, `palloc`, `MemoryContext`,
      `ResourceOwner`, `fmgr`, `SPI` — not parallel reinventions.
- [ ] Error messages follow the message style guide (capitalization,
      no period on `errmsg`, `errdetail`/`errhint` separated correctly).
- [ ] No new platform-specific code without portability gating.
- [ ] No new compiler warnings with `-Wall -Wextra`.

## Phase 6 — Architecture review

The harder one — does this fit?

- [ ] Locking: are locks acquired in an order consistent with the rest
      of the system? Could this deadlock against existing paths?
- [ ] Concurrency: signal-handler safety, `PG_TRY`/`PG_CATCH` resource
      cleanup, reentrancy.
- [ ] Storage / WAL: backwards-compatibility of any on-disk or WAL
      format change. New WAL records → `XLOG_PAGE_MAGIC` bump.
- [ ] Catalog change → `CATALOG_VERSION_NO` bumped, OIDs assigned, and
      this is master-only (never backpatchable).
- [ ] If touching `src/include/` structs in back branches: ABI rules —
      new members at end, no signature changes on exported functions,
      new enum values at end.
- [ ] Does it foreclose obvious future extensions? Flag if yes.

## Phase 7 — Review review

Before posting:

- [ ] Have I covered all six prior phases, or am I explicit about which
      I skipped and why?
- [ ] Have I distinguished **blocking** issues from **nits**?
- [ ] Are my asks **concrete**? "Please add a test for the empty-array
      case" beats "needs more tests."

## Posting the review

- Reply to the **patch email** on pgsql-hackers (preserve threading).
- Plain text, no HTML, no top-posting — quote inline and respond
  beneath each quoted block.
- Structure suggestion:
  1. One-line summary of where the patch stands.
  2. **Blocking issues** (numbered list).
  3. **Nits / style** (numbered list).
  4. **Questions / design discussion**.
- Flip the CommitFest entry:
  - `Waiting on Author` if you raised blocking issues
  - `Ready for Committer` if you're satisfied (committer will still
    re-review)

## Pre-submission self-review

When reviewing our **own** change before sending upstream, run the same
seven phases but be ruthless on:

- Tests cover corner cases, not just the happy path
- Docs include an example
- Commit history is split into logical units
- `git diff --check` is clean
- No leftover debug `elog(WARNING, ...)`, no commented-out code
- Catversion / WAL magic / control version bumps where needed

## Sources

- [Reviewing a Patch — wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch)
- [Submitting a Patch — wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)
- [Committing Checklist — wiki](https://wiki.postgresql.org/wiki/Committing_checklist)
- knowledge/community/review-patterns.md
