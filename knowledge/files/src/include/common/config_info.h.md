---
path: src/include/common/config_info.h
anchor_sha: 4b0bf0788b0
loc: 21
depth: skim
---

# config_info.h

- **Source path:** `source/src/include/common/config_info.h`
- **Lines:** 21
- **Last verified commit:** `4b0bf0788b0`
- **Companion file:** `common/config_info.c`.

## Purpose

Tiny key/value struct (`ConfigData{name,setting}`) and the single function `get_configdata(my_exec_path, *configdata_len)` used by the `pg_config` CLI to produce its `name = value` lines from build-time `VAL_*` constants and runtime path resolution. [from-comment, config_info.h:1-19]

## Public surface

- `typedef struct ConfigData { char *name; char *setting; }`. [verified-by-code, config_info.h:12-16]
- `get_configdata(my_exec_path, *configdata_len)` — returns palloc'd array of 23 entries. [verified-by-code, config_info.h:18-19]

## Phase D notes

- Pure introspection / read-only. Not a trust boundary.

## Confidence tag tally
`[from-comment]=1 [verified-by-code]=2`
