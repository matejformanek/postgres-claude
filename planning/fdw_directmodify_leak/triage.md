# Phase 1 triage — fdw_directmodify_leak

## Target selection

**Chosen:** upstream commit
`232d8caeaaa06fd3c6b76a68ef9c62ea5fdf12ea`
*"Fix memory leakage in postgres_fdw's DirectModify code path."*

- **Author + committer:** Tom Lane, 2025-05-30
- **Bug shape:** PG_TRY blocks in postgres_fdw's DirectModify
  path cannot reliably free a remote PGresult when the containing
  query throws mid-iteration — most often when a locally-computed
  `RETURNING` expression (e.g. `1000/(id-50)` with id=50 in the
  batch) dies while the remote's PGresult is still held.
- **Diff:** single file, +35 / −27, back-patched-through PG13.

## Why this target (vs. the 3 prior calibration wins)

|                          | jsonpath_leak (`5a2043bf`) | pgstat_progress_leak (`b20c952c`) | nodesubplan_leak (`abdeacdb`) | **fdw_directmodify_leak (`232d8cae`)** |
|--------------------------|---------------------------|-----------------------------------|-------------------------------|----------------------------------------|
| Subsystem                | utils/adt/jsonpath        | utils/activity/pgstat             | executor/TupleHashTable       | **contrib/postgres_fdw**               |
| Bug shape                | Transient-lifetime leak   | Redundant double-init             | Ownership-boundary API change | **PG_TRY / mid-query-error orphan**    |
| Diff size                | +362/−233 (1 file)        | −2 (1 file)                       | +33/−43 (2 files)             | **+35/−27 (1 file)**                    |
| Signal shape             | Query-lifespan quadratic  | Per-parallel-worker cumulative    | Query-lifespan per-hash-probe | **Session-lifespan per-error**          |
| Observability            | RSS obvious               | RSS subtle (per-worker)           | RSS + pg_backend_memory_contexts | **RSS only under amplification / Valgrind** |
| Approach-E trigger (L6)  | (n/a — struct redesign)   | (n/a — 2-line delete)             | fires (6 exit paths)          | **fires** (PG_TRY handler → callback shift) |

**Novelty for the calibration:**

1. **New subsystem** — contrib/postgres_fdw + libpq PGresult
   lifetime. The prior three hit `utils/adt`, `utils/activity`,
   and `executor`. FDW brings its own idioms:
   `postgresBeginDirectModify` / `postgresIterateDirectModify` /
   `postgresEndDirectModify` state-machine pattern, libpq
   PGresult ownership across the C-level malloc boundary
   (context-managed doesn't apply), and PG_TRY / PG_END_TRY
   error-safety idiom.
2. **First "PG_TRY is not enough" bug in the calibration.** The
   fix isn't "add a MemoryContextReset" — it's "PG_TRY blocks
   don't cover mid-fetch aborts; move ownership to a memory
   context reset callback so the resource dies with the
   executor state context." That is exactly the
   *"restructure control flow to match the new invariant"*
   pattern L6 codifies. This target is the L6 stress test.
3. **New signal shape** — session-lifespan. Doesn't grow inside
   one query (`ExecutorState` context lifetime is
   per-query-invocation; the PGresult is malloc'd by libpq
   outside PG's memory-context system, so it survives context
   teardown). Grows across queries in one session, released only
   at backend exit. Different observability profile from the
   3 prior wins.
4. **Author diversity again weak** (Tom Lane × 3 of 4 targets),
   but the subsystem novelty compensates.

## Subsystem mapping

| Layer                         | Files                                              | Prior corpus support                             |
|-------------------------------|----------------------------------------------------|--------------------------------------------------|
| DirectModify state machine    | `contrib/postgres_fdw/postgres_fdw.c`             | `knowledge/subsystems/foreign.md` if present     |
| PGresult lifetime idiom       | `src/interfaces/libpq/fe-exec.c` (read-only)      | `knowledge/idioms/libpq-backend-usage.md` (?)    |
| Memory-context reset callback | `src/backend/utils/mmgr/mcxt.c`                    | `knowledge/idioms/memory-contexts.md` (rich)     |
| PG_TRY / error handling       | `src/include/utils/elog.h`                         | `knowledge/idioms/error-handling.md`             |

## Blast-radius estimate

- **Direct edits:** `postgresBeginDirectModify` +
  `postgresIterateDirectModify` + `postgresEndDirectModify` + a
  new memory-context reset callback registration site. All in
  the one file.
- **Callers of the modified API:** none directly (FDW methods are
  invoked via the FDW routine table).
- **Sister leaks:** the commit message flags that other backend
  modules using libpq (`walreceiver`, `dblink`, others) may have
  similar leaks. Tom explicitly defers the universal fix to v19.
  Our scope: only DirectModify.
- **On-disk / catalog / WAL / concurrency:** none.

## Reproducer recipe (validated in Phase 0 baseline.md)

```sql
-- Setup: postgres_fdw + loopback + foreign table on remote_t
CREATE EXTENSION postgres_fdw;
CREATE SERVER loopback FOREIGN DATA WRAPPER postgres_fdw
  OPTIONS (host '/tmp', port '<port>', dbname 'postgres');
CREATE USER MAPPING FOR PUBLIC SERVER loopback;
CREATE TABLE remote_t (id int PRIMARY KEY, val int, tag text);
INSERT INTO remote_t
  SELECT g, g*10, 'row' || g FROM generate_series(1, 1000) g;
CREATE FOREIGN TABLE t_fdw (id int, val int, tag text)
  SERVER loopback OPTIONS (table_name 'remote_t');

-- Reproducer, 20 000 iterations, all in ONE session:
BEGIN;
UPDATE t_fdw SET val = val WHERE id BETWEEN 1 AND 100
  RETURNING id, 1000/(id-50);
ROLLBACK;
-- ... × 20000
```

Signal: backend RSS climbs **11.6 → 90.9 MB across ~25 s** of the
loop (~3.3 MB/s ≈ 4 KB per leaked PGresult × 200 iter/s).

## Ranked runners-up (kept for reference)

Position 2 — `be86ca103a4` (Tom Lane, 2025-05-28, plpgsql
`funccache` + `pl_comp.c` compilation-failure leak). +41/−9, two
files. Reproducer: syntax-error function. Passed over as
runner-up because the fix is a "reparent on success" allocation
reordering — good, but the L6 approach-E trigger is weaker
(the leak is a 2-branch commit-vs-rollback shape, not a 3+-exit
control-flow refactor).

Position 3 — `dc9a2d54fd2` (Álvaro Herrera, 2025-05-29, relcache
CHECK-constraint conditional allocation). +7/−4, single file.
Passed over as too small — same size class as the
`pgstat_progress_leak` byte-identical convergence.

## Phase 2 handoff

- Read `baseline.md` for the reproducer + measurement.
- BLIND CONSTRAINT: do NOT read `232d8caeaaa` source, commit
  message body beyond the summary + first paragraph (already
  quoted in baseline.md), or the discussion thread during
  Phases 2-3.
- Enter `pg-feature-brainstorm` next with the leak evidence.
- L5 (storage representation) — likely N/A (PGresult is an
  opaque libpq struct; no data-structure choice on our side).
- **L6 (approach E, freshly-landed 2026-07-13) MUST fire** — this
  target's fix pattern IS the approach-E shape.
- F30 grep-pass — search for `PG_TRY(` / `PG_CATCH(` / `PG_END_TRY`
  in `contrib/postgres_fdw/postgres_fdw.c` and confirm the
  ownership assumption (which paths hold the PGresult, which
  release it).

## Phase 1 exit condition — MET

- Target picked with explicit reasoning against 2 alternatives.
- Reproducer recipe carried forward from Phase 0.
- Blast radius mapped; L6 relevance called out as the primary
  interest for this run.
