# publicationcmds.h

- **Source path:** `source/src/include/commands/publicationcmds.h`
- **Lines:** 43
- **Last verified commit:** `ef6a95c7c64`

Defines `MAX_RELCACHE_INVAL_MSGS = 4096` — the cap before ALTER PUBLICATION falls back to a catalog-wide invalidation. Prototypes: `CreatePublication`, `AlterPublication`, `RemovePublicationById`, `RemovePublicationRelById`, `RemovePublicationSchemaById`.
