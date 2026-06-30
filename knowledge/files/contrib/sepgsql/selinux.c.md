# selinux.c

## One-line summary

The libselinux facade: maintains `selinux_catalog[]` (internal class/AV codes
↔ kernel-side names), wraps `security_compute_av_flags_raw` and
`security_compute_create_name_raw`, holds the global `sepgsql_mode`, and emits
formatted audit records.

## Public API / entry points

- `sepgsql_is_enabled(void) → bool` — `source/contrib/sepgsql/selinux.c:615-619`.
- `sepgsql_get_mode(void) → int` — `selinux.c:624-628`.
- `sepgsql_set_mode(int) → int` — `selinux.c:633-641`, returns previous mode.
- `sepgsql_getenforce(void) → bool` — `selinux.c:650-658`. Returns true *only*
  if `sepgsql_mode == SEPGSQL_MODE_DEFAULT && selinux_status_getenforce() > 0`.
  This is the central "is this query actually enforcing" predicate. [verified-by-code]
- `sepgsql_audit_log(denied, enforcing, scontext, tcontext, tclass, audited,
  audit_name) → void` — `selinux.c:677-723`. Emits one `LOG`-level message per
  audited decision.
- `sepgsql_compute_avd(scontext, tcontext, tclass, *avd) → void` —
  `selinux.c:738-818`. The kernel-call wrapper; computes both `allowed` and
  `auditallow/auditdeny` bitmasks.
- `sepgsql_compute_create(scontext, tcontext, tclass, objname) → char *` —
  `selinux.c:841-888`. Computes a default label for a new object via
  `security_compute_create_name_raw`.

No SQL-callable functions in this file.

## Key invariants

- `tclass < SEPG_CLASS_MAX` is asserted before any `selinux_catalog[tclass]`
  index — `selinux.c:692, 751-752, 853`. [verified-by-code]
- `tclass == selinux_catalog[tclass].class_code` is asserted in
  `sepgsql_compute_avd` (`selinux.c:752`) — the table must be ordered by
  class_code. [verified-by-code]
- `sepgsql_mode` defaults to `SEPGSQL_MODE_INTERNAL` (`selinux.c:610`). This is
  the *pre-authentication* default: bgworkers, autovacuum, and the brief window
  between fork and ClientAuthentication run in INTERNAL mode (no audit, no
  enforcement). After authentication, mode is bumped to DEFAULT or PERMISSIVE
  per the `sepgsql.permissive` GUC (`label.c:253-256`). [verified-by-code]
- `sepgsql_compute_avd` failure mode on unknown class:
  `tclass_ex = string_to_security_class(class_name)`; if 0 ("policy doesn't
  know this class"), fall back to either *all-allowed* or *all-denied*
  depending on `security_deny_unknown()` (`selinux.c:757-771`). [verified-by-code]

## Notable internals

`selinux_catalog[]` is a static array of `{ class_name, class_code, av[32] }`
records (`selinux.c:39-600`). It is consumed two ways:

1. By `sepgsql_compute_avd` to translate internal codes → libselinux external
   codes: `string_to_security_class(class_name)` then loop over `av[].av_name`
   doing `string_to_av_perm`.
2. By `sepgsql_audit_log` to format the bit pattern back to a human-readable
   `denied { select update }` form.

The translation is bit-position-coupled: `selinux_catalog[tclass].av[i]`'s
`av_code` must equal `(1 << i)` *or the audit log will misname permissions*.
Inspecting the table confirms each entry uses positional bits matching the
header macros (e.g., `db_table:select` at index 6 has code `1<<6` =
`SEPG_DB_TABLE__SELECT`).

`sepgsql_compute_avd` flow on success:

1. Call `security_compute_av_flags_raw` (`selinux.c:777-784`). If it errors
   (`< 0`), `ereport(ERROR, ...)` with `ERRCODE_INTERNAL_ERROR`. **Fail
   closed** — the query aborts; no AVD is returned.
2. Iterate over `selinux_catalog[tclass].av[]`. For each named permission,
   resolve to kernel code; if `string_to_av_perm` returns 0 (permission
   unknown to current policy), fall back to `deny_unknown` semantics.
3. Translate bits via OR; populate `avd->allowed`, `avd->auditallow`,
   `avd->auditdeny`.

`sepgsql_compute_create` wraps `security_compute_create_name_raw`. On error
`ereport(ERROR)` (fail closed). On success it uses `PG_TRY/PG_FINALLY` to
ensure `freecon(ncontext)` runs even if the inner `pstrdup` throws
(`selinux.c:877-885`). This is a textbook libselinux memory-handover pattern.

Audit log format (`selinux.c:697-721`):

```
SELinux: denied|allowed { perm1 perm2 ... } scontext=... tcontext=... tclass=... name="..." permissive=0|1
```

This is the same format Linux kernel SELinux uses for kaudit messages, by
design — `ausearch` and `audit2allow` can consume it.

## Trust boundary / Phase D surface

- **`sepgsql_getenforce()` is the central enforcement gate.**
  `selinux.c:650-658`. The conjunction is critical: *both* sepgsql_mode must
  be DEFAULT *and* the OS-level setenforce must be enabled. A root user on
  the host can `setenforce 0` to put the whole cluster in non-enforcing mode
  without touching any DB state. **DB-side defenders cannot detect this**
  except by audit records noting `permissive=1`. [verified-by-code]

- **Fail-closed on libselinux error in `sepgsql_compute_avd`**
  (`selinux.c:780-784`). Good. The whole `ereport(ERROR)` blows away the
  transaction. [verified-by-code]

- **Fail-OPEN on unknown class** (`selinux.c:757-771`) unless
  `security_deny_unknown()` is positive. A misconfigured policy that lacks
  any of `db_table/db_schema/db_database/db_procedure/db_column/db_blob/
  db_language/db_view/db_sequence/db_tuple` will silently allow access for
  that class. Mitigation: `security_deny_unknown` is normally `1` on RHEL
  policies, but a custom policy could disable it. [ISSUE-security:
  fail-open on unknown class is the only behavior when
  `security_deny_unknown() == 0` — practical attack requires control of
  policy (maybe)]

- **`security_compute_av_flags_raw` permission failure path also fail-closed**
  but raises `ERRCODE_INTERNAL_ERROR` rather than `INSUFFICIENT_PRIVILEGE`,
  which is fine semantically but confusing for the user: they see "SELinux
  could not compute av_decision" with errno from libselinux. [ISSUE-error-handling:
  ERRCODE_INTERNAL_ERROR for SELinux-side failures means clients cannot
  distinguish "policy bug" from "denied" via SQLSTATE (nit)]

- **No retry on libselinux transient errors.** `compute_avd` errors flow
  straight up; if libselinux returns -1 due to a transient mmap state, the
  query just aborts. The `do {} while (!sepgsql_avc_check_valid())` retry
  loop in uavc.c covers policy-reload races, but does not cover transient
  libselinux call failures. [verified-by-code]

- **`sepgsql_mode` is process-local.** Each backend has its own
  `sepgsql_mode`. A `sepgsql.permissive` reload sets the *GUC*; the actual
  mode flip from INTERNAL → DEFAULT/PERMISSIVE happens once at
  authentication (`label.c:253-256`). Subsequent reloads do not re-run the
  authentication hook — so a *post-authentication* `pg_reload_conf()` does
  *not* downgrade an already-DEFAULT backend to PERMISSIVE. Verified by
  noting only `sepgsql_client_auth` calls `sepgsql_set_mode` outside of
  `_PG_init`. [ISSUE-defense-in-depth: sepgsql.permissive GUC change after
  authentication does not take effect on existing backends — admin
  expectations may be wrong; new backends get the new value, existing
  ones do not (likely)]

- **Audit log goes through `ereport(LOG, ...)`** (`selinux.c:722`). Subject
  to `log_min_messages`, `log_destination`, etc. If `log_min_messages =
  WARNING` (default for DBA-set installations), audit records are dropped.
  [ISSUE-audit-gap: SELinux audit emitted at LOG level — if
  log_min_messages is set above LOG, audit records vanish; sepgsql does
  not detect this (confirmed)]

- **`sepgsql_set_mode` is unguarded.** Anyone who can call into selinux.c
  can flip the mode. It's only called by `_PG_init` and
  `sepgsql_client_auth`, but lack of an internal guard means a future
  contributor could expose it. [ISSUE-api-shape: sepgsql_set_mode is
  externally linkable and has no caller-class restriction; relies entirely
  on convention (nit)]

- **`selinux_catalog[]` ordering coupling.** The `selinux.c:752` Assert
  catches the case where `selinux_catalog[X].class_code != X`. There is no
  matching Assert for AV entries being in `(1<<i)` order. A bit-shift typo
  in the header would manifest as wrong audit text but possibly
  *correct* enforcement (because the same bits round-trip through
  `string_to_av_perm`). [verified-by-code]

## Cross-references

- libselinux: `security_compute_av_flags_raw`,
  `security_compute_create_name_raw`, `string_to_security_class`,
  `string_to_av_perm`, `selinux_status_getenforce`, `security_deny_unknown`.
- uavc.c — the only consumer of `sepgsql_compute_avd`.
- label.c — the only consumer of `sepgsql_compute_create` (via uavc).

<!-- issues:auto:begin -->
- [Issue register — `sepgsql`](../../../issues/sepgsql.md)
<!-- issues:auto:end -->

## Issues spotted

- `[ISSUE-security: unknown-class fallback is fail-open unless
  security_deny_unknown() > 0 (selinux.c:757-771) (maybe)]`
- `[ISSUE-defense-in-depth: sepgsql.permissive GUC reload does not affect
  existing backends — sepgsql_set_mode only called at _PG_init and
  client_auth (likely)]`
- `[ISSUE-audit-gap: audit emitted at LOG level; if log_min_messages is
  set above LOG, audit records are silently dropped (confirmed)]`
- `[ISSUE-error-handling: ERRCODE_INTERNAL_ERROR for SELinux call failures
  blends "policy unknown" with "denied" from the client's POV (nit)]`
- `[ISSUE-correctness: selinux_catalog[X].av[i] entries must satisfy
  av_code == (1 << i) for audit text to be correct; no Assert enforces
  this (nit)]`
- `[ISSUE-api-shape: sepgsql_set_mode is externally linkable with no
  internal access control; convention-only (nit)]`
- `[ISSUE-defense-in-depth: SEPGSQL_MODE_INTERNAL is silently
  non-enforcing AND silently non-auditing — bgworkers (autovacuum) thus
  run unmonitored with server label as scontext; intentional but worth a
  big warning (maybe)]`
- `[ISSUE-error-handling: no retry on transient libselinux errors from
  security_compute_av_flags_raw — only policy-reload races are retried,
  in uavc.c (nit)]`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-sepgsql.md](../../../subsystems/contrib-sepgsql.md)
