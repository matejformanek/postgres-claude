# Common Review Patterns on pgsql-hackers

Distilled list of things reviewers (and committers) routinely raise. Format:
**rule** → why it matters → confidence tag.

## Patch format and hygiene

- **Use unified or context diff with surrounding context lines.** Plain
  `diff` output without context is unreviewable and gets bounced.
  `[from-wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch)`
- **Patch must apply cleanly to current `master`.** Reviewers will not
  hand-rebase for you. Re-post `v(N+1)` when master moves.
  `[from-wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch)`
- **No whitespace junk.** `git diff --check` should be clean.
  `[from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)`
- **Version your patches: `v3-0001-…patch`.** Reviewers track revisions by
  filename; ambiguous names cause confusion in long threads.
  `[from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)`
- **Split logical commits.** A multi-step feature posted as one giant patch
  is harder to review than `0001-refactor`, `0002-new-API`, `0003-use-it`.
  `[inferred]` from `git format-patch` convention.

## Mailing-list etiquette

- **No top-posting.** Reply inline; quote only the lines you're answering.
  Top-posted replies get explicit pushback and slow your review.
  `[from-wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F)`
- **Plain text, no HTML.** HTML mail is silently ignored by many reviewers.
  `[from-wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F)`
- **Keep threading intact.** Reply to the patch thread; don't start a new
  thread per revision or the author/reviewers lose context.
  `[from-wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch)`
- **Link prior discussion** via Message-Id (`https://postgr.es/m/<id>`) when
  resurrecting an old design. `[from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)`

## Tests

- **Regression tests are mandatory** for any behavioral change. A patch
  without tests is incomplete. `[from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)`
- **Tests must cover corner cases**, not just the happy path.
  `[from-wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch)`
- **TAP tests** for cross-process / replication / recovery scenarios;
  `src/test/regress` SQL tests for SQL-visible behavior. `[inferred]` from
  source tree conventions.

## Documentation

- **SGML docs updated in the same patch.** A feature without doc updates
  won't be committed. `[from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)`
- **Examples in the docs**, not just syntax reference.
  `[from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)`
- **Release-note-worthy changes** should be flagged in the commit message
  so it shows up correctly in release-note generation.
  `[from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist)`

## Code style

- **Blend in with the surrounding code.** Patches that stylistically look
  "bolted on" get flagged. `[from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)`
- **CamelCase or snake_case**, both acceptable, but stay consistent with the
  module you're modifying. `[from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)`
- **`pgindent` will be run by the committer.** Don't fight it; write code
  that survives pgindent unchanged.
  `[from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist)`
- **Comments explain *why*, not *what*.** "Increment counter" is noise;
  "increment after acquiring lock to avoid race with checkpointer" is
  signal. `[from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)`
- **No long lines** if they can be reasonably wrapped (>78 cols).
  `[from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist)`

## Portability

- **Builds clean on multiple platforms** — at minimum no new compiler
  warnings on the buildfarm's compiler matrix.
  `[from-wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch)`
- **No reliance on GNU-only extensions** unless gated.
  `[inferred]` from portability sections of PG coding conventions.
- **Test with `--enable-cassert --enable-debug`** to catch assertion
  failures and undefined behavior.
  `[from-wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch)`

## Backwards compatibility & ABI

- **Don't change exported function signatures in back branches.** Extensions
  link against them. `[from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist)`
- **Don't change struct layouts in `src/include/`** for backpatched fixes.
  `[from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist)`
- **New struct members go at the end** to keep ABI stable.
  `[from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist)`
- **New enum values go at the end** of the enum.
  `[from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist)`
- **Catalog changes are master-only** — never backpatched. They require a
  `CATALOG_VERSION_NO` bump. `[from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist)`
- **`pg_dump` support**: any new schema object must round-trip through
  `pg_dump`. Reviewers will ask. `[from-wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch)`

## Catversion / format bumps

- **Bump `CATALOG_VERSION_NO`** when system catalogs change. Forgetting this
  is one of the most common reviewer/committer flags.
  `[from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist)`
- **Bump `PG_CONTROL_VERSION`** when `pg_control` layout changes.
  `[from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist)`
- **Bump `XLOG_PAGE_MAGIC`** when WAL record format changes.
  `[from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist)`
- **Bump `PGSTAT_FILE_FORMAT_ID`** when stats file format changes.
  `[from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist)`
- **OID assignments** need updating when adding pg_proc / pg_type entries.
  `[from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist)`

## Locking & concurrency

- **Lock acquisition order must match existing conventions.** Out-of-order
  acquisition is a deadlock generator and reviewers will probe it.
  `[unverified]` exact wiki wording, but consistently raised in -hackers
  threads.
- **Reentrancy of signal handlers / `PG_TRY`.** Reviewers ask about error
  paths releasing held resources. `[inferred]`
- **Buffer pin / content-lock interactions** in storage code — a recurring
  flag in storage-layer reviews. `[inferred]` from buffer manager
  conventions.

## Performance

- **Does it slow down something already fast?** Reviewers run common
  benchmarks (`pgbench`, a few queries) and look for regressions even in
  unchanged paths. `[from-wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch)`
- **Does it deliver the speedup it claims?** Reviewers will reproduce.
  `[from-wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch)`
- **No new O(N²) loops** without justification. `[inferred]`

## Architectural fit

- **Aligns with SQL standard** where applicable.
  `[from-wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch)`
- **Doesn't paint future features into a corner.** "We can extend this
  later" claims get challenged.
  `[from-wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch)`
- **Reuses existing infrastructure** (e.g. ResourceOwner, MemoryContext,
  ereport, fmgr) instead of inventing parallel mechanisms. `[inferred]` from
  pg-claude idioms guidance.

## Commit-message expectations (committer will rewrite if needed)

- Subject line: imperative, ~50 chars
- Body explains *why* and notable design decisions
- Trailers:
  - `Author: Name <email>` (multiple lines if co-authored)
  - `Reviewed-by: Name <email>` (one per reviewer — **credit them**)
  - `Discussion: https://postgr.es/m/<message-id>`
  - `Backpatch-through: <version>` when applicable

`[from-wiki](https://wiki.postgresql.org/wiki/Committing_checklist)`

## Sources

- [Reviewing a Patch — wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch)
- [Submitting a Patch — wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)
- [Committing Checklist — wiki](https://wiki.postgresql.org/wiki/Committing_checklist)
- [So you want to be a developer — wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F)
- [Versioning policy](https://www.postgresql.org/support/versioning/)
