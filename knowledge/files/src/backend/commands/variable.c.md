# variable.c

- **Source path:** `source/src/backend/commands/variable.c`
- **Lines:** 1295
- **Last verified commit:** `ef6a95c7c64`
- **Note:** despite the location, there is **no `variable.h`** — the GUC hooks declared here are prototyped in `utils/misc/guc_hooks.h`.

## Purpose

"Routines for handling specialized SET variables." [from-comment, variable.c:3-4] The GUC `check_hook`/`assign_hook`/`show_hook` implementations for variables whose semantics are non-trivial — `DateStyle`, `IntervalStyle`, `TimeZone`, `timezone_abbreviations`, `client_encoding`, `server_encoding`, `role`, `session_authorization`, `transaction_isolation`, `transaction_read_only`, `transaction_deferrable`, `XactIsoLevel`-link, `default_transaction_*` mirrors, plus the SQL `SET ROLE`/`SET SESSION AUTHORIZATION` statement bodies.

## Public surface (selected)

- `check_datestyle`/`assign_datestyle` — DateStyle parses combined "ISO, DMY"-style strings.
- `check_timezone`/`assign_timezone`/`show_timezone` — TimeZone GUC; look up named zone via `pg_tzset`; the assign_hook stores the `pg_tz*` in `session_timezone`.
- `check_client_encoding`/`assign_client_encoding` — set up the conversion functions to/from server encoding.
- `check_role` / `assign_role` / `show_role` — SET ROLE.
- `check_session_authorization` / `assign_session_authorization` / `show_session_authorization` — SET SESSION AUTHORIZATION (requires superuser to change identity).
- `check_transaction_isolation` etc. — SET TRANSACTION on the current xact only; gates that the xact hasn't done writes yet.

## Pattern

Every GUC with non-trivial parsing follows the (check_fn, assign_fn, show_fn) triple registered in `utils/misc/guc_tables.c`. check_fn validates and stashes a parsed form in `*extra`; assign_fn pulls from extra and updates the real C variable; show_fn formats for display. Errors in check_fn before assign make the SET fail without side-effects.

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
