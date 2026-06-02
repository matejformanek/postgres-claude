# Edits applied to SKILL.md before iteration 2

Applied via Edit tool to
`/Users/matej/Work/postgres/postgres-claude/.claude/skills/patch-submission/SKILL.md`.

1. **Section 0 (pre-flight)** — added a bullet making the WIP-vs-ready
   decision explicit upfront, not buried in the cover-email section.

2. **Section 1 (completeness)** — added a checklist item pointing at the
   Error Message Style Guide (`doc/src/sgml/sources.sgml`) and the
   in-repo `error-handling` skill for any user-facing message changes.

3. **Section 2 (clean history)** — added a `git fetch origin && git
   rebase origin/master` block with explanation that "doesn't apply
   against current master" is the most common silent rejection reason.
   Used `origin` (the symlinked clone in `dev/`) rather than `upstream`
   to match the postgres-claude workspace convention.

4. **Section 6 (CF registration)** — expanded the `Topic` bullet with
   concrete examples (Server / Autovacuum, SQL Commands, Replication &
   Recovery, Performance) so first-time submitters know what to pick.

5. **Section 7 (review feedback)** — inserted an explicit "fold via
   `git rebase -i master`, don't ship a fix-on-top commit" step as the
   new step 3, and renumbered the rest (3→4, 4→5).

6. **Quick reference** — prepended `git fetch origin && git rebase
   origin/master` to the versioned-format-patch block.

No content was removed. The PG20-1 reference, version-macro list, and
mailing-list addresses were left untouched.

Cross-checks performed:
- Verified `doc/src/sgml/sources.sgml` is the canonical location of the
  Error Message Style Guide (referenced from the existing
  `error-handling` skill and from upstream wiki).
- Did not introduce new file paths that aren't in the source tree.
