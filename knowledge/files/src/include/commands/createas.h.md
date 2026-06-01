# createas.h

- **Source path:** `source/src/include/commands/createas.h`
- **Lines:** 34
- **Last verified commit:** `ef6a95c7c64`

Prototypes for `commands/createas.c` (CREATE TABLE AS, CREATE MATERIALIZED VIEW, SELECT INTO): `ExecCreateTableAs`, `GetIntoRelEFlags`, `CreateIntoRelDestReceiver` (the custom DestReceiver that materialises executor output into the new relation).
