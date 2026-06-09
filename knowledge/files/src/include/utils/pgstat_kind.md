# `src/include/utils/pgstat_kind.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Enumerates cumulative-stats *kinds* (database, relation, function,
replslot, subscription, backend, archiver, bgwriter, checkpointer,
IO, lock, SLRU, WAL). Sharable between frontend and backend code
[from-comment: lines 4-7].

## Public API

[verified-by-code: lines 17-71]
- `PgStat_Kind` = `uint32`.
- ID range: `PGSTAT_KIND_MIN=1`, `PGSTAT_KIND_MAX=32`,
  `PGSTAT_KIND_INVALID=0`.
- Built-in IDs 1..13 (lines 27-42); built-in range:
  `[PGSTAT_KIND_BUILTIN_MIN .. PGSTAT_KIND_BUILTIN_MAX]` ⇒ 1..13.
- **Custom (extension-defined) range: 24..32**
  (`PGSTAT_KIND_CUSTOM_MIN..MAX`) [lines 50-52], capacity 9 slots.
- `PGSTAT_KIND_EXPERIMENTAL = 24` — shared slot for in-development
  extensions that have not reserved a unique ID at
  <https://wiki.postgresql.org/wiki/CustomCumulativeStats>.
- Inline predicates `pgstat_is_kind_builtin` / `pgstat_is_kind_custom`.

## Invariants

- **INV-RANGE** [verified-by-code: lines 20-21] Kinds must fit in
  uint32 with values 1..32; ID 0 reserved for INVALID.
- **INV-GAP** [verified-by-code: lines 44-50] IDs 14..23 are reserved
  (intentional gap between built-in and custom ranges).

## Trust boundary (Phase D)

- **Pluggable custom kinds** [from-comment: lines 47-59]: extensions
  call `pgstat_register_kind()` (defined in `pgstat.h`, not here) with
  a chosen ID. There's no central registry — collisions between two
  loaded extensions both claiming `PGSTAT_KIND_EXPERIMENTAL=24` are
  expected unless one moves to a "reserved" wiki-tracked ID.
- The 9-slot custom range is a hard limit. Two extensions registering
  different IDs in 24..32 is fine; >9 third-party stats kinds in the
  same backend is impossible.
- Custom kinds inherit the same shared-memory plumbing as built-ins
  — their handlers run inside the stats system's locks and the same
  restart-on-corruption semantics.

## Cross-refs

- `pgstat_internal.h` — the `PgStat_HashKey` uses this `PgStat_Kind`.
- `pgstat.h` (not in this slice) — the kind-registration API.
- A11 monitoring-extraction cluster.

## Issues

- [ISSUE-DESIGN: only 9 custom-kind slots cluster-wide; not
  documented as a hard limit users may hit (low)] — lines 50-52.
- [ISSUE-CONVENTION: `PGSTAT_KIND_EXPERIMENTAL` is a shared "default"
  ID for unregistered extensions — collision is the expected case,
  the design banks on wiki coordination (medium)] — lines 54-59.
