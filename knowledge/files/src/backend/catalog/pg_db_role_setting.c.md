# pg_db_role_setting.c

- **Source path:** `source/src/backend/catalog/pg_db_role_setting.c`
- **Lines:** ~250
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines to support manipulation of the pg_db_role_setting relation." Stores per-(database, role) GUC overrides: `ALTER ROLE x SET ...`, `ALTER DATABASE d SET ...`, `ALTER ROLE x IN DATABASE d SET ...`. Applied at session start by `process_settings`.

## Public surface

- `AlterSetting` — universal update: insert or update the pg_db_role_setting row's setconfig array (a text[] of "key=value" strings).
- `DropSetting` — remove all rows mentioning a dropped role or database.
- `ApplySetting` — at session start, walk the matching rows and call `SetConfigOption` per item.

## Confidence tag tally

`[inferred]=3`
