# `src/backend/utils/misc/rls.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~150
- **Source:** `source/src/backend/utils/misc/rls.c`

Row-level security policy applicability helpers. The actual policy
expressions live in `pg_policy` and are merged into queries by
`rewrite/rowsecurity.c`; this file just answers "does RLS apply to this
relation for this user right now?":
- `check_enable_rls(Oid relid, Oid checkAsUser, bool noError)` →
  `RLS_NONE | RLS_NONE_ENV | RLS_ENABLED`. Honors `row_security` GUC
  (`off`/`on`/`force`), BYPASSRLS role attribute, table owner bypass, and
  the `relrowsecurity`/`relforcerowsecurity` columns of `pg_class`.
- `row_security_active(text|oid)` SQL functions: tells policies (and
  user code) whether RLS is currently engaged on a relation. [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
