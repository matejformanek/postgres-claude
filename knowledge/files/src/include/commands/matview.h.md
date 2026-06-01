# matview.h

- **Source path:** `source/src/include/commands/matview.h`
- **Lines:** 36
- **Last verified commit:** `ef6a95c7c64`

Prototypes: `SetMatViewPopulatedState`, `ExecRefreshMatView`, `RefreshMatViewByOid`. The Oid-keyed variant is used internally (CREATE MATERIALIZED VIEW WITH DATA invokes it after building the relation).
