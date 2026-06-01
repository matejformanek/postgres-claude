# `src/backend/utils/misc/superuser.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~100
- **Source:** `source/src/backend/utils/misc/superuser.c`

Two functions:
- `superuser()` — is the **current effective** role a superuser?
- `superuser_arg(Oid roleid)` — is a given role a superuser?

Both consult `pg_authid.rolsuper` via syscache, with a tiny last-result
cache keyed on `(roleid, current xact id)` for the common case of
repeated lookups. A registered `CacheRegisterSyscacheCallback` on
`AUTHOID` invalidates the cache on `pg_authid` changes.

The single-user/`InitPostgres` escape hatch: during bootstrap and in
`--single` mode, `superuser()` returns true unconditionally so
initialization can proceed before `pg_authid` is queryable. **All
superuser checks must go through this file** — never read `rolsuper`
directly. [from-comment] (`superuser.c:1-10`)
