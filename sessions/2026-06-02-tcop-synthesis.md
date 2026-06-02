# 2026-06-02 — tcop spine synthesis

**Type:** interactive (worktree `ft_corpus_tcop`).
**Outcome:** `knowledge/subsystems/tcop.md`, 770 lines, 39
confidence-tagged cites, verified against source commit `4b0bf0788b0`.

## What this session did

Closed the priority-15 spine gap from `pg-claude-plan.md` §5.3 — the
last of the four spine syntheses queued for today. tcop had 7 per-file
docs + 6 header docs but no directory-level synthesis.

The synthesis covers:

1. **The per-backend lifecycle**: postmaster fork → `BackendMain` →
   `BackendInitialize` (with the "no shmem" invariant) → `InitProcess`
   → `PostgresMain` → sigsetjmp landing → main loop.
2. **First-byte dispatch table** for the V3 wire protocol
   (Q/P/B/E/F/C/D/H/S/X plus COPY d/c/f).
3. **Simple vs extended query paths** including the implicit transaction
   block for multi-stmt simple queries and `ignore_till_sync` for
   extended error recovery.
4. **Portal runner** (`pquery.c`) — `PortalStart` → `PortalRun` →
   strategy dispatch (5 strategies) → `ExecutorStart`/`Run`/`Finish`/`End`.
5. **Utility dispatcher** (`utility.c`) — the two-tier
   `standard_ProcessUtility` (no event triggers) vs `ProcessUtilitySlow`
   (has event triggers) split, with the routing table from `T_*Stmt` to
   `commands/*.c`.
6. **`DestReceiver` abstraction** — receiver factory in `dest.c`, 12
   concrete kinds, the "first-field embedding" trick for subclass casting.
7. **`HandleFunctionRequest`** for the `PQfn()` fastpath.
8. **`CommandTag` registry** generated from `cmdtaglist.h`.
9. **Signal handling** — `quickdie`/`die`/`StatementCancelHandler`/
   `FloatExceptionHandler`/`ProcessInterrupts`.
10. **Memory-context discipline** — `TopMemoryContext` / `PostmasterContext` /
    `MessageContext` (reset every iteration) / `portalContext` /
    `holdContext` (sibling not child for `WITH HOLD`).
11. **23 invariants** tagged INV-tcop-1..23. Load-bearing ones:
    - INV-tcop-1: One backend = one client = one `PostgresMain`; bottom
      of exception stack.
    - INV-tcop-2: `MessageContext` reset every iteration.
    - INV-tcop-3: `BackendInitialize` MUST NOT touch shared memory
      (SIGTERM/timeout model relies on it).
    - INV-tcop-4: `InitProcess` is the first shmem access.
    - INV-tcop-6: Mid-extended-query errors set `ignore_till_sync = true`.
    - INV-tcop-12: Cancel requests handled by `B_DEAD_END_BACKEND`.
    - INV-tcop-17: `standard_ProcessUtility` vs `ProcessUtilitySlow` split.
    - INV-tcop-23: `WITH HOLD` cursor `holdContext` is a SIBLING of
      `TopPortalContext`, not a child.
12. **§11 most-cited file:line table** — 40+ anchors.
13. **§9 Open Questions** — 4 items.

## Verification

All line numbers verified via `grep -n` at `4b0bf0788b0`:
- `postgres.c`: `exec_simple_query:1029`, `exec_parse_message:1406`,
  `exec_bind_message:1640`, `exec_execute_message:2122`,
  `quickdie:2927`, `die:3024`, `StatementCancelHandler:3065`,
  `FloatExceptionHandler:3082`, `ProcessInterrupts:3362`,
  `PostgresMain:4274`.
- `pquery.c`: `ProcessQuery:138`, `ChoosePortalStrategy:206`,
  `PortalStart:430`, `PortalRun:681`, `PortalRunSelect:860`,
  `PortalRunUtility:1118`, `PortalRunMulti:1182`, `PortalRunFetch:1374`.
- `utility.c`: `ClassifyUtilityCommandAsReadOnly:130`,
  `ProcessUtility:504`, `standard_ProcessUtility:548`,
  `ProcessUtilitySlow:1094`, `CreateCommandTag:2385`.

## What I did NOT do

- Did not register new rows in `files-examined.md` — all 7 + 6 already
  in the registry from the original deep-read pass.
- Did not trace the bind+describe wire-format details (O1).
- Did not run any tests.

## Ledger updates

- `progress/coverage.md` — appended `tcop` row.
- `progress/STATE.md` — bumped subsystem count 16→20 (24 incl.
  data-structures), updated Phase + Last-activity, added this session
  log + the three earlier corpus sessions to Recent.

## Day-of context — the 2026-06-02 corpus batch

This is the fourth and final spine synthesis of the interactive day:

1. `parser-and-rewrite.md` — 766 lines, 47 cites (PR #19).
2. `access-nbtree.md` — 892 lines, 60 cites (PR #21).
3. `replication.md` — 979 lines, 70 cites (PR #25).
4. `tcop.md` — 770 lines, 39 cites (this session).

Total: 3407 lines of synthesis, 216 confidence-tagged cites, covering
four of the largest-or-most-fragile PG subsystems. With these four
landed, the spine-synthesis catch-up phase from §5.3 is substantially
complete — the remaining items are either already done (storage-buffer,
access-heap, access-transam, executor, optimizer, storage-lmgr,
storage-ipc, utils-mmgr, utils-cache) or are the long tail (other
access methods, contrib, FDW) marked for on-demand attention.

## Why this matters

tcop is "where the backend meets the world." Concrete confident-but-wrong
claims this synthesis is structured to catch:

- Claiming `PostgresMain` returns (it doesn't — `proc_exit` from below).
- Claiming `MessageContext` survives across messages (it doesn't —
  reset every iteration).
- Touching shared memory in `BackendInitialize` (forbidden by design).
- Skipping `InitProcess` before LWLock access (deadlocks the cluster).
- Forgetting `ignore_till_sync` in extended-query error paths.
- Building a new utility command that needs event triggers but adding
  it to `standard_ProcessUtility` instead of `ProcessUtilitySlow`.
- Caching `FmgrInfo` in fastpath (deliberately rejected).
- Adding a `CommandTag` directly in `cmdtag.c` instead of
  `cmdtaglist.h`.
- Treating `holdContext` as a child of `TopPortalContext` (it's a
  sibling, so commit doesn't drop it).
- Sending `ereport` to the client before `pq_init` (no destination).
- Forgetting `disable_all_timeouts` first in the sigsetjmp landing.
