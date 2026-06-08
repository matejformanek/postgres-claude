---
source_url: https://wiki.postgresql.org/wiki/Committing_checklist
fetched_at: 2026-06-07T00:00:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
audience: committers (but the smoke-test + version-bump items are useful to any patch author preparing a serious submission)
---

# Wiki distilled — Committing checklist

The committers-only pre-/post-push checklist. Distilled for the **version-bump
matrix**, the **back-patch mechanics**, and the **smoke-test menu** — the parts a
patch author can run *before* a committer ever sees the patch, plus the
release-freeze rule that explains why a committed-looking patch sometimes sits.

## Version-stamp bumps (the "did you forget?" matrix)

A change can require bumping any of these, independently: [from-wiki]

- `CATALOG_VERSION_NO` (catversion.h) — any catalog/initdb-format change.
- `PG_CONTROL_VERSION` — pg_control layout change.
- `XLOG_PAGE_MAGIC` — WAL format change.
- `PGSTAT_FILE_FORMAT_ID` — stats-file format change.
- Function/other OIDs as needed (new builtins).

[cross: knowledge/idioms/catalog-conventions.md — catversion discipline]

## Formatting / lint gates before commit

- Run `pgindent`, `pgperltidy`, and `reformat-dat-files`; keep churn minimal.
  Run `pgperlcritic` on touched Perl. [from-wiki]
- Long-line spotter (the page's exact recipe): [from-wiki]
  ```
  git diff origin/master | grep -E '^(\+|diff)' | sed 's/^+//' \
    | expand -t4 | awk 'length > 78 || /^diff/'
  ```
- All headers must pass `src/tools/pginclude/headerscheck` in normal **and**
  `--cplusplus` modes. Every `.c` starts with `postgres.h` / `postgres_fe.h` /
  `c.h` as appropriate. [from-wiki] [cross: knowledge/conventions/coding-style.md]

## Regression-test rules

- Add new test files to **both** serial and parallel schedules (releases 14+ are
  parallel-only). Check for platform alternative-output files. [from-wiki]
- **"Do not add the output of EXPLAIN statements to the regression tests without
  using `COSTS OFF`."** [from-wiki — exact wording] [cross:
  knowledge/wiki-distilled/Regression_test_authoring.md]
- Transient test objects must use the `regress_*` name prefix (build with
  `-DENFORCE_REGRESSION_TEST_NAME_RESTRICTIONS` to enforce). [from-wiki]

## Smoke tests (the heavyweight menu)

Run as warranted by what the patch touches: [from-wiki]

- **Valgrind memcheck** + `make installcheck`.
- `CLOBBER_CACHE_ALWAYS` build (cache-invalidation correctness).
- WAL-logging changes → test a replica with `wal_consistency_checking=all`.
- `nodes/*` changes → build with `#define COPY_PARSE_PLAN_TREES` and
  `#define WRITE_READ_PARSE_PLAN_TREES`.
- `-fsanitize=alignment` for unaligned-access bugs.
- `sqlsmith` for grammar changes.
- `PG_TEST_EXTRA` / `EXTRA_TESTS` to pull in the gated suites.

[cross: knowledge/wiki-distilled/Valgrind.md, knowledge/wiki-distilled/Continuous_Integration.md]

## Commit-message + push mechanics

- Message must carry `Discussion: <postgr.es link>`, reviewer credit, back-patch
  depth, and release-note/compatibility guidance. [from-wiki]
  [cross: knowledge/wiki-distilled/Commit_Message_Guidance.md]
- Make author == committer timestamp: `git commit --amend --reset-author`. [from-wiki]
- Reference other commits by their **first 9 SHA chars**. [from-wiki]
- **Always `--dry-run` before pushing**; check `git status` for stragglers. [from-wiki]
  [cross: knowledge/wiki-distilled/Committing_with_Git.md]

## Back-patching

- Commit messages must be **identical across branches** so tooling correlates the
  set; apply with `git commit --amend --reset-author -C <commit>` on each back
  branch. [from-wiki]
- Dry-run all branches at once: `git push origin : --dry-run`. [from-wiki]
- **ABI stability on back branches:** do NOT modify structs in `src/include/*`,
  and add new enum values only at the end. [from-wiki]

## Policy items easy to miss

- **"Internal errors with SQLSTATE XX000 should not be triggerable from SQL."**
  [from-wiki — exact wording] [cross: knowledge/idioms/error-handling.md]
- Datatype I/O functions must not be marked volatile. [from-wiki]
- Validate `err*()` calls against the error-style guide; `*printf` calls for
  trailing newlines. [from-wiki]

## Release freeze

- No commits to **release branches** from ~noon UTC the Saturday before a release
  until the tag lands (typically late Tuesday UTC). Security + release-note
  patches are exempt. The **master** branch has no freeze (unless a beta is
  pending). This is why a "ready" back-patch sometimes waits. [from-wiki]

## Links into corpus

- [[knowledge/wiki-distilled/Committing_with_Git.md]] — the git-config side
  (`branch.autosetuprebase=always`, push dry-run).
- [[knowledge/wiki-distilled/Commit_Message_Guidance.md]] — the trailer format.
- [[knowledge/wiki-distilled/CommitFest_Checklist.md]] — the CFM flips CF→Committed
  after this checklist's push.
- [[knowledge/conventions/coding-style.md]] / [[knowledge/conventions/testing.md]].
- review-checklist + patch-submission + commit-message-style skills.

## Caveats

- This is a committer's page; an author can run the lint + smoke menu but cannot
  push. Re-verify version-bump constant names against `src/include/catalog/catversion.h`
  etc. before quoting in tooling — they're stable but the list grows. [from-wiki]
