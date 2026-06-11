# `src/bin/scripts/dropuser.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~188
- **Source:** `source/src/bin/scripts/dropuser.c`

CLI wrapper that issues `DROP ROLE [IF EXISTS] <name>` against a
maintenance database. Optionally prompts in `-i/--interactive`
mode for both confirmation AND a missing role name.
[verified-by-code]

## API / entry points

- `main(argc, argv)` — parses options, optionally prompts for
  role name, optionally prompts for confirmation, builds and
  sends the SQL. [verified-by-code]

## Notable invariants / details

- Role-name handling differs from `createuser`: if no positional
  arg is given AND we're not in interactive mode, dropuser
  exits with `missing required argument role name` (line
  121-124). Only in `-i` mode is the user prompted via
  `simple_prompt`. [verified-by-code]
- `--if-exists` long-only flag (line 37) with the `&if_exists, 1`
  getopt convention. [verified-by-code]
- SQL: `DROP ROLE %s%s;` with `fmtIdEnc(name, encoding)` — line
  145-147. [verified-by-code]
- No automatic maintenance-db fallback (dbname=NULL → default
  `postgres`); dropping a role has no per-db requirement, so any
  db works. [verified-by-code]

## Potential issues

- Interactive flow (line 128-133) shows "Role \"%s\" will be
  permanently removed." but a role is reusable as a name, so the
  message is slightly stronger than the action warrants (no
  data is destroyed, just the role entry). [verified-by-code]
- No client-side check that the role doesn't own important
  objects; the server will refuse with "role ... cannot be
  dropped because some objects depend on it" if so. Standard
  wrapper behaviour. [verified-by-code]
- `connectMaintenanceDatabase` with dbname=NULL → connects to
  `postgres`. If `postgres` doesn't exist, the script fails to
  connect even though it could have used `template1`. Could be
  argued either way. [verified-by-code]
