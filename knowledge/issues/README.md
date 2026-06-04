# Issues register — corpus-discovered concerns

The append-only register of potential issues surfaced while reading
PostgreSQL source for the per-file documentation pass (Phase A).

This is **not** a bug tracker. It's a corpus-side notebook of things
that looked suspicious, surprising, or worth a second look while
documenting. Some entries become CommitFest patches; some become
non-issues on a closer read; some sit here as known-unknowns for years.

## What lands here

- `[ISSUE-correctness: ...]` — a logic bug, race, or invariant
  violation. Reproducible or strongly suspected.
- `[ISSUE-leak: ...]` — a memory, FD, lock, or information leak.
  Includes side-channel hints (timing, error-message granularity).
- `[ISSUE-doc-drift: ...]` — comment or README diverges from code.
  Common after a refactor.
- `[ISSUE-style: ...]` — code that violates `coding-style` skill rules
  (long lines, BSD-brace breaks, include-order). Low-priority.
- `[ISSUE-stale-todo: ...]` — a `TODO` / `FIXME` / `XXX` comment that
  hasn't been touched in years; flag for triage.
- `[ISSUE-dead-path: ...]` — code that looks unreachable. May be
  defensive, may be genuinely dead.
- `[ISSUE-undocumented-invariant: ...]` — an invariant the code clearly
  relies on but doesn't comment. Adding to corpus is the fix.
- `[ISSUE-question: ...]` — a "why is this here?" question that
  reading didn't answer. Surface for the next session or for a
  domain expert.

## Workflow

1. While writing or refreshing a per-file doc under `knowledge/files/`,
   if you spot one of the above, **tag inline in the per-file doc**:
   ```
   ## Potential issues

   - **[ISSUE-leak: lookup memory not freed on fast-path return]**
     `nbtsearch.c:1284` — `_bt_search` allocates a stack-local
     buffer but the FAST_PATH branch at line 1290 returns without
     hitting the `pfree(stack)` at line 1308. Likely benign (palloc
     in per-query context) but worth a second read.
   ```
2. **Also append a row** to the matching subsystem register
   `knowledge/issues/<subsystem>.md` so cross-corpus triage stays
   cheap. Format:
   ```
   | Date | File:line | Type | Severity | Summary | Status | Linked doc |
   |---|---|---|---|---|---|---|
   | 2026-06-02 | nbtsearch.c:1284 | leak | maybe | Stack buffer not freed on FAST_PATH return | open | knowledge/files/.../nbtsearch.c.md §Potential issues |
   ```
3. **Severity scale**: `nit` < `maybe` < `likely` < `confirmed` <
   `critical`. Be conservative — most things start at `maybe`.
4. **Status scale**: `open` (default) → `triaged` (we looked again,
   here's the read) → `wontfix` (deliberate; documented why) →
   `submitted` (sent upstream as CF entry / patch; link the CF#) →
   `landed` (upstream commit applied).

## How this register is used

- `pg-quality-auditor` cloud routine scans new per-file docs for the
  `[ISSUE-*]` tag and appends to the matching `<subsystem>.md`
  register if it hasn't been mirrored already. (Once that integration
  lands; see follow-up in `.claude/cloud/pg-quality-auditor.md`.)
- `pg-patch-review` skill's critic A (architecture + INV) checks the
  relevant `knowledge/issues/<subsystem>.md` to see if the patch
  addresses or contradicts any open issue.
- `pg-feature-brainstorm` skill triages this register during its
  "Has this been tried?" pass — open issues are candidate starting
  points for features.
- Periodic triage: `pg-state-keeper`'s daily briefing surfaces issues
  whose status hasn't moved in 30 days.

## Per-subsystem registers

One file per subsystem doc under `knowledge/subsystems/`. Created on
first issue. Index here:

| Subsystem | Register file | Open / Triaged / Wontfix / Submitted / Landed |
|---|---|---|
| storage-buffer | knowledge/issues/storage-buffer.md | (no issues yet) |
| access-nbtree | knowledge/issues/access-nbtree.md | (no issues yet) |
| utils-adt | knowledge/issues/utils-adt.md | 12 open (all nit/maybe; scalar-type cluster, 2026-06-03) |
| fe_utils | knowledge/issues/fe_utils.md | 20 open (all nit/maybe; A11 sweep, 2026-06-04 — secret-scrub + backup-stream-trust + decompression-bomb + identifier-quoting clusters) |
| ... | ... | ... |

(Will populate as Phase A issues land.)

## Boundaries

- **Not for confirmed crashes / RCE / security vulnerabilities** — those
  go straight to `pgsql-security@lists.postgresql.org` per the
  upstream disclosure policy. The register is for the squishy middle:
  "this looks odd, let's track it".
- **Not for feature ideas** — those go in `planning/<slug>/brainstorm.md`
  via `/pg-brainstorm`.
- **Not for in-flight CF patches** — those live in CommitFest.

## See also

- `.claude/skills/pg-corpus-maintainer/SKILL.md` (cloud routine that
  writes corpus updates — owns issue-tag mirroring).
- `.claude/skills/pg-patch-review/SKILL.md` (critic A consults this
  register).
- `progress/coverage-gaps.md` (Phase A work queue — issue surface
  scales with coverage).
