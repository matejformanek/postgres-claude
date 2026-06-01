# `src/backend/utils/misc/guc_funcs.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~1030
- **Source:** `source/src/backend/utils/misc/guc_funcs.c`

## Purpose

SQL surface for GUCs: `SET`/`SET LOCAL`/`SET SESSION`, `RESET`, `SHOW`,
`current_setting()`, `set_config()`, plus the SRFs that back
`pg_settings`, `pg_settings_get_flags`, `pg_show_all_settings`,
`pg_show_all_file_settings`, `pg_file_settings`. Wraps the lower-level
`set_config_option_ext` / `find_option` from `guc.c`. [from-comment]
(`guc_funcs.c:1-4`)

## Notable

- `ExecSetVariableStmt` is the dispatcher for `VariableSetStmt`
  (`SET ... TO ...` / `SET TIME ZONE ...` / `RESET ...`).
- `SetPGVariable` is the C-level setter used by `ExecSetVariableStmt`
  and other utility commands; calls `set_config_option` with the right
  source/context.
- `GetPGVariable` / `GetPGVariableResultDesc` back `SHOW`.
- `set_config` SQL function (3-arg: name, value, is_local) lets the
  user toggle SET LOCAL semantics from inside an expression — used by
  `pg_dump` to set isolation per-transaction.

## Tag tally

`[from-comment]` 2
