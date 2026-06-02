# Proposed edits (iteration 1)

The SKILL.md already scored a perfect 21/21 in iteration 1. The skill is dense
and well-organised. The proposed edits are minor robustness improvements aimed
at making routing even more obvious on related prompts (not just the three
sampled), and at calling out two recipes that came up implicitly while
answering.

## Edit 1 — Add an explicit "learning paths" subsection in the flowchart

The MVCC eval revealed value in suggesting an ordered learning path
(overview → mvcc → wal → access-heap → access-transam). Make this an explicit
pattern other PG-wide concepts can follow.

**Location:** at the end of the "Quick-orientation flowchart" section, add:

```
## Suggested reading orders for "explain how X works"

For broad concept questions, propose an ordered reading list rather than dump:

- MVCC:        architecture/overview → architecture/mvcc → architecture/wal
               → subsystems/access-heap → subsystems/access-transam
- WAL / crash: architecture/overview → architecture/wal
               → subsystems/access-transam → idioms/(none yet — see wal-and-xlog skill)
- Planner:     architecture/overview → architecture/query-lifecycle
               → architecture/planner → subsystems/optimizer
- Executor:    architecture/overview → architecture/query-lifecycle
               → architecture/executor → subsystems/executor
- Buffer mgr:  architecture/overview → subsystems/storage-buffer
- Replication: architecture/overview → architecture/replication
               → (replication-overview skill for code-level)
```

## Edit 2 — Add explicit "debug a deadlock" recipe

The debug eval surfaced a multi-tool recipe (attach + tail-log + lmgr docs +
fork-model warning). Codify it.

**Location:** in "Quick-orientation flowchart", expand the "debug" row:

```
"debug a deadlock"    → /pg-attach + /pg-tail-log + locking skill
                        + knowledge/subsystems/storage-lmgr.md
                        + knowledge/idioms/locking-overview.md
                        (remember: per-connection fork model — attach AFTER
                         the psql connect, the pid is fresh per session)
```

## Edit 3 — Cross-link the new-SQL-function path explicitly

Adding a built-in is a recurring task and currently the user has to assemble
catalog-conventions + fmgr-and-spi + coding-style + /pg-restart themselves.

**Location:** in the "add a feature" row of the flowchart, append a sub-bullet:

```
"add a built-in SQL function"
   → catalog-conventions skill (pg_proc.dat, catversion bump)
   + fmgr-and-spi skill (PG_FUNCTION_INFO_V1)
   + knowledge/idioms/fmgr.md and idioms/catalog-conventions.md
   + edit in dev/src/backend/utils/adt/, /setup-pg, /pg-restart, /pg-psql
```

## Not proposed

- No description-line change. The current description correctly triggers on PG
  backend work and explicitly excludes user-level SQL / DBA tuning.
- No structural reshuffle — the table-of-contents layout is already the right
  shape for a master navigator.
