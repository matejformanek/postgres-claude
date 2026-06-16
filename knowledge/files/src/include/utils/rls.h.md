# `utils/rls.h` — Row-Level Security check-enable API

**Verified against source pin `4b0bf0788b0`** (path:
`source/src/include/utils/rls.h`)

## Role

Tiny header (50 lines) exporting the single function every planner/executor
site uses to decide whether RLS policies must be applied to a relation:
`check_enable_rls(relid, checkAsUser, noError)`. Also publishes the
`row_security` GUC.

## Public API

- `extern PGDLLIMPORT bool row_security` —
  `source/src/include/utils/rls.h:17`. The session-level GUC. Default `on`.
- `enum CheckEnableRlsResult { RLS_NONE, RLS_NONE_ENV, RLS_ENABLED }` —
  `:41-46`.
- `int check_enable_rls(Oid relid, Oid checkAsUser, bool noError)` — `:48`.

## Invariants

- Three-state return is **load-bearing for plan-cache invalidation**:
  - `RLS_NONE`: no RLS on this relation — plan is environment-independent.
  - `RLS_NONE_ENV`: relation has RLS but the current user bypasses it (e.g.
    BYPASSRLS, table owner, or `row_security=off` with permission). The
    cached plan must be invalidated if any of those facts change.
  - `RLS_ENABLED`: policies apply; plan also must invalidate if env
    changes. [from-comment, `:27-33`]
- `noError == true` returns `RLS_ENABLED` even in the "this user can't see
  the table at all" case — callers use it to "decide if data from the table
  should be passed back" without throwing. [from-comment, `:34-39`]
- `checkAsUser` lets views and security-definer functions check RLS as the
  underlying definer rather than the current user. [inferred from API]

## Notable internals

The three-state result is what makes the planner's plan-cache code
correct in the face of `row_security=off`. A two-state (yes/no) result would
mean a session that flips the GUC and then runs a cached query would keep
running with the *previous* environment.

## Trust-boundary / Phase D surface

- `row_security` is `PGC_USERSET` — any user can flip it to `off`. They
  still need BYPASSRLS or table-owner to actually skip policies, but
  combined with `RLS_NONE_ENV`, this means audit-trail of "RLS was active"
  must track both the GUC and the role attribute at execution time, not
  just plan time. [ISSUE-audit-gap: `row_security=off` toggle visibility
  for audit (maybe)]
- The comment says "noError ... is used by other error cases where we're
  just trying to decide if data from the table should be passed back to the
  user or not" — this is the partition pruning / view-expansion path. A
  reviewer adding a new caller with `noError=true` must understand that it
  short-circuits the "no policy applies" detection into "RLS_ENABLED".
  [ISSUE-api-shape: `noError=true` collapses two distinct states into
  RLS_ENABLED — non-obvious (likely)]
- `check_enable_rls` is the **single** trust boundary for RLS. Any caller
  that reads tuples without first asking it is a bypass.
  [ISSUE-defense-in-depth: no compiler-enforced reminder that table opens
  for SELECT must consult check_enable_rls (nit)]

## Cross-refs

- `knowledge/files/src/include/utils/acl.h.md` — `has_bypassrls_privilege`
  is what `check_enable_rls` consults for the "bypass" branch.
- `knowledge/subsystems/` (not yet documented) — row security policy
  evaluation lives in `src/backend/rewrite/rowsecurity.c`.

<!-- issues:auto:begin -->
- [Issue register — `include-utils`](../../../../issues/include-utils.md)
<!-- issues:auto:end -->

## Issues

1. [ISSUE-api-shape: `noError=true` collapses "no RLS" and "RLS applies"
   into a single RLS_ENABLED return (likely)] —
   `source/src/include/utils/rls.h:34-39`.
2. [ISSUE-audit-gap: `row_security=off` is PGC_USERSET — audit must
   capture execution-time state, not plan-time (maybe)] —
   `source/src/include/utils/rls.h:17`.
3. [ISSUE-defense-in-depth: `check_enable_rls` is the lone trust boundary
   for RLS; no compile-time discipline reminds new code to call it (nit)] —
   `source/src/include/utils/rls.h:48`.
