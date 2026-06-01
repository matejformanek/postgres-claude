# Source census

**Source commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)
**Generated:** 2026-06-01

One-time enumeration of the upstream tree as it stands at the verified commit.
Counts are `.c` files and total LOC under each directory (non-recursive for
subsystem rows, since each subsystem is mostly flat).

## READMEs (90 files — these are the highest-signal anchors)

### Backend subsystems (priority anchors)

- `source/src/backend/access/brin/README`
- `source/src/backend/access/gin/README`
- `source/src/backend/access/gist/README`
- `source/src/backend/access/hash/README`
- `source/src/backend/access/nbtree/README`
- `source/src/backend/access/rmgrdesc/README`
- `source/src/backend/access/spgist/README`
- `source/src/backend/access/transam/README`
- `source/src/backend/executor/README`
- `source/src/backend/jit/README`
- `source/src/backend/lib/README`
- `source/src/backend/nodes/README`
- `source/src/backend/optimizer/README`
- `source/src/backend/optimizer/plan/README`
- `source/src/backend/parser/README`
- `source/src/backend/regex/README`
- `source/src/backend/replication/README`
- `source/src/backend/snowball/README`
- `source/src/backend/statistics/README`
- `source/src/backend/storage/buffer/README` ← **Phase 0.5 target**
- `source/src/backend/storage/freespace/README`
- `source/src/backend/storage/lmgr/README`
- `source/src/backend/storage/page/README`
- `source/src/backend/storage/smgr/README`
- `source/src/backend/utils/fmgr/README`
- `source/src/backend/utils/mb/README`
- `source/src/backend/utils/misc/README`
- `source/src/backend/utils/mmgr/README`
- `source/src/backend/utils/resowner/README`

### Headers & catalog

- `source/src/include/catalog/README`

### Other (bin, interfaces, common)

- `source/src/bin/pg_amcheck/README`
- `source/src/bin/pgevent/README`
- `source/src/common/unicode/README`
- `source/src/interfaces/ecpg/test/connect/README`
- `source/src/interfaces/libpq-oauth/README`
- `source/src/interfaces/libpq/README`
- `source/src/pl/plperl/README`
- `source/src/port/README`
- `source/src/timezone/README`
- `source/src/timezone/tznames/README`
- `source/src/tutorial/README`

### Tests

- `source/src/test/README`
- `source/src/test/authentication/README`
- `source/src/test/icu/README`
- `source/src/test/isolation/README`
- `source/src/test/kerberos/README`
- `source/src/test/ldap/README`
- `source/src/test/locale/README` (+ 3 nested ISO/koi8 dirs)
- `source/src/test/mb/README`
- `source/src/test/modules/README` (+ 24 nested module READMEs)
- `source/src/test/perl/README`
- `source/src/test/postmaster/README`
- `source/src/test/recovery/README`
- `source/src/test/regress/README`
- `source/src/test/ssl/README`
- `source/src/test/subscription/README`

### Tooling

- `source/src/tools/ci/README`
- `source/src/tools/ifaddrs/README`
- `source/src/tools/pg_bsd_indent/README`
- `source/src/tools/pginclude/README`
- `source/src/tools/pgindent/README`

## Backend top-level directories (`source/src/backend/`)

Files = non-recursive `.c` count; LOC = total lines across those .c files
(only counts top-level files of the dir, drill-down below).

| Dir | files | LOC |
|---|---|---|
| access | 157 | 164 227 |
| archive | 1 | 143 |
| backup | 14 | 6 666 |
| bootstrap | 1 | 1 196 |
| catalog | 34 | 46 337 |
| commands | 56 | 115 178 |
| executor | 65 | 79 540 |
| foreign | 1 | 891 |
| jit | 5 | 5 538 |
| lib | 9 | 4 319 |
| libpq | 17 | 17 755 |
| main | 1 | 520 |
| nodes | 16 | 15 574 |
| optimizer | 52 | 98 365 |
| parser | 21 | 40 312 |
| partitioning | 3 | 10 363 |
| port | 10 | 4 249 |
| postmaster | 16 | 20 204 |
| regex | 13 | 13 475 |
| replication | 27 | 47 800 |
| rewrite | 8 | 10 888 |
| snowball | 56 | 58 912 |
| statistics | 8 | 11 030 |
| storage | 59 | 67 233 |
| tcop | 7 | 13 007 |
| tsearch | 15 | 10 372 |
| utils | 209 | 294 004 |

## Drill-down: access / storage / utils / optimizer subsystems

(non-recursive `.c` counts per leaf subsystem dir)

### `access/`

| Subsystem | files | LOC |
|---|---|---|
| brin | 10 | 10 920 |
| common | 17 | 10 043 |
| gin | 15 | 13 610 |
| gist | 11 | 10 603 |
| hash | 10 | 7 681 |
| heap | 11 | 25 587 |
| index | 4 | 2 465 |
| nbtree | 13 | 24 519 |
| rmgrdesc | 22 | 3 324 |
| sequence | 1 | 77 |
| spgist | 11 | 9 045 |
| table | 4 | 1 463 |
| tablesample | 3 | 525 |
| transam | 25 | 44 365 |

### `storage/`

| Subsystem | files | LOC |
|---|---|---|
| aio | 10 | 5 894 |
| buffer | 5 | 11 103 ← **Phase 0.5** |
| file | 6 | 6 188 |
| freespace | 3 | 1 412 |
| ipc | 19 | 18 700 |
| large_object | 1 | 911 |
| lmgr | 8 | 17 111 |
| page | 3 | 1 725 |
| smgr | 3 | 3 569 |
| sync | 1 | 620 |

### `utils/`

| Subsystem | files | LOC |
|---|---|---|
| activity | 20 | 9 900 |
| adt | 119 | 201 376 |
| cache | 15 | 25 775 |
| error | 4 | 4 902 |
| fmgr | 3 | 5 021 |
| hash | 2 | 2 041 |
| init | 4 | 3 717 |
| mb | 5 | 2 787 |
| misc | 17 | 12 866 |
| mmgr | 10 | 12 911 |
| resowner | 1 | 1 110 |
| sort | 7 | 9 263 |
| time | 2 | 2 335 |

### `optimizer/`

| Subsystem | files | LOC |
|---|---|---|
| geqo | 15 | 2 655 |
| path | 9 | 28 670 |
| plan | 8 | 31 561 |
| prep | 5 | 8 441 |
| util | 15 | 27 038 |

## Test directories (`source/src/test/`)

| Dir | Role (one-line) |
|---|---|
| authentication | TAP tests for auth methods (pg_hba, scram, etc.) |
| examples | Sample programs (libpq usage, not really a test suite) |
| icu | ICU locale handling tests |
| isolation | Concurrency tests using the isolation tester (predicate locks, SSI, MVCC corners) |
| kerberos | GSSAPI / krb5 TAP tests |
| ldap | LDAP auth TAP tests (requires OpenLDAP) |
| locale | Locale-dependent regression tests (per-charset subdirs) |
| mb | Multibyte / encoding regression tests |
| modules | Self-contained test extensions exercising specific subsystems (~24 modules) |
| perl | Shared Perl helpers for TAP tests (PostgreSQL::Test::*) |
| postmaster | Postmaster startup/teardown TAP tests |
| recovery | Crash recovery & replication TAP tests |
| regress | The primary SQL regression suite (this is what `ninja test` runs) |
| ssl | TLS / certificate handling TAP tests |
| subscription | Logical replication subscription TAP tests |

## Notes for prioritization

Phase 0.5 calibration target is `storage/buffer` (compact at 5 files / 11 KLOC,
has a long README, central to everything). Likely next candidates per
`pg-claude-plan.md §5.3`:

- `access/heap` (25 KLOC, 11 files) — heap AM, MVCC tuple format
- `access/transam` (44 KLOC, 25 files) — XID assignment, commit, WAL, clog
- `storage/lmgr` (17 KLOC, 8 files) — heavyweight & lightweight locks
- `storage/smgr` + `storage/page` — block-level I/O and page layout
- `utils/mmgr` (12 KLOC, 10 files) — memory contexts (also drives an idiom skill)

Re-confirm this ordering against the master plan before starting the next doc.
