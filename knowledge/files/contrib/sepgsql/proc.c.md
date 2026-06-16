# proc.c

## One-line summary

`db_procedure` class hooks: per-function labels, `create/install/drop/
relabel/setattr/execute` checks, and the `INSTALL` perm gated on
`proleakproof`.

## Public API / entry points

- `sepgsql_proc_post_create(functionId) → void` —
  `source/contrib/sepgsql/proc.c:36-147`. SnapshotSelf-scan pg_proc, check
  `db_schema:{add_name}` on namespace, compute label from
  (client, namespace_label, DB_PROCEDURE, funcname), check
  `db_procedure:{create [|install]}`, SetSecurityLabel.
- `sepgsql_proc_drop(functionId) → void` — `proc.c:154-189`. Checks
  `db_schema:{remove_name}` then `db_procedure:{drop}`.
- `sepgsql_proc_relabel(functionId, seclabel) → void` —
  `proc.c:197-227`.
- `sepgsql_proc_setattr(functionId) → void` — `proc.c:234-307`. Old-vs-new
  pg_proc compare; namespace move triggers add/remove_name; rename triggers
  schema rename check. **`INSTALL` perm required if `proleakproof` flips
  from false to true** (`proc.c:288-289`).
- `sepgsql_proc_execute(functionId) → void` — `proc.c:314-333`. Checks
  `db_procedure:{execute}`. Called from `hooks.c:277` on
  `OAT_FUNCTION_EXECUTE`.

## Key invariants

- The `INSTALL` permission gates *making a function leakproof*. The
  semantics: a leakproof function can run in contexts where row-security
  quals run early; granting leakproof to attacker code = expanded attack
  surface. SELinux's `db_procedure:{install}` is intended to be a separate
  permission for that. [verified-by-code]
- `SnapshotSelf` is required (proc.c:65) because pg_proc's new tuple isn't
  visible in the current snapshot during the post-create hook.
- Audit name includes the full `schema.func(argtypes)` signature
  (`proc.c:104-118`).

## Notable internals

`sepgsql_proc_post_create` audit_name construction is unusually rich:

```
schema.funcname(argtype1, argtype2, ...)
```

via `getObjectIdentity(&typeObject, false)` per argument (`proc.c:108-118`).
This is the most verbose audit_name in sepgsql — useful for forensics on
function-overload disputes.

`required = SEPG_DB_PROCEDURE__CREATE | (proleakproof ?
SEPG_DB_PROCEDURE__INSTALL : 0)` (`proc.c:120-122`). This is the
**conditional install gate** — creating a leakproof function requires
*both* perms in one check (single AVC lookup, ANDed in `required`).

`sepgsql_proc_setattr` flow (`proc.c:234-307`):

1. Re-read new pg_proc row via SnapshotSelf.
2. Read old pg_proc row via syscache.
3. If namespace changed, do `remove_name + add_name` (BUG below).
4. If name changed, do schema rename.
5. `required = SETATTR | (newly-leakproof ? INSTALL : 0)`.
6. Check on the procedure.

**Apparent bug at proc.c:276-280**: when `newform->pronamespace !=
oldform->pronamespace`, the code calls
`sepgsql_schema_remove_name(oldform->pronamespace)` followed by
`sepgsql_schema_add_name(oldform->pronamespace)`. The second call should
use `newform->pronamespace`. As written, it removes from old and *adds back
to old*, never checking add_name on the new namespace. Compare
`relation.c:678-682` which correctly uses `newform->relnamespace` for the
add. [ISSUE-correctness: proc.c:279 uses oldform->pronamespace where it
should use newform->pronamespace; ALTER FUNCTION ... SET SCHEMA does not
check add_name on the destination schema (confirmed)]

`sepgsql_proc_execute` is the lightest entry point: single AVC check on
`db_procedure:{execute}` against the function's stored label. It's called
*per fmgr-resolved function*, so happens on EVERY function invocation
unless the cache hit suppresses the kernel call.

## Trust boundary / Phase D surface

- **Execute check is per-call.** Every function call resolves via fmgr
  and (when sepgsql is loaded) gates through `OAT_FUNCTION_EXECUTE` →
  `sepgsql_proc_execute`. Cache amortizes this. [verified-by-code]

- **Leakproof install gate.** Granting `proleakproof = true` on a function
  is a privilege-escalation vector for row-security-bypass attacks
  (the function runs with a relaxed leakproof contract). sepgsql's
  `db_procedure:{install}` is the policy-side knob to control which
  callers can install leakproof functions. **A policy that doesn't
  separately constrain `install` from `create` loses this protection.**
  [verified-by-code]

- **`sepgsql_needs_fmgr_hook` (in label.c, calls into this file
  indirectly).** The fmgr_hook + needs_fmgr_hook installation in label.c
  drives the trusted-procedure transition. proc.c's `execute` check is
  separate from the transition machinery — execute happens first
  (via OAT_FUNCTION_EXECUTE), then if the proc is "trusted" the fmgr
  hook fires and does `entrypoint + transition` checks.

- **The proc_setattr namespace-rename bug (above) is a real audit
  gap**: ALTER FUNCTION ... SET SCHEMA = newns is not validated
  against the new schema's `add_name` permission. A user with
  remove_name on the old schema and an existing label permitting
  setattr on the function can move the function into a schema where
  they lack add_name, escaping the policy's namespace boundaries.
  [ISSUE-security: ALTER FUNCTION ... SET SCHEMA bypasses
  destination-schema add_name check due to proc.c:279 typo
  (confirmed)]

- **Function argument types appear in audit_name** but only via
  `getObjectIdentity(&typeObject, false)`. If the type is in a schema
  the user lacks search on, the audit name resolution itself might
  hit a sepgsql check recursively. In practice `getObjectIdentity`
  doesn't trigger sepgsql since it's a catalog lookup.
  [unverified]

- **Bootstrap and internal functions.** `sepgsql_proc_post_create`
  is gated by the dispatcher's `Assert(!is_internal)` on
  ProcedureRelationId (`hooks.c:142`). So internal-created functions
  (e.g., from bootstrap) hit an Assert if sepgsql is loaded.
  In production cassert builds this would PANIC if reached; in
  release builds the Assert is a no-op and an internal-create
  function gets unconditionally labeled and checked. [ISSUE-
  correctness: Assert(!is_internal) on proc post_create depends on
  hooks.c gating; release builds skip the assert, internal proc
  creation triggers full sepgsql labeling (nit)]

- **No language check on CREATE FUNCTION.** The XXX comment at
  `proc.c:86-87` notes "db_language:{implement} also should be
  checked here" — the language permission is *defined* in
  `sepgsql.h` (`SEPG_DB_LANGUAGE__IMPLEMENT`) but never invoked.
  PostgreSQL's pg_language ACL is the only gate. [ISSUE-audit-gap:
  db_language:{implement} is unimplemented; per the XXX comment
  in proc.c:86 (confirmed)]

- **No `pg_aggregate` or `pg_operator` coverage.** Aggregates and
  operators ride on top of pg_proc entries; sepgsql treats them as
  procedures, which is mostly right but misses operator-specific
  semantics. [inferred]

## Cross-references

- hooks.c — `OAT_POST_CREATE/DROP/POST_ALTER/FUNCTION_EXECUTE`
  dispatchers.
- label.c — `sepgsql_needs_fmgr_hook`, `sepgsql_fmgr_hook` (trusted
  procedure transitions).
- uavc.c — permission check funnel.
- `source/src/backend/utils/fmgr/fmgr.c` —
  `OAT_FUNCTION_EXECUTE` invocation.
- `source/src/backend/commands/functioncmds.c` — CREATE / ALTER
  / DROP FUNCTION path.
- `source/src/include/catalog/pg_proc.h` —
  `proleakproof` field.

<!-- issues:auto:begin -->
- [Issue register — `sepgsql`](../../../issues/sepgsql.md)
<!-- issues:auto:end -->

## Issues spotted

- `[ISSUE-security: proc.c:279 typo — namespace-change setattr
  re-adds to old namespace instead of new; ALTER FUNCTION ... SET
  SCHEMA does not check add_name on destination (confirmed)]`
- `[ISSUE-audit-gap: db_language:{implement} permission is defined
  but never checked (XXX comment proc.c:86) (confirmed)]`
- `[ISSUE-correctness: Assert(!is_internal) in dispatcher means
  release builds (no asserts) silently label and check internally-
  created procs (nit)]`
- `[ISSUE-defense-in-depth: aggregates and operators inherit
  pg_proc handling; sepgsql does not distinguish them, so
  policy authors cannot target operator vs procedure separately
  (nit)]`
- `[ISSUE-audit-gap: every function call hits sepgsql_proc_execute
  (via OAT_FUNCTION_EXECUTE); for high-frequency function workloads
  the AVC cache hit rate is critical to performance (nit)]`
