# dest.h

- **Source:** `source/src/include/tcop/dest.h` (150 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (entire file)

## What's here

The `DestReceiver` contract: every output destination implements
`receiveSlot`, `rStartup`, `rShutdown`, `rDestroy` + a `mydest` tag.
[from-comment `dest.h:30-58`]

## `CommandDest` enum (`:85-100`)

- `DestNone` — discard.
- `DestDebug` — printf to stdout (single-user mode).
- `DestRemote` / `DestRemoteExecute` / `DestRemoteSimple` — wire protocol
  (the last is used where catalog access isn't possible).
- `DestSPI` — SPI manager (function calls).
- `DestTuplestore` / `DestIntoRel` / `DestCopyOut` / `DestSQLFunction` /
  `DestTransientRel` / `DestTupleQueue` / `DestExplainSerialize`.

## `_DestReceiver` struct (`:115-130`)

```c
struct _DestReceiver {
    bool (*receiveSlot)(TupleTableSlot *slot, DestReceiver *self);
    void (*rStartup)(DestReceiver *self, int operation, TupleDesc typeinfo);
    void (*rShutdown)(DestReceiver *self);
    void (*rDestroy)(DestReceiver *self);
    CommandDest mydest;
    /* private fields beyond this point */
};
```

`receiveSlot` returns false to mean "stop early as if EOF" — used by
`LIMIT`-style early termination and tuple-queue full conditions.

## Public API

`BeginCommand`, `CreateDestReceiver`, `EndCommand`, `EndCommandExtended`,
`EndReplicationCommand`, `NullCommand`, `ReadyForQuery`.

`None_Receiver` — globally available singleton for `DestNone`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/tcop.md](../../../../subsystems/tcop.md)
