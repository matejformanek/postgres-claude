# usercontext.c

- **Source path:** `source/src/backend/utils/init/usercontext.c`
- **Lines:** 92
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/utils/usercontext.h` (UserContext struct), `init/miscinit.c::Get/SetUserIdAndSecContext`, `utils/misc/guc.c::NewGUCNestLevel`, `utils/adt/acl.c::member_can_set_role`

> Note: the deep-corpus task listed `usermap.c` for this directory; the actual fourth `.c` file under `src/backend/utils/init/` is `usercontext.c`. Documenting the real file.

## Purpose

Two-function helper for "do something briefly as another user". Used by VACUUM/ANALYZE-style maintenance routines and any code that needs to execute SQL or run user-defined functions with a *different* effective userid while preserving the ability to switch back. Encapsulates the SECURITY_RESTRICTED_OPERATION + GUC-nest-level dance that the original userid would otherwise have to write by hand. [from-comment, usercontext.c:3-4]

## Top-of-file comment (verbatim)

> "usercontext.c — Convenience functions for running code as a different database user." [from-comment, usercontext.c:1-13]

## Public surface

- `SwitchToUntrustedUser(Oid userid, UserContext *context)` (33) — switch to `userid`, saving old state into `*context`. Errors with `ERRCODE_INSUFFICIENT_PRIVILEGE` ("role X cannot SET ROLE to Y") if the caller can't `SET ROLE` to the target.
- `RestoreUserContext(UserContext *context)` (87) — undo the switch; if a GUC nest level was created, `AtEOXact_GUC(false, save_nestlevel)` rolls back GUC changes too.

## Key types

- `UserContext { Oid save_userid; int save_sec_context; int save_nestlevel; }` — defined in the matching header; populated by `SwitchToUntrustedUser`. A `save_nestlevel == -1` sentinel means "no nest level was created, just swap back".

## Key invariants

- **Reciprocal SET-ROLE capability decides the security regime.** If `member_can_set_role(userid, save_userid)` returns true (i.e. the target user could also assume the caller's identity), no `SECURITY_RESTRICTED_OPERATION` is imposed — they're symmetric so it's pointless. Otherwise, `SECURITY_RESTRICTED_OPERATION` is set AND a new GUC nest level is created so GUC mutations are rollbackable. [from-comment, usercontext.c:46-77]
- **Caller-side privilege check is mandatory.** `member_can_set_role(save_userid, userid)` checked *before* any state change (line 40-45). If it fails, ereport(ERROR) and `context` is left in a partially-populated but consistent state — the caller must not invoke `RestoreUserContext`.
- **`save_nestlevel == -1` is the "did not create a nest level" sentinel.** Tested in `RestoreUserContext` (line 89) to decide whether to call `AtEOXact_GUC`.
- **Order of restoration: GUC rollback first, then `SetUserIdAndSecContext`.** This matters because `AtEOXact_GUC` may need to read the *current* user's privileges to decide which assign hooks to fire.

## Cross-references

- Consumed by `commands/vacuum.c`, `commands/analyze.c`, `commands/cluster.c`, `commands/indexcmds.c::DefineIndex` — any place where the engine needs to enumerate relations and run owner-defined code (statistics targets, expression indexes, partial-index predicates).
- Builds on `init/miscinit.c::Get/SetUserIdAndSecContext` (the underlying state) and the `SECURITY_RESTRICTED_OPERATION` flag semantics documented in miscinit.c:579-602.
- `member_can_set_role` is in `utils/adt/acl.c` and consults the role-membership graph (pg_auth_members) including `SET` and `INHERIT` options.

## Open questions

- None at the file scope. The semantic question of *which* operations actually need `SECURITY_RESTRICTED_OPERATION` is owned by the callers, not this file.

## Confidence tag tally

`[verified-by-code]=4 [from-comment]=3 [from-readme]=0 [inferred]=1 [unverified]=0`
