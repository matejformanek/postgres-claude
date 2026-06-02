# pg-claude — current state

**Phase:** Tooling buildout (three-phase planner suite) + nightly cloud routines (autonomous). Spine-synthesis catch-up complete (20 subsystem docs); `/refresh-upstream` shakedown still pending.
**Last activity:** 2026-06-02 (afternoon, interactive) — landed the **three-phase PG planner suite**: `pg-feature-brainstorm` (Phase 1 skill) + `pg-feature-plan` (Phase 2 skill) + `pg-implement` (Phase 3 skill, distinct from generic `/implement`) + their three slash-command wrappers (`/pg-brainstorm`, `/pg-plan`, `/pg-implement`) + the strict `.claude/rules/pg-implement-discipline.md` rules file (R1–R12, plan-linked commits, scope discipline, two-repo separation) + `meta-commit-style` skill (postgres-claude commit style, distinct from upstream-only `commit-message-style`) + `planning/` directory + README. Master `pg-claude` skill updated to register all of it. Earlier same afternoon: CF #6402 review validation run proved the corpus composes for review work — draft review email + analysis in `sessions/2026-06-02-cf6402-review-validation.md`. Same-day priors: 4 subsystem-synthesis PRs merged — parser-and-rewrite (#19), access-nbtree (#21), replication (#25), tcop (#27). Cloud cycle: 7 of 9 producers opened PRs (#11–#17); pg-quality-auditor SILENT (needs investigation). Daily watchdog briefing at `progress/_briefings/2026-06-02.md`. Prior activity 2026-06-01: cross-reference pass added 633 upward backlinks, `data-structures/bufferdesc-state.md` refreshed for PG18 atomic state-word.
**Source commit at last verification:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (refreshed 2026-06-01; previous anchor `ef6a95c7c64` had 1 trailing commit, build-system only, no corpus impact — see `progress/refresh-2026-06-01.md`).

## Done

### Scaffold + behavioral surface

- Two-repo split wired: `postgresql/` read-only reference + `postgresql-dev/` mutable test field, both mounted via symlinks in `postgres-claude/`.
- **25 skills** (10 C-idioms, 5 contribute-upstream, 3 dev-loop, 1 master navigator, 2 internal, **+3 planner-suite added 2026-06-02:** `pg-feature-brainstorm`, `pg-feature-plan`, `pg-implement`, **+1 commit-style:** `meta-commit-style`). Descriptions optimized for trigger accuracy with explicit near-miss exclusions.
- **17 slash commands**: `/init-pg-dev`, `/link-claude-corpus`, `/setup-pg`, `/pg-start`, `/pg-stop`, `/pg-restart`, `/pg-psql`, `/pg-tail-log`, `/pg-attach`, `/pg-test`, `/pg-fresh`, `/pg-reclone-dev`, `/document-subsystem`, `/refresh-upstream`, **+3 planner-suite added 2026-06-02:** `/pg-brainstorm`, `/pg-plan`, `/pg-implement`. Build invocation verified end-to-end (245 regression subtests pass in ~34s on M-series).
- **1 rules file** at `.claude/rules/pg-implement-discipline.md` (R1–R12) — binding invariants for the planner suite, separate from procedural skills.

### Knowledge corpus

- **Architecture** (9 docs): `overview`, `process-model`, `query-lifecycle`, `executor`, `planner`, `wal`, `mvcc`, `replication`, `access-methods`. The 4 long-form docs flagged by file-level passes (`process-model`, `replication`, `executor`, `planner`) have been corrected in this session with file:line cites for the new findings (SIGURG vs SIGUSR1, `subsystemlist.h`, ProcSignalBarrier, PG18 `effective_wal_level`, sequence sync, `pg_conflict_detection`, failover slots, `resvalue`/`resnull` direct-write, `execAmi.c` mini-dispatch, MinimalTuple loss in tqueue, `additionalsize` HashAgg, ModifyTable Prologue/Act/Epilogue refactor, 9-item `set_plan_references` contract, four-phase join simplification, GEQO as planner extension, PHI freeze invariant).
- **Subsystems** (20 docs): `storage-buffer` (calibration anchor) + 8 spine syntheses `access-heap`, `access-transam`, `storage-lmgr`, `storage-ipc`, `utils-mmgr`, `utils-cache`, `executor`, `optimizer`. Plus 7 leaf subsystem docs from wave 3 (`libpq-backend`, `port`, `main`, `foreign`, `jit`, `partitioning`, `headers-wave3`). **+4 added 2026-06-02 (interactive batch):** `parser-and-rewrite` (766 lines, 47 cites, merged in #19), `access-nbtree` (892 lines, 60 cites, merged in #21), `replication` (979 lines, 70 cites, merged in #25), `tcop` (770 lines, 39 cites).
- **Idioms** (10 docs): `error-handling`, `memory-contexts`, `locking-overview`, `catalog-conventions`, `fmgr`, `spi`, `node-types-and-lists`, `parser-pipeline`, `guc-variables`, `bgworker-and-parallel`.
- **Data-structures** (4 docs): `heap-tuple-layout`, `snapshot-lifecycle`, `bufferdesc-state`, `pgproc-fields`. New this session — focused notes between the idiom level and the per-file level.
- **Conventions** (3): `coding-style`, `testing`, `extension-layout`.
- **Community** (5): `patch-workflow`, `review-patterns`, `wiki-index`, `developer-faq-distilled`, `so-you-want-to-be-a-developer`.
- **Files** (902 docs, 1021 registry rows): per-file mirror under `knowledge/files/src/...`. Covers every spine subsystem at deep-read or read depth — `access/{heap,transam,nbtree,brin,gin,gist,hash,spgist,common,index,table,sequence,tablesample}`, `storage/{buffer,smgr,page,file,freespace,sync,lmgr,ipc}`, `executor/`, `optimizer/`, `parser/`, `rewrite/`, `nodes/`, `catalog/`, `commands/`, `replication/`, `backup/`, `statistics/`, `tsearch/`, `regex/`, `utils/{mmgr,cache,sort,adt,activity,fmgr,hash,mb,resowner,misc,time,init,error}`, `postmaster/`, `tcop/`, `libpq/`, `port/`, `jit/`, `partitioning/`, `foreign/`, `main/`.

### Progress + sessions

- `progress/STATE.md`, `progress/coverage.md`, `progress/census.md` (one-time enumeration at commit `ef6a95c7c64`), `progress/files-examined.md` (1021 rows, append-only ledger).
- ~10 session logs under `sessions/` for major waves.

## In progress

- (nothing in flight)

## Next

1. **PG patch-review v2** (the priority follow-up to the CF #6402 validation run). Today's review was the manual v0 — the user wants this upgraded to a `plan-review-comprehensive`-style multi-agent pipeline: `/pg-review <CF# | PR#>` slash command that fetches + applies + builds + tests mechanically, then fans out to 4 critic agents in parallel (design/architecture against subsystem docs; breaking-change scan; test-coverage critic; style/commit-message critic), then a synthesizer composes one review email. Design notes in `sessions/2026-06-02-cf6402-review-validation.md`.
2. **First real run of the three-phase planner.** The planner suite (Phase 1 brainstorm → Phase 2 plan → Phase 3 pg-implement, with `.claude/rules/pg-implement-discipline.md` as binding rules) landed 2026-06-02 — pick a real feature to brainstorm + plan + implement, calibrate the skills.
3. Workflow agents (Phase 2 of master plan): `code-explorer`, `doc-verifier`. (`patch-reviewer` + `feature-planner` superseded by the planner suite + review-v2 above.)
4. Stretch: filename-form backlink pass — syntheses also mention files by short name (`aset.c`, `heapam.c`) in prose without the `knowledge/files/` prefix. Could widen backlinks beyond the current 633 but carries false-positive risk for common names.
5. Audit pass for pre-anchor staleness: the `bufferdesc-state.md` fix on 2026-06-01 was drift from BEFORE the anchor. Other PG18-era changes may have invalidated similar claims (lwlock subsystem, AIO read-stream, SLRU). Spot-check the most-asserted invariants in idiom + data-structures docs against current source.

## Coverage snapshot

- Registry rows in `progress/files-examined.md`: **1021**.
- Per-file docs under `knowledge/files/`: **917** (+15 this session — 13 synthesis-gap backfills + 2 buffer backfills).
- Per-file docs with upward backlinks: **652** (+17 net-new blocks from the 2026-06-02 corpus-maintainer source-path backlink pass; 633 from the earlier cross-reference pass).
- Subsystem + data-structures docs: **24** (20 subsystem + 4 data-structures).
- Long-form architecture docs: **9**.
- Idiom docs: **10**.
- Glossary: `knowledge/glossary.md`, **15** entries (top-15 internals terms; grown by `pg-corpus-maintainer`).
- Top directories by registry rows: `executor/` (80+), `access/transam` (47), `catalog/` (50), `commands/` (78), `replication/` (56), `optimizer/` (75), `parser/+rewrite/` (57), `storage/ipc` (35), `access/{brin,gin,gist,hash,spgist}` (~80), `nodes/` (33), `utils/cache` (25), `utils/mmgr` (11).

## Recent session logs

- `sessions/2026-06-02-planner-suite.md` — interactive: landed the three-phase planner suite (3 skills + 3 commands + rules file + meta-commit-style + planning/ dir).
- `sessions/2026-06-02-cf6402-review-validation.md` — interactive: Phase-D validation run; reviewed CF #6402 (nbtree dedup) end-to-end; draft review email + system-validation analysis.
- `sessions/2026-06-02-tcop-synthesis.md` — interactive: wrote `knowledge/subsystems/tcop.md` (770 lines, 39 cites).
- `sessions/2026-06-02-replication-synthesis.md` — interactive: wrote `knowledge/subsystems/replication.md` (979 lines, 70 cites) — merged in #25.
- `sessions/2026-06-02-access-nbtree-synthesis.md` — interactive: wrote `knowledge/subsystems/access-nbtree.md` (892 lines, 60 cites) — merged in #21.
- `sessions/2026-06-02-parser-rewrite-synthesis.md` — interactive: wrote `knowledge/subsystems/parser-and-rewrite.md` (766 lines, 47 cites) — merged in #19.
- `sessions/2026-06-02-corpus-maintainer-backlinks-glossary.md` — cloud routine: +117 source-path backlinks, new 15-entry glossary.
- `sessions/2026-06-01-wave2-consolidation.md` — wave-2 consolidation.
- `sessions/2026-06-01-leaf-subsystems-wave3.md` — libpq-backend, port, main, foreign, jit, partitioning.
- `sessions/2026-06-01-mmgr-file-by-file.md`, `sessions/2026-06-01-postmaster-tcop-file-by-file.md`.
- `sessions/2026-06-01-storage-buffer.md` — calibration-run notes.
- `sessions/2026-06-01-build-commands.md` — verified meson + initdb + 245-test green.

## Deferred (not blocking — see `pg-claude-plan.md §14`)

- Whether `knowledge/` doubles as a human-readable handbook (Q6).
- Refresh cadence (Q14) — `/refresh-upstream` exists now; cadence still TBD.
- Direction A (Claude-friendly vs human-friendly prose) — revisit after the cross-ref pass.
- Direction B (teaching vs working mode for `/explain`) — defer until `/explain` exists.
- Workflow agents (code-explorer / patch-reviewer / feature-planner / doc-verifier).
- Tier 2–4 sourcing (web docs, hackers list, CommitFest) on demand.
