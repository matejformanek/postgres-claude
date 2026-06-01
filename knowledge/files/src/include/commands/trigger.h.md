# trigger.h

- **Source path:** `source/src/include/commands/trigger.h`
- **Lines:** 313
- **Last verified commit:** `ef6a95c7c64`

Public surface of trigger.c. Defines `TriggerData` (the fmgr context for trigger functions: event, relation, OLD/NEW tuples, trigger object, transition tables) and `CALLED_AS_TRIGGER` macro. Declares the constant `TRIGGER_EVENT_*` bit flags and the executor-side firing entries: `ExecBSInsertTriggers`/`ExecBRInsertTriggers`/`ExecASInsertTriggers`/`ExecARInsertTriggers`/`ExecIRInsertTriggers` plus the UPDATE/DELETE/TRUNCATE/SELECT variants. Statement entries `CreateTrigger`/`CreateTriggerFiringOn`/`RemoveTriggerById`/`RenameTrigger`/`EnableDisableTrigger`. The xact lifecycle hooks `AfterTrigger*` plus `MakeTransitionCaptureState` for transition-table capture.
