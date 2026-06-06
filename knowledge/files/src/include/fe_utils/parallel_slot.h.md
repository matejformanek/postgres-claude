---
path: src/include/fe_utils/parallel_slot.h
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 84
depth: read
---

# `src/include/fe_utils/parallel_slot.h`

- **File:** `source/src/include/fe_utils/parallel_slot.h` (84 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-05)

## Purpose

API for the parallel-connection-slot pool used by `bin/scripts/` tools (reindexdb, vacuumdb)
to run many commands concurrently across a fixed set of libpq connections. Declares the
`ParallelSlot` (one connection + in-use flag + result handler), the `ParallelSlotArray`
(flexible-array pool with shared `ConnParams`), three trivial inline state mutators, and the
pool lifecycle/dispatch functions. Implementation in
[[knowledge/files/src/fe_utils/parallel_slot.c]]. `[from-comment]` (:1-10)

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `ParallelSlotResultHandler` | :18 | Callback type: process one `PGresult`; returns success. |
| `ParallelSlot` | :21 | One pooled connection + `inUse` + handler + handler_context. |
| `ParallelSlotArray` | :36 | The pool: numslots + `ConnParams *cparams` + echo + initcmd + `slots[FLEXIBLE_ARRAY_MEMBER]`. |
| `ParallelSlotSetHandler` | :46 | Inline: attach handler + context to a slot. |
| `ParallelSlotClearHandler` | :54 | Inline: NULL out handler + context. |
| `ParallelSlotSetIdle` | :61 | Inline: mark not-in-use + clear handler. |
| `ParallelSlotsGetIdle` | :68 | Block until a slot is free for `dbname`; returns it. |
| `ParallelSlotsSetup` | :71 | Allocate + initialize the pool. |
| `ParallelSlotsAdoptConn` | :75 | Hand an already-open conn to the pool. |
| `ParallelSlotsTerminate` | :77 | Close all connections + free the pool. |
| `ParallelSlotsWaitCompletion` | :79 | Drain all in-flight commands; returns overall success. |
| `TableCommandResultHandler` | :81 | A ready-made handler that expects `PGRES_TUPLES_OK`/`COMMAND_OK`. |

## Internal landmarks

- The pool is a single `ParallelSlotArray` allocation with `slots[]` as a trailing
  flexible-array member (`:43`); all slots share one `ConnParams *cparams`, `progname`, `echo`,
  and `initcmd` so new connections are opened identically. `[verified-by-code]`
- The result-handler indirection (`:26-33`) lets a caller register per-command result
  processing + context before issuing a query; `ParallelSlotsWaitCompletion` invokes the
  registered handler as each result arrives. `[from-comment]` (:26-31)

## Invariants & gotchas

- **Handler result-ownership contract.** A `ParallelSlotResultHandler` that returns NULL/false
  is responsible for freeing its own `PGresult` — that contract lives only in the
  `parallel_slot.c` comment, not in this header's signature; a non-conforming handler leaks
  every failed result. Tracked in `knowledge/issues/fe_utils.md` row `parallel_slot.c:43`. `[verified-by-code]`
- `ParallelSlotSetIdle` both clears `inUse` and the handler (`:61-66`) — slots are reused, so a
  stale handler from a prior command would otherwise fire against the next one. `[verified-by-code]`

## Cross-refs

- Implementation + the connect-then-initcmd ordering note:
  [[knowledge/files/src/fe_utils/parallel_slot.c]] (register rows `parallel_slot.c:333`, `:43`).
- Connection params struct: [[knowledge/files/src/include/fe_utils/connect_utils.h]].

## Potential issues

None new at the header level — the handler result-ownership contract and the connect-ordering
nuance are tracked against `parallel_slot.c` in `knowledge/issues/fe_utils.md`. Cross-linked.
