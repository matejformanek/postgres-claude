# Iteration 2 — edits applied

Applied all three proposed edits from iteration-1/proposed-edits.md to
`.claude/skills/pg-claude/SKILL.md`.

1. **Quick-orientation flowchart — debug-a-deadlock row** added below the
   generic `"debug"` row. Names `/pg-attach`, `/pg-tail-log`, locking skill,
   `knowledge/subsystems/storage-lmgr.md`, `knowledge/idioms/locking-overview.md`,
   and the fork-model gotcha.

2. **Quick-orientation flowchart — add-a-built-in-SQL-fn row** added below
   the generic `"add a feature"` row. Names `catalog-conventions` skill,
   `fmgr-and-spi` skill, the two relevant idiom docs, the
   `dev/src/backend/utils/adt/` location, and the
   `/setup-pg → /pg-restart → /pg-psql → /pg-test` loop.

3. **New section** `## Suggested reading orders for "explain how X works"`
   inserted above `## After-action follow-up`. Covers MVCC, WAL/crash,
   planner, executor, buffer manager, replication — each with an ordered
   architecture → subsystem walk, plus a one-liner about cites being stable
   via `source/...`.

## Path verification

All 16 referenced knowledge paths verified to exist under
`/Users/matej/Work/postgres/postgres-claude/knowledge/`.
