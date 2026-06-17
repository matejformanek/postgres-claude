# pg-claude — meta repo for deep PostgreSQL collaboration

This repo turns Claude Code into a long-term collaborator on PostgreSQL internals.
Two upstream PG clones are mounted via symlinks:

- `source/` → `../postgresql/` — **read-only reference**. Kept in sync with
  upstream `master`. Use this for every code citation in `knowledge/...` so
  `file:line` references stay stable.
- `dev/` → `../postgresql-dev/` — **mutable test field**. All build artifacts
  (`dev/build-debug/`, `dev/install-debug/`, `dev/data-debug/`) and any local
  patches/branches live here. Designed to be disposable: if confused, blow
  away `../postgresql-dev/` and re-clone from `../postgresql/` in ~30s.

## Layout

- `source/` — read-only reference clone. Never edit, never build from here.
- `dev/` — mutable clone. Build, run, test, and edit here. `/setup-pg` etc.
  all target `dev/`.
- `.claude/` — skills, agents, commands, settings. The behavioral surface.
- `knowledge/` — generated, durable docs distilled from the source.
  - `subsystems/<name>.md` — one file per backend subsystem (storage-buffer, access-heap, …).
  - `data-structures/<name>.md` — focused notes on a single struct or invariant family.
  - `idioms/<name>.md` — PG-wide patterns (memory contexts, ereport, fmgr, SPI, …).
  - `scenarios/<name>.md` — task-shaped playbooks for recurring change-classes
    (add-new-data-type, add-new-sql-keyword, add-startup-hook, …). Each
    carries an authoritative file checklist that `pg-feature-plan` PINS
    as the §3 table. See `scenarios/README.md` + `scenarios/_index.md`.
- `sessions/` — append-only logs of significant working sessions (one file per session).
- `progress/`
  - `STATE.md` — current phase, what's done, what's next. Always re-read at session start.
  - `coverage.md` — table of which subsystems/idioms are documented, with last-verified commit.
  - `census.md` — one-time enumeration of READMEs, subsystem dirs, test dirs in the source tree.
  - `files-examined.md` — registry of every source file the corpus has looked at
    (with depth, date, last-verified commit, produced-doc). Updated whenever a
    file gets examined in the file-by-file deep-corpus phase.

## Working rules

1. **Cite or don't claim.** Any concrete statement about PG behavior must come with
   a `file:line` cite into `source/…`, or be tagged `[unverified]`. The Multigres
   lesson: confident-sounding wrong claims about locking order are the failure mode
   to avoid (see `pg-claude-plan.md` Appendix A).
2. **Confidence tags.** Mark claims as `[verified-by-code]`, `[from-README]`,
   `[from-comment]`, `[inferred]`, or `[unverified]`. No bare assertions.
3. **STATE.md is authoritative.** Update it at the end of any session that
   produced durable output. Future sessions read it first.
4. **One subsystem at a time.** Don't fan out before calibrating. The buffer-manager
   doc is the calibration run.
5. **Scope discipline.** This repo is the meta system. Patches to PG itself live
   inside `../postgresql-dev/` (the mutable clone) on a feature branch and never
   touch `.claude/` or `knowledge/`. `../postgresql/` (read-only reference) must
   stay clean against upstream master.

6. **Track what you read.** Every time an agent or session reads a source file
   in non-trivial depth, append a row to `progress/files-examined.md`. This is
   how the file-by-file deep-corpus phase stays honest about coverage.

## Build & run

Primary toolchain is **meson** (PG ≥ 16 default). Configure once into an out-of-tree
build dir, then `ninja` from there. The per-connection fork model means a fresh
backend starts on every `psql` connect — surprising if you're used to threaded servers.
See `.claude/skills/build-and-run/SKILL.md` for the actual commands once you need them.

Code-quality + test gating is automated via hooks installed by `/setup-pg`
(format-check on edit, R13-scoped `meson test` on commit). Source of truth:
`.claude/hooks/`; installer: `/pg-install-hooks`. Discipline contract: R4 +
R13 in `.claude/rules/pg-implement-discipline.md` (v1.3).

## Where to look

- `pg-claude-plan.md` (in the parent dir) — the master design doc, 15-decision blueprint.
- `progress/STATE.md` — what's actually done right now.
- `progress/census.md` — what's in the source tree, with anchors.
