---
path: src/backend/libpq/hba.c
anchor_sha: 4b0bf0788b0
loc: 2951
depth: deep
---

# hba.c

- **Source path:** `source/src/backend/libpq/hba.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 2951

## Purpose

The pg_hba.conf parser AND the runtime match engine. Reads
`HbaFileName` (and any `@`-included or `include`/`include_dir`
sub-files) into a list of `HbaLine` records held in
`parsed_hba_context`, and given an incoming `Port *` walks that list
top-to-bottom to pick the *first* matching record. Also owns the
parallel pg_ident.conf parser + match engine for username-mapping. The
file is the load-bearing surface for "who is allowed to connect, and
how do we challenge them." [from-comment, hba.c:1-15]

## Public API surface

| Line | Symbol | Semantics |
|---|---|---|
| 2452 | `load_hba(void) → bool` | Re-parse `pg_hba.conf` into `parsed_hba_lines`. Atomically swap-or-keep on parse error. Called on postmaster start + SIGHUP. |
| 2338 | `check_hba(Port *port)` | Set `port->hba` to the first matching `HbaLine` or to a synthetic `uaImplicitReject` if no line matches. **The default-deny gate.** |
| 2935 | `hba_getauthmethod(Port *port)` | One-line wrapper around `check_hba` — what `auth.c` actually calls. |
| 2948 | `hba_authname(UserAuth)` | Stringify a `UserAuth` enum via the `UserAuthName[]` table (matched by a `StaticAssertDecl`). |
| 2846 | `load_ident(void) → bool` | Re-parse `pg_ident.conf` into `parsed_ident_lines`. |
| 2791 | `check_usermap(usermap_name, pg_user, system_user, case_insensitive) → STATUS_OK/STATUS_ERROR` | Walk `parsed_ident_lines`; NULL/empty usermap means "system_user must equal pg_user". |
| 687 | `tokenize_auth_file(filename, file, **tok_lines, elevel, depth)` | The lexer. Reused by reload SQL views (`pg_hba_file_rules`). |
| 593 / 568 | `open_auth_file` / `free_auth_file` | Owned file-open helpers; track depth for `@`-recursion. |

## Internal landmarks

### Globals (file-static)
- `tokenize_context` (80) — `MemoryContext` for the raw
  `TokenizedAuthLine` list. Created at depth 0; lives only during a
  parse. [verified-by-code, hba.c:75-80]
- `parsed_hba_lines` / `parsed_hba_context` (86-87) — the current,
  *active* HBA. Swapped under postmaster lock by `load_hba`.
  [verified-by-code, hba.c:82-87]
- `parsed_ident_lines` / `parsed_ident_context` (93-94) — same for ident.
- `UserAuthName[]` (102-119) — string table matching the `UserAuth`
  enum in `hba.h`. `StaticAssertDecl` (124) catches mismatches at
  compile time. **If you add a UserAuth value, you MUST add to this
  table or the build breaks.** [verified-by-code, hba.c:102-125]

### Token helpers (140-360)
- `pg_isblank` (140) — ASCII-only `isblank()`. Rejects high-bit chars
  via `IS_HIGHBIT_SET` to avoid locale-dependent classification.
  [verified-by-code, hba.c:140-145]
- `next_token` (182) — the lexer. Single-pass; handles `"..."` quoting
  (two `""` for literal quote), `#` comment-to-EOL outside quotes,
  comma-terminated fields, blank/EOL termination. Tracks
  `initial_quote` so that `@x` (file include) and `"@x"` (literal) are
  distinguishable. The "only possible error condition is lack of
  terminating quote" is NOT detected — the lexer silently slurps to
  EOL. [from-comment, hba.c:155-181] [verified-by-code, hba.c:182-249]
- `AuthToken` struct (in hba.h) carries `string`, `quoted`, `regex`.
  `make_auth_token` (255) palloc0s struct + string in one block.
  Convenience macros:
  - `token_has_regexp(t)` → `t->regex != NULL`
  - `token_is_member_check(t)` → `!t->quoted && t->string[0] == '+'`
    (i.e. role group-membership check)
  - `token_is_keyword(t, k)` → unquoted exact match (case-SENSITIVE!)
  - `token_matches(t, k)` → strcmp on `t->string`
  - `token_matches_insensitive(t, k)` → `pg_strcasecmp` [verified-by-code, hba.c:69-73]
- Regex compilation: a token beginning with `/` is treated as a
  POSIX ERE (`pg_regcomp(... REG_ADVANCED, C_COLLATION_OID)`); UTF-8
  via `pg_mb2wchar_with_len`. [verified-by-code, hba.c:298-336]

### File inclusion (415-555)
- `next_field_expand` (377) recognises `@filename` (unquoted) and
  recurses through `tokenize_expand_file`.
- `tokenize_include_file` (435) handles the `include` /
  `include_if_exists` / `include_dir` record forms; `missing_ok` for
  `include_if_exists`.
- `AbsoluteConfigLocation` resolves the include path relative to the
  *outer* file's directory.
- Depth tracking via `CONF_FILE_START_DEPTH` (in `utils/conffiles.h`)
  guards against infinite include loops.

### Match engine

`check_hba` (2338) is the engine. Per `HbaLine`, in order:

1. **conntype gate.** `ctLocal` ↔ `AF_UNIX`; otherwise `ctHostSSL` /
   `ctHostNoSSL` / `ctHostGSS` / `ctHostNoGSS` filter on
   `port->ssl_in_use` and `port->gss->enc`. A plain `host` matches both
   SSL and non-SSL. [verified-by-code, hba.c:2352-2387]
2. **IP gate.** `ipCmpAll` (matches anything), `ipCmpSameHost` /
   `ipCmpSameNet` (delegates to `check_same_host_or_net` →
   `pg_foreach_ifaddr`), `ipCmpMask` (hostname → `check_hostname` with
   forward+reverse confirmation, or numeric → `check_ip` =
   `pg_range_sockaddr`). [verified-by-code, hba.c:2389-2418]
3. **database gate.** `check_db` (989) — keyword `all`, `sameuser`,
   `samegroup`/`samerole` (current pg_user is a member of role named
   after dbname), `replication` (only physical walsenders match it;
   non-walsenders skip past replication keyword); regex; literal.
   [verified-by-code, hba.c:988-1030]
4. **role gate.** `check_role` (950) — `+groupname` for membership
   (via `is_member_of_role_nosuper`, so a superuser is NOT
   automatically considered a member), keyword `all`, regex, optional
   case-insensitive literal. [verified-by-code, hba.c:949-979]

If all four match, `port->hba = hba; return;`. Else the loop falls off
the end and a synthetic `HbaLine` with `auth_method = uaImplicitReject`
is allocated. **This is the default-deny guarantee.** [verified-by-code, hba.c:2434-2438]

### Hostname matching
- `hostname_match` (1054) — leading `.` means suffix match (e.g.
  `.example.com` matches `host.example.com`); otherwise exact
  case-insensitive. [verified-by-code, hba.c:1054-1068]
- `check_hostname` (1074) — caches result in
  `port->remote_hostname_resolv` per backend (-2 = error remembered,
  -1 = forward verify failed, +1 = forward verify succeeded). Reverse
  lookup → forward lookup → IP-equality round-trip ("forward
  confirmation"). If forward doesn't match, log a `DEBUG2` and reject.
  [verified-by-code, hba.c:1074-1159]

### `parse_hba_line` (1324) — the per-line decoder

A 670-line state machine that pulls fields one at a time:

1. conntype keyword (1346-1429) — encodes the SSL/GSS variants by
   examining `token->string[4]` (the character after "host"). Builds
   under `#ifdef USE_SSL` / `#ifdef ENABLE_GSS` else emits "cannot
   match because … is not supported" parse error.
2. database list (1432-1454) — regex-compiles `/`-prefixed tokens.
3. role list (1457-1479) — same.
4. for non-local: IP/hostname/CIDR (1481-1666). `pg_getaddrinfo_all`
   with `AI_NUMERICHOST`; on `EAI_NONAME`, treat as hostname instead.
   Separate netmask field allowed only when no CIDR slash present.
5. auth method (1669-1772). Each `#ifndef ENABLE_*` arm leaves
   `unsupauth` set so the error is "not supported by this build"
   rather than "invalid".
6. **The `ident` → `peer` rewrite** (1774-1780): "When using ident on
   local connections, change it to peer, for backwards compatibility."
   Marked `XXX:` in the comment — long-standing wart. [from-comment, hba.c:1774-1777]
7. Auth-method × conntype validity matrix (1782-1820): `gss` not on
   local, `peer` only on local, `cert` only on `hostssl`.
8. The auth-options loop (after line 1820) delegates to
   `parse_hba_auth_opt` (2000) which validates per-method options via
   the `INVALID_AUTH_OPTION` / `REQUIRE_AUTH_OPTION` /
   `MANDATORY_AUTH_ARG` macros (1240-1276).

### `parse_ident_line` (2558) → `IdentLine` (usermap, system_user,
pg_user). `check_ident_usermap` (2626) supports regex-based
`system_user` with `\1` back-substitution into `pg_user` — used for
"strip the realm from kerberos principals" patterns.
[verified-by-code, hba.c:2643-2773]

## Invariants & gotchas

- **Default-deny is `check_hba`'s "fall off the end" clause.** If you
  add a new conntype/method, make sure no path silently `return;`s
  without setting `port->hba`. The synthetic `uaImplicitReject` is the
  only safety net. [verified-by-code, hba.c:2434-2438]
- **First-match wins; order matters.** The loop in `check_hba` does
  NOT continue after a match. Therefore a `reject` line earlier in the
  file overrides a `trust` later — and vice versa. There's no built-in
  warning for shadowed lines. [verified-by-code, hba.c:2347-2432]
- **Mixed case-sensitivity.** Token keywords (`all`, `sameuser`,
  `host`, `local`, …) use `strcmp` — case-SENSITIVE. Auth methods use
  `strcmp` — case-sensitive. But `token_matches_insensitive` is used
  for role matches only when the auth method opts in via
  `case_insensitive` arg to `check_role`, and for `hostname_match`
  always. Inconsistent enough that a careless reader will guess wrong.
  [verified-by-code, hba.c:71-73, 970-973, 1064-1067]
- **`ident` on local sockets is silently rewritten to `peer`.** A
  config audit that greps for `peer` won't find the lines that say
  `ident` but behave as `peer`. Marked `XXX` in the source. [from-comment, hba.c:1774-1777]
- **Group membership is "nosuper".** `is_member` uses
  `is_member_of_role_nosuper` — a superuser is NOT automatically a
  member of every group for HBA purposes. So `+admins` does what you
  want even when the user is also a superuser. [from-comment, hba.c:933-938]
- **`replication` keyword is mode-coupled.** Physical replication
  walsenders only match a `replication` database keyword and nothing
  else; non-walsenders match anything except `replication`. Logical
  decoding walsenders (`am_db_walsender`) match like ordinary
  connections. [verified-by-code, hba.c:997-1020]
- **Hostname forward-confirmation cached per backend.**
  `port->remote_hostname_resolv` is set on first check and reused. If
  DNS changes mid-session, the cached verdict sticks until backend
  exit. Cache is a per-backend field, no cross-backend sharing.
  [verified-by-code, hba.c:1109-1158]
- **Regex compilation uses `C_COLLATION_OID`.** So regex matches are
  locale-independent (good for stability), but `[[:alpha:]]` is the C
  locale's notion. Documented. [verified-by-code, hba.c:316]
- **The lexer silently swallows unterminated quotes.** "The only
  possible error condition is lack of terminating quote, but we
  currently do not detect that, but just return the rest of the line"
  — explicit in the comment. So `host all "alice db all 0.0.0.0/0
  trust` (missing close quote) eats the rest of the line as part of
  the role token. [from-comment, hba.c:176-178]
- **`load_hba` is atomic-or-keep-old.** Any parse error → keep the
  previously-loaded `parsed_hba_lines`. Postmaster startup is FATAL
  only because the caller of `load_hba` in postmaster init treats
  `false` as fatal; SIGHUP just keeps the old config. [from-comment, hba.c:2443-2450]
- **Empty file = reject all.** "A valid HBA file must have at least
  one entry; else there's no way to connect to the postmaster." So an
  empty pg_hba.conf is treated as a parse error. [from-comment, hba.c:2505-2517]
- **Ident regex back-substitution `\1` rewrites a literal token.** The
  expanded `pg_user` is marked `quoted=true` so it can never trigger
  `all` / `+group` / regex special-handling. [from-comment, hba.c:2727-2731]
- **The macros `INVALID_AUTH_OPTION` / `REQUIRE_AUTH_OPTION` /
  `MANDATORY_AUTH_ARG` `return false`** — they're not just logging
  macros, they exit the caller. Reading `parse_hba_auth_opt` (2000)
  requires holding that in mind. [from-comment, hba.c:1227-1238]
- **`tokenize_context` is shared across the whole parse.** Per-line
  errors don't free per-line allocations; only `MemoryContextDelete`
  at end of `load_hba` cleans up. Noted by comment "Note: this
  function leaks memory when an error occurs." in `parse_ident_line`.
  [from-comment, hba.c:2553-2555]

## Cross-refs

- Header: `source/src/include/libpq/hba.h` (HbaLine, AuthToken,
  UserAuth enum, IPCompareMethod, ConnType)
- Match engine consumed by: `source/src/backend/libpq/auth.c`
  (`ClientAuthentication` switches on `port->hba->auth_method`)
- Helpers used: `source/src/backend/libpq/ifaddr.c` (range/CIDR/iface),
  `source/src/common/ip.c` (getaddrinfo wrappers),
  `source/src/backend/utils/adt/regexp.c` (pg_regcomp/pg_regexec)
- Reload trigger: `source/src/backend/postmaster/postmaster.c`
  (SIGHUP → `ProcessConfigFile` → `load_hba` / `load_ident`)
- SQL view: `source/src/backend/utils/adt/hbafuncs.c` exposes the
  parsed state via `pg_hba_file_rules` and `pg_ident_file_mappings`

## Potential issues

- **[ISSUE-correctness: lexer silently accepts unterminated quote]**
  `hba.c:176-178` — top-of-`next_token` comment admits the bug.
  Effect: `host all "admin db all trust` (typo) eats `db all trust`
  as the role token, matches no role, line silently doesn't match
  what the admin meant. severity: maybe
- **[ISSUE-correctness: first-match silently shadows]** `hba.c:2347-2432`
  — no warning when a later line is unreachable due to an earlier
  match. A typical foot-gun is `host all all 0/0 reject` *above* the
  intended `hostssl ... cert` line. severity: maybe
- **[ISSUE-undocumented-invariant: case-sensitivity matrix]**
  `hba.c:71-73, 1064-1067` — keywords case-sensitive, hostnames
  case-insensitive, role literals depend on per-method
  `case_insensitive` flag (e.g. `ldap` sets it). Worth a corpus doc
  cross-reference once this lands. severity: nit
- **[ISSUE-question: ident-rewrite-to-peer hides config intent]**
  `hba.c:1775-1780` — the `XXX:` comment is decades old; in a config
  audit, a literal `ident` line behaves as `peer` and operators may
  not realise. A LOG-level "rewriting `ident` to `peer` on local
  socket" would be friendlier than silent rewrite. severity: maybe
- **[ISSUE-leak: parse_ident_line leaks on error]** `hba.c:2553-2555`
  — explicitly acknowledged by comment. The "caller is expected to
  have set a memory context that will be reset" contract is fragile;
  any new caller must replicate it. severity: nit
- **[ISSUE-correctness: hostname forward-confirmation cached too
  aggressively]** `hba.c:1109-1158` —
  `port->remote_hostname_resolv == +1` is set once and never
  re-checked. A connection that survives DNS rotation effectively
  bypasses revoked-hostname HBA changes. Per-backend cache so blast
  radius is limited to one long-lived session. severity: maybe
- **[ISSUE-correctness: empty-file = reject all but only logs on
  reload]** `hba.c:2505-2517` — emits ERRCODE_CONFIG_FILE_ERROR
  `configuration file "..." contains no entries`. On postmaster
  startup this is FATAL; on SIGHUP reload the old config is kept (so
  no actual outage). Good behaviour, but the admin's reload "succeeds
  silently" with stale config — they may not realise. severity: nit
- **[ISSUE-undocumented-invariant: token_is_member_check requires
  `!quoted`]** `hba.c:70` — `+admin` is a group check, `"+admin"` is
  a literal role name. Not surfaced anywhere except this macro
  definition; a typo `+"admin"` (quote in wrong place) silently
  becomes a literal lookup for role `+admin` which fails. severity: nit
- **[ISSUE-correctness: cert auth-method check requires hostssl,
  but `hostgssenc` does not check for certificate]** `hba.c:1813-1820`
  — `cert` is restricted to `hostssl` only. Worth checking that
  `hostgssenc cert` is properly rejected (it should be, since cert is
  TLS-only, but the matrix isn't enumerated). severity: maybe
- **[ISSUE-stale-todo: XXX on ident→peer rewrite]** `hba.c:1774-1777`
  — `XXX:` comment is the type of marker that gets ignored. severity: nit
- **[ISSUE-leak: regex_t leaked if parse error occurs mid-line]**
  `regcomp_auth_token` palloc0s a `regex_t` into the per-token
  AuthToken (hba.c:311); on a later field's parse error, the line is
  discarded and only `MemoryContextDelete` on the *whole* hba context
  reclaims it. Within a single load this is fine, but the
  comment "MemoryContextDelete is enough to clean up everything,
  including regexes" (hba.c:2527) relies on `free_auth_token` being
  called on individual frees. severity: nit

## Tally

`[verified-by-code]=24 [from-comment]=14 [inferred]=0`
