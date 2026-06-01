# proclang.h

- **Source path:** `source/src/include/commands/proclang.h`
- **Lines:** 23
- **Last verified commit:** `ef6a95c7c64`

Prototypes: `CreateProceduralLanguage` (CREATE LANGUAGE), `get_language_oid` (lookup helper). The actual file `proclang.c` is small — most language registration goes through pg_pltemplate (deprecated) or extension scripts.
