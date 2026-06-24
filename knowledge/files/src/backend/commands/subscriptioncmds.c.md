# subscriptioncmds.c

- **Source path:** `source/src/backend/commands/subscriptioncmds.c`
- **Lines:** 3530
- **Last verified commit:** `9a60f295bcb1`

## Purpose

"Subscription catalog manipulation functions." [from-comment, subscriptioncmds.c:3-4] CREATE / ALTER / DROP SUBSCRIPTION — the subscriber side of logical replication.

## Public surface

- `CreateSubscription` — open a libpqwalreceiver connection to the publisher, create a replication slot (unless `create_slot = false`), fetch the publisher's list of tables matching the subscription's publications, write `pg_subscription` + `pg_subscription_rel` rows (one per table, state=INIT). The apply worker (in `replication/logical/worker.c`) is started by the launcher.
- `AlterSubscription` — many subcommands: SET PUBLICATION, REFRESH PUBLICATION (re-fetch table list), ENABLE/DISABLE, SET (connection params, slot, streaming, two_phase, run_as_owner, password_required, …), SKIP (skip a specific LSN's apply).
- `DropSubscription` — disable, terminate workers, drop the replication slot on the publisher (if still reachable), delete catalog rows.
- `AlterSubscriptionOwner` — owner change; requires DB superuser or membership.
- Helpers for connection-string handling: `parse_subscription_options`, `check_publications`, `fetch_table_list`.

## Replication-command quoting (since `a75bd485b5ea`)

This file gained the same self-contained quoting helper as
`libpqwalreceiver.c`: `appendQuotedString(buf, str, quote)` (line 530) plus
`appendQuotedIdentifier` (`'"'`) and `appendQuotedLiteral` (`'\''`) macros
(lines 544-545). The helper doubles any embedded quote char; it is used when
constructing the publisher-side commands the subscriber sends, replacing
ad-hoc interpolation so slot/publication identifiers with embedded quotes are
escaped safely. (Pre-existing `quote_literal_cstr` calls for schema/table names
in the table-list fetch path, lines ~2822/2949, are unchanged.) [verified-by-code, subscriptioncmds.c:530-545 @ a75bd485b5ea]

## Two-phase commit support (PG 15+)

`WITH (two_phase = on)` makes the subscription replicate PREPARE/COMMIT PREPARED of two-phase commits separately. Only available if the publisher has `wal_level=logical` and the slot is at `LSN >= prepare_LSN`. Once enabled cannot be disabled (would require re-syncing).

## Run AS OWNER (PG 16+)

Default: apply worker runs as subscription owner (so RLS policies on the subscription's target tables are evaluated for that role). `run_as_owner = false` (PG 17+ default for new subscriptions) runs as the table-owner for each replicated change — better separation of privilege.

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
