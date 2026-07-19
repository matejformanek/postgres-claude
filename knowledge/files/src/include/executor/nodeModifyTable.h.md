# nodeModifyTable.h

- **Source:** `source/src/include/executor/nodeModifyTable.h` (~35 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## API

- `ExecInitModifyTable / ExecEndModifyTable / ExecReScanModifyTable`.
- `ExecInitGenerated(resultRelInfo, estate, cmdtype)` — set up
  generated-column projection (`GENERATED ALWAYS AS …`) per relation.
- `ExecComputeStoredGenerated(resultRelInfo, estate, slot, cmdtype)` —
  compute generated columns and store back into `slot`. Called for INSERT
  and the post-image of UPDATE.
- `ExecInitMergeTupleSlots(mtstate, resultRelInfo)` — allocate the
  pre-image + post-image slots used by MERGE WHEN MATCHED expressions.

## Notable absences

No parallel hooks — DML is not parallel-aware (writes happen leader-side
only; the input plan beneath ModifyTable can still be parallel via Gather).

## Tags

- [verified-by-code] full surface.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
