# extension.c

- **Source path:** `source/src/backend/commands/extension.c`
- **Lines:** 4123
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Commands to manipulate extensions." [from-comment, extension.c:3-4] CREATE/DROP/ALTER EXTENSION machinery. The file's own comment is the canonical explanation:

> "Extensions in PostgreSQL allow management of collections of SQL objects. All we need internally to manage an extension is an OID so that the dependent objects can be associated with it. An extension is created by populating the pg_extension catalog from a 'control' file. **The extension control file is parsed with the same parser we use for postgresql.conf.** An extension also has an installation script file, containing SQL commands to create the extension's objects." [from-comment, extension.c:6-13]

## Public surface

- `CreateExtension` — CREATE EXTENSION. Locates `$SHAREDIR/extension/<name>.control` (with `Extension_control_path` GUC override since PG 18), parses it, picks a `default_version` or user-supplied version, optionally chains through update scripts from one version to the target, and runs the resulting SQL via SPI. Sets `creating_extension` so dependency.c records each newly-created object as DEPENDENCY_EXTENSION on the pg_extension row.
- `RemoveExtensionById`, `AlterExtensionContentsStmt` (`ALTER EXTENSION … ADD / DROP …`), `ExecAlterExtensionStmt` (`ALTER EXTENSION … UPDATE TO …`), `ExecAlterExtensionContentsStmt`, `AlterExtensionNamespace` (`ALTER EXTENSION … SET SCHEMA …`).
- `read_extension_control_file`, `parse_extension_control_file` — control-file parser (reuses GUC parser machinery).
- `find_update_path` — graph search through available `<name>--<v1>--<v2>.sql` scripts to find a shortest upgrade chain.
- `extension_file_exists`, `pg_extension_config_dump` (SQL function) — extensions can mark configuration tables to be included in `pg_dump`.

## `creating_extension` flag

A global bool. While CREATE EXTENSION's script is running, any object created records an `EXTENSION` dependency on the pg_extension row. This is how `DROP EXTENSION` knows to cascade-drop all member objects. It also affects `pg_dump`: extension-owned objects are not dumped individually; the extension declaration is.

## Confidence tag tally

`[verified-by-code]=4 [from-comment]=2`
