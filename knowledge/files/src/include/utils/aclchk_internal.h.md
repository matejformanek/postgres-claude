# `utils/aclchk_internal.h` — InternalGrant struct

**Verified against source pin `4b0bf0788b0`** (path:
`source/src/include/utils/aclchk_internal.h`)

## Role

Internal representation of a single GRANT/REVOKE statement after name→OID
resolution, shared between aclchk.c and a few callers that need to construct
synthetic grants (e.g. extension scripts, parser helpers). 46-line glue
header.

## Public API

- `InternalGrant { is_grant, objtype, objects, all_privs, privileges, col_privs,
   grantees, grant_option, grantor, behavior }` —
  `source/src/include/utils/aclchk_internal.h:31-43`.

## Invariants

- `objects` is a `List *` of OIDs for the target objects (objtype
  determines which catalog they're OIDs in). [inferred, `:35`]
- `privileges` is an `AclMode` bitmask; if `all_privs == true` AND
  `privileges == ACL_NO_RIGHTS (0)`, aclchk.c rewrites `privileges` in place
  to the ACL_ALL_RIGHTS_* mask for that objtype.
  **Side effect: this mutates the caller's struct.** [from-comment, `:21-24`]
- `col_privs` is valid only when `objtype == OBJECT_TABLE`; it carries the
  un-transformed `AccessPriv` nodes for column-level grants. [from-comment,
  `:26-29`]
- `grantor` is the role explicitly named in `GRANTED BY`; if NULL, the
  grantor is selected by `select_best_grantor` (see acl.h). [inferred]

## Notable internals

Tiny header. The interesting structural fact is that PG keeps column
privileges separate from object privileges even inside this internal form —
the parser turns `GRANT SELECT(col1, col2) ON t` into one object-level
record + a list of AccessPriv nodes.

## Trust-boundary / Phase D surface

- The "rewrites `privileges` in place" comment (`:21-24`) means any caller
  re-using an `InternalGrant` across multiple objtypes will silently get
  the wrong mask second time around.
  [ISSUE-correctness: `InternalGrant.privileges` mutated in-place breaks
  reuse across objtypes (maybe)]
- `col_privs` carries un-transformed AccessPriv nodes — these can hold
  attacker-controlled column names that get resolved later in aclchk.c.
  Any path that materialises an error before resolution may echo unverified
  names. [ISSUE-audit-gap: un-transformed AccessPriv nodes can be
  echoed in errors (nit)]

## Cross-refs

- `knowledge/files/src/include/utils/acl.h.md` — defines the AclMode bitmask
  and ACL_ALL_RIGHTS_* this struct refers to.

## Issues

1. [ISSUE-correctness: `InternalGrant.privileges` is mutated in place;
   re-using the struct across objtypes silently wrong (maybe)] —
   `source/src/include/utils/aclchk_internal.h:21`.
2. [ISSUE-audit-gap: `col_privs` AccessPriv nodes echoed in errors before
   name resolution (nit)] —
   `source/src/include/utils/aclchk_internal.h:38`.
