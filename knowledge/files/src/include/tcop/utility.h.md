# utility.h

- **Source:** `source/src/include/tcop/utility.h`
- **Depth:** skim

## Symbols

- `ProcessUtilityContext` enum: `PROCESS_UTILITY_TOPLEVEL`,
  `_QUERY`, `_QUERY_NONATOMIC`, `_SUBCOMMAND`.
- `ProcessUtility_hook` (extension hook).
- `ProcessUtility`, `standard_ProcessUtility`.
- `CommandIsReadOnly`, `ClassifyUtilityCommandAsReadOnly`,
  `PreventCommandIfReadOnly`, `PreventCommandIfParallelMode`,
  `PreventCommandDuringRecovery`, `CheckRestrictedOperation`.
- `UtilityReturnsTuples`, `UtilityTupleDescriptor`, `QueryReturnsTuples`,
  `UtilityContainsQuery`.
- `CreateCommandTag`, `AlterObjectTypeCommandTag`, `GetCommandLogLevel`.
- `AlterTableUtilityContext` (for `ProcessUtilityForAlterTable`).
- Bitmask values: `COMMAND_OK_IN_READ_ONLY_TXN`,
  `COMMAND_OK_IN_PARALLEL_MODE`, `COMMAND_OK_IN_RECOVERY`,
  `COMMAND_IS_STRICTLY_READ_ONLY`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/tcop.md](../../../../subsystems/tcop.md)
- [idioms/process-utility-hook-chain.md](../../../../idioms/process-utility-hook-chain.md)

