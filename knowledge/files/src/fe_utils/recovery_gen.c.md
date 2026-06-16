# `src/fe_utils/recovery_gen.c`

- **File:** `source/src/fe_utils/recovery_gen.c` (236 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-04)

## Purpose

Generates standby recovery configuration for `pg_basebackup` (and `pg_rewind` via the
shared header). Turns the live `PGconn`'s connection options into a `primary_conninfo`
string and writes it — together with `primary_slot_name` and (post-v12) a `standby.signal`
file — into `postgresql.auto.conf` (or legacy `recovery.conf`) inside the new data
directory. Because `PQconninfo(pgconn)` includes whatever auth options were used to make
the backup connection, **this is the code path that can persist a `password=...` to disk in
cleartext.**

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `GenerateRecoveryConfig` | :27 | Build a `PQExpBuffer` of recovery GUCs from the conn's options + optional slot + dbname. |
| `WriteRecoveryConfig` | :124 | Append/write the buffer to `postgresql.auto.conf`/`recovery.conf`; touch `standby.signal`. |
| `GetDbnameFromConnectionOptions` | :203 | Pull `dbname` from a connstr, else from env defaults; strdup'd or NULL. |

## Internal landmarks

- `escape_quotes` `recovery_gen.c:163-171` — thin wrapper over `escape_single_quotes_ascii`;
  `pg_fatal` on OOM. Escapes the *whole conninfo* for the outer `'...'` in the config line. `[verified-by-code]`
- `FindDbnameInConnOpts` `recovery_gen.c:180-192` — linear scan for a non-empty `dbname`
  keyword; returns `pg_strdup`'d value. `[verified-by-code]`
- Conninfo assembly loop `recovery_gen.c:54-74` — iterates `PQconninfo(pgconn)` options.
  **Skips** `replication`, `dbname`, `fallback_application_name`, and empty values
  (`:57-62`) — these are overridden by libpqwalreceiver. Everything else (host, port, **user,
  password**, sslmode, ...) is emitted via `appendConnStrVal` which does per-value escaping/quoting. `[verified-by-code]`
- Optional dbname append `recovery_gen.c:76-87` — appended only when the caller passes a
  `dbname` (used by slot-sync / logical slot synchronization). `[from-comment]` (:78-81)
- Two-layer escaping `recovery_gen.c:68-99` — inner: each value escaped by `appendConnStrVal`
  (conninfo grammar); outer: the assembled string escaped by `escape_quotes` for the
  single-quoted GUC value. Comment at `:92-96` explicitly flags the two layers are different. `[from-comment]`
- `primary_slot_name` `recovery_gen.c:102-107` — emitted unescaped; comment justifies it via
  `ReplicationSlotValidateName` allowing only `[a-z0-9_]`. `[from-comment]` (:104)
- `WriteRecoveryConfig` version gate `recovery_gen.c:133-137` — `< MINIMUM_VERSION_FOR_RECOVERY_GUC`
  → legacy `recovery.conf` (mode `"w"`); else append to `postgresql.auto.conf` (mode `"a"`)
  + create empty `standby.signal`. `[verified-by-code]`

## Invariants & gotchas

- **`password` IS written verbatim to disk if present in the conn options.** The skip list at
  `:57-61` does NOT include `password`. If the base-backup connection carried a password
  (e.g. `pg_basebackup -d "...password=secret..."` or `PGPASSWORD`), it lands escaped-but-
  cleartext inside `primary_conninfo` in `postgresql.auto.conf`. This is *known/intended*
  PG behavior (the standby needs credentials to stream), but it is the canonical secret-to-disk
  site. `[verified-by-code]` (see Potential issues)
- The in-memory conninfo is a `PQExpBuffer` (`conninfo_buf`) holding the cleartext; it is
  `termPQExpBuffer`'d at `:98` (libpq `free`, no zeroing). The plaintext secret persists in
  freed heap until overwritten. `[verified-by-code]`
- `escaped` is `free()`d at `:100` (also no zero). `[verified-by-code]`
- Memory: `connOptions` from `PQconninfo` freed via `PQconninfoFree` (`:112`); buffers via
  `createPQExpBuffer`/`termPQExpBuffer`; `dbname` results via `pg_strdup`/`PQconninfoFree`.
  Mixed libpq-owned + `pg_*`-owned — caller `pg_free`s the `GetDbnameFromConnectionOptions`
  result. `[verified-by-code]`
- All OOM paths are `pg_fatal` — no partial files because the buffer is fully built before
  `WriteRecoveryConfig` opens any fd. `[inferred]`

## Cross-references

- `knowledge/files/src/fe_utils/connect_utils.c.md` — sibling secret-handling; same
  no-scrub-on-free property.
- `source/src/include/fe_utils/recovery_gen.h` — `MINIMUM_VERSION_FOR_RECOVERY_GUC`, prototypes.
- `source/src/fe_utils/string_utils.c` — `appendConnStrVal`, `appendShellString`.
- `source/src/common/string.c` — `escape_single_quotes_ascii`.
- `source/src/bin/pg_basebackup/pg_basebackup.c` — primary caller.
- Secret-scrub cluster: walreceiver A8 (consumes this `primary_conninfo`), libpq A2, common A5.

<!-- issues:auto:begin -->
- [Issue register — `fe_utils`](../../../issues/fe_utils.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: cleartext password persisted to postgresql.auto.conf]**
  `recovery_gen.c:57-61,99` — the conninfo skip list omits `password`, so a password supplied
  to the base-backup connection is written (escaped, but cleartext) into `primary_conninfo` on
  disk and is also left unscrubbed in the freed `conninfo_buf`/`escaped` heap. This is intended
  PG behavior — a standby must authenticate to stream WAL — but it is the canonical "secret to
  disk" site and the anchor of the recovery-config end of the secret-scrub cluster. Documented
  here so reviewers stop re-discovering it. (maybe)

## Confidence tag tally

- `[verified-by-code]` × 9
- `[from-comment]` × 3
- `[inferred]` × 1
