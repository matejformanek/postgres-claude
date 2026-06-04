# src/backend/utils/adt/acl.c

## Purpose

The heart of PostgreSQL's access-control machinery: input/output and
manipulation of `aclitem[]` (GRANTed privileges per object), the
`has_*_privilege` SQL function family, and the role-membership recursion
machinery (`has_privs_of_role`, `member_can_set_role`, `roles_is_member_of`).
~5800 lines.

Public C API used by every catalog-permissions check in the rest of the
backend (`pg_class_aclcheck`, `object_aclcheck`, `object_ownercheck`, …)
ultimately reaches `aclmask` and `has_privs_of_role` here. The
`pg_proc.dat` declares hundreds of SQL functions backed by this file.

## Role in PG

Three responsibilities, in roughly increasing complexity:

1. **`aclitem` type I/O and array operations**: parse / emit the
   `grantee=privs/grantor` text form, build defaults, merge, sort,
   compare, update with grant/revoke semantics.
2. **`has_*_privilege` SQL functions**: a combinatorial explosion of
   variants (3×3 name/OID dimensions, plus per-object-type families:
   table, sequence, column, any-column, database, schema, function,
   tablespace, foreign data wrapper, server, language, type,
   parameter, large object). Each variant ultimately resolves to the
   same `aclmask`-based check.
3. **Role-membership cache and recursion**: caches `(member,
   RoleRecurseType)` → list of all roles a member belongs to,
   invalidated on `pg_authid` / `pg_auth_members` /
   `pg_database_rolemembership` changes. A bloom filter accelerates
   large lists.

## Key functions

### aclitem text I/O (`:155-430`)

- `getid(s, n, escontext)` (`:171`) — consumes one identifier
  (optionally double-quoted, with `""` escape), errors via
  `ereturn`/`ereport` so it's soft-error-safe. Length capped at
  `NAMEDATALEN-1`.
- `putid(p, s)` (`:223-?`) — inverse, doubling internal `"` and
  conditionally quoting based on `is_safe_acl_char`. Must stay in
  sync with `dequoteAclUserName` in pg_dump/dumputils.c (comment
  `:221`).
- `aclparse(s, aip, escontext)` (`:279-430`) — full parser for
  `[group|user] <name>=<privchars>[*]…[/grantor]`. Privilege char
  switch (`:320-378`) maps `r/a/w/d/D/x/t/X/U/C/T/c/s/A/m` to
  ACL_SELECT/INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER/
  EXECUTE/USAGE/CREATE/CREATE_TEMP/CONNECT/SET/ALTER_SYSTEM/MAINTAIN.
  Empty name → `ACL_ID_PUBLIC`. Missing grantor defaults to
  `BOOTSTRAP_SUPERUSERID` with a WARNING (`:419-425`) except in
  bootstrap mode.
- `aclitemin` / `aclitemout` (`:628-735`) — fmgr wrappers.

### ACL array operations (`:432-?`)

- `allocacl`, `aclcopy`, `aclconcat`, `aclmerge` (`:471-553`).
  `aclconcat` is documented "cheesy" — may produce redundant entries,
  caller beware (`:487-488`).
- `aclitemsort` / `aclequal` (`:559-573`).
- `acldefault(objtype, ownerId)` (`:827-940`) — per-object-type
  defaults. Notable backwards-compat carve-outs:
  - DATABASE: `world_default = ACL_CREATE_TEMP | ACL_CONNECT` —
    public can connect and create temp tables by default.
    Footgun for naive deployments.
  - FUNCTION: `world_default = ACL_EXECUTE`. Means `CREATE FUNCTION
    foo … LANGUAGE plpgsql` is implicitly PUBLIC-callable unless the
    creator `REVOKE`s.
  - LANGUAGE: `world_default = ACL_USAGE`.
  - TYPE / DOMAIN: `world_default = ACL_USAGE`.
  - Everything else: `ACL_NO_RIGHTS` by default (RELATION,
    SEQUENCE, SCHEMA, TABLESPACE, FDW, SERVER, PARAMETER_ACL,
    LARGEOBJECT, COLUMN).
  - Comment `:922-931` explains the SQL-spec "_SYSTEM" grantor
    convention and how PG models owner's grant options implicitly.
- `aclupdate` (`:1020-?`) — single GRANT/REVOKE on an Acl. Handles
  `DROP_RESTRICT` vs `DROP_CASCADE` semantics.
- `aclnewowner` (`:1147-?`) — REASSIGN OWNED BY rewriter.

### Privilege checking core (`:1416-?`)

- `aclmask(acl, roleid, ownerId, mask, how)` (`:1416-1495`) — THE
  core check. Computes the bitmask of privileges `roleid` actually
  holds against `acl`.
  - First special-cases owner: if `has_privs_of_role(roleid,
    ownerId)` then add `mask & ACLITEM_ALL_GOPTION_BITS` (owner
    implicitly has all grant options).
  - First pass: direct grants to `roleid` or PUBLIC.
  - Second pass: grants to *other* roles, gated by
    `has_privs_of_role(roleid, aidata->ai_grantee)` to test
    membership inheritance.
  - `how == ACLMASK_ALL` requires all bits to be present;
    `ACLMASK_ANY` returns on first match (early exit).
  - Two-pass design (`:1469-1473`) is a deliberate perf trick:
    membership tests are expensive, so we skip them for entries
    whose direct grants already covered all `remaining` bits.
- `aclmask_direct` (`:1505-?`) — same without membership recursion.
- `aclmembers(acl, &roleids)` (`:1568-?`) — extracts all
  grantor+grantee OIDs (used for dependency tracking).

### `has_*_privilege` family

Each object-type has a 3×3 matrix of name/OID variants for the role
arg and the object arg, plus a no-role variant defaulting to
`GetUserId()`. The implementation pattern is uniform:
- Look up role OID (via `get_role_oid` or `PG_GETARG_OID`).
- Look up object OID similarly.
- Parse the priv string (`convert_*_priv_string`).
- Call `object_aclcheck(objClassId, objId, roleid, mask)` or
  type-specific `pg_class_aclcheck`/`pg_database_aclcheck`/etc.

Coverage:
- TABLE / SEQUENCE / DATABASE / SCHEMA / FUNCTION / TABLESPACE /
  LANGUAGE / TYPE / FDW / SERVER / LARGEOBJECT / PARAMETER (PG 15+).
- COLUMN (with both attname and attnum variants), ANY_COLUMN.
- Role-level: `pg_has_role(member, role, privstring)` — different
  in that "privilege" here is `MEMBER` / `USAGE` / `SET`.

### Role membership engine

- `RoleMembershipCacheCallback(Datum, SysCacheIdentifier, uint32)`
  (`:5099-?`) — invalidates `cached_roles[]` and `cached_role[]` on
  AUTHOID / AUTHMEMMEMROLE / AUTHMEMROLEMEM cache flushes.
- `roles_is_member_of(roleid, type, admin_of, is_admin)`
  (`:5182-?`) — walks `pg_auth_members` recursively, dedup'd,
  bloom-filter accelerated past `ROLES_LIST_BLOOM_THRESHOLD` (`:88`).
  `RoleRecurseType` ∈ {`ROLERECURSE_PRIVS`, `ROLERECURSE_SETROLE`,
  `ROLERECURSE_MEMBERS`, `ROLERECURSE_ADMIN`}.
- `has_privs_of_role(member, role)` (`:5314-5331`) — fast paths
  for `member == role` and `superuser_arg(member)`; otherwise
  `list_member_oid(roles_is_member_of(member, ROLERECURSE_PRIVS, …),
  role)`. Inherit-vs-not is encoded in `ROLERECURSE_PRIVS`.
- `member_can_set_role(member, role)` (`:5348-5365`) — same shape
  but uses `ROLERECURSE_SETROLE`. SET ROLE is a separate dimension
  from inherited privs.
- `check_can_set_role(member, role)` (`:5371-5378`) — error-thrower
  wrapper.
- `select_best_grantor(grantedBy, privileges, acl, roleid, …)`
  (`:5508-?`) — for GRANT, picks the highest-privilege grantor in
  the caller's membership chain that holds the required grant
  options.

### `pg_role_aclcheck(role_oid, roleid, mode)` (`:5039-?`)

The role-as-securable-object check (different from
`has_privs_of_role`!). Used for `GRANT pg_monitor TO x WITH ADMIN
OPTION` etc.

## State / globals

- `cached_role[ROLERECURSE_MAX]` and
  `cached_roles[ROLERECURSE_MAX]` arrays (`:71-77` comment) — caches
  the most recently looked-up roles per recursion type. Comment
  notes "Possibly this mechanism should be generalized to allow
  caching membership info for multiple roles" — long-standing TODO
  (`:68-69`).
- `cached_bloom_filter` — bloom filter for the cached_roles list
  once it exceeds `ROLES_LIST_BLOOM_THRESHOLD`.
- Static `RoleMembershipCacheCallback` registered against THREE
  syscaches (AUTHOID, AUTHMEMMEMROLE, AUTHMEMROLEMEM) at init
  (`:5083-5089`).

## Phase D notes — critical surface

- **Owner has all grant options implicitly** (`:1440-1447`).
  Implemented by `has_privs_of_role(roleid, ownerId)` check inside
  `aclmask`. So if a role can SET ROLE to the object owner, they
  inherit all grant options. This is intentional but means object
  ownership transitively flows grant power.
- **`has_privs_of_role` is the universal trust check** — invoked
  by every per-object aclcheck. Its fast paths are `member == role`
  and `superuser_arg(member)`. Bug here = privilege escalation.
- **Default ACLs encode trust assumptions**:
  - `OBJECT_DATABASE`: PUBLIC gets CONNECT + CREATE_TEMP (`:850-853`).
    Comment notes "for backwards compatibility, grant some rights
    by default". A fresh `CREATE DATABASE x` is connectable by
    anyone unless explicitly revoked.
  - `OBJECT_FUNCTION` / `OBJECT_LANGUAGE`: PUBLIC gets EXECUTE / USAGE
    (`:855-863`). Same backwards-compat carve-out. Means every
    CREATE FUNCTION is implicitly callable by PUBLIC.
  - `OBJECT_TYPE` / `OBJECT_DOMAIN`: PUBLIC gets USAGE
    (`:885-888`). Any user can declare a column of any new type.
- **aclparse grantor defaulting** (`:419-425`): outside bootstrap
  mode, a missing `/grantor` produces a WARNING and defaults to
  `BOOTSTRAP_SUPERUSERID`. Means `aclitemin` accepting a hand-crafted
  `joe=arwd` string (no grantor) WARNS but succeeds — pg_dump output
  always has grantors, but adversarial input could exploit this.
  No security risk (grantor must already exist as a role), but a
  parser footgun.
- **Bloom filter on `roles_is_member_of`** (`:86-90` comment):
  threshold-gated to avoid the construction cost in the common case.
  False-positive risk on bloom is acceptable because actual
  membership is double-checked.
- **OID-vs-name precedence**: every `has_*_privilege` variant has
  both name and OID forms. Name forms call `get_role_oid` /
  `get_database_oid`/etc., which resolve via syscaches. Race against
  concurrent role/object drop returns either `false` (if
  `missing_ok=true`) or errors.
- **Soft-error path** (`escontext`) is plumbed through `getid`,
  `aclparse`, `aclitemin` — important for `COPY FROM` of `aclitem[]`
  columns with `ON_ERROR ignore`.

## Potential issues

- [ISSUE-trust-boundary: `acldefault(OBJECT_DATABASE)` grants
  PUBLIC `CONNECT|CREATE_TEMP` by default (`:850-853`). Every new
  database is open to all roles. Comment marks this as backwards
  compat. Frequent source of CVE-adjacent misconfigurations
  (medium, by design)]
- [ISSUE-trust-boundary: `acldefault(OBJECT_FUNCTION)` grants
  PUBLIC `EXECUTE` (`:855-858`). Combined with SECURITY DEFINER,
  this is the prime privilege-escalation vector (medium, by
  design)]
- [ISSUE-correctness: `aclparse`'s missing-grantor fallback to
  `BOOTSTRAP_SUPERUSERID` with WARNING (`:419-425`) means hand-crafted
  `aclitem` literals silently attribute grants to the bootstrap
  superuser. Downstream dependency tracking will record bootstrap
  superuser as grantor. (low — would require ability to inject
  aclitem literals already)]
- [ISSUE-undocumented-invariant: `cached_roles[]` caches by-member;
  comment `:68-69` admits this should be generalized but never was.
  Worst case: rapid SET ROLE between two roles triggers per-call
  cache flush + recompute. Not exploitable but a perf wart (low)]
- [ISSUE-info-disclosure: `aclmembers()` (`:1568`) returns ALL
  grantor+grantee OIDs without ACL filtering — used internally for
  dependency tracking, but SQL surface via `aclexplode()` exposes
  the full per-role grant matrix to anyone who can read the
  catalog (low — matches documented `\dp` behaviour)]
- [ISSUE-correctness: `aclconcat` is self-described as "cheesy"
  (`:487-488`), producing potentially redundant entries. Callers
  must follow up with `aclmerge` or `aclitemsort`. If a new caller
  forgets, dependent code may see duplicate grants in `aclexplode`
  output (low)]
- [ISSUE-state-transition: `RoleMembershipCacheCallback` (`:5099`)
  blows away the entire cached_roles array on ANY pg_authid change
  — including unrelated roles. Pathological workload: rapid CREATE
  ROLE / DROP ROLE thrashes the cache for unrelated SQL backends
  (low)]
