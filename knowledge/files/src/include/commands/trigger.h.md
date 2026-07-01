# trigger.h

- **Source path:** `source/src/include/commands/trigger.h`
- **Lines:** 315
- **Last verified commit:** `b7e4e3e7fa73`

Public surface of trigger.c. Defines `TriggerData` (the fmgr context for trigger functions: event, relation, OLD/NEW tuples, trigger object, transition tables) and `CALLED_AS_TRIGGER` macro. Declares the constant `TRIGGER_EVENT_*` bit flags and the executor-side firing entries: `ExecBSInsertTriggers`/`ExecBRInsertTriggers`/`ExecASInsertTriggers`/`ExecARInsertTriggers`/`ExecIRInsertTriggers` plus the UPDATE/DELETE/TRUNCATE/SELECT variants. Statement entries `CreateTrigger`/`CreateTriggerFiringOn`/`RemoveTriggerById`/`RenameTrigger`/`EnableDisableTrigger`. The xact lifecycle hooks `AfterTrigger*` plus `MakeTransitionCaptureState` for transition-table capture.

As of 6f4bac854fb7 (2026-06-29) the header also exposes the RI fast-path
batch surface used to hardwire end-of-xact FK cleanup into `xact.c`:
the `AfterTriggerBatchCallback` typedef, `RegisterAfterTriggerBatchCallback`
(`:309`), `AfterTriggerIsActive` (`:311`), and `AtEOXact_RI(bool isCommit)`
(`:313`). `ri_triggers.c` registers a batch callback to flush fast-path FK
batches; `xact.c` calls `AtEOXact_RI` at commit/abort.

## Synthesized by
<!-- backlinks:auto -->
- [idioms/trigger-constraint-deferral.md](../../../../idioms/trigger-constraint-deferral.md)
- [idioms/trigger-firing-order.md](../../../../idioms/trigger-firing-order.md)
- [idioms/trigger-transition-tables.md](../../../../idioms/trigger-transition-tables.md)
