# src/include/commands/repack.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 68 [verified-by-code]

## Role

PG18 REPACK command — successor to CLUSTER, supports CONCURRENT mode
that performs logical decoding of changes during table-rewrite (echoes
contrib `pg_repack`). Header keeps the legacy `cluster_rel` /
`finish_heap_swap` exports because CLUSTER shares the code path.

## Public API

- Flag bits `CLUOPT_*` for `ClusterParams.options` (`:25-30`): VERBOSE,
  RECHECK, RECHECK_ISCLUSTERED, ANALYZE, **CONCURRENT** (the new bit).
- `ClusterParams` — bitmask wrapper (`:33-36`).
- `RepackMessagePending` — `sig_atomic_t` flag for inter-process
  message handling between the REPACK driver and its decoding worker
  (`:38`).
- `ExecRepack(ParseState, RepackStmt, isTopLevel)` — utility entry
  point (`:41`).
- `cluster_rel(RepackCommand, Relation, Oid indexOid, ClusterParams*,
  isTopLevel)` — legacy CLUSTER core, still used (`:43-44`).
- `check_index_is_clusterable`, `mark_index_clustered` — helpers (`:45-47`).
- `make_new_heap(OIDOldHeap, NewTableSpace, NewAccessMethod,
  relpersistence, lockmode) -> Oid` (`:49-50`).
- `finish_heap_swap(...)` — swap old / new relfilenode with TOAST,
  index, frozenXid considerations (`:51-59`).
- Interrupt handlers: `HandleRepackMessageInterrupt`,
  `ProcessRepackMessages` (`:61-62`).
- Worker: `RepackWorkerMain(Datum)`, `AmRepackWorker(void)` (`:65-66`).

## Invariants

- INV-REPACK-CONCURRENT: CLUOPT_CONCURRENT requires the table have a
  replica identity (or PK) AND `wal_level >= logical` AND a logical
  replication slot for the duration. Without those, REPACK silently
  falls back to non-concurrent mode — or errors (verify in
  `repack.c`).
- `finish_heap_swap` mutates `pg_class.relfilenode`, `relfrozenxid`,
  `relminmxid` of the old relation. All concurrent readers must be on
  the OLD relfilenode at this point — guaranteed by AccessExclusive
  lock (CLUSTER) or by the catch-up phase (REPACK CONCURRENT).
- `make_new_heap` creates the new table in `NewTableSpace` (0 = same
  as old) with `NewAccessMethod` (0 = same). Required to drop and
  re-create indexes from `IndexInfo` afterward — handled by core.

## Notable internals

- `RepackMessagePending` is checked from interrupt context; can NOT
  call palloc / ereport / etc. directly. Pattern follows the
  procsignal infrastructure.
- `AmRepackWorker()` lets shared code (the decoding output plugin)
  distinguish REPACK's bgworker from a normal logical-replication
  apply worker.

## Trust boundary / Phase D surface

- **A8 logical-replication echo / NEW attack surface.** REPACK
  CONCURRENT uses a **transient replication slot** internally; the
  slot is created with the REPACK invoker's role. A non-superuser
  with `pg_create_logical_replication_slot` (PG18 reserved role?) +
  REPACK on a table they OWN may be able to retain WAL longer than
  intended if REPACK fails mid-flight.
- **`make_new_heap` access-method swap (`NewAccessMethod`).** Allows
  switching table AMs as a side-effect of REPACK; an attacker who can
  REPACK a victim's table (via inheritance? via partitioning?) into a
  custom AM they control could inject AM callbacks. Mitigated by
  `must own table` check at SQL level, but the C signature does NOT
  enforce it.
- **A14 pg_repack contrib parallel.** Contrib `pg_repack` had multiple
  CVEs (CVE-2018-1058 style search_path injection, race during swap);
  in-tree REPACK avoids contrib's `pg_repack.schema` indirection but
  inherits the same conceptual swap-window risk.
- `RepackWorkerMain` runs as a bgworker — runs under `BackgroundWorker`
  privilege escalation rules from `gucs-bgworker-parallel`.

## Cross-references

- `commands/repack_internal.h` — `RepackDecodingState`,
  `DecodingWorkerShared` for the logical-decoding worker.
- `commands/progress.h` — `PROGRESS_REPACK_*` slot constants.
- `nodes/parsenodes.h` — `RepackStmt`, `RepackCommand` enum.
- `replication/logical.h` — slot management used in CONCURRENT mode.
- `access/tableam.h` — for the AM-swap path.

## Issues / drift

- `[ISSUE-TRUST: NewAccessMethod arg to make_new_heap is unchecked at C level — caller must enforce "owner can pick AM"; not commented in header (medium)] — source/src/include/commands/repack.h:49-50`
- `[ISSUE-TRUST: CONCURRENT-mode slot lifecycle on REPACK failure not documented; potential WAL retention DoS (medium)] — source/src/include/commands/repack.h:41`
- `[ISSUE-DOC: header doesn't say whether CLUOPT_CONCURRENT requires wal_level=logical; reader must dig into source (low)] — source/src/include/commands/repack.h:30`
