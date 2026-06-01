# lsyscache.h

- **Source path:** `source/src/include/utils/lsyscache.h`
- **Lines:** 227
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `lsyscache.c` (impl), `syscache.h` (underlying mechanism).

## Purpose

Public-surface declarations for the ~130 convenience accessors that wrap `SearchSysCache*` lookups. Also declares a small number of result-type structs and helper enums.

## Top-of-file comment

> "Convenience routines for common queries in the system catalog cache." [lsyscache.h:3-4]

## Public surface (key non-function declarations)

- **`OpIndexInterpretation`** (25) — `{opfamily_id; cmptype; oplefttype; oprighttype}`; result element for `get_op_index_interpretation`.
- **`IOFuncSelector`** (34) — `{IOFunc_input, IOFunc_output, IOFunc_receive, IOFunc_send}` for `get_type_io_data`.
- **`ATTSTATSSLOT_VALUES`/`ATTSTATSSLOT_NUMBERS`** (43-44) — bit flags for `get_attstatsslot`.
- **`AttStatsSlot`** (47) — result struct for `get_attstatsslot` carrying both the public fields (staop, stacoll, valuetype, values[], numbers[]) and a private free-list region used by `free_attstatsslot`.
- **`get_attavgwidth_hook_type`** — extension hook (used by file 57).
- **131 `get_*` / `op_*` / `type_*` / etc. functions** — see lsyscache.c.md for the categorical breakdown.

## Key invariants

- All declared functions are **read-only over syscache**. No state on this header.
- `AttStatsSlot` has a "private to free_attstatsslot" tail region; callers must always pair `get_attstatsslot` with `free_attstatsslot` to release pg_statistic's array memory. [from-comment, lsyscache.h:60]

## Confidence tag tally

verified-by-code: 1 — from-comment: 2 — from-readme: 0 — inferred: 0 — unverified: 0
