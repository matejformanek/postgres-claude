# `executor/nodeSeqscan.h` — sequential scan declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeSeqscan.h`)

## Role
Declares entry points for `SeqScan` — the unqualified table-AM full-scan node. Parallel-aware via a shared block-allocator in DSM. Foundational; every plan tree without an index path leans on this.

## Public API
- Lifecycle — nodeSeqscan.h:20-22: `ExecInitSeqScan` / `ExecEndSeqScan` / `ExecReScanSeqScan`
- Parallel scan — nodeSeqscan.h:25-29: `ExecSeqScanEstimate` / `…InitializeDSM` / `…ReInitializeDSM` / `…InitializeWorker`
- Instrument split — nodeSeqscan.h:32-38: `ExecSeqScanInstrumentEstimate` / `…InstrumentInitDSM` / `…InstrumentInitWorker` / `…RetrieveInstrumentation`

## Cross-refs
- Plan node: `SeqScan` in `nodes/plannodes.h`
- State node: `SeqScanState` in `nodes/execnodes.h`
- Table-AM: `access/tableam.h` (`table_beginscan` / `table_beginscan_parallel`)
- `.c` impl: `source/src/backend/executor/nodeSeqscan.c`
