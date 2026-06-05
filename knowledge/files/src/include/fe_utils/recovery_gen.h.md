---
path: src/include/fe_utils/recovery_gen.h
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 30
depth: read
---

# `src/include/fe_utils/recovery_gen.h`

- **File:** `source/src/include/fe_utils/recovery_gen.h` (30 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-05)

## Purpose

Public API for the standby recovery-configuration generator shared by `pg_basebackup` and
`pg_rewind`. Declares the version constant separating the post-v12 `postgresql.auto.conf`
world from the legacy `recovery.conf` world, plus the three functions that build and write a
`primary_conninfo`/`primary_slot_name` recovery config from a live `PGconn`. Implementation
in [[knowledge/files/src/fe_utils/recovery_gen.c]]. `[from-comment]` (:1-9)

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `MINIMUM_VERSION_FOR_RECOVERY_GUC` | :21 | `120000` — at/above this, recovery config is GUCs in `postgresql.auto.conf`; below, it's `recovery.conf`. |
| `GenerateRecoveryConfig` | :23 | Build a `PQExpBuffer` of recovery GUCs from the conn + optional slot + dbname. |
| `WriteRecoveryConfig` | :26 | Write that buffer into the target data dir; touch `standby.signal`. |
| `GetDbnameFromConnectionOptions` | :28 | Extract `dbname` from a connstring (or env defaults). |

## Internal landmarks

- `MINIMUM_VERSION_FOR_RECOVERY_GUC = 120000` (`:21`) is the single switch that
  `WriteRecoveryConfig` uses to choose append-to-`postgresql.auto.conf` + `standby.signal`
  (v12+) vs overwrite-`recovery.conf` (pre-v12). `[from-comment]` (:17-20)
- `GenerateRecoveryConfig`'s `dbname` param (`:23-25`) is non-NULL only for logical-slot
  synchronization callers; base-backup callers pass NULL and get no `dbname=` in the conninfo. `[verified-by-code]` (recovery_gen.c:76-87)

## Invariants & gotchas

- **This is the canonical secret-to-disk site.** `GenerateRecoveryConfig` emits the connection's
  `password` (if present) escaped-but-cleartext into `primary_conninfo` in
  `postgresql.auto.conf`; the conninfo skip-list does not include `password`. Known/intended
  (the standby needs credentials) but the corpus's anchor secret-to-disk finding. Tracked in
  `knowledge/issues/fe_utils.md` row `recovery_gen.c:57`. `[verified-by-code]`

## Cross-refs

- Implementation + the secret-to-disk analysis: [[knowledge/files/src/fe_utils/recovery_gen.c]].
- Secret-scrub cluster context: `knowledge/issues/fe_utils.md` §Notes ("Secret-scrub cluster
  extension"), `knowledge/issues/libpq.md`, `knowledge/issues/common.md` (SecretBuf proposal).

## Potential issues

None new at the header level — the secret-to-disk property is tracked against `recovery_gen.c`
in `knowledge/issues/fe_utils.md`. Cross-linked.
