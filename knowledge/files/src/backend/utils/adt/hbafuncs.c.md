# src/backend/utils/adt/hbafuncs.c

## Purpose

Backing C functions for the `pg_hba_file_rules` and `pg_ident_file_mappings`
SQL views — runtime introspection of the parsed `pg_hba.conf` and
`pg_ident.conf` contents, including the line number and parse error of any
unparsable line. Lets DBAs verify their auth config without restarting.

## Role in PG

- Re-tokenizes and re-parses the on-disk files at call time (does NOT
  consult the postmaster's currently-loaded HBA). Practical implication:
  after editing pg_hba.conf but before `pg_reload_conf()`, the view
  shows the new file, but new connections still use the old rules.
- Each row carries `error` text when its line failed to parse, so a
  bad config still produces useful output.

## Key functions

- `get_hba_options(HbaLine *)` (`hbafuncs.c:53-?`) — flattens parsed
  HBA options to a `text[]` array of `"key=value"` strings.
- `fill_hba_line(tuple_store, tupdesc, rule_number, file_name, line_num,
  hbaline, err_msg)` (`:184-?`) — one row per non-comment line.
  Columns include type, database[], user_name[], address, netmask,
  auth_method, options[], error.
- `fill_hba_view(tuple_store, tupdesc)` (`:375-423`) — opens
  `HbaFileName`, tokenizes via `tokenize_auth_file(…, DEBUG3, …)`,
  parses via `parse_hba_line(tok_line, DEBUG3)`. Uses a
  child `AllocSetContext` (`"hba parser context"`,
  `ALLOCSET_SMALL_SIZES`) and deletes it on exit so parse-time
  allocations don't leak (`:396-422`).
- `pg_hba_file_rules(PG_FUNCTION_ARGS)` (`:431-449`) —
  Materialize-mode SRF wrapper.
- `fill_ident_line` / `fill_ident_view` / `pg_ident_file_mappings`
  (`:469-?`) — analogous for `pg_ident.conf`.

## State / globals

None local. Reads `HbaFileName`, `IdentFileName` (GUCs).

## Phase D notes

- **Default ACL** (per `system_views.sql:665-673` and
  `pg_proc.dat:6607` `proacl => '{POSTGRES=X}'`): functions are
  owned by the bootstrap superuser with EXECUTE granted only to the
  owner; the views are `REVOKE ALL FROM PUBLIC`. So out-of-the-box
  only superusers (and any role explicitly granted by a superuser)
  can read this. No predefined-role grant.
- **No password fields exposed**: `pg_hba.conf` has no inline secrets
  by design — passwords for `password` / `md5` / `scram-sha-256`
  methods live in `pg_authid`. `radiussecret` and similar option
  values DO appear in the options[] array (`get_hba_options`
  flattens every option), so a superuser-granted-EXECUTE grantee
  sees the RADIUS shared secret and LDAP bind credentials.
- **Re-tokenize at call time** means a misconfigured running cluster
  can still be inspected after a bad edit — but conversely the view
  doesn't reflect what's *currently authenticating*. Documented
  behaviour but easy to misread.
- Token re-parsing under `DEBUG3` elevel — failures populate
  `tok_line->err_msg` instead of throwing (`:406-407`). Good UX, low
  risk.

## Potential issues

- [ISSUE-info-disclosure: `pg_hba_file_rules.options[]` exposes
  every option value, including `radiussecret`, `ldapbindpasswd`,
  `pamservice`, etc. Default ACL is owner-only, so this requires an
  explicit grant — but the moment an admin says
  `GRANT EXECUTE ON FUNCTION pg_hba_file_rules() TO some_monitor`,
  those secrets leak. No masking applied in C
  (`get_hba_options`). (medium if mis-granted, low by default)]
- [ISSUE-info-disclosure: re-tokenize-at-call exposes the parsed
  contents of `pg_hba.conf` regardless of whether the file has been
  reloaded — this can reveal in-flight admin work-in-progress edits
  (low)]
- [ISSUE-undocumented-invariant: the function does NOT check
  `IsTransactionState()` or similar; calling from a SECURITY DEFINER
  function makes the parsed HBA secrets cross trust boundaries
  (low — by design of the ACL system)]
