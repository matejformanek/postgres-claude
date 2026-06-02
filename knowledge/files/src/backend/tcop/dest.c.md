# dest.c

- **Source:** `source/src/backend/tcop/dest.c` (298 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (entire file)

## Purpose

The plumbing that connects executor output to wherever the rows need to
go: client (`DestRemote*`), SPI, tuplestore, SELECT INTO, COPY TO, SQL
function returns, tuple queue (parallel workers), explain-serialize.
[from-comment] `:3-27`

## The `DestReceiver` abstraction

`include/tcop/dest.h:115-130` — every receiver is a struct with
`receiveSlot(slot, self)`, `rStartup(self, op, typeinfo)`, `rShutdown(self)`,
`rDestroy(self)`, and a `mydest` tag. Concrete receivers embed `DestReceiver`
as the first field so casting from `DestReceiver*` yields the subclass
state. [from-comment `dest.h:38-53`]

## Static (stateless) receivers in this file

- `donothingDR` (`:70-73`) — used for `DestNone`. `None_Receiver` is the
  globally accessible singleton (`:91-96`).
- `debugtupDR` — `DestDebug`, used by single-user mode.
- `printsimpleDR` — `DestRemoteSimple`, minimal protocol (no catalog access).
- `spi_printtupDR` — `DestSPI`.

## `CreateDestReceiver(CommandDest)` (`:112-162`)

Switch that returns the right (static or freshly palloc'd) receiver for the
destination. Receivers needing config (e.g. `DestIntoRel`,
`DestCopyOut`, `DestTupleQueue`) are returned with sensible defaults and
caller patches in extra params via direct setter calls (e.g.
`SetTuplestoreDestReceiverParams`).

## Other top-level functions

| Symbol | Role |
|---|---|
| `BeginCommand` (`:102`) | currently a no-op; legacy hook spot |
| `EndCommand` / `EndCommandExtended` (`:204`, `:169`) | format CommandComplete tag (e.g. `"INSERT 0 5"`) and send |
| `EndReplicationCommand` (`:216`) | stripped-down replication-cmd version |
| `NullCommand` (`:229`) | send `EmptyQueryResponse` |
| `ReadyForQuery` (`:267`) | send `'Z'` with `TransactionBlockStatusCode()` and `pq_flush()` |

## Where the concrete receivers live

- `access/common/printtup.c` — text/binary V3 protocol for `DestRemote{,Execute}`.
- `access/common/printsimple.c` — `DestRemoteSimple`.
- `executor/spi.c` — `DestSPI` callers via `spi_printtup`.
- `executor/tstoreReceiver.c` — `DestTuplestore`.
- `executor/tqueue.c` — `DestTupleQueue` (parallel workers).
- `commands/createas.c` — `DestIntoRel`.
- `commands/matview.c` — `DestTransientRel`.
- `commands/copy*.c` — `DestCopyOut`.
- `executor/functions.c` — `DestSQLFunction`.
- `commands/explain_dr.c` — `DestExplainSerialize`.

## Header

`include/tcop/dest.h` — see the long top comment for the receiver contract,
especially the rule that `receiveSlot` must be called with the same TupleDesc
that was given to `rStartup`. [from-comment `dest.h:107-111`]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [subsystems/tcop.md](../../../../subsystems/tcop.md)
