# pg-claude — current state

**Phase:** Cross-reference pass + correctness fixes — done. `/refresh-upstream` shakedown next.
**Last activity:** 2026-06-02 — first cloud-routine cycle ran. 7 of 9 roster routines opened clean PRs (#11–#17, all `exit_reason: ok`, docs/corpus-only, still **open**); pg-evening-merger ran at its 02:11 slot before the workers' ~09:2x PRs existed, so it merged nothing (**0 roster PRs on `main` this cycle**); pg-quality-auditor was **SILENT** (no PR — did not start, needs investigation). Daily watchdog briefing at `progress/_briefings/2026-06-02.md`; per-cycle ledger started at `progress/STATE-log.md`. The coverage counts below are unchanged because no roster PR has merged yet — `storage.md`, `Hint_Bits.md`, `citus.md`, `glossary.md`, the `heapam_visibility.c` deep re-verify, and +117 backlinks all sit in the open PRs awaiting tonight's merger. Prior activity: 2026-06-01 — cross-reference pass added upward backlinks from 633 per-file docs to the long-form synthesizers that reference them (specific cites + directory-scope globs from optimizer.md / executor.md). Idempotent regenerator at `/tmp/build_backlinks.py`. Also: backfilled `buf_internals.h.md` + `bufmgr.c.md` per-file docs (broken-cite gap surfaced by the cross-ref pass); refreshed stale `data-structures/bufferdesc-state.md` to match current source (state word is now `pg_atomic_uint64` with content lock encoded in-word, not a separate LWLock). Earlier same date: 13 per-file backfills for spine-synthesis gaps; 4 remaining spine syntheses completed (all 8 now exist).
**Source commit at last verification:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (refreshed 2026-06-01; previous anchor `ef6a95c7c64` had 1 trailing commit, build-system only, no corpus impact — see `progress/refresh-2026-06-01.md`).

## Done

### Scaffold + behavioral surface

- Two-repo split wired: `postgresql/` read-only reference + `postgresql-dev/` mutable test field, both mounted via symlinks in `postgres-claude/`.
- 21 skills (10 C-idioms, 5 contribute-upstream, 3 dev-loop, 1 master navigator, 2 internal). Descriptions optimized in this session via 21 trigger-eval sets + reasoning rewrites with explicit near-miss exclusions.
- 14 slash commands: `/init-pg-dev`, `/link-claude-corpus`, `/setup-pg`, `/pg-start`, `/pg-stop`, `/pg-restart`, `/pg-psql`, `/pg-tail-log`, `/pg-attach`, `/pg-test`, `/pg-fresh`, `/pg-reclone-dev`, `/document-subsystem`, `/refresh-upstream`. Build invocation verified end-to-end (245 regression subtests pass in ~34s on M-series).

### Knowledge corpus

- **Architecture** (9 docs): `overview`, `process-model`, `query-lifecycle`, `executor`, `planner`, `wal`, `mvcc`, `replication`, `access-methods`. The 4 long-form docs flagged by file-level passes (`process-model`, `replication`, `executor`, `planner`) have been corrected in this session with file:line cites for the new findings (SIGURG vs SIGUSR1, `subsystemlist.h`, ProcSignalBarrier, PG18 `effective_wal_level`, sequence sync, `pg_conflict_detection`, failover slots, `resvalue`/`resnull` direct-write, `execAmi.c` mini-dispatch, MinimalTuple loss in tqueue, `additionalsize` HashAgg, ModifyTable Prologue/Act/Epilogue refactor, 9-item `set_plan_references` contract, four-phase join simplification, GEQO as planner extension, PHI freeze invariant).
- **Subsystems** (16 docs): `storage-buffer` (calibration anchor) + 8 spine syntheses `access-heap`, `access-transam`, `storage-lmgr`, `storage-ipc`, `utils-mmgr`, `utils-cache`, `executor`, `optimizer` (synthesized over the per-file corpus, ~287–1092 lines each, ~80–120 citations each, all cross-referenced via `[via knowledge/files/...]`). Plus 7 leaf subsystem docs from wave 3 (`libpq-backend`, `port`, `main`, `foreign`, `jit`, `partitioning`, `headers-wave3`).
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

1. Validation run: pick an actual PG hacking task and run it through the system (the "Phase D" from the master plan) — tests whether the corpus + skills + commands compose into something useful.
2. Workflow agents (Phase 2 from the master plan): `code-explorer`, `patch-reviewer`, `feature-planner`, `doc-verifier`.
3. Stretch: filename-form backlink pass — syntheses also mention files by short name (`aset.c`, `heapam.c`) in prose without the `knowledge/files/` prefix. Could widen backlinks beyond the current 633 but carries false-positive risk for common names.
4. Audit pass for pre-anchor staleness: the `bufferdesc-state.md` fix this session was drift from BEFORE the anchor. Other PG18-era changes may have invalidated similar claims (lwlock subsystem, AIO read-stream, SLRU). Spot-check the most-asserted invariants in idiom + data-structures docs against current source.

## Coverage snapshot

- Registry rows in `progress/files-examined.md`: **1021**.
- Per-file docs under `knowledge/files/`: **917** (+15 this session — 13 synthesis-gap backfills + 2 buffer backfills).
- Per-file docs with upward backlinks: **633** (cross-reference pass).
- Subsystem + data-structures docs: **20** (16 subsystem + 4 data-structures).
- Long-form architecture docs: **9**.
- Idiom docs: **10**.
- Top directories by registry rows: `executor/` (80+), `access/transam` (47), `catalog/` (50), `commands/` (78), `replication/` (56), `optimizer/` (75), `parser/+rewrite/` (57), `storage/ipc` (35), `access/{brin,gin,gist,hash,spgist}` (~80), `nodes/` (33), `utils/cache` (25), `utils/mmgr` (11).

## Recent session logs

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
