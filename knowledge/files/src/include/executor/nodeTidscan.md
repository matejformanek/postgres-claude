# `executor/nodeTidscan.h` — TID point-list scan declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeTidscan.h`)

## Role
Declares entry points for `TidScan` — fetches a specific list of `ctid` values directly (e.g. `WHERE ctid = '(0,1)' OR ctid = ANY(...)`). Not parallel-aware.

## Public API
- `ExecInitTidScan(TidScan *, EState *, int eflags)` — nodeTidscan.h:19
- `ExecEndTidScan(TidScanState *)` — nodeTidscan.h:20
- `ExecReScanTidScan(TidScanState *)` — nodeTidscan.h:21

## Cross-refs
- Plan node: `TidScan` in `nodes/plannodes.h`
- State node: `TidScanState` in `nodes/execnodes.h`
- Sibling (range): `executor/nodeTidrangescan.h`
- `.c` impl: `source/src/backend/executor/nodeTidscan.c`
