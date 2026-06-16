# `utils/acl.h` — ACL data structures and the canonical authz API

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/utils/acl.h`)

## Role

Defines the on-disk `AclItem` / `Acl` (array of AclItems) representation used
inside every catalog that carries an `aclitem[]` column (`pg_class.relacl`,
`pg_namespace.nspacl`, etc.), and exports the canonical privilege/ownership
check entry points (`object_aclcheck`, `pg_class_aclcheck`,
`pg_attribute_aclcheck_*`, `object_ownercheck`, `has_privs_of_role`,
`is_member_of_role`, `member_can_set_role`). Every authz site in the backend
ultimately funnels through this header.

## Public API

- `AclItem { ai_grantee, ai_grantor, ai_privs }` —
  `source/src/include/utils/acl.h:54` (size hardcoded in pg_type.h).
- Bit-twiddling macros `ACLITEM_GET_PRIVS/GOPTIONS/RIGHTS` etc. — `:66-84`.
  Lower 32 bits = privilege bits, upper 32 bits = WITH GRANT OPTION bits.
- Per-object "all rights" masks `ACL_ALL_RIGHTS_COLUMN/RELATION/SEQUENCE/...`
  — `:159-172`.
- `AclResult { ACLCHECK_OK, ACLCHECK_NO_PRIV, ACLCHECK_NOT_OWNER }` — `:182`.
- `object_aclcheck(classid, objectid, roleid, mode)` — `:245`. Generic dispatch.
- `pg_class_aclcheck`, `pg_attribute_aclcheck`, `pg_attribute_aclcheck_all`,
  `pg_parameter_aclcheck`, `pg_largeobject_aclcheck_snapshot` — `:252-268`.
- Role-membership: `has_privs_of_role`, `member_can_set_role`,
  `check_can_set_role`, `is_member_of_role`, `is_member_of_role_nosuper`,
  `is_admin_of_role`, `select_best_admin` — `:213-219`.
- Name→OID: `get_role_oid(rolname, missing_ok)`,
  `get_role_oid_or_public`, `get_rolespec_oid` — `:220-222`.
- `select_best_grantor` — `:227`. Computes the implicit grantor when a role
  has multiple paths to grant a privilege.
- Privilege bit accessors: `has_createrole_privilege`,
  `has_bypassrls_privilege` — `:288-289`.

## Invariants

- `AclItem.size == 16` on every platform; size is wired into pg_type.h's
  `aclitem` tuple. [from-comment, `:51-53`]
- `Acl` is a one-dimensional non-null `ArrayType`; lower bound ignored on
  read, forced to 1 on write. [from-comment, `:91-94`]
- AclItem order matters: pg_dump replays GRANTs in array order so that
  WITH-GRANT-OPTION rows precede dependents. [from-comment, `:17-25`]
- A NULL `Acl` column means "default protection" (the `acldefault()` return).
  [from-comment, `:27-29`]
- Upper 32 bits of `ai_privs` = grant options, lower 32 = base privileges.
  [verified-by-code, `:62-71`]
- `has_privs_of_role` is the **only** correct membership test for "is this
  role actually allowed to act with the target role's privileges?". It
  respects `INHERIT` and `NOINHERIT`. By contrast, `is_member_of_role`
  ignores INHERIT and was historically misused — it is the classic
  false-friend in PG authz code. [inferred from API split, `:213-218`]
- `member_can_set_role` covers SET ROLE / SECURITY DEFINER targets. Distinct
  from `has_privs_of_role` because the user can SET to a role without
  inheriting it. [from-comment, `:214`]
- `Acl` is a TOASTable array; callers must use `DatumGetAclP` /
  `PG_GETARG_ACL_P` (which detoasts) unless they know the value is inline.
  [from-comment, `:96-99`]

## Notable internals

- 14 distinct ACL bit characters (`a r w d D x t X U C T c s A m` —
  insert/select/update/delete/truncate/references/trigger/execute/usage/create/
  create-temp/connect/set/alter-system/maintain) — `:137-154`. New bits
  require coordinating with pg_type.h, the parser, and pg_dump.
- `ACL_MODECHG_ADD/DEL/EQL` opcodes for `aclupdate` — `:129-131`.
- `aclmask()` runs the matching scan; `AclMaskHow { ACLMASK_ALL, ACLMASK_ANY }`
  lets ACL bit accumulation short-circuit when caller only needs a yes/no.

## Trust-boundary / Phase D surface

- `is_member_of_role` is documented (`:216`) but the comment-less header
  doesn't warn callers that it skips INHERIT. Any new authz code that
  mistakenly calls it instead of `has_privs_of_role` produces a privilege
  leak. The header should explicitly mark it deprecated-for-authz.
  [ISSUE-api-shape: `is_member_of_role` vs `has_privs_of_role` are
  silent footguns (likely)]
- `get_role_oid(name, missing_ok)` accepts arbitrary text and resolves it
  through the pg_authid name lookup — classic NAME→OID surface (echo
  A3+A6+A7+A8+A9+A10). A caller that passes attacker-controlled text without
  validating role-existence-vs-create-race can be tricked into using a role
  that gets dropped+recreated between resolution and use.
  [ISSUE-correctness: `get_role_oid` name-vs-OID resolution is racey across
  CONCURRENT DROP ROLE (maybe)]
- `pg_largeobject_aclcheck_snapshot(lobj_oid, roleid, mode, snapshot)` —
  `:267`. Takes an explicit `Snapshot`; rest of the family doesn't. That's
  because LO ACLs are queried under a specific snapshot for cursor
  semantics. Callers passing the wrong snapshot can see stale grants.
  [ISSUE-correctness: LO acl-check snapshot parameter is a load-bearing
  gotcha (maybe)]
- `select_best_grantor` decides which of a user's transitive memberships is
  used to grant — this is the path that has had CVEs around "shadowing"
  grants in the past. Worth scrutinising any change here. [ISSUE-audit-gap:
  grantor selection is non-obvious and undocumented in this header (nit)]
- `has_bypassrls_privilege(roleid)` is the dispatch used by RLS — a single
  bool that bypasses every policy. Audit logging of role attribute changes
  must always cover this attribute. [ISSUE-audit-gap: BYPASSRLS toggles
  need explicit audit-event coverage (maybe)]
- Header doesn't expose any "redact me from logs" annotation — every error
  thrown via `aclcheck_error(_col|_type)` includes `objectname` verbatim,
  which can be attacker-controlled (e.g. via search_path); this is by
  design but worth flagging for any log-sanitisation pass. [ISSUE-audit-gap:
  ACL error messages echo attacker-supplied object names (nit)]

## Cross-refs

- `knowledge/files/src/include/utils/rls.h.md` — uses `has_bypassrls_privilege`.
- `knowledge/files/src/include/utils/usercontext.h.md` — `SwitchToUntrustedUser`
  composes with `member_can_set_role`.
- `knowledge/files/src/include/utils/aclchk_internal.h.md` — the
  `InternalGrant` representation used by `ExecuteGrantStmt`.
- Echo: A3/A6/A7/A8/A9/A10 NAME-vs-OID cluster.

<!-- issues:auto:begin -->
- [Issue register — `include-utils`](../../../../issues/include-utils.md)
<!-- issues:auto:end -->

## Issues

1. [ISSUE-api-shape: `is_member_of_role` is a silent footgun vs
   `has_privs_of_role` (likely)] — `source/src/include/utils/acl.h:216`.
2. [ISSUE-correctness: `get_role_oid` resolution racey vs concurrent
   DROP ROLE (maybe)] — `source/src/include/utils/acl.h:220`.
3. [ISSUE-correctness: `pg_largeobject_aclcheck_snapshot` snapshot
   parameter is a load-bearing gotcha (maybe)] —
   `source/src/include/utils/acl.h:267`.
4. [ISSUE-audit-gap: grantor selection in `select_best_grantor` undocumented
   in header (nit)] — `source/src/include/utils/acl.h:227`.
5. [ISSUE-audit-gap: BYPASSRLS bool needs explicit audit-event coverage
   (maybe)] — `source/src/include/utils/acl.h:289`.
6. [ISSUE-audit-gap: `aclcheck_error*` echoes attacker-supplied object
   names verbatim (nit)] — `source/src/include/utils/acl.h:270-276`.
