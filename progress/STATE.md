# pg-claude — current state

**Phase:** Deep file-by-file corpus building (Phase 0.5 calibration long-done).
**Last activity:** 2026-06-01 — wave 3 leaf subsystems (libpq-backend, port, main, foreign, jit, partitioning) completed: 6 new `knowledge/subsystems/*.md` docs + 1 `headers-wave3.md` skim doc + 63 registry rows.
**Source commit at last verification:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3`

## Done

- Reverse symlink `postgres-claude/source -> ../postgresql` in place; `source` added to `postgres-claude/.gitignore`.
- `postgresql/.git/info/exclude` extended with `.claude/` and `CLAUDE.md` so meta files never get committed upstream.
- Repo skeleton created: `.claude/{skills,agents,commands}`, `knowledge/{subsystems,data-structures,idioms,files}`, `sessions/`, `progress/`.
- Parent router `/Users/matej/Work/postgres/CLAUDE.md` + meta-repo `postgres-claude/CLAUDE.md` + `postgres-claude/README.md` written.
- `.claude/settings.json` — Phase 0 permission posture (allow read/build/git-read, ask on write/commit/destructive).
- `.claude/agents/subsystem-documenter.md` — the §5.1 miner agent with full doc template (§3 of master plan) embedded.
- `.claude/skills/memory-keeping/SKILL.md` — discipline for STATE.md / coverage.md / sessions/.
- `.claude/skills/build-and-run/SKILL.md` — meson primary, fork-model gotcha, single-user mode, regression suites.
- `progress/census.md` — full enumeration of READMEs (90), backend subsystems with file counts & LOC, test dirs with roles. Stamped with commit `ef6a95c7c64`.
- `knowledge/subsystems/storage-buffer.md` — calibration subsystem doc. Tag tally: verified-by-code=49, from-README=27, from-comment=15, inferred=0, unverified=5. 6 open questions logged in §9.
- `progress/coverage.md` updated with the storage-buffer row.
- Wave 2 file-by-file agents complete (registry rows added per agent):
  - `utils/cache` — 12 files.
  - `utils/{time,init,error}` — 10 files (time=2, init=4, error=4).
  - `access/{common,index,table,sequence,tablesample}` — file-level coverage of the access entry layer.
  - `access/nbtree` — 13 files.
  - `storage/ipc` — file-level coverage of the IPC layer.
  - `nodes` — node-infrastructure files including `pathnodes.h`, `memnodes.h`, `execnodes.h`.
  - `parser` + `rewrite` — rewrite layer headers landed (`rewriteHandler.h`, `rewriteSearchCycle.h`, etc.).
  - `utils/sort` + `utils/adt` foundational — adt foundations covered.

## In progress

Wave 3 file-by-file agents launched today:
- `utils/adt` finish
- `executor` remaining
- `optimizer` remaining
- `replication`
- `catalog`
- `commands` core DDL
- `access/{brin,gin,gist,hash,spgist}`
- ~~`libpq` / `port` / `jit` / `partitioning` / `foreign` / `main`~~ — DONE (this pass): `knowledge/subsystems/{libpq-backend,port,main,foreign,jit,partitioning,headers-wave3}.md`.
- `backup` / `statistics` / `tsearch` / `regex` / `utils-rest`
- this consolidation pass (the one writing this STATE.md)

## Next

1. Once `smgr` + `md` + `fd` are all in the registry, write `knowledge/architecture/storage-layer.md`.
2. Cross-reference pass: link `knowledge/files/` docs back from `knowledge/architecture/` and `knowledge/idioms/`.
3. Revisit the calibration doc `knowledge/subsystems/storage-buffer.md` against what other docs surfaced — count corrections.
4. Decide whether to re-run `subsystem-documenter` on the next subsystem now that file-level coverage exists.

## Coverage snapshot

- Registry rows in `progress/files-examined.md`: **273** (matched by `grep -c '^| src/'`).
- Per-file docs under `knowledge/files/`: **414** (matched by `find knowledge/files -name '*.md' | wc -l`).
- Top directories by registry rows: `access/nbtree` (13), `utils/cache` (12), `utils/mmgr` (11), `storage/lmgr` (10), `storage/file` (6), `storage/buffer` (6).

## Recent session logs

- `sessions/2026-06-01-leaf-subsystems-wave3.md` — libpq-backend, port, main, foreign, jit, partitioning fan-out (this pass).
- `sessions/2026-06-01-wave2-consolidation.md` — previous wave.
- `sessions/2026-06-01-mmgr-file-by-file.md`
- `sessions/2026-06-01-postmaster-tcop-file-by-file.md`
- `sessions/2026-06-01-storage-buffer.md` — calibration-run notes.
- `sessions/2026-06-01-build-commands.md`

## Deferred (not blocking — see `pg-claude-plan.md §14`)

- Whether `knowledge/` doubles as a human-readable handbook (Q6).
- Refresh cadence (Q14) — only relevant once ≥ 3 docs exist.
- Direction A (Claude-friendly vs human-friendly prose) — revisit after the calibration doc.
- Direction B (teaching vs working mode for `/explain`) — defer until `/explain` exists.
- Idiom skills (memory-contexts, ereport, fmgr, spi), workflow skills beyond build-and-run, all slash commands, the code-explorer / patch-reviewer / feature-planner / doc-verifier agents, the cross-reference pass, Tier 2–4 sourcing.
