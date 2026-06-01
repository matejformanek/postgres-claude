# extension.h

- **Source path:** `source/src/include/commands/extension.h`
- **Lines:** 60
- **Last verified commit:** `ef6a95c7c64`

Public surface of CREATE/ALTER/DROP EXTENSION. Exports `Extension_control_path` GUC (PG 18+: search-path for `.control` files). Exports the `creating_extension` global bool plus the `CurrentExtensionObject` OID — these gate `recordDependencyOnCurrentExtension` so all objects created during a CREATE EXTENSION are tagged as extension members. Statement prototypes: `CreateExtension`, `RemoveExtensionById`, `InsertExtensionTuple`, `ExecAlterExtensionStmt`, `ExecAlterExtensionContentsStmt`, `get_extension_oid`/`get_extension_name`, `get_extension_schema`, `binary_upgrade_extension_member`.
