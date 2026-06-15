---
path: src/test/modules/dummy_index_am/dummy_index_am.c
anchor_sha: e18b0cb7344
loc: 353
depth: read
---

# src/test/modules/dummy_index_am/dummy_index_am.c

## Purpose

Minimal Index Access Method (IndexAm) skeleton — the canonical "show me how
to write a custom index AM" example. Implements the full `IndexAmRoutine`
function table (build, scan, insert, vacuum, …) as no-ops or trivial
returns, plus a full set of relation options exercising every `reloptions`
type (int, real, bool, ternary, enum, two string variants). Used by both the
regression test suite (to verify the AM-template registration path) and by
extension authors as a copy-paste starting point. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `dihandler` | `dummy_index_am.c:57` (declared) | The AM handler — returns the `IndexAmRoutine *` |
| `_PG_init` (implicit via `create_reloptions_table` call from `dihandler`) | — | Builds the reloption parse table |
| Static IndexAm callbacks: `dibuild`, `dibuildempty`, `diinsert`, `dibulkdelete`, `divacuumcleanup`, `dicanreturn`, `dicostestimate`, `dioptions`, `divalidate`, `diadjustmembers`, `dibeginscan`, `direscan`, `digettuple`, `digetbitmap`, `diendscan`, `dimarkpos`, `direstrpos`, `diestimateparallelscan`, `diinitparallelscan`, `diparallelrescan` | throughout | All no-op stubs that satisfy the IndexAmRoutine contract |

## Internal landmarks

- `DummyIndexOptions` (`:37`) is the per-relation options struct — every
  reloption type the system supports is represented (int, real, bool,
  ternary `pg_ternary`, enum, two string offsets).
- `di_relopt_tab[8]` (`:25`) is the parse table consumed by
  `fillRelOptions`. The 8 slots cover the 7 declared options plus
  terminator.
- `create_reloptions_table` builds the table once via `add_*_reloption`
  calls — each adds the option to the named `di_relopt_kind` (a new
  `relopt_kind` ID) and records the offset into `DummyIndexOptions` for
  fillRelOptions.
- `validate_string_option` (`:62`) is the validator for string reloptions;
  emits a NOTICE so regression tests can see the validator firing.

## Invariants & gotchas

- **Test module — never load in production.** This index AM rejects all
  inserts and returns no rows from any scan; you'd lose data fast.
- The AM is registered via `CREATE ACCESS METHOD dummy_index_am TYPE INDEX
  HANDLER dihandler` in the SQL test setup.
- Every IndexAmRoutine field must be filled in (or NULL where the AM
  declares it doesn't support that operation). Missing a required field
  is a classic SEGV when the planner tries to call through.
- The `pg_ternary` option (`option_ternary_1`) tests the relatively rare
  three-valued reloption added for boolean-with-default options.
- String reloptions use offset-into-struct encoding (`option_string_val_offset`,
  `option_string_null_offset`, `:45-46`) — the actual chars live in the
  varlena tail.

## Cross-refs

- `source/src/backend/access/index/amapi.c` — IndexAm registration.
- `source/src/include/access/amapi.h` — `IndexAmRoutine` struct.
- `source/src/backend/access/common/reloptions.c` — `add_*_reloption`,
  `fillRelOptions`.
- `source/contrib/bloom/blutils.c` — a real example of a custom IndexAm.
