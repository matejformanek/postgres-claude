---
source_url: https://www.postgresql.org/docs/current/runtime-config-client.html
fetched_at: 2026-07-02T20:52:00Z
anchor_sha: b542d5566705
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18/19devel)
primary: true
---

# Docs distilled — Client Connection Defaults (§20.12)

The per-session behavior GUCs. Sections: Statement Behavior, Locale and
Formatting, Shared Library Preloading, Other Defaults. Focus here is the
backend-relevant, non-obvious semantics. Companion skills: `gucs-config`,
`extension-development`, `executor-and-planner`.

## search_path resolution has invisible entries

- **`search_path` (default `"$user", public`, USERSET)** — first match wins.
  Two entries are searched even when not listed: **`pg_catalog` is always
  searched first** unless you list it explicitly (then its listed position
  wins), and **`pg_temp` (the temp schema) is searched first if it exists** —
  but only for **relations and types, never for functions/operators** (a
  security-relevant asymmetry). `$user` silently drops if that schema doesn't
  exist or you lack USAGE. Inspect the *effective* path with
  `current_schemas(true)`, which differs from the raw GUC string. [from-docs]

## The timeout family — exact scoping differs per knob

- **`statement_timeout` (ms, 0=off)** — from command arrival to completion;
  since PG13 it applies **per statement** within a multi-statement simple-query.
  In extended protocol it starts on Parse/Bind/Execute/Describe. [from-docs]
- **`lock_timeout` (ms, 0)** — **per lock-acquisition attempt while waiting**,
  not total execution; moot if a smaller `statement_timeout` is set. [from-docs]
- **`idle_in_transaction_session_timeout` (ms, 0)** — kills a session idle
  inside an open transaction; its purpose is preventing the open snapshot from
  **blocking vacuum of recently-dead tuples** (bloat). [from-docs]
- **`idle_session_timeout` (ms, 0)** — kills a session idle *outside* a txn
  (lower cost); dangerous behind a connection pooler. [from-docs]
- **`transaction_timeout` (ms, 0)** — spans explicit + implicit txns; if it is
  ≤ either of the two above, the longer one is ignored; **prepared (2PC)
  transactions are exempt**. [from-docs]

## session_replication_role — the trigger/FK/apply master switch

- **`session_replication_role` (enum, default `origin`, superuser/SET-priv)** —
  `replica` makes ordinary triggers and rules **not fire** and **disables ALL
  foreign-key checks** (can corrupt data if misused — but this is exactly how
  logical/physical replication apply avoids re-firing triggers and re-checking
  FKs). `origin` and `local` are treated identically internally; third-party
  systems set `local` to mark changes as not-to-be-replicated. **Changing it
  discards cached query plans.** [from-docs] — pairs with
  `logical-replication-subscription.md` and `trigger-definition.md`.

## Compression / storage / AM defaults

- **`default_toast_compression` (enum, default `pglz`, SIGHUP)** — `pglz` or
  `lz4` (if built with lz4) for new TOASTed values; column `COMPRESSION`
  overrides. [from-docs]
- **`default_table_access_method` (default `heap`, SIGHUP)** — the table AM for
  `CREATE TABLE` / matview / `SELECT INTO` (the latter has no explicit-AM
  syntax, so this is the only lever). [from-docs] — pairs with `tableam.md`.
- **`gin_pending_list_limit` (default 4MB)** — GIN `fastupdate` pending-list
  size before bulk-merge into the main tree; per-index storage param overrides.
  [from-docs]

## The library-preload trio (load timing is the whole point)

- **`shared_preload_libraries` (POSTMASTER)** — the ONLY one that runs at
  postmaster start, so it's **required** for a module that needs shared memory,
  LWLocks, or background workers. Server fails to start if missing. [from-docs]
- **`session_preload_libraries` (superuser, connection-start)** — settable via
  `ALTER ROLE SET`; good for a debugging module across new sessions. [from-docs]
- **`local_preload_libraries` (USERSET, connection-start)** — unprivileged, but
  restricted to `$libdir/plugins/`. [from-docs]
- **`jit_provider` (default `llvmjit`, POSTMASTER)** — a non-existent library
  here **silently disables JIT** rather than erroring. [from-docs]

## Extension / module search paths (runtime-mutable but session-scoped)

- **`dynamic_library_path` (default `$libdir`)** and **`extension_control_path`
  (default `$system`, appends `/extension`)** — both can be changed at runtime
  but the change persists only to connection end (a development convenience);
  set them in `postgresql.conf` for real use. [from-docs] — pairs with
  `extend-extensions.md` / `extend-pgxs.md`.

## Other developer-relevant toggles

- **`check_function_bodies` (on)** — `off` skips body validation at
  `CREATE FUNCTION` (avoids forward-reference false-positives; `pg_dump` sets
  off). **`row_security` (on)** — `off` makes any query that *would* apply an
  RLS policy **error** instead of silently filtering (superusers/BYPASSRLS
  unaffected). **`event_triggers` (on)** — `off` disables all event triggers
  (escape hatch for a broken one). [from-docs]
- **`extra_float_digits` (default 1 since PG12)** — ≥1 = shortest round-trip
  format (exact binary value); the semantics flipped in PG12 (a classic
  cross-version float-output diff in regress `resultmap` territory). [from-docs]
- **`temp_tablespaces`** — random tablespace per temp object; interactive set
  errors on a bad tablespace, config-file set silently ignores. [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/runtime-config-developer.md]] — sibling §20 page.
- [[knowledge/docs-distilled/logical-replication-subscription.md]] — `session_replication_role=replica` is the apply-worker mode.
- [[knowledge/docs-distilled/extend-extensions.md]] — the preload/control-path mechanics.
- [[knowledge/docs-distilled/trigger-definition.md]] — what `replica` mode suppresses.
- Skills: `gucs-config`, `extension-development`, `executor-and-planner`.

## Confidence note

All `[from-docs]` (Client Connection Defaults chapter, fetched 2026-07-02).
Section numbering renders as §19.11 in the fetched page (docs version skew) but
the slug is stable; cite by slug. GucContext values are as the page states.
