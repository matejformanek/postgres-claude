# pg-claude — current state

**Phase:** **Phase A — corpus completeness + issue surfacing.** Tooling buildout complete (three-phase planner suite + pg-patch-review v2 landed 2026-06-02). New arc decided 2026-06-02 evening: A → B → C → D where A=full file-by-file coverage of src/+contrib/ (currently 35.8%; gap 1 647 files), B=developer personas mined from pgsql-hackers + commits, C=calibration of the planner + review pipelines, D=PG data-leak hardening project. Nightly cloud routines run autonomously.
**Last activity:** 2026-06-03 (morning, interactive) — **A2 libpq-stack sweep landed**: 69 per-file docs across `src/include/libpq/` (20) + `src/backend/libpq/` (17) + `src/interfaces/libpq/` (32) via 6 parallel general-purpose agents (~13 min wall time, B4 written to wrong location and manually relocated); **227 [ISSUE-*] tags surfaced** and consolidated into `knowledge/issues/libpq.md` grouped by Phase D priority (secret-scrubbing gaps, downgrade/protocol-confusion, DoS uncapped inputs, TLS/cert validation, wire-protocol invariants, trust boundaries, info disclosure) + P1 undocumented invariants + P2 stale TODOs + P3 win32 shim gaps. Coverage bumps: 989→1 058 docs (38.6%→41.3%); src/include 42.8%→45.1%; src/backend 69.2%→71.1%; src/interfaces 0%→19.3%. Overnight cloud cycle was the first under the new behavior (#33+#32 merged, #36 throughput bump NOT yet — 7 OK / 2 SILENT [community-pulse, upstream-watcher]; pg-quality-auditor SILENT incident from 2026-06-02 **RESOLVED** by the defenses we added). #36 throughput bump merged this morning so tonight's cycle uses new budgets. #40 (state-keeper morning briefing) closed due to STATE.md conflict; tomorrow's run will cover both nights. Earlier 2026-06-02 (late evening): cloud throughput bump landed (#36): `.claude/cloud/_loader.md` §5 rewritten with the "fill the budget" floor (loop until ≥70% output consumed; empty-handed run = process bug); all 10 routine frontmatters bumped (`pg-file-backfiller` 120k/25k → 400k/100k; `pg-corpus-maintainer` 80k/20k → 250k/60k; `pg-quality-auditor` 80k/20k → 250k/60k; `pg-docs-miner` 60k/20k → 200k/50k; `pg-extension-anthropologist` 70k/20k → 250k/60k; `pg-upstream-watcher` 80k/25k → 200k/50k; `pg-community-pulse` 100k/30k → 250k/60k; `pg-user-question-harvester` 70k/15k → 200k/50k; `pg-evening-merger` 150k/30k → 300k/60k; `pg-state-keeper` 60k/20k → 150k/40k); 4 producer recipes restructured to loop-not-once (file-backfiller 2-3 files/run → 10-20; extension-anthropologist 1 → 3-4; docs-miner 2 → 6-10; quality-auditor 1 → 5-10; user-question-harvester 5-8 → 20-30; corpus-maintainer glossary top-15 → top-50). Expected effect: Phase A closes in ~3-4 months instead of ~18. Earlier 2026-06-02 evening: A1 catalog-headers sweep landed 72 docs + 68 issues (#35). Earlier same evening: Phase A setup landed (#33). Earlier afternoon: refreshed `progress/coverage.md` with current numbers; wrote `progress/coverage-gaps.md` (per-directory work queue); created `knowledge/issues/` skeleton (README + tag convention `[ISSUE-&lt;type&gt;: ...]` + template + storage-buffer starter); extended `.claude/cloud/pg-file-backfiller.md` (scope widened beyond src/backend; batch 2-3 small files/run; issue-surfacing step added; budgets bumped); extended `.claude/cloud/pg-corpus-maintainer.md` (added Pass 3 issue-register mirroring); extended `.claude/cloud/pg-quality-auditor.md` (added third ISSUE-triage mode + failure-to-run defenses for the 2026-06-02 SILENT incident). Master `pg-claude` skill updated to register `knowledge/issues/` and `progress/coverage-gaps.md`. Earlier same afternoon: **PG patch-review v2** + **three-phase planner suite** landed (#28, #29). Same-day priors: 4 subsystem-synthesis PRs merged — parser-and-rewrite (#19), access-nbtree (#21), replication (#25), tcop (#27). Cloud cycle: 7 of 9 producers opened PRs (#11–#17); pg-quality-auditor SILENT — defenses added this session, real root cause still TBD. Daily watchdog briefing at `progress/_briefings/2026-06-02.md`. Prior activity 2026-06-01: cross-reference pass added 633 upward backlinks, `data-structures/bufferdesc-state.md` refreshed for PG18 atomic state-word.
**Source commit at last verification:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (refreshed 2026-06-01; previous anchor `ef6a95c7c64` had 1 trailing commit, build-system only, no corpus impact — see `progress/refresh-2026-06-01.md`).

## Done

### Scaffold + behavioral surface

- Two-repo split wired: `postgresql/` read-only reference + `postgresql-dev/` mutable test field, both mounted via symlinks in `postgres-claude/`.
- **26 skills** (10 C-idioms, 5 contribute-upstream, 3 dev-loop, 1 master navigator, 2 internal, 3 planner-suite, 1 meta-commit-style, **+1 added 2026-06-02 evening:** `pg-patch-review` — multi-agent comprehensive review). Descriptions optimized for trigger accuracy with explicit near-miss exclusions.
- **18 slash commands**: `/init-pg-dev`, `/link-claude-corpus`, `/setup-pg`, `/pg-start`, `/pg-stop`, `/pg-restart`, `/pg-psql`, `/pg-tail-log`, `/pg-attach`, `/pg-test`, `/pg-fresh`, `/pg-reclone-dev`, `/document-subsystem`, `/refresh-upstream`, `/pg-brainstorm`, `/pg-plan`, `/pg-implement`, **+1 added 2026-06-02 evening:** `/pg-review`. Build invocation verified end-to-end (245 regression subtests pass in ~34s on M-series).
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

- **Phase A** — corpus completeness + issue surfacing. Setup landed 2026-06-02; bulk fill ongoing (cloud routine + foreground sweeps).

## Next

### Phase A active work queue (corpus completeness — 1 506 files to go)

1. ~~**Foreground sweep #1** — `src/include/catalog/`~~ — DONE 2026-06-02 (72 docs, 68 issues; PR #35 merged).
2. ~~**Foreground sweep #2** — libpq stack~~ — DONE 2026-06-03 (69 docs, 227 issues; PR pending).
3. **Foreground sweep #3 — `src/bin/pg_dump/` + `src/bin/psql/` + `src/bin/pg_basebackup/`** (~46 files). User-facing tool surface; pg_dump security model is Phase D territory.
4. **Foreground sweep #4 — `src/backend/utils/cache/` + `src/backend/utils/adt/`** (the heaviest part of the 233 utils/ files).
5. **Foreground sweep #5 — `src/common/`** (50, 1.6% covered) — cross-frontend/backend shared crypto + scram + base64 + protocol; Phase D candidate because libpq + pg_dump rely on these.
6. **Foreground sweep #6 — `src/include/replication/`** (22, 4.5%) — close the gap exposed by the spine doc.
7. **Foreground sweep #7 — `src/pl/plpgsql/`** (16 files) — privileged sandbox boundary; PL code runs inside backend with full privilege.
8. **Cloud routine grind** — pg-file-backfiller continues nightly under widened scope + new budgets; targets remaining `src/port`, `src/timezone`, `src/fe_utils`, then contrib/.
9. Refresh `progress/coverage-gaps.md` whenever per-file count moves ≥50 or a dir crosses a 10% boundary.

### Phase B/C/D — queued behind Phase A

6. **Phase B — developer personas.** Mine pgsql-hackers + commit attribution for 6-12 reviewer/committer personas (Tom Lane, Andres Freund, Robert Haas, Peter Eisentraut, Heikki, Álvaro, Tomas Vondra, Nathan Bossart, Michael Paquier). Each: typical concerns, blocking-vs-nit threshold, what they catch others miss. Wire into `pg-patch-review` as critic-persona options + into `pg-feature-plan` as planning lenses.
7. **Phase C — calibration.** Exercise the planner suite + review v2 + personas against real CF entries + small features. Tighten skill prompts via `hf(skill):` commits. Goal: production-ready before Phase D.
8. **Phase D — PostgreSQL data-leak hardening project.** The payload. Scope TBD (memory / info / RLS / leaky-view family); will brainstorm via `/pg-brainstorm` once A-C done.

### Side concerns (pickable anytime)

9. Workflow agents (Phase 2 of master plan): `code-explorer`, `doc-verifier`. (`patch-reviewer` + `feature-planner` superseded by `pg-patch-review` + the planner suite.)
10. Filename-form backlink pass — syntheses also mention files by short name (`aset.c`, `heapam.c`) in prose without the `knowledge/files/` prefix. Stretch; false-positive risk for common names.
11. Audit pass for pre-anchor staleness: the `bufferdesc-state.md` fix on 2026-06-01 was drift from BEFORE the anchor. Other PG18-era changes (lwlock, AIO read-stream, SLRU) may have invalidated similar claims. Spot-check the most-asserted invariants.
12. **pg-quality-auditor SILENT 2026-06-02 root cause.** Defenses landed in this session; the actual reason it didn't write a log still unknown. Pull the cloud-routine event log next day cycle.

## Coverage snapshot (refreshed 2026-06-02 evening)

- Source files (.c + .h) under `source/src/` + `source/contrib/`: **2 564**.
- Per-file docs under `knowledge/files/`: **917** (35.8%).
- Registry rows in `progress/files-examined.md`: **1 021**.
- **Phase A gap: 1 647 files undocumented.** Full per-directory breakdown in `progress/coverage-gaps.md`.
- Top-line per top-level tree: src/backend 69.2%, src/include 34.2%, src/common 1.6%, src/port 0%, src/interfaces 0%, src/bin 0%, src/pl 0%, contrib 0%.
- Per-file docs with upward backlinks: **652** (+17 net-new blocks from the 2026-06-02 corpus-maintainer source-path backlink pass; 633 from the earlier cross-reference pass).
- Subsystem + data-structures docs: **24** (20 subsystem + 4 data-structures).
- Long-form architecture docs: **9**.
- Idiom docs: **10**.
- Issue registers: **knowledge/issues/** — 1 starter file (`storage-buffer.md`) + README/template. Will grow as Phase A surfaces issues.
- Glossary: `knowledge/glossary.md`, **15** entries (top-15 internals terms; grown by `pg-corpus-maintainer`).

## Recent session logs

- `sessions/2026-06-02-phase-a-setup.md` — interactive: Phase A (corpus completeness) setup landed — refreshed coverage.md, wrote coverage-gaps.md, created knowledge/issues/ skeleton, extended pg-file-backfiller + pg-corpus-maintainer + pg-quality-auditor recipes.
- `sessions/2026-06-02-pg-review-v2.md` — interactive: landed `pg-patch-review` skill (4 critics + synthesizer) + `/pg-review` slash command. Modeled on `plan-review-comprehensive`. Master `pg-claude` nav updated.
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
