# `src/fe_utils/connect_utils.c`

- **File:** `source/src/fe_utils/connect_utils.c` (171 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-04)

## Purpose

Frontend connect/disconnect helpers shared by the non-psql CLI tools
(createdb, dropdb, reindexdb, vacuumdb, clusterdb, etc.). Wraps
`PQconnectdbParams` with an interactive password-prompt retry loop, a maintenance-db
fallback (`postgres` then `template1`), and a disconnect path that cancels any
in-flight statement first. Holds the prompted password in a function-local `static`
across calls so a reconnect can reuse it.

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `connectDatabase` | :31 | Connect with `ConnParams`; prompt for password if needed; loop until auth succeeds or fails. |
| `connectMaintenanceDatabase` | :133 | Connect to `--maintenance-db`, else try `postgres` then `template1`. |
| `disconnectDatabase` | :157 | Cancel any active statement, then `PQfinish`. |

## Internal landmarks

- `static char *password` `connect_utils.c:37` — module-lifetime cached password. Persists
  between calls so the retry loop and reconnects can reuse it. `[verified-by-code]`
- `allow_password_reuse` gate `connect_utils.c:42-46` — if false, the cached password is
  `free()`d and nulled before use. The header comment warns callers to only pass
  `allow_password_reuse=true` when reconnecting to the *same* host+port+user, else "password
  exposure hazards". `[from-comment]` (:26-29)
- Initial prompt `connect_utils.c:48-49` — `simple_prompt("Password: ", false)` only when
  `prompt_password == TRI_YES`. `[verified-by-code]`
- Keyword/value arrays `connect_utils.c:57-85` — fixed 8-slot arrays; `password` is passed as
  the `"password"` value. `override_dbname` may add a second `dbname` entry that wins.
  `Assert(i <= lengthof(keywords))` guards the slot count. `[verified-by-code]`
- Retry loop `connect_utils.c:55-106` — on `CONNECTION_BAD` + `PQconnectionNeedsPassword` +
  not `TRI_NO`: `PQfinish`, `free(password)`, re-prompt, loop. `[verified-by-code]`
- Secure search-path `connect_utils.c:120` — every successful connection runs
  `ALWAYS_SECURE_SEARCH_PATH_SQL` (`SELECT pg_catalog.set_config('search_path', '', false)`)
  to start strict. `[verified-by-code]`
- `disconnectDatabase` `connect_utils.c:157-171` — if `PQtransactionStatus == PQTRANS_ACTIVE`,
  uses the modern `PQcancelCreate` / `PQcancelBlocking` / `PQcancelFinish` API before
  `PQfinish`. Note the local `PGcancelConn *cancelConn` shadows nothing global here. `[verified-by-code]`

## Invariants & gotchas

- **Password lifetime — NOT scrubbed.** The cached `password` (`:37`) is released with plain
  `free()` (`:44`, `:102`) and re-`simple_prompt`'d, but the buffer is never zeroed before
  free. The plaintext password therefore lingers in freed heap until overwritten. This is the
  established libpq/frontend pattern (libpq itself does not scrub conn->pgpass), so it is a
  cluster-wide property, not a local bug. `[verified-by-code]` (see Potential issues)
- **Memory ownership:** `password` is from `simple_prompt` (malloc'd by libpq common); freed
  with `free`, not `pg_free`. `ConnParams` strings are caller-owned and only borrowed. `[inferred]`
- `connectMaintenanceDatabase` mutates `cparams->dbname` (hence non-const) when filling the
  default — caller's struct is modified as a side effect. `[from-comment]` (:128-131)
- The `static` password means a single process can only meaningfully cache one credential at a
  time; concurrent connections to different servers would clobber it. Not an issue for the
  serial CLI tools that use this. `[inferred]`

## Cross-references

- `knowledge/files/src/fe_utils/cancel.c.md` — older signal-path `PQcancel`; this file uses
  the newer blocking `PQcancel*` family instead.
- `source/src/include/fe_utils/connect_utils.h` — `ConnParams`, `trivalue` (`TRI_DEFAULT`/`TRI_NO`/`TRI_YES`).
- `source/src/include/common/connect.h` — `ALWAYS_SECURE_SEARCH_PATH_SQL`.
- `source/src/common/sprompt.c` — `simple_prompt`.
- Secret-scrub cluster: libpq A2, psql/initdb A4, common A5, pg_upgrade A6, walreceiver A8.

<!-- issues:auto:begin -->
- [Issue register — `fe_utils`](../../../issues/fe_utils.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: prompted password freed without zeroing]** `connect_utils.c:44,102` —
  the cached plaintext `password` is `free()`d (not zeroed-then-freed) on reuse-reset and on
  password retry, leaving the secret in freed heap. Consistent with the rest of the
  frontend/libpq (no scrub anywhere in this path), so it is a *cluster-wide* design property
  worth recording, not a local regression. (maybe)

## Confidence tag tally

- `[verified-by-code]` × 7
- `[from-comment]` × 3
- `[inferred]` × 2
