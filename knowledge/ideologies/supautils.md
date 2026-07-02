# supautils — a ProcessUtility interceptor that emulates SUPERUSER for an allowlisted proxy role

> Ideology note produced by the pg-extension-anthropologist cloud routine.
> Repo: `supabase/supautils` @ branch `master` (MODVERSION 3.2.3), fetched 2026-07-02.
> Caveat: characterization based on the files actually fetched — `README.md`,
> `Makefile`, `src/supautils.c` (the ~1550-line core, read in full), `src/utils.c`,
> plus `src/privileged_extensions.{c,h}`, `src/constrained_extensions.{c,h}`,
> `src/extensions_parameter_overrides.{c,h}`, `src/policy_grants.c`,
> `src/drop_trigger_grants.c`, `src/event_triggers.c`. NOT fetched: the reserved-role
> logic is *inline in supautils.c* (there is no `reserved_roles.c`; probe → 404), and
> `permission_hints.c` (the `find_missing_perm` / `build_privileges_string` machinery,
> included via `permission_hints.h`) was not fetched — its call sites in `supautils.c`
> are cited instead. There is no `supautils.control` (probe → 404): the module is
> loaded as a library, never `CREATE EXTENSION`'d.

## Domain & purpose

supautils is a **privilege-emulation hook layer** for managed/cloud Postgres, where
the provider cannot hand end users real `SUPERUSER`. Its thesis: a designated
non-superuser "privileged role" should be able to run superuser-gated utility
commands (`CREATE PUBLICATION`, `CREATE EVENT TRIGGER`, `CREATE FOREIGN DATA WRAPPER`,
`CREATE EXTENSION` of allowlisted extensions, certain `SET` of superuser-only GUCs),
while a complementary "reserved roles / reserved memberships" policy stops even
`CREATEROLE` holders from touching the provider's own infrastructure roles
[from-README]. It is "completely managed by configuration — no tables, functions, or
security labels are added to your database" [from-README, README.md:10]: every
behavior is driven by `PGC_SIGHUP` GUCs in `postgresql.conf`, and the module ships
no SQL objects.

## How it hooks into PG

Load model is `shared_preload_libraries = 'supautils'` (cluster-wide) or
`session_preload_libraries` via `ALTER ROLE ... SET` (per-role)
[from-README, README.md:20-31]. Build is `MODULE_big = supautils` over
`SRC = $(wildcard src/*.c)` PGXS — a multi-file shared object, not a single
translation unit [verified-by-code, Makefile:20-25]. On PG ≥ 18 it uses the new
`PG_MODULE_MAGIC_EXT(.name=..., .version=...)` form, else plain `PG_MODULE_MAGIC`
[verified-by-code, supautils.c:37-41].

`_PG_init` installs **four hooks** and defines the GUC surface
[verified-by-code, supautils.c:1407-1421]:

- `ProcessUtility_hook` → `supautils_hook` — the centerpiece: intercepts DDL/utility
  statements and either guards them (reserved roles) or elevates them (privileged role).
- `needs_fmgr_hook` + `fmgr_hook` → `supautils_needs_fmgr_hook` /
  `supautils_fmgr_hook` — attaches *only* to functions that `RETURN event_trigger`
  (`supautils_needs_fmgr_hook`, supautils.c:98-102), to police event-trigger execution.
- `ExecutorStart_hook` → `supautils_executor_start` — wraps execution to rewrite
  "permission denied" (SQLSTATE 42501) errors into actionable `GRANT ...` hints for
  configured `hint_roles`.

All GUCs are `DefineCustomStringVariable`/`BoolVariable` at `PGC_SIGHUP`
(config-file reloadable, not per-session user-settable), e.g. `supautils.privileged_role`,
`supautils.superuser`, `supautils.reserved_roles`, `supautils.reserved_memberships`,
`supautils.privileged_extensions`, `supautils.privileged_role_allowed_configs`
[verified-by-code, supautils.c:1423-1528]. It also implements **GUC placeholders**: a
comma list in `supautils.placeholders` is walked at init and each name gets its own
`DefineCustomStringVariable` with a `restrict_placeholders_check_hook` that rejects
disallowed substrings (supautils.c:1530-1546) [verified-by-code].

### The core mechanism: switch-run-restore around chained utility

The privilege-emulation trick is a scoped identity swap.
`switch_to_superuser()` records the current id via `GetUserIdAndSecContext` and calls
`SetUserIdAndSecContext(superuser_oid, ... | SECURITY_LOCAL_USERID_CHANGE |
SECURITY_RESTRICTED_OPERATION)`; `superuser_oid` defaults to `BOOTSTRAP_SUPERUSERID`
or the role named by `supautils.superuser`
[verified-by-code, utils.c:15-32]. A module-static `is_switched_to_superuser`
guards against nested swaps corrupting the saved role
[verified-by-code, utils.c:8-9,17-22]. Each intercepted statement follows the pattern:
`switch_to_superuser(...)` → `run_process_utility_hook_with_cleanup(prev_hook, ...)`
(chain to the previous hook, running the real command as the superuser) →
`switch_to_original_role()` (supautils.c:547-580 for `CREATE EXTENSION`, and every
other elevated case) [verified-by-code]. For object-creation cases it then re-owns
the new object to the *privileged* role via `alter_owner()` — which for FDWs and event
triggers temporarily flips the role's `superuser` attribute through `AlterRole` because
those objects can only be owned by a superuser
[verified-by-code, supautils.c:667-701, utils.c:110-145].

## Where it diverges from core idioms

- **Inverts core's "you have the privilege or you don't" ACL model.** Core Postgres
  gates superuser-only operations with a hard `superuser()`/`has_privs_of_role` check
  and no in-between. supautils inserts a *policy layer above the ACL check*: it runs
  the command as the bootstrap superuser on behalf of a non-superuser, gated by a
  C-level allowlist (`is_current_role_privileged`, `is_extension_privileged`), then
  re-owns the result back to the caller (supautils.c:560-580, 1381-1392)
  [verified-by-code]. The privilege is emulated in C, not granted in the catalog.
- **ProcessUtility interception as a policy point.** Rather than an
  `object_access_hook` or catalog ACL, it dispatches on `pstmt->utilityStmt->type`
  through a giant switch (`T_AlterRoleStmt`, `T_CreateRoleStmt`, `T_DropRoleStmt`,
  `T_GrantRoleStmt`, `T_RenameStmt`, `T_CreateExtensionStmt`, `T_CreatePublicationStmt`,
  `T_CreateEventTrigStmt`, `T_DropStmt` sub-dispatched on `removeType`, …) and either
  `ereport(ERROR, ...)` (guard) or elevate-and-chain (proxy)
  [verified-by-code, supautils.c:252-1019]. The default arm just chains
  `run_process_utility_hook(prev_hook)` unchanged (supautils.c:1014-1018).
- **Reserved-role guard vs core's role system.** Core lets a `CREATEROLE` holder
  ALTER/DROP/GRANT most roles. supautils reintroduces a protected class the catalog has
  no notion of: `is_reserved_role()` splits `supautils.reserved_roles` and rejects any
  `ALTER/DROP/RENAME/GRANT` touching a listed name with
  `ERRCODE_INSUFFICIENT_PRIVILEGE` "is a reserved role"
  (supautils.c:274, 383-384, 479-480, 530-534, 1242-1269) [verified-by-code]. A trailing
  `*` wildcard marks a role "configurable", letting the privileged role edit its
  settings but not the role itself (`remove_ending_wildcard`, supautils.c:1252-1258;
  utils.c:69-81) [verified-by-code].
- **Blocks superuser self-escalation explicitly.** Both `CREATE ROLE ... SUPERUSER` and
  `ALTER ROLE ... SUPERUSER` are special-cased to `ereport(ERROR)` even for the
  privileged role — "Only roles with the SUPERUSER attribute may create/alter roles with
  the SUPERUSER attribute" (supautils.c:287-297, 396-403) [verified-by-code]. The
  emulation is deliberately not transitive to superuser itself.
- **fmgr_hook used as an execution firewall, not for instrumentation.** Since an
  `fmgr_hook` "can't skip execution directly", it neutralizes an event-trigger function
  by rewriting the `FmgrInfo` to a no-op (`force_noop(flinfo)`), skipping triggers for
  superusers/reserved roles per an ownership matrix
  (supautils.c:104-122, 127-187) [verified-by-code]. This is an unusual, adversarial use
  of a hook meant for tracking function calls.
- **Error post-processing via ExecutorStart PG_TRY/PG_CATCH.** It catches a 42501 error,
  `CopyErrorData` into a saved `MemoryContext`, `FlushErrorState`, computes the missing
  ACL bits, rewrites `edata->hint` to a ready-to-paste `GRANT`, and `ReThrowError`s
  (supautils.c:189-250) [verified-by-code]. Careful cross-context memory discipline
  (`MemoryContextSwitchTo(cur_ctx)` before `CopyErrorData`) is the notable idiom here.
- **Emulation guarded by `IsTransactionState()` / `superuser()` early-outs.** Most arms
  bail immediately if `!IsTransactionState()` or the caller already `superuser()`, so the
  proxy layer is a no-op for real superusers and outside a transaction
  (supautils.c:265-268, 319-322, 371) [verified-by-code].

## Notable design decisions

- **PG16 CREATEROLE-self-grant awareness.** On PG ≥ 16, `CREATE ROLE` deliberately does
  *not* switch to superuser, because switching would rob the creator of the implicit
  ADMIN grant PG16 gives them on the new role; pre-16 it still elevates to set
  BYPASSRLS/REPLICATION (supautils.c:423-453) [verified-by-code].
- **CREATE EXTENSION delegation adapted from pgextwlist.** Allowlisted extensions in
  `supautils.privileged_extensions` are created as the superuser; others run as the
  caller. It also runs before/after custom scripts, applies parameter overrides
  (`override_ext_options`), and enforces resource constraints
  (`constrain_extension`) before delegating (supautils.c:542-581) [verified-by-code,
  from-README README.md:155-174].
- **Constrained extensions / parameter overrides parse JSON in GUC check hooks.**
  `supautils.constrained_extensions` and `...extensions_parameter_overrides` are JSON
  GUCs validated in `*_check_hook` and materialized into fixed-size static arrays
  (`MAX_CONSTRAINED_EXTENSIONS 100`, etc.) in `*_assign_hook`
  (supautils.c:32-35, 1036-1073, 1201-1240) [verified-by-code].
- **Table-ownership bypass for policies and triggers.** `supautils.policy_grants` /
  `supautils.drop_trigger_grants` let named roles CREATE/ALTER/DROP POLICY and DROP
  TRIGGER on tables they do not own, again via the switch-run-restore path
  (supautils.c:738-887) [verified-by-code].
- **`switch_to_superuser` uses `SECURITY_RESTRICTED_OPERATION`.** The elevated window is
  hardened against search-path/trojan attacks by ORing in
  `SECURITY_RESTRICTED_OPERATION | SECURITY_LOCAL_USERID_CHANGE` (utils.c:29-31)
  [verified-by-code].
- **`_PG_fini` restores hooks but is documented as never called.** It resets
  `ProcessUtility_hook`/`ExecutorStart_hook` "just for completion", with a comment
  pointing at `dfmgr.c` (supautils.c:1549-1556) [verified-by-code].
- **All policy GUCs are `PGC_SIGHUP`, not per-user.** End users cannot flip the guard
  from a session; only the provider's `postgresql.conf` can (supautils.c:1423-1518)
  [verified-by-code]. `supautils.disable_program` is `GUC_SUPERUSER_ONLY` and marked "DO
  NOT USE; here for backward compat" (supautils.c:1525-1528) [verified-by-code].

## Links into corpus

- [[pg_tle]] — AWS Trusted Language Extensions: the adjacent "let non-superusers do
  privileged extension things safely" angle, from a different mechanism (trusted
  install path vs ProcessUtility proxy).
- [[wrappers]] — Supabase's own FDW framework; supautils is what lets a non-superuser
  `CREATE FOREIGN DATA WRAPPER` in the first place (supautils.c:651-677).
- [[pgaudit]] — another `ProcessUtility_hook` / execution-hook consumer, but for
  observation rather than privilege emulation; useful contrast on hook intent.
- [[pgsodium]] — Supabase security extension using SECURITY LABEL; contrast with
  supautils's explicit "no security labels are added" stance (README.md:10).

## Sources

- `https://raw.githubusercontent.com/supabase/supautils/master/README.md` — HTTP 200.
- `https://raw.githubusercontent.com/supabase/supautils/master/Makefile` — HTTP 200.
  MODVERSION 3.2.3, `MODULE_big`, `SRC = $(wildcard src/*.c)`.
- `https://raw.githubusercontent.com/supabase/supautils/master/src/supautils.c` — HTTP
  200. The core; all supautils.c cites point here.
- `https://raw.githubusercontent.com/supabase/supautils/master/src/utils.c` — HTTP 200.
  `switch_to_superuser`, `switch_to_original_role`, `alter_owner`.
- `.../src/utils.h` — HTTP 200.
- `.../src/privileged_extensions.c` — HTTP 200. `is_extension_privileged`, `force_noop`.
- `.../src/privileged_extensions.h` — HTTP 200.
- `.../src/constrained_extensions.c` + `.h` — HTTP 200.
- `.../src/extensions_parameter_overrides.c` + `.h` — HTTP 200.
- `.../src/policy_grants.c` — HTTP 200.
- `.../src/drop_trigger_grants.c` — HTTP 200.
- `.../src/event_triggers.c` — HTTP 200.
- `.../supautils.control` — HTTP 404. No control file; loaded as a library, not
  `CREATE EXTENSION`'d.
- `.../src/reserved_roles.c`, `.../src/reserved_memberships.c` — HTTP 404. Reserved-role
  and reserved-membership logic is inline in `supautils.c` (`is_reserved_role`,
  `confirm_reserved_memberships`), not separate TUs.
- `.../src/permission_hints.c` (a.k.a. hints/enhanced_hints/privileged_role/
  table_ownership_bypass) — not fetched (probe → 404 for the guessed names); the
  `find_missing_perm` / `build_privileges_string` call sites are cited in `supautils.c`
  instead.
- `https://api.github.com/repos/supabase/supautils/git/trees/master?recursive=1` — not
  usable (GitHub API access not enabled for this session); file set enumerated by
  direct raw probes.
