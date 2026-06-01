# sequence.h

- **Source path:** `source/src/include/commands/sequence.h`
- **Lines:** 53
- **Last verified commit:** `ef6a95c7c64`

Defines the on-disk tuple layout `FormData_pg_sequence_data` (`last_value`, `log_cnt`, `is_called`) — every sequence relation has exactly one tuple of this form. Prototypes the SQL-callable functions (`nextval`, `currval`, `lastval`, `setval`, `setval3`) and the catalog-mutation helpers (`DefineSequence`, `AlterSequence`, `SequenceGetTuple`, `ResetSequence`, `ResetSequenceCaches`).
