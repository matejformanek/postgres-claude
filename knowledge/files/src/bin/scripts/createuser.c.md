# `src/bin/scripts/createuser.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~459
- **Source:** `source/src/bin/scripts/createuser.c`

CLI wrapper that issues `CREATE ROLE <name> [SUPERUSER|NOSUPERUSER]
[CREATEDB|...] ... [PASSWORD ...] [VALID UNTIL ...]` against a
maintenance database. Uses trivalued `enum trivalue` for each
attribute so we can distinguish "user didn't say" from "user said
no". [verified-by-code]

## API / entry points

- `main(argc, argv)` — getopt loop, default resolution, attribute
  prompt-if-interactive, password prompt, then build + send the
  SQL. [verified-by-code]

## Notable invariants / details

- Password handling: when `-P/--pwprompt`, the user is prompted
  twice and the two values must match. The actual SQL uses
  `PQencryptPasswordConn(conn, password, role, NULL)` (line
  306-309), which asks the server for its preferred password
  encryption (scram-sha-256 since PG10). The encrypted value is
  emitted as a SQL literal via `appendStringLiteralConn`, so the
  plaintext never appears in the SQL. [verified-by-code]
- Once-encrypted password buffer is `PQfreemem`'d (line 314), but
  the plaintext `newpassword` is NOT explicitly cleared from
  memory before exit. A core dump captured during a `createuser`
  invocation could leak the plaintext. [verified-by-code]
  [ISSUE-security: plaintext password buffer in newpassword
  global not explicitly memset(0) before exit; core-dump leak
  hazard (maybe)]
- Default attribute matrix (line 243-284):
  - `superuser` default `NO`. **However**, if `superuser=YES`,
    `createdb` and `createrole` are silently forced to YES as
    well (line 251-256) — comment "Not much point in trying to
    restrict a superuser" since a superuser bypasses all those
    flags anyway.
  - `createdb`/`createrole`/`bypassrls`/`replication` default
    `NO`.
  - `inherit`/`login` default `YES`.
  [verified-by-code]
- Role-name default: `simple_prompt` in interactive mode, else
  `$PGUSER`, else the OS user (line 214-227). This means
  `createuser` with no args creates a role named after the
  invoking user — a footgun if you forget to add an arg.
  [verified-by-code] [ISSUE-undocumented-invariant: zero-arg
  createuser creates a role for the OS user; surprising default
  (maybe)]
- Members lists (`--with-admin`, `--with-member`, `--member-of` /
  `--role`) accumulate into `SimpleStringList`s and become
  `IN ROLE`, `ROLE`, and `ADMIN` clauses respectively (line
  351-392). Each role name is `fmtId`-quoted. [verified-by-code]
- `--encrypted` (`-E`) is accepted for backward compatibility but
  is a no-op (line 125) — PG removed support for non-encrypted
  password storage. [verified-by-code]
- `-c/--connection-limit` is parsed with `option_parse_int(-1,
  INT_MAX)` (line 111). Default `-2` is "user didn't say"; the
  SQL clause is emitted only if `>= -1` (line 344). The server
  semantics: `-1` means unlimited. [verified-by-code]

## Potential issues

- Line 245: the interactive `yesno_prompt("Shall the new role be
  a superuser?")` will create a superuser if the user types `y`.
  No double-confirmation. Combined with the auto-cascade that
  also sets createdb/createrole, this means a single careless `y`
  produces a wide-privilege role. Documented behaviour, but a
  security paper-cut. [verified-by-code]
  [ISSUE-security: interactive --interactive prompt grants
  SUPERUSER on single 'y' with no confirmation (nit)]
- Line 51-54: `-w/--no-password` and `-W/--password` control
  password prompt for the *connection*, not for the role being
  created. The flag overlap with `-P/--pwprompt` is mentioned in
  help but easy to confuse. [verified-by-code]
- Lines 33-34: `-d/--createdb` is `createdb=YES`, `-D` is
  `createdb=NO`. The uppercase/lowercase convention is used
  throughout but unfamiliar to users expecting GNU-style
  `--no-X` only. The script also accepts `--no-createdb` (long
  form). [verified-by-code]
- `connectMaintenanceDatabase` is called with `dbname=NULL`,
  which falls back to `postgres`. If `postgres` doesn't exist
  the connection fails immediately, even though we don't need a
  particular db. [verified-by-code]
- The replication and bypassrls TRI_DEFAULT branches (line
  274-278) skip the interactive prompt — they always default to
  NO. Inconsistent with createdb/createrole/superuser which do
  prompt. [verified-by-code] [ISSUE-style: --interactive prompts
  for createdb/createrole/superuser but silently defaults
  replication/bypassrls to NO (nit)]
- Line 305-313: `PQencryptPasswordConn` may use scram-sha-256 or
  md5 depending on `password_encryption` GUC on the server. With
  a misconfigured server, the role could end up with a less-secure
  hash type than expected. [verified-by-code]
