---
path: src/test/modules/injection_points/injection_points.h
anchor_sha: e18b0cb7344
loc: 33
depth: read
---

# src/test/modules/injection_points/injection_points.h

## Purpose

Module-local header for the `injection_points` test module. Defines the
`InjectionPointCondition` struct attached to each named injection point,
encoding whether the point fires unconditionally or is restricted to a
specific PID. Kept out of the core `utils/injection_point.h` header
because the conditioning is a test-module concern, not part of the
generic injection-point API. `[verified-by-code]` `injection_points.h:18-31`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `enum InjectionPointConditionType` | `:18-22` | `INJ_CONDITION_ALWAYS`, `INJ_CONDITION_PID` |
| `struct InjectionPointCondition` | `:24-31` | `type` + `pid` |

## Internal landmarks

Two-field enum and a two-field struct, no functions declared here. The
struct is laid down in the module's DSM/shmem state by `injection_points.c`.

## Cross-refs

- `knowledge/files/src/test/modules/injection_points/injection_points.c.md`
  — the module body that uses these definitions.
- `source/src/include/utils/injection_point.h` — the generic injection-point
  API the module installs callbacks into.
