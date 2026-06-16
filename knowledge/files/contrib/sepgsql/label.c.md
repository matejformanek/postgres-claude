# label.c

## One-line summary

Label-provider implementation: client-label management
(getpeercon/sepgsql_setcon/trusted-procedure stack), the
`SEPGSQL_LABEL_TAG = "selinux"` provider hook into `pg_seclabel`, plus
`sepgsql_restorecon` for bulk re-labeling at install time.

## Public API / entry points

- `sepgsql_get_client_label(void) → char *` — `source/contrib/sepgsql/label.c:78-99`.
  The single read-end for "what is my current scontext"; precedence: trusted-proc
  override → uncommitted setcon → committed setcon → peer (`label.c:82-98`).
- `sepgsql_init_client_label(void) → void` — `label.c:402-434`. Called from
  `_PG_init`. Calls `getcon_raw` to seed `client_label_peer` (server label,
  default before authentication), installs `ClientAuthentication_hook`,
  `needs_fmgr_hook`, `fmgr_hook`, and registers xact/subxact callbacks.
- `sepgsql_get_label(classId, objectId, subId) → char *` — `label.c:443-473`.
  Wraps `GetSecurityLabel`; returns "unlabeled" sentinel if the stored label
  fails `security_check_context_raw`.
- `sepgsql_object_relabel(*object, seclabel) → void` — `label.c:480-527`. The
  callback registered as the SEPGSQL_LABEL_TAG provider; validates the label
  with `security_check_context_raw` then dispatches per classId to the
  per-object relabel routines.

SQL-callable functions:

- `sepgsql_getcon() RETURNS text` — `label.c:534-546`. Returns the current
  client label. Returns NULL when sepgsql is disabled.
- `sepgsql_setcon(text) RETURNS bool` — `label.c:553-567`. Switches the client
  label for the current (sub-)transaction; validated via setcurrent +
  dyntransition perm checks (`label.c:130-140`).
- `sepgsql_mcstrans_in(text) RETURNS text` — `label.c:575-605`. MLS/MCS
  translate-in.
- `sepgsql_mcstrans_out(text) RETURNS text` — `label.c:613-643`. MLS/MCS
  translate-out.
- `sepgsql_restorecon(text specfile) RETURNS bool` — `label.c:858-915`. Bulk
  install of initial labels across pg_database/pg_namespace/pg_class/
  pg_attribute/pg_proc. **Superuser-only** (`label.c:876-879`).

Hooks installed:

- `ClientAuthentication_hook = sepgsql_client_auth` — `label.c:421-422`.
- `needs_fmgr_hook = sepgsql_needs_fmgr_hook` — `label.c:425-426`.
- `fmgr_hook = sepgsql_fmgr_hook` — `label.c:428-429`.
- `RegisterXactCallback(sepgsql_xact_callback)` — `label.c:432`.
- `RegisterSubXactCallback(sepgsql_subxact_callback)` — `label.c:433`.

## Key invariants

- `client_label_peer != NULL` after `_PG_init` (`label.c:97`, asserted by
  `sepgsql_get_client_label`). [verified-by-code]
- Precedence of returned label in `sepgsql_get_client_label`: trusted-proc
  func override > pending-setcon top of stack > committed setcon > peer.
  [verified-by-code]
- Pending setcon labels are allocated in `CurTransactionContext`
  (`label.c:146-154`). On abort they vanish with the context; on commit the
  top of the pending stack is `MemoryContextStrdup`'d to `TopMemoryContext`
  as the new `client_label_committed` (`label.c:172-189`). [verified-by-code]
- The `sepgsql_set_client_label` ALWAYS calls
  `sepgsql_avc_check_perms_label(..., SEPG_PROCESS__SETCURRENT, ...,
  abort=true)` followed by `SEPG_PROCESS__DYNTRANSITION` on the new label
  (`label.c:130-140`). Both checks abort on violation. [verified-by-code]
- Subtransaction abort scrubs *only* the labels whose `subid` matches
  (`label.c:208-219`). Commit of a subtransaction promotes pending labels
  to the parent xact (because they remain on the list).
- `sepgsql_object_relabel` only supports four classes: Database, Namespace,
  Relation, Procedure. Other classes raise `ERRCODE_FEATURE_NOT_SUPPORTED`
  (`label.c:520-526`). [verified-by-code]

## Notable internals

`sepgsql_client_auth` (`label.c:228-257`):

1. Call the chained `next_client_auth_hook` first (`label.c:231-232`).
2. If `status != STATUS_OK`, just return — the socket is being closed.
3. Call `getpeercon_raw(port->sock, &client_label_peer)` — peeks SO_PEERCRED
   to derive the connecting process's SELinux label. **Fail-FATAL on
   error** (`label.c:244-247`). The peer label is leaked from libselinux into
   `client_label_peer` directly — never freed (it's per-backend-lifetime).
4. Switch mode INTERNAL → DEFAULT or PERMISSIVE based on the GUC
   (`label.c:253-256`).

`sepgsql_needs_fmgr_hook` (`label.c:266-301`) — called by fmgr to decide if
a function needs the fmgr_hook wrapping (for trusted-proc transitions):

- Returns `true` if `sepgsql_avc_trusted_proc(functionId)` returns a label
  (proc has a transition rule).
- Returns `true` if the proc *would fail* an EXECUTE + ENTRYPOINT check
  (NOAUDIT probe) — the rationale (comment, label.c:284-289) is to force
  the hook to fire so the check happens via the normal execute path, not
  inlined.

`sepgsql_fmgr_hook` (`label.c:309-394`) — the trusted-procedure entry/exit
wrapper:

- FHET_START: allocate a stack frame in `flinfo->fn_mcxt`, fetch the
  transition label, do the `db_procedure:entrypoint` and
  `process:transition` checks (`label.c:346-363`), then swap
  `client_label_func` to the new label.
- FHET_END / FHET_ABORT: restore the previous `client_label_func`.

`sepgsql_xact_callback` (`label.c:163-194`):

- COMMIT: top of pending list becomes `client_label_committed` (copied to
  TopMemoryContext); pending list set to NIL.
- ABORT: pending list set to NIL (memory cleaned by CurTransactionContext
  teardown).

`sepgsql_restorecon` flow (`label.c:858-915`):

- Open a selabel handle (`SELABEL_CTX_DB`) — either the system default or a
  user-supplied spec file path.
- For each of pg_database, pg_namespace, pg_class, pg_attribute, pg_proc:
  systable_beginscan, derive the object name in the form expected by the
  selabel lookup (`quote_object_name` produces a dotted, quoted-identifier
  form), call `selabel_lookup_raw`, then run
  `sepgsql_object_relabel(&object, context)` to do the permission check
  and `SetSecurityLabel(&object, SEPGSQL_LABEL_TAG, context)` to commit.
- Uses `PG_TRY/PG_FINALLY` to `freecon` and `selabel_close`.

## Trust boundary / Phase D surface

- **`sepgsql_setcon` is callable by any user.** The function is not
  superuser-only — instead it's policy-gated via
  `process:setcurrent + process:dyntransition` checks. If the SELinux
  policy lets the user's domain self-transition to any label
  (e.g., `unconfined_t`), then the user can effectively become any
  label *within the policy*. This is the design. [verified-by-code]

- **Trusted-procedure transition is the privilege-escalation path.**
  `sepgsql_fmgr_hook` swaps `client_label_func` *without* checking who
  is calling — only the policy controls whether `process:transition`
  is allowed. A misconfigured policy that grants transition from
  `user_t` to `dbadmin_t` lets the user execute a `dbadmin_t`-labeled
  function and gain that label for its duration. **This is by design but
  load-bearing.** [verified-by-code]

- **`getpeercon_raw` fails FATAL** (`label.c:244-247`). On systems where
  the socket is not a Unix domain socket (e.g., TCP without peer-cred
  forwarding), getpeercon will fail. This effectively requires Unix
  socket connections for sepgsql to work — TCP backends die at
  authentication. [ISSUE-defense-in-depth: TCP-only deployments cause
  every backend to FATAL out on connect — sepgsql is effectively
  Unix-domain-socket-only; documented but easily missed (confirmed)]

- **`client_label_peer` is allocated by libselinux and never freed.**
  `getcon_raw` and `getpeercon_raw` populate the pointer with a malloc'd
  string. The pointer is never `freecon`'d — it lives for the backend
  lifetime. That's a tiny leak (one string per backend) but means
  ASAN/Valgrind will flag it. [ISSUE-memory: client_label_peer from
  getcon/getpeercon is never freecon'd; tiny leak per backend (nit)]

- **`sepgsql_restorecon` is superuser-only** (`label.c:876-879`).
  Good. It's also the only documented way to (re-)label the catalog en
  masse. But it also *bypasses* normal labeling-permission checks —
  wait, actually it doesn't: `exec_object_restorecon` calls
  `sepgsql_object_relabel(&object, context)` (`label.c:820`) which
  enforces the standard `db_xxx:{setattr relabelfrom relabelto}`
  checks against the current scontext (which is superuser's label).
  So an admin who is `sepgsql_admin_t` can restorecon, but
  `user_t` cannot escalate via this. [verified-by-code]

- **`sepgsql_object_relabel` registered as the provider for "selinux"
  tag.** Any `SECURITY LABEL FOR selinux ON ... IS ...` command lands
  here. The per-class dispatcher rejects unsupported classes
  (`label.c:520-526`) — extension types, languages, etc. cannot be
  labeled by sepgsql. [verified-by-code]

- **`sepgsql_get_label` returns "unlabeled" for invalid stored labels**
  (`label.c:444-471`). If `pg_seclabel` has a row with a malformed
  label string (perhaps from a policy that no longer parses the format),
  the label silently becomes "unlabeled" rather than raising. Decisions
  on unlabeled tcontext default to the `unlabeled` domain's rules —
  potentially over- or under-permissive. [ISSUE-correctness: malformed
  stored labels silently degrade to "unlabeled"; admins may not notice
  policy drift broke a row (likely)]

- **Subtransaction commit promotes pending labels** — but the
  `sepgsql_subxact_callback` (`label.c:202-219`) handles ONLY abort,
  not commit. On COMMIT of a subxact, the labels stay on the pending
  list with their now-defunct `subid`. They will be promoted by the
  next outer-xact commit. This is correct but subtle.

- **No invalidation of uavc cache on `sepgsql_setcon`.** Switching the
  client label changes the scontext used in future checks; the cache
  is keyed on (s,t,class), so old entries (different scontext) remain
  in the cache and won't be hit. No correctness issue, just memory.
  [verified-by-code]

- **`client_label_func` (trusted-proc) is not stacked beyond a single
  level via the `stack->old_label` field**, but FHET_START allocates
  a fresh stack per call via `palloc` (`label.c:328-329`) — so nested
  trusted-proc calls *do* nest via the per-call frame, just stored on
  the `private` Datum of the inner fmgr call. The single `client_label_func`
  global is a stack of one, written by the outermost active frame.
  [verified-by-code]

- **`sepgsql_mcstrans_in/out` errors raise ERRCODE_INTERNAL_ERROR** on
  libselinux failure (`label.c:592, 630`). Fail-closed via ereport.

- **Authentication-only mode flip.** Once a backend transitions
  INTERNAL → DEFAULT (or PERMISSIVE) at authentication, no subsequent
  reload re-runs `sepgsql_client_auth`. A `sepgsql.permissive` change
  thus does not affect existing backends. (Cross-ref selinux.c finding.)

## Cross-references

- `source/src/backend/libpq/auth.c` — invokes `ClientAuthentication_hook`.
- `source/src/backend/utils/fmgr/fmgr.c` — drives `needs_fmgr_hook` and
  `fmgr_hook` around function calls.
- `source/src/backend/access/transam/xact.c` — drives
  `RegisterXactCallback`/`RegisterSubXactCallback`.
- `source/src/backend/commands/seclabel.c` — multi-provider label dispatch;
  `SetSecurityLabel`, `GetSecurityLabel`, `register_label_provider`.
- uavc.c — `sepgsql_avc_check_perms_label`, `sepgsql_avc_trusted_proc`.
- libselinux: `getcon_raw`, `getpeercon_raw`, `security_check_context_raw`,
  `security_get_initial_context_raw`, `selinux_trans_to_raw_context`,
  `selinux_raw_to_trans_context`, `selabel_open`, `selabel_lookup_raw`,
  `selabel_close`.

<!-- issues:auto:begin -->
- [Issue register — `sepgsql`](../../../issues/sepgsql.md)
<!-- issues:auto:end -->

## Issues spotted

- `[ISSUE-defense-in-depth: TCP connections fail FATAL at
  ClientAuthentication because getpeercon_raw cannot derive a peer
  label; sepgsql is effectively Unix-socket-only (confirmed)]`
- `[ISSUE-memory: client_label_peer (and ncontext leaks elsewhere) are
  per-backend lifetime strings from libselinux that are never freecon'd
  (nit)]`
- `[ISSUE-correctness: invalid stored labels silently degrade to
  "unlabeled" via sepgsql_get_label (label.c:454-470); silent
  policy-drift signal (likely)]`
- `[ISSUE-security: sepgsql_setcon is callable by any user — policy
  controls the transition; misconfigured policy = privilege escalation
  vector (by design but load-bearing) (confirmed)]`
- `[ISSUE-security: parallel workers and other bgworkers run with
  client_label_peer = server's getcon_raw label, no
  ClientAuthentication_hook fires for them, so mode stays INTERNAL —
  silently non-enforcing and non-auditing (confirmed; cf hooks.c
  comment at label.c:407-413)]`
- `[ISSUE-audit-gap: sepgsql_setcon does not emit an audit record of
  its own beyond the setcurrent/dyntransition checks; an attacker
  switching labels in a tight loop leaves only AVC audit entries (nit)]`
- `[ISSUE-correctness: sepgsql_subxact_callback handles SUBXACT_ABORT
  but not SUBXACT_COMMIT — pending labels remain on the list under the
  parent's subid, which is the intent but undocumented (nit)]`
- `[ISSUE-defense-in-depth: sepgsql_restorecon is the only way to
  initialize labels en masse; if it's never called after initdb,
  every object has NULL label which sepgsql_get_label downgrades to
  "unlabeled" — admin can run a "sepgsql-enabled" cluster with no
  effective labels (likely)]`
- `[ISSUE-error-handling: getcon_raw failure in _PG_init aborts the
  postmaster — sepgsql in shared_preload_libraries can prevent server
  start on hosts where SELinux is sort-of-enabled but getcon fails
  (nit)]`
- `[ISSUE-audit-gap: sepgsql_setcon, sepgsql_restorecon, and the
  trusted-procedure transitions all happen without a dedicated audit
  category — they leak into the standard PG log under their
  respective AVC audit lines, but no "label changed" log line exists
  (nit)]`
- `[ISSUE-defense-in-depth: client_label_committed is updated only at
  xact commit, but trusted-procedure label override
  (client_label_func) is process-global; if a trusted proc is called
  inside a subtransaction that aborts, client_label_func is restored
  by FHET_ABORT — but if the backend dies mid-procedure, the global
  leaks at backend exit (nit)]`
- `[ISSUE-api-shape: sepgsql_setcon takes text and stores nothing
  about who called it or when — the pending label list does not
  record subid for client visibility (nit)]`
