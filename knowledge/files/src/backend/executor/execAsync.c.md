# execAsync.c

- **Source:** `source/src/backend/executor/execAsync.c` (155 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (whole file)

## Purpose

Tiny glue module implementing the async-execution mini-protocol described in
the README. Three callbacks bounce between an async-requester (`nodeAppend`)
and an async-capable child (`nodeForeignscan`). [from-README §Asynchronous]

## The protocol

- `ExecAsyncRequest(AsyncRequest *areq)` — leader asks a child for a row.
  If the child has pending param changes, ReScan first. Calls child's
  `ExecAsyncRequest` (currently only ForeignScan; routes to FDW
  `ForeignAsyncRequest`).
- `ExecAsyncRequestPending(areq)` — child sets `areq->callback_pending = true`
  and `areq->request_complete = false`; leader records that no row is ready
  yet and the child has a file descriptor to wait on.
- `ExecAsyncRequestDone(areq, result)` — child sets `areq->request_complete = true`
  and stashes the result (or NULL for EOS); leader picks it up next iteration.
- `ExecAsyncConfigureWait(areq)` — child registers its FD with the leader's
  WaitEventSet (typically by calling FDW `ForeignAsyncConfigureWait`).
- `ExecAsyncNotify(areq)` — leader calls when the FD is ready; child reads
  whatever it can and either completes or stays pending.
- `ExecAsyncResponse(areq)` — generic upcall: routes the completion to the
  requestor's specific response handler (e.g. `ExecAsyncAppendResponse`).

## Used by

Only Append on the leader side, only ForeignScan on the child side, today.
(`ExecAppendAsyncEventWait` in `nodeAppend.c` is the event-loop owner.)

## Tags

- [verified-by-code] all 6 functions in this file.
- [from-README] role and protocol order.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
