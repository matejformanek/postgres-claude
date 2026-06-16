# `utils/usercontext.h` — SwitchToUntrustedUser

**Verified against source pin `4b0bf0788b0`** (path:
`source/src/include/utils/usercontext.h`)

## Role

Two-function wrapper around the
`GetUserIdAndSecContext`/`SetUserIdAndSecContext`/`NewGUCNestLevel`/
`AtEOXact_GUC` sequence used to temporarily run code as a different user
in a "trust-no-one" mode. Created in response to CVE-2023-2454 (search-path
hijacks during maintenance operations like REINDEX / REFRESH MATERIALIZED
VIEW / CREATE INDEX CONCURRENTLY).

## Public API

- `UserContext { save_userid, save_sec_context, save_nestlevel }` —
  `source/src/include/utils/usercontext.h:15-20`.
- `SwitchToUntrustedUser(Oid userid, UserContext *context)` — `:23`.
- `RestoreUserContext(UserContext *context)` — `:24`.

## Invariants

- The triple `{save_userid, save_sec_context, save_nestlevel}` is the
  minimum state needed to undo a switch: current role, sec-context flags
  (`SECURITY_LOCAL_USERID_CHANGE`, `SECURITY_RESTRICTED_OPERATION`,
  etc.), and the GUC nest level for popping any SET that was applied while
  in the untrusted context. [inferred from struct shape, `:17-19`]
- "Untrusted" implies `SECURITY_RESTRICTED_OPERATION` is set, which causes
  any GUC marked `GUC_NOT_WHILE_SEC_REST` to refuse SET. See guc.h `:226`
  `GUC_NOT_WHILE_SEC_REST`. [inferred]
- `RestoreUserContext` MUST be paired with a `SwitchToUntrustedUser` call;
  asymmetric use leaks the security context. [inferred from API shape]

## Notable internals

Header doesn't show implementation, but the design pattern is "save 3
ints, run code, restore 3 ints". The interesting bit is what's *not* saved:
- search_path is restored only via the GUC nest-level pop, not directly.
  So if the called code does `RestoreUserContext` before
  `AtEOXact_GUC`, search_path remains contaminated.
- `current_user` SQL function reads via `GetUserId()` which the switch
  updates, so SQL inside the untrusted block sees the new identity.

## Trust-boundary / Phase D surface

- This is the trust boundary for **maintenance commands run as table owner
  but invoked by a different user** (autovacuum running as bgworker but
  effectively executing functions defined by the table owner). The header
  exposes ZERO documentation of which sec-context bits get set; readers
  have to dig into miscadmin.h and the call sites.
  [ISSUE-documentation: header is mute about which SECURITY_* bits the
  switch applies (likely)]
- `save_sec_context` is an `int` of opaque flags — extension code calling
  `SwitchToUntrustedUser` then doing further `SetUserIdAndSecContext` of
  its own can stack flags incorrectly. [ISSUE-api-shape:
  no nesting guard on UserContext (nit)]
- Pre-CVE-2023-2454, maintenance commands were not wrapped. New
  maintenance-like commands (e.g. a future contrib AM that does heavy work
  as table owner) need to remember to wrap; nothing in the header signals
  this requirement. [ISSUE-defense-in-depth: no compile-time hint that
  "run as table owner" code paths must use SwitchToUntrustedUser (maybe)]
- The patch that introduced this also introduced `RestrictSearchPath()` in
  guc.h `:435` — the two are typically used together but the linkage is
  invisible at the header level. [ISSUE-documentation: linkage to
  `RestrictSearchPath` not documented (nit)]

## Cross-refs

- `knowledge/files/src/include/utils/acl.h.md` —
  `member_can_set_role` is the prerequisite check before
  `SwitchToUntrustedUser` is safe.
- `knowledge/files/src/include/utils/guc.h.md` — `NewGUCNestLevel` /
  `AtEOXact_GUC` / `RestrictSearchPath` are the GUC-side machinery.
- CVE-2023-2454 — the motivating vulnerability.

<!-- issues:auto:begin -->
- [Issue register — `include-utils`](../../../../issues/include-utils.md)
<!-- issues:auto:end -->

## Issues

1. [ISSUE-documentation: header is mute about which SECURITY_* bits
   `SwitchToUntrustedUser` sets (likely)] —
   `source/src/include/utils/usercontext.h:23`.
2. [ISSUE-api-shape: `UserContext` provides no nesting guard for stacked
   sec-context changes (nit)] —
   `source/src/include/utils/usercontext.h:15`.
3. [ISSUE-defense-in-depth: nothing signals to new maintenance-like code
   that it must wrap in SwitchToUntrustedUser (maybe)] —
   `source/src/include/utils/usercontext.h:23`.
4. [ISSUE-documentation: linkage to `RestrictSearchPath` from guc.h is
   invisible (nit)] — `source/src/include/utils/usercontext.h:23`.
