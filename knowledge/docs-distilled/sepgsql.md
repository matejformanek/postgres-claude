---
source_url: https://www.postgresql.org/docs/current/sepgsql.html
fetched_at: 2026-07-16
anchor_sha: 572c3b2ddf8c
module: contrib/sepgsql
---

# sepgsql — SELinux label-based Mandatory Access Control

Makes PostgreSQL a **userspace object manager** for SELinux: every DDL/DML
access is checked against the SELinux security policy in addition to (never
instead of) PostgreSQL's own DAC privileges. The single largest example of the
`object_access_hook` + `ExecutorCheckPerms_hook` extension surface. Linux-only,
build-time `--with-selinux` / `-Dselinux=enabled`. Author: KaiGai Kohei.

## Non-obvious claims — architecture

- It is a **pure hook chain installer**. `_PG_init` saves the previous hook
  pointers and installs three of its own, preserving the chain:
  - `object_access_hook` ← `sepgsql_object_access` (DDL + label events),
  - `ExecutorCheckPerms_hook` ← `sepgsql_exec_check_perms` (DML),
  - `ProcessUtility_hook` ← `sepgsql_utility_command` (to reject e.g. `LOAD`).
  `[verified-by-code source/contrib/sepgsql/hooks.c:40-42,473-482]`
- Must be in `shared_preload_libraries` (restart) **and** its `sepgsql.sql`
  must be sourced into *every* database via single-user `postgres --single`
  (template0/template1/postgres and any others), which both installs the
  label-management functions and assigns initial labels. A fresh DB created
  later needs the same treatment. `[from-README]`
- Two GUCs, both `DefineCustomBoolVariable`, `postgresql.conf`/command-line
  only:
  - `sepgsql.permissive` (default `off`) — force permissive (log, don't
    block) regardless of the system-wide SELinux mode; test-only.
  - `sepgsql.debug_audit` (default `off`) — force audit logging of *all*
    decisions, including allowed ones (normally only denials are logged).
  `[verified-by-code source/contrib/sepgsql/hooks.c:63,74,431,449]`

## Non-obvious claims — enforcement semantics

- **Granularity is schema / table / column / sequence / view / function only —
  there is NO row-level MAC.** PG's row-security policies are orthogonal and
  sepgsql does not participate in them. This is the single biggest scope
  limitation. `[from-README]`
- Column-level checks are computed per-statement and can attach multiple
  permissions to one column. Docs' canonical example
  `UPDATE t1 SET x=2, y=func1(y) WHERE z=100`:
  `db_column:update` on `x`; `db_column:{select update}` on `y`;
  `db_column:select` on `z`; `db_table:{select update}` on `t1`. `[from-README]`
- New objects **inherit the parent's security label** (table←schema,
  column←table, …) unless a SELinux *type-transition* rule fires. `[from-README]`
- **Trusted procedures** are the sepgsql analogue of `SECURITY DEFINER`:
  label a function with a `*_trusted_proc_exec_t` type and it runs under that
  label, letting an unprivileged caller reach data (e.g. a masked
  `customer.credit`) they can't select directly. Enforced by the extra
  `db_procedure:entrypoint` check beyond `db_procedure:execute`. `[from-README]`
- **Dynamic domain transition** via `sepgsql_setcon()` is only safe toward
  *reduced* privilege — the policy allows `s0-s0:c0.c1023 → c1.c4` (subset)
  but denies widening back to `c1.c1023`. Intended for connection poolers to
  drop into a per-end-user domain and later revert. `[from-README]`
- **DAC still applies fully** — sepgsql is a second gate, never a bypass. And
  when enabled it *tightens* one thing: superuser DML on system catalogs /
  TOAST tables (normally unrestricted) now goes through MAC. `[from-README]`
- **`LOAD` is rejected outright** (via the utility hook) so a client can't
  side-load a `.so` to escape policy. `[from-README][verified-by-code hooks.c:481-482 ProcessUtility hook]`
- **Covert-channel caveat:** it hides *contents*, not *existence*. Unique/PK/FK
  violations still leak the presence of invisible rows. Some DDL/DCL paths are
  not yet checked at all. `[from-README]`

## Label-management functions (from `sepgsql.sql`)

- `sepgsql_getcon() → text` — current client domain.
- `sepgsql_setcon(text) → bool` — switch client domain (NULL ⇒ revert);
  needs `setcurrent` + `dyntransition` policy permissions.
- `sepgsql_mcstrans_in/out(text) → text` — qualified↔raw MLS/MCS range
  translation (needs mcstrans daemon).
- `sepgsql_restorecon(text) → bool` — (re)initialize labels for all objects in
  the current DB; arg NULL or a specfile path.
`[from-README]` — SQL-visible signatures; the C entry points live in
`contrib/sepgsql/*.c`, not re-verified per-line this run.

## Links into corpus

- The generic `object_access_hook` / `ExecutorCheckPerms_hook` surfaces
  sepgsql consumes: `[[knowledge/docs-distilled/extend-extensions.md]]`,
  `[[knowledge/subsystems/…executor…]]` (executor permission checks live in
  `src/backend/executor/execMain.c`).
- `SECURITY LABEL` statement + label providers:
  `[[knowledge/docs-distilled/ddl-priv.md]]`.
- Row-security (the orthogonal, NOT-covered layer) for contrast:
  `[[knowledge/idioms/…row-level-security…]]` /
  `[[knowledge/docs-distilled/ddl-priv.md]]`.
