# user.h

- **Source path:** `source/src/include/commands/user.h`
- **Lines:** 43
- **Last verified commit:** `ef6a95c7c64`

Exports `Password_encryption` GUC (md5 vs scram-sha-256) and `createrole_self_grant` (which privileges a CREATEROLE auto-grants itself on new roles). Declares `check_password_hook_type` (extension hook — passwordcheck contrib uses it) and `check_password_hook` global. Statement prototypes: `CreateRole`, `AlterRole`, `AlterRoleSet`, `DropRole`, `RenameRole`, `DropOwnedObjects`, `ReassignOwnedObjects`, `GrantRole`.
