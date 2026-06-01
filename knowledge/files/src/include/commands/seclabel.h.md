# seclabel.h

- **Source path:** `source/src/include/commands/seclabel.h`
- **Lines:** 34
- **Last verified commit:** `ef6a95c7c64`

Internal APIs: `GetSecurityLabel`, `SetSecurityLabel`, `DeleteSecurityLabel`, `DeleteSharedSecurityLabel`. Statement entry: `ExecSecLabelStmt`. Provider-registration callback type: `check_object_relabel_type` — extensions like sepgsql register one of these at `_PG_init`.
