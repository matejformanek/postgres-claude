# `src/include/storage/reinit.h`

- **Last verified commit:** `ef6a95c7c64`

## Surface

- `UNLOGGED_RELATION_CLEANUP`, `UNLOGGED_RELATION_INIT` op flags.
- `ResetUnloggedRelations(int op)` — called from startup process.
- `parse_filename_for_nontemp_relation(name, …)` — filename parser
  helper (used both by reinit and other tools).

## Tag tally

`[verified-by-code]` 1.
