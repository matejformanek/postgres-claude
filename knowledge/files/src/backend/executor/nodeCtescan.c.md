# nodeCtescan.c

- **Source:** `source/src/backend/executor/nodeCtescan.c` (≈300 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Reads from a **non-recursive WITH** CTE. The CTE's subplan is owned by the
EState (in `es_subplanstates`), executed lazily; each CteScan owns a
Tuplestorestate position (read pointer) that advances independently of
sibling CteScans of the same CTE.

## Mechanics

`CteScanNext`:
- Looks up the shared tuplestore via the CTE's `cteplaninfo` (held in
  the leader CteScan, identified by `ctePlanId`).
- If our read pointer hasn't reached EOF of the store, fetch next.
- Else: pull a row from the CTE's subplan, push into the shared store,
  return it via our read pointer.

## Multiple readers

Multiple CteScans of the same WITH clause read from the same materialized
tuplestore at different positions; one "leader" CteScan owns the population
side and pulls from the subplan, others reuse those rows.

## Tags

- [verified-by-code] shared-tuplestore mechanism.
- [from-comment] CteScanNext docstring.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
