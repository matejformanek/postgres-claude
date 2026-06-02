# Getting your autovacuum-GUC feature on pgsql-hackers as v1

Here's the order of operations, mapped to the patch-submission checklist.

## 0. Pre-flight

A new GUC is **not trivial** — name, units, default, scope (PGC_USERSET vs PGC_SIGHUP?), and the autovacuum-tuning *semantics* will all be argued over. Before you format any patch, check:

- Have you posted a **design email** to pgsql-hackers describing the problem, the proposed knob, and why existing knobs (`autovacuum_vacuum_scale_factor`, `autovacuum_vacuum_cost_limit`, etc.) aren't enough? If not, the right next step is that design email, not v1. A "finished" patch built against an approach -hackers rejects is wasted work.
- Target branch is `master` (new feature → master only, no backpatch).
- Search the archives + open CF for any existing thread/entry covering this knob. If one exists, you're producing `vN+1` there, not starting fresh.

If design discussion already happened (even informally) or you're confident the shape is right, proceed.

## 1. Confirm the change is "complete" in PG terms

A submittable patch needs all of:

- [ ] Code change (the GUC + the autovacuum logic that consumes it)
- [ ] **Regression tests** under `src/test/regress` or a TAP test under `src/test/` exercising the new behavior + at least one corner case (boundary value, interaction with existing autovacuum knobs)
- [ ] **SGML docs** in `doc/src/sgml/config.sgml` (the autovacuum section) — with a usable example, not just syntax
- [ ] Comments that explain *why*, not *what*
- [ ] No catalog/WAL/pg_control/stats-format changes for a pure-GUC patch, so no version bumps needed

Build clean and run the suite from the build dir:

```bash
cd dev/build-debug
ninja
meson test
```

Fix anything red before formatting.

## 2. Clean up git history

```bash
cd dev
git log --oneline master..HEAD
git rebase -i master   # squash WIP, split mixed commits
```

For a single GUC, one coherent commit is usually fine. If you also refactored existing autovacuum code, split: `0001-refactor-...`, `0002-add-GUC-...`.

## 3. Generate the patch series

```bash
git format-patch -v1 master..HEAD
# → v1-0001-Add-autovacuum-aggressiveness-GUC.patch
git diff --check master..HEAD   # whitespace
```

## 4. Compose the cover email

To **pgsql-hackers@lists.postgresql.org**, plain text, patch as **attachment** (not inline). Body should contain:

- One paragraph: the problem (workload where current autovacuum knobs are insufficient)
- One paragraph: the solution and why this approach beats alternatives you considered
- Target branch: `master`
- Confirmation it builds + `meson test` / `ninja test` is clean
- Platforms tested (e.g. "Linux x86_64, macOS arm64")
- Any performance notes (does the new code path measurably affect a vacuum-heavy benchmark?)
- Link to prior design thread via `https://postgr.es/m/<message-id>` if there was one
- State explicitly: **ready for review** (or **WIP** if you want shape feedback first)

If you posted a design thread earlier, **reply** to it rather than starting a new one.

## 5. Anti-checklist — bounceable mistakes

- HTML email — never. Plain text only.
- Top-posted reply — never. Quote inline.
- Patch pasted in body instead of attached.
- Patch that doesn't apply cleanly to current master.
- Missing tests or missing docs (a new GUC must be documented).
- Corporate confidentiality footer on the email.

## 6. Register the CommitFest entry

Go to <https://commitfest.postgresql.org/> and add to the open CF (currently `PG20-1`):

- Title mirrors the patch subject
- Authors: you
- Target version: master / next major
- Topic: Server / Autovacuum
- Thread Message-Id: the URL `https://www.postgresql.org/message-id/<id>` of your -hackers post

Then **review at least one other patch** in the same CF. That's the community's bartering norm — skipping it is noticed.

## 7. From here on

Cycle is: reviewer comments → CF flips to **Waiting on Author** → you address everything (disagree in reply, don't silently ignore) → `git format-patch -v2` attached to a reply on the same thread → flip CF back to **Needs Review**. Repeat until **Ready for Committer**, then a committer takes it from there (pgindent, final commit message with `Author:` / `Reviewed-by:` / `Discussion:` trailers, commit to master).

Want me to draft the cover email body now?
