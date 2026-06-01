# `src/backend/utils/misc/guc_tables.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~810
- **Source:** `source/src/backend/utils/misc/guc_tables.c`

## Purpose

The registry of every built-in GUC: `ConfigureNamesBool[]`,
`ConfigureNamesInt[]`, `ConfigureNamesReal[]`, `ConfigureNamesString[]`,
`ConfigureNamesEnum[]`. Each row holds boot value, min/max, flags, group,
short/long descriptions, and the check/assign/show hook function pointers.
Most rows are auto-generated from `guc_parameters.dat` via
`gen_guc_tables.pl`; this file holds the static prologue + the enum value
arrays (`server_message_level_options[]`, `log_destination_options[]`, …)
plus `config_group_names[]`. [from-comment] (`guc_tables.c:1-10`)

## Notable

- `ConfigureNames*` rows are **mutable** — guc.c stores the live current
  value, source, scontext, srole right in the struct. The "const-looking"
  fields like `boot_val` and `min`/`max` actually are constant.
  (`guc_tables.c:7-10`)
- Group enum + `config_group_names[]` drives `--config-group` filtering
  and the SGML documentation generator.

## Tag tally

`[from-comment]` 2
