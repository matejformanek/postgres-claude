# src/test/modules/injection_points/injection_points.h

**Pin:** `b78cd2bda5b1a306e2877059011933de1d0fb735`
**LOC:** 33
**Verification depth:** full read

## Role

Private header for the `injection_points` test module. It defines the small condition-typing vocabulary that lets an attached injection point be gated at runtime — currently "always run" vs "run only in a specific PID". The struct it declares (`InjectionPointCondition`) is what `injection_points.c` stores as the private data attached to a point and re-reads in each callback. [verified-by-code] `source/src/test/modules/injection_points/injection_points.h:3` (header comment), `:24` (struct).

## Public API

- `InjectionPointConditionType` — enum: `INJ_CONDITION_ALWAYS = 0` (always run), `INJ_CONDITION_PID` (restrict to a PID). [verified-by-code] `source/src/test/modules/injection_points/injection_points.h:18`
- `InjectionPointCondition` — struct holding a `type` and an `int pid` (the process where the point may run). [verified-by-code] `source/src/test/modules/injection_points/injection_points.h:24`

## Invariants

- INV-1: `INJ_CONDITION_ALWAYS` is explicitly `0`, so a zero-initialized `InjectionPointCondition` (`{0}`) means "always run with no PID restriction". `injection_points.c` relies on this: `injection_points_attach` declares `InjectionPointCondition condition = {0}` and only sets the PID branch when in local mode. [verified-by-code] `source/src/test/modules/injection_points/injection_points.h:20`, `source/src/test/modules/injection_points/injection_points.c:299`
- INV-2: The header is purely a data contract — no functions, just the include guard `INJECTION_POINTS_H`. Any new condition type must extend both this enum and the `switch` in `injection_point_allowed()`. [verified-by-code] `source/src/test/modules/injection_points/injection_points.h:15`, `source/src/test/modules/injection_points/injection_points.c:157`

## Notable internals

- `pid` is a plain `int`, matching `MyProcPid`'s type used for the comparison in `injection_point_allowed`. [verified-by-code] `source/src/test/modules/injection_points/injection_points.h:30`, `source/src/test/modules/injection_points/injection_points.c:160`

## Cross-refs

- `injection_points.c` (same dir) — sole consumer; stores this struct as private data and switches on `type` in `injection_point_allowed`.

## Potential issues

None.
