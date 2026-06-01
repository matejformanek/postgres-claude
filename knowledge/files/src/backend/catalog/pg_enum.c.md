# pg_enum.c

- **Source path:** `source/src/backend/catalog/pg_enum.c`
- **Lines:** ~920
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines to support manipulation of the pg_enum relation." CREATE TYPE AS ENUM and ALTER TYPE ... ADD VALUE backend. Handles the **uncommitted-enum-value** trick (a hash of in-flight enum OIDs so that the same xact can use a value it just added even before commit — usually enum changes are disallowed inside a multi-statement xact, but the same-statement read is fine).

## Public surface

- `EnumValuesCreate` (84) — bulk-insert all labels for a fresh enum type. Each label gets a fresh OID; `enumsortorder` is integer-spaced (1.0, 2.0, …) to leave room for ADD VALUE BEFORE/AFTER inserts.
- `EnumValuesDelete` (237) — drop all values when the type is dropped.
- `AddEnumLabel` (305) — ALTER TYPE ... ADD VALUE; handles BEFORE/AFTER position. If sort-order space runs out, calls `RenumberEnumType` to redistribute.
- `RenameEnumLabel` (620) — ALTER TYPE ... RENAME VALUE.
- `EnumTypeUncommitted` (703), `EnumUncommitted` (721), `AtEOXact_Enum` (739) — uncommitted-enum tracking. At xact end, the in-memory hash is flushed.
- `RenumberEnumType` (774), `sort_order_cmp` (810) — float-space recompaction.
- `EstimateUncommittedEnumsSpace` (826), `SerializeUncommittedEnums` (840), `RestoreUncommittedEnums` (886) — share the uncommitted-enums state with parallel workers.

## Confidence tag tally

`[verified-by-code]=4`
