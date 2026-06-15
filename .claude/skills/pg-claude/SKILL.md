---
name: pg-claude
description: Route any PostgreSQL backend-hacking task through the pg-claude meta repo's skill / slash-command / knowledge map — master index cataloguing every pg-claude skill, every slash command, and the knowledge/ corpus layout (subsystems, idioms, data-structures). Use proactively as the first-touch routing skill whenever the task is PG backend work: building from source, debugging a backend, writing C in src/backend, adding a GUC / index AM / table AM / access method, hacking the executor or planner, adding a SQL keyword, preparing a pgsql-hackers patch, reviewing a CommitFest entry, or any "where does X live in PG" navigation question. Skip for user-level SQL writing and tuning, autovacuum / shared_buffers / work_mem production DBA tuning, psycopg / pg8000 / node-postgres / pgx / JDBC / SQLAlchemy / Prisma / Django ORM client libraries, comparing PG distros (Aurora / Cloud SQL / Crunchy / Supabase / Neon), and SQL standard / ANSI compatibility questions.
companion_skills:
  - memory-keeping
  - pg-feature-brainstorm
  - pg-feature-plan
  - pg-implement
  - pg-patch-review
  - build-and-run
  - debugging
---

# pg-claude — the master navigator

You're working inside **pg-claude**, a meta repo at `/Users/matej/Work/postgres/postgres-claude/`
that turns Claude into a deep PostgreSQL collaborator. Two upstream PG clones are mounted:

- `source/` → `../postgresql/` — **read-only reference**. All `knowledge/` cites use these paths so file:line refs stay stable.
- `dev/` → `../postgresql-dev/` — **mutable test field**. All builds + clusters live here; safe to wipe and re-clone.

This skill is the **table of contents** for everything pg-claude offers. Use it
to pick the right specialized skill, slash command, or knowledge doc — don't
construct equivalents by hand when one already exists.

## Slash commands — the dev loop

Invoke these instead of constructing bash. They encode verified invocations,
correct `dev/...` paths, and macOS gotchas.

| User intent | Command |
|---|---|
| First-time setup from nothing (no clone yet) | `/init-pg-dev` |
| Hook pg-claude into an existing PG dev tree | `/link-claude-corpus` |
| Build / rebuild PG | `/setup-pg` (`--force` to wipe) |
| Start the cluster | `/pg-start` |
| Stop the cluster | `/pg-stop` |
| Restart (after backend code change + `ninja install`) | `/pg-restart` |
| Open psql | `/pg-psql` |
| Tail server.log | `/pg-tail-log` |
| Attach lldb to a backend | `/pg-attach` |
| Run tests | `/pg-test [--suite X --test PAT]` |
| Wipe data dir, keep build | `/pg-fresh --yes` |
| Nuke the dev clone and re-clone | `/pg-reclone-dev --yes` |
| Document a subsystem | `/document-subsystem <path>` |
| Brainstorm a PG feature (Phase 1 of planner) | `/pg-brainstorm <idea>` |
| Heavy plan for a brainstormed feature (Phase 2) | `/pg-plan <slug>` |
| Execute a plan phase-by-phase (Phase 3, plan-linked commits) | `/pg-implement <slug>` |
| Multi-agent comprehensive patch review (CF# / PR# / .patch) | `/pg-review <ref>` |

**Be proactive.** If the user says "let's build", "start the server", "run tests",
"debug this backend", "let me query that", etc., invoke the command — don't ask
"want me to run /setup-pg?". The exception is destructive ones (`/pg-fresh`,
`/pg-reclone-dev`): if `--yes` wasn't explicit, run without it so the command's
own prompt fires.

## Specialized skills — what to reach for and when

The skills below auto-load by their descriptions. This index is the quick-glance
"what exists" view so you can route mentally even when a skill's description
didn't trigger.

### Writing / editing C code in source/dev

| Topic | Skill | Trigger |
|---|---|---|
| C style, includes, pgindent, C99 subset | `coding-style` | any C edit under `source/src/**/*.{c,h}` |
| ereport/elog, SQLSTATE, PG_TRY/CATCH | `error-handling` | any error-reporting or longjmp-safe cleanup |
| palloc, MemoryContexts, OOM behavior | `memory-contexts` | any allocation, context creation, leak worry |
| LWLocks, heavyweight locks, atomics, SSI | `locking` | any shared-state code |
| Catalog edits, pg_proc.dat, catversion | `catalog-conventions` | any change under `src/include/catalog/` |
| WAL records, redo functions, custom rmgr | `wal-and-xlog` | any XLogInsert, redo, durability change |
| fmgr/PG_FUNCTION_INFO_V1, SPI lifecycle | `fmgr-and-spi` | any SQL-callable C fn, any SPI work |
| Extension layout, hooks, custom GUCs | `extension-development` | building an extension or hook |
| Custom GUCs (DefineCustomXxxVariable, check/assign hooks) | `gucs-config` | any custom GUC add/change |
| Background workers + extension hooks | `bgworker-and-extensions` | RegisterBackgroundWorker, shmem, hook layering |
| Parallel-query workers (Gather/GatherMerge, parallel-safe) | `parallel-query` | any parallel-aware code |
| IndexAmRoutine / TableAmRoutine | `access-method-apis` | any new AM or AM-pluggable code |
| Replication overview (physical + logical) | `replication-overview` | walsender/walreceiver/slot/logical-decoding work |

### Running / testing / debugging

| Topic | Skill | Notes |
|---|---|---|
| Build, configure, run | `build-and-run` | Underlies `/setup-pg`, `/pg-start` etc. |
| Test selection (regress vs isolation vs TAP) | `testing` | What flavor to add, how to run only one |
| gdb/lldb attach, single-user, log instrumentation | `debugging` | Per-connection fork-model implications |

### Contributing upstream

| Topic | Skill | Trigger |
|---|---|---|
| Format-patch + CF registration + email etiquette | `patch-submission` | "let's send this upstream" |
| Pre-submission self-review checklist (seven-phase scaffold) | `review-checklist` | "review my patch" or pre-mailing pass |
| Multi-agent deep review of someone else's CF patch | `pg-patch-review` | "/pg-review <CF#>", "deep-review this patch" |
| PG-style commit messages (no Co-Authored-By!) | `commit-message-style` | drafting commits in `dev/` intended for upstream |
| Parser, Node taxonomy, gen_node_support.pl | `parser-and-nodes` | grammar/Node changes, new SQL statement |
| Executor + planner integration | `executor-and-planner` | new node type, new path, planner change |

### Planning + implementing a PG feature (the three-phase planner)

| Topic | Skill | Trigger |
|---|---|---|
| Phase 1: explore an idea, sketch 2-3 approaches | `pg-feature-brainstorm` | "let's brainstorm X", "/pg-brainstorm" |
| Phase 2: heavy plan with file:line cites | `pg-feature-plan` | "plan this", "/pg-plan <slug>" |
| Phase 3: execute plan phase-by-phase, plan-linked commits | `pg-implement` | "/pg-implement <slug>" |
| Strict rules for plan-linked commits + scope discipline | `.claude/rules/pg-implement-discipline.md` (not a skill — binding rules) | auto-loaded by `pg-implement` |

### Project-internal

| Topic | Skill |
|---|---|
| Master command index (this skill) | `pg-claude` |
| Keep STATE.md / coverage.md / sessions/ in sync | `memory-keeping` |
| Commit-message style for THIS repo (with Co-Authored-By) | `meta-commit-style` |

## Knowledge corpus — where to look things up

The `knowledge/` tree is the durable corpus. Reach for it whenever you need to
recall a fact you don't already know.

```
knowledge/
├── architecture/   # PG-wide concepts (overview, process-model, query-lifecycle,
│                   #   executor, planner, wal, mvcc, replication, access-methods)
├── conventions/    # cross-cutting style: coding-style.md, testing.md, extension-layout.md
├── community/      # patch-workflow.md, review-patterns.md, wiki-index.md,
│                   #   developer-faq-distilled.md, so-you-want-to-be-a-developer.md
├── idioms/         # PG-wide patterns: error-handling, memory-contexts,
│                   #   locking-overview, fmgr, spi, catalog-conventions,
│                   #   node-types-and-lists, parser-pipeline, guc-variables,
│                   #   bgworker-and-parallel
├── subsystems/     # per-subsystem deep-dives (storage-buffer.md is the calibration
│                   #   anchor; more land via /document-subsystem)
├── data-structures/# focused notes on individual structs / invariant families
├── issues/         # corpus-surfaced issue register (Phase A) — one .md per subsystem
│                   #   with [ISSUE-*] tagged concerns: leaks, doc-drift, stale TODOs,
│                   #   undocumented invariants, questions. See issues/README.md.
└── files/          # one .md per source file — 917+ docs mirroring source/src/
                    #   layout. Use when you need precise file:line context for a
                    #   specific .c or .h.

planning/           # forward-looking design docs for features in-flight (Phase B/C/D)
                    # one subdir per slug, with brainstorm.md / plan.md / notes.md
                    # See planning/README.md for the layout.
```

**Routing rule:**
- "What does PG do at a high level?" → `architecture/`.
- "How is this pattern done in PG?" → `idioms/`.
- "Is there a doc for `bufmgr.c`?" → `files/src/backend/storage/buffer/bufmgr.c.md`.
- "What's odd / suspect / undocumented in subsystem X?" → `issues/X.md`.
- "What's the current state of pg-claude itself?" → `progress/STATE.md`.
- "Where can I help close the corpus gap?" → `progress/coverage-gaps.md` (Phase A work queue).

## Progress files — the ledger

- `progress/STATE.md` — current phase, what's done, what's next. **Re-read at session start.**
- `progress/coverage.md` — subsystems documented + per-file coverage summary (top-line numbers).
- `progress/coverage-gaps.md` — per-directory gap map; the Phase A work queue. Updated when coverage shifts ≥50 docs or a dir crosses a 10% boundary.
- `progress/census.md` — one-time enumeration of the source tree.
- `progress/files-examined.md` — append-only ledger: every source file read in non-trivial depth, with verification commit + produced-doc link.

If you read a source file in depth and there's no row for it, **append to
`files-examined.md`** — the user explicitly asked for file-by-file accountability.

## Working rules (from `CLAUDE.md`)

1. **Cite or tag.** Every concrete claim about PG behavior gets a `file:line`
   cite into `source/...` or is tagged `[unverified]`. Confident-but-wrong is
   the failure mode to avoid (Multigres lesson).
2. **Confidence tags:** `[verified-by-code]` `[from-README]` `[from-comment]`
   `[from-docs]` `[from-wiki]` `[inferred]` `[unverified]`. Untagged = failure.
3. **STATE.md authoritative.** Update at end of any durable-output session.
4. **Scope discipline.** Source patches live in `dev/` on a branch. Never edit
   `source/` (read-only reference). Never edit `.claude/` or `knowledge/` from
   inside `dev/`.
5. **Track what you read.** Append to `progress/files-examined.md`.

## Quick-orientation flowchart

```
User asks for...                              You reach for...
─────────────────                            ────────────────
"set up PG"           → /init-pg-dev (no clone)  or  /setup-pg (have clone)
                        or /link-claude-corpus (have own dev tree elsewhere)
"build" / "rebuild"   → /setup-pg
"start" / "psql"      → /pg-start then /pg-psql
"test"                → /pg-test
"debug"               → /pg-attach + debugging skill
"debug a deadlock"    → /pg-attach + /pg-tail-log + locking skill
                        + knowledge/subsystems/storage-lmgr.md
                        + knowledge/idioms/locking-overview.md
                        (per-connection fork model — attach AFTER the psql
                         connect; the backend pid is fresh per session)
"reset"               → /pg-fresh (data only)  or  /pg-reclone-dev (whole tree)
"how does X work"     → knowledge/architecture/X.md or knowledge/subsystems/X.md
"what file does Y"    → knowledge/files/src/backend/<...>.md
"edit C code"         → coding-style + the relevant idiom skill
                        (error-handling / memory-contexts / locking / ...)
"add a feature"       → relevant subsystem skill (catalog-conventions /
                        wal-and-xlog / access-method-apis /
                        extension-development / ...)
"add a built-in SQL fn" → catalog-conventions skill (pg_proc.dat, catversion)
                        + fmgr-and-spi skill (PG_FUNCTION_INFO_V1)
                        + knowledge/idioms/fmgr.md
                        + knowledge/idioms/catalog-conventions.md
                        + edit dev/src/backend/utils/adt/, then
                          /setup-pg → /pg-restart → /pg-psql → /pg-test
"send upstream"       → patch-submission + review-checklist + commit-message-style
"review a CF patch"   → /pg-review <CF#|PR#|file>   (multi-agent, 4 critics + synthesizer)
"document subsystem"  → /document-subsystem <path>
"brainstorm a feature"→ /pg-brainstorm <idea>  (Phase 1; ~150-300 line sketch)
"plan that feature"   → /pg-plan <slug>        (Phase 2; heavy implementable plan)
"implement the plan"  → /pg-implement <slug>   (Phase 3; per-phase commits, plan-linked)
"commit in THIS repo" → meta-commit-style skill (with Co-Authored-By)
"commit in dev/"      → commit-message-style skill (NO Co-Authored-By; upstream style)
"what was done"       → progress/STATE.md + progress/coverage.md
```

## Suggested reading orders for "explain how X works"

For broad concept questions, propose an ordered reading list rather than dumping a folder:

- MVCC:        `architecture/overview.md` → `architecture/mvcc.md` → `architecture/wal.md`
               → `subsystems/access-heap.md` → `subsystems/access-transam.md`
- WAL / crash: `architecture/overview.md` → `architecture/wal.md`
               → `subsystems/access-transam.md` (use `wal-and-xlog` skill for code edits)
- Planner:     `architecture/overview.md` → `architecture/query-lifecycle.md`
               → `architecture/planner.md` → `subsystems/optimizer.md`
- Executor:    `architecture/overview.md` → `architecture/query-lifecycle.md`
               → `architecture/executor.md` → `subsystems/executor.md`
- Buffer mgr:  `architecture/overview.md` → `subsystems/storage-buffer.md`
- Replication: `architecture/overview.md` → `architecture/replication.md`
               (use `replication-overview` skill for code-level)

All cites inside those docs use `source/...` so file:line refs stay stable across upstream pulls.

## After-action follow-up

When you finish a command or an edit, give the user one short "what now" line:

- After `/setup-pg`: "Built. Next: `/pg-start`."
- After `/pg-start`: "Cluster up on /tmp. `/pg-psql` to connect."
- After a code edit in `dev/src/`: "Edited. `/pg-restart` to pick up the new binary."
- After a knowledge doc landed: "Wrote `knowledge/files/.../X.md`. Registry row appended."

Don't recap what already showed in the tool output. Just point at the next move.
