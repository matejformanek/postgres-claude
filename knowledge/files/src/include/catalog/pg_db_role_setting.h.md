# pg_db_role_setting.h

- **Source path:** `source/src/include/catalog/pg_db_role_setting.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "database/role setting" system catalog (`pg_db_role_setting`) — per-(database, role) GUC overrides applied at login. Stores `ALTER DATABASE ... SET`, `ALTER ROLE ... SET`, and `ALTER ROLE ... IN DATABASE ... SET` rows; either key column may be 0 to mean "applies regardless". [from-comment]

## Catalog definition

- `CATALOG(pg_db_role_setting, 2964, DbRoleSettingRelationId) BKI_SHARED_RELATION` — lives in `global/`. [verified-by-code]
- `FormData_pg_db_role_setting` typedef; pointer alias `Form_pg_db_role_setting`. [verified-by-code]
- `DECLARE_TOAST_WITH_MACRO(pg_db_role_setting, 2966, 2967, PgDbRoleSettingToastTable, PgDbRoleSettingToastIndex)`. [verified-by-code]
- `DECLARE_UNIQUE_INDEX_PKEY(pg_db_role_setting_databaseid_rol_index, 2965, ...)` over `(setdatabase, setrole)`. [verified-by-code]
- No syscache (`MAKE_SYSCACHE`) declared in this header — settings are loaded by direct relation scan at login time. [verified-by-code]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| setdatabase | Oid | BKI_LOOKUP_OPT (0 means role-specific) | pg_database |
| setrole | Oid | BKI_LOOKUP_OPT (0 means database-specific) | pg_authid |
| setconfig | text[] | (varlena, nullable) | — (each element is `name=value`) |

## Key declarations beyond FormData

- `extern void AlterSetting(Oid databaseid, Oid roleid, VariableSetStmt *setstmt)` — handles ALTER ... SET / RESET. [verified-by-code]
- `extern void DropSetting(Oid databaseid, Oid roleid)`. [verified-by-code]
- `extern void ApplySetting(Snapshot snapshot, Oid databaseid, Oid roleid, Relation relsetting, GucSource source)` — called during InitPostgres to apply the matching row's GUCs. [verified-by-code]
- Header pulls in `utils/guc.h`, `utils/relcache.h`, `utils/snapshot.h` for those prototypes — unusual for a catalog header. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related backend: `source/src/backend/catalog/pg_db_role_setting.c`, `source/src/backend/utils/init/postinit.c` (where ApplySetting is called).

## Tally

`[verified-by-code]=11 [from-comment]=1`
