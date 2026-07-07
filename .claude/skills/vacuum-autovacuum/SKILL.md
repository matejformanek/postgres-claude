---
name: vacuum-autovacuum
description: PostgreSQL's VACUUM machinery — heap scanning, dead-tuple collection, index cleanup, HOT pruning, freezing, VM/FSM updates, truncation — plus the autovacuum launcher/worker architecture. Loads when the user asks about `VACUUM` internals, `vacuumlazy.c`'s three-phase orchestration, TidStore (the radix-tree dead-TID collector), HOT chains, HEAP_XMIN_FROZEN and freeze planning, VACUUM FREEZE, VACUUM FULL vs `vacuum_full_freeze_min_age`, autovacuum threshold + cost-limit tuning, autovacuum worker scheduling, or debugging "why is my table getting vacuumed constantly / never". Also for the xmin horizon (RecentXmin / OldestXmin / GlobalVis), the interaction between vacuum and replication slots, parallel VACUUM (`vacuumparallel.c`), and the wraparound-emergency path. Skip when the ask is about `pg_repack` (contrib alternative), pg_amcheck (verifier), or `CREATE INDEX CONCURRENTLY` (index-build side, not vacuum-side).
when_to_load: Understand or debug VACUUM behavior; add a new vacuum-related feature or GUC; work with autovacuum tuning; investigate index-cleanup phases; touch freeze / xmin-horizon logic; extend TidStore for a new consumer.
companion_skills:
  - locking
  - executor-and-planner
  - access-method-apis
---

# vacuum-autovacuum — the VACUUM and autovacuum subsystem

VACUUM is PostgreSQL's storage reclaimer. It reads live-and-dead tuples off pages, prunes HOT chains, collects dead item IDs, invokes each index's bulk-delete callback, revisits heap pages to mark item IDs unused, updates the FSM/VM, freezes old tuples, and optionally truncates trailing empty pages. Autovacuum is the launcher+worker daemon that decides which relations to vacuum and when, based on cumulative-stats thresholds.

Files here are big — `vacuumlazy.c` and `autovacuum.c` are both 100+ KB — because the state machine has many phases and many edge cases.

## The file map

### VACUUM engine

| File | Lines / KB | Role |
|---|---|---|
| `commands/vacuum.c` | 85K | Outer dispatch — parses `VACUUM (options ...) rel`, iterates the relation list, opens each rel with the right lock, drives the per-relation vacuum, cleans up. |
| `access/heap/vacuumlazy.c` | 129K | The heap engine. Three-phase: (1) heap scan collecting dead TIDs into TidStore; (2) index vacuum via `amvacuumcleanup` / `ambulkdelete` callbacks; (3) heap revisit marking LP_UNUSED. Also runs the freeze planner and updates VM. |
| `commands/vacuumparallel.c` | 42K | Parallel-index-vacuum coordinator. Launches bgworkers per index (when `PARALLEL n` requested or triggered by `min_parallel_index_scan_size`), each runs its AM's vacuum callback. |

### Autovacuum daemon

| File | Lines / KB | Role |
|---|---|---|
| `postmaster/autovacuum.c` | 113K | Launcher + worker. Launcher is an aux process that spawns workers (which are bgworkers) as needed. Workers pick candidate relations from cumulative stats + reltuples/relfrozenxid thresholds, then run VACUUM/ANALYZE against them. |

### Supporting layer

- `access/common/vacuum_stat.c` — statistics accumulation during a single vacuum run.
- `access/gin/ginvacuum.c` / `access/gist/gistvacuum.c` / `access/spgist/spgvacuum.c` / `access/hash/hash.c` (hashbucketcleanup) / `access/nbtree/nbtree.c` (btvacuumscan) — per-AM vacuum callbacks.
- `storage/freespace/freespace.c` — FSM updates.
- `storage/buffer/bufmgr.c` — `VacuumBufferPins` etc.

## The three phases of `vacuumlazy.c`

The `## Idioms invoked` block on scenarios and the corpus-chain output both surface this — see `knowledge/idioms/vacuum-two-pass-heap.md`. Concise version:

1. **Phase I — heap scan** (`lazy_scan_heap`). Read each block (via read-stream since PG 17), skip if the VM says "all-visible + all-frozen", otherwise:
   - Prune HOT chains (`heap_page_prune_and_freeze`).
   - Freeze if `heap_prepare_freeze_tuple` says so.
   - Collect dead item IDs into TidStore (radix-tree).
   - Update VM bits after commit if this page is now all-visible / all-frozen.

2. **Phase II — index cleanup** (per index; can be parallel). For each index, call `ambulkdelete` (with the dead-TID callback) OR `amvacuumcleanup` (for indexes that don't need per-page cleanup). Each AM knows how to remove/tombstone tuples pointing at the dead TIDs.

3. **Phase III — heap revisit** (`lazy_vacuum_heap_rel`). Second pass through the heap pages that had dead tuples, marking each dead item ID as LP_UNUSED. VM update to all-visible if applicable.

If TidStore fills to `maintenance_work_mem`, Phase I pauses, Phase II runs (index vacuum), Phase III runs, TidStore resets, Phase I resumes. Big tables can go through this cycle many times.

## Autovacuum architecture

**Launcher** (`AutoVacLauncherMain`) — an aux process the postmaster starts if `autovacuum = on`. Runs in a loop:

1. Sleep for `autovacuum_naptime` (default 1 min).
2. Wake up, connect to each database, read cumulative stats to compute per-relation "needs vacuum?" thresholds (`autovacuum_vacuum_threshold + reltuples * autovacuum_vacuum_scale_factor` for regular; `_freeze_max_age` for wraparound).
3. If a relation needs vacuum, launch a **worker** (a bgworker) to handle it. Cap at `autovacuum_max_workers`.
4. Repeat.

**Worker** (`AutoVacWorkerMain`) — a bgworker. Connects to the launcher-assigned database, runs `vacuum` or `analyze` on the assigned relations, then exits. Workers don't survive across naptimes — one worker per "batch of tables in one database".

**Wraparound protection** — if any relation's `relfrozenxid` age exceeds `autovacuum_freeze_max_age`, the launcher will spawn workers regardless of `autovacuum = off`. This is the "you can't turn off autovacuum for xid safety" invariant.

## Data structures

- **`TidStore`** — the radix-tree dead-TID collector. Replaces the old `LVDeadItems` array in PG 17+. Uses adaptive bitmap-vs-short-list encoding per block. Bounded by `maintenance_work_mem`. See `knowledge/idioms/vacuum-tid-store.md`.
- **`LVRelState`** — the per-relation vacuum state carried through all three phases.
- **`GlobalVisState`** — the xmin horizon — the OldestXmin below which we can freeze/remove.
- **`PgStat_TabEntry`** — cumulative stats consulted by autovacuum launcher.

## Common patch shapes

### Add a new VACUUM option

- Extend `VacuumParams` in `src/include/commands/vacuum.h`.
- Add option parsing in `commands/vacuum.c` (`ExecVacuum` / `vacuum_option_map`).
- Thread the option through `lazy_scan_heap` etc.
- Doc it in `doc/src/sgml/ref/vacuum.sgml`.
- Test in `src/test/regress/sql/vacuum.sql`.

### Add a new autovacuum threshold or cost knob

- New GUC in `src/backend/utils/misc/guc_tables.c`.
- Read + apply in `postmaster/autovacuum.c` where the existing thresholds are computed.
- Consider per-table override via `pg_class.reloptions` (extend `heap_reloptions` in `access/common/reloptions.c`).

### Change what triggers autovacuum

- Modify the "needs vacuum?" computation in `relation_needs_vacanalyze` (in `autovacuum.c`).
- Test carefully — this affects every table on every naptime cycle.
- Add a new stats counter if the trigger uses info not already in `PgStat_TabEntry` (touches `pgstat-framework` — see `knowledge/skills/pgstat-framework/SKILL.md`).

### Extend TidStore

Uncommon. Talk to hackers-list first; this is a hot path. See `knowledge/idioms/vacuum-tid-store.md` for the radix-tree layout and encoding rules.

## Pitfalls

- **`OldestXmin` is a snapshot, not a live value** — vacuum computes it once per relation and uses it throughout. If a long transaction on another backend is holding an old xmin, vacuum can't freeze past it. This is why one long-idle transaction can effectively disable freezing cluster-wide.
- **VM bits are a hint, not authoritative** — vacuum reads VM to skip pages, but VM can be stale. A skip based on all-visible only avoids scanning; a skip based on all-frozen also lets vacuum move `relfrozenxid` forward.
- **`autovacuum = off` doesn't stop wraparound autovac** — the launcher will still spawn workers when xid age crosses the limit.
- **Parallel vacuum uses bgworkers** — you get `max_worker_processes` from the same pool. On a busy cluster this can starve out other bgworker consumers (like logical rep apply).
- **`VACUUM FULL` is a rewrite, not a `vacuumlazy.c` op** — it's implemented via `commands/cluster.c` (calls `cluster_rel` with a fresh heap). Only `VACUUM` (no FULL) goes through `vacuumlazy.c`.
- **`ANALYZE` inside `VACUUM` is separate** — same command boundary but different code path (`commands/analyze.c`). VACUUM options don't automatically apply to the ANALYZE portion.
- **HOT prune runs at read time too** — `heap_page_prune_opt` fires from `heap_getnextslot` under SELECT if a heavy chain accumulates. Vacuum's HOT prune is just the "definitive" pass — the same code runs opportunistically elsewhere. So a VACUUM you thought did nothing may have been redundant with earlier read-time pruning.
- **`freeze_min_age` vs `freeze_max_age`** — min is "when may we freeze"; max is "when must we freeze". They govern proactive vs required freezing.
- **`maintenance_work_mem` bounds TidStore** — a huge table with lots of dead tuples doesn't fail; it just does more three-phase cycles. But that means more index scans, so heavy vacuum benefits disproportionately from more m_w_m.

## Related corpus

- **Idioms** (all 8 relevant): `autovacuum-launcher`, `heap-tuple-freeze`, `vacuum-hot-prune`, `vacuum-skip-pages`, `vacuum-tid-store`, `vacuum-truncate-relation`, `vacuum-two-pass-heap`, `xmin-horizon-management`.
- **Subsystems**: `access-heap` (heapam.c hosts the freeze/prune helpers), `access-transam` (xid horizon), `contrib-pg_visibility` (VM inspection), `contrib-amcheck` (audit tool that can cross-check vacuum state).
- **Data structures**: `pgproc-fields` (PGPROC.xmin is the horizon source), `bufferdesc-state` (BufferPin discipline during vacuum).
- **Related planning**: `planning/pgstat_progress_leak/` — worked in `backend_progress.c` which VACUUM uses for `pg_stat_progress_vacuum`.

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --file src/backend/access/heap/vacuumlazy.c
python3 scripts/corpus-chain.py --idiom vacuum-two-pass-heap
python3 scripts/corpus-chain.py --file src/backend/postmaster/autovacuum.c
```

The first surfaces the three-phase caller graph + related idioms; the second gives the pattern-with-live-examples; the third the autovac architecture.

## Boundary

**Use this skill** for VACUUM (non-FULL) internals + autovacuum daemon behavior.

**Don't use** for:
- **`VACUUM FULL` / `CLUSTER`** — those are in `commands/cluster.c`, different code path (relation rewrite via new relfilenumber).
- **`REINDEX`** — separate; index-only rebuild, no dead-tuple collection.
- **`pg_repack` / `pg_squeeze`** — contrib alternatives; touch userspace only.
- **`ANALYZE`-only** — has its own file `commands/analyze.c` with different sampling logic.
- **Index-AM internals** — see `access-method-apis` skill; this skill covers the vacuum ORCHESTRATION, not what each AM does internally.
