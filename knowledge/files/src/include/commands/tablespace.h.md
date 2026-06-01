# tablespace.h

- **Source path:** `source/src/include/commands/tablespace.h`
- **Lines:** 71
- **Last verified commit:** `ef6a95c7c64`

Exports `default_tablespace` and `temp_tablespaces` GUCs and `allow_in_place_tablespaces` (dev). Defines the WAL types `XLOG_TBLSPC_CREATE` / `XLOG_TBLSPC_DROP` and the record struct `xl_tblspc_create_rec`. Prototypes the SQL statements (`CreateTableSpace`, `DropTableSpace`, `RenameTableSpace`, `AlterTableSpaceOptions`), the redo function `tblspc_redo`, and runtime helpers (`PrepareTempTablespaces`, `GetDefaultTablespace`, `GetTablespacePageCosts`, `get_tablespace_oid`, `get_tablespace_name`, `directory_is_empty`).
