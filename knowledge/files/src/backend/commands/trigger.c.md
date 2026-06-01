# trigger.c

- **Source path:** `source/src/backend/commands/trigger.c`
- **Lines:** 6906
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"PostgreSQL TRIGGERs support code." [from-comment, trigger.c:3-4] Owns CREATE/ALTER/DROP TRIGGER, partition-inheritance recursion of triggers, the `TriggerDesc`/`TriggerData` runtime structures, the **after-trigger event queue**, deferred-trigger execution at statement/transaction boundaries, transition tables (OLD/NEW per-statement relations), and the FK-internal triggers that implement foreign-key enforcement.

## Public surface (selected)

- `CreateTrigger`, `CreateTriggerFiringOn` — CREATE TRIGGER; recurse to partitions if on a partitioned table.
- `RemoveTriggerById`, `RenameTrigger`, `EnableDisableTrigger`, `EnableDisableTriggerNew` — ALTER mutations.
- `ExecBSInsertTriggers` / `ExecBRInsertTriggers` / `ExecASInsertTriggers` / `ExecARInsertTriggers` / `ExecIRInsertTriggers` (and the parallel UPDATE/DELETE variants) — **the executor's trigger-firing entry points**. BS/BR = Before-Statement / Before-Row, AS/AR = After-Statement / After-Row, IR = INSTEAD OF Row. Called from `nodeModifyTable.c`.
- `AfterTriggerBeginQuery`, `AfterTriggerEndQuery` — bracket each statement so deferred-IMMEDIATE triggers fire at the right time.
- `AfterTriggerBeginXact`, `AfterTriggerFireDeferred`, `AfterTriggerEndXact` — handle DEFERRED triggers that wait until commit (or `SET CONSTRAINTS ALL IMMEDIATE`).
- `MakeTransitionCaptureState`, `AfterTriggerSaveEvent` — capture OLD/NEW relations for transition tables.
- `RI_FKey_*` (in ri_triggers.c, but coordinated from here) — the internal triggers that enforce FK constraints.

## After-trigger event queue [load-bearing]

The "AfterTriggerEvents" data structure is a linked list of "chunks" of event records, each event carrying the TIDs of OLD and NEW tuples. Statements push to it; subtransactions can preserve or discard it on abort. At end-of-statement (for IMMEDIATE-mode triggers) or end-of-transaction (for DEFERRED), the queue is drained and each event fires its associated row-trigger. This is what makes "1 million inserts in a transaction with a deferred FK" use lots of memory — every event is recorded.

## Transition tables (PG 10+)

A trigger declared `REFERENCING OLD TABLE AS o NEW TABLE AS n` gets statement-level transition tables that capture all affected rows. Implemented as tuplestores; the trigger function reads them via SPI as if they were ordinary relations. The capture happens in `AfterTriggerSaveEvent` and the tuplestore is held until the after-statement trigger fires.

## Confidence tag tally

`[verified-by-code]=5 [from-comment]=1`
