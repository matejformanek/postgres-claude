# contrib-btree_gist (B-tree operator semantics for GiST indexes)

- **Source path:** `source/contrib/btree_gist/`
- **Last verified commit:** `e18b0cb7344` (2026-06-12 anchor)
- **Extension version:** `1.9` (per `btree_gist.control`)
- **Trusted:** yes

## 1. Purpose

GiST operator classes for the standard scalar types — `int2`,
`int4`, `int8`, `float4`, `float8`, `numeric`, `text`, `bytea`,
`date`, `time`, `timestamp`, `timestamptz`, `interval`, `uuid`,
`inet`, `cidr`, `macaddr`, `oid`, `bit`, `enum`, etc. The primary
use case is **exclusion constraints** that mix a btree-like
scalar with a range / geometric type: e.g.
`EXCLUDE USING gist (room WITH =, during WITH &&)` needs the
`room` column to live in a GiST index alongside the `tsrange`.

GiST doesn't natively know how to index `int4` — btree_gist
supplies the operator class so the same physical index can hold
both kinds of keys.

## 2. Mental model

- **One `btree_<type>.c` per indexed scalar type.** Each file
  implements the GiST opclass support functions (`consistent`,
  `compress`, `decompress`, `penalty`, `picksplit`, `same`,
  `distance`) for that type, glued onto a shared utility layer.
- **Two shared utility libraries** depending on whether the type
  is numeric or varlen:
  - `btree_utils_num.c` / `.h` — for fixed-width scalar types
    (int4, int8, float, etc.). The per-type file reduces to a
    handful of comparison callbacks; the union / split logic is
    in `gbt_num_*` helpers.
  - `btree_utils_var.c` / `.h` — for varlen types (text, bytea,
    bit). Holds compression / prefix logic.
- **No `NotEqual` strategy in GiST**, except the extension defines
  one. `BtreeGistNotEqualStrategyNumber 6` (`btree_gist.h:9`)
  — used for `<>` evaluation that exclusion constraints need.
- **KNN (`<->` distance ordering)** is supported on numeric and
  date/time types — useful for "nearest int" / "nearest timestamp"
  queries via a GiST scan.

## 3. Key files

- `btree_gist.h` — shared enum `gbtree_type`, `BtreeGistNotEqualStrategyNumber`.
- `btree_utils_num.h`, `btree_utils_num.c` — numeric-type
  GiST helpers (`gbt_num_consistent`, `gbt_num_same`,
  `gbt_num_picksplit`, etc.).
- `btree_utils_var.h`, `btree_utils_var.c` — varlen-type GiST
  helpers; prefix-compression for text / bytea.
- `btree_<type>.c` — one per supported scalar (~20 files: int4,
  int8, float4, float8, numeric, text, bytea, date, time,
  timetz, ts, tstz, interval, oid, uuid, enum, inet, cidr,
  macaddr, macaddr8, bit, varbit, bool, cash).
- `btree_gist--<version>.sql` — opclass / opfamily / function
  registration per version; each new version adds opclasses for
  new types or KNN support.

## 4. Key data structures

- **`gbtree_type` enum** (`btree_gist.h:13-24`) — internal type
  tag for the union-of-types representation used by `gbt_num_*`.
- **`gbt_var_key`** (`btree_utils_var.h`) — wraps the lower /
  upper bounds of a varlen GiST key. The internal-page entries
  store these as a compressed pair.
- **`gbtreekey<N>`** types — fixed-size variants for numeric keys
  (e.g. `gbtreekey8` for int8 ranges).

## 5. SQL surface

- One opclass per supported type: `gist_int4_ops`,
  `gist_int8_ops`, `gist_float8_ops`, `gist_text_ops`,
  `gist_timestamp_ops`, etc.
- Distance operator `<->` for KNN-supporting types.
- No new SQL functions exposed to users — everything is via the
  opclass.

## 6. Invariants and gotchas

- **[INV-1]** Strategy number 6 is `<>` (not equal), used by
  exclusion constraints. Other AMs use 6 differently;
  `BtreeGistNotEqualStrategyNumber 6` is a local convention.
- **[INV-2]** `picksplit` quality directly affects index height
  / page packing. The numeric utility's split algorithm sorts
  by midpoint; varlen's uses prefix similarity.
- **[INV-3]** Adding a new opclass requires both a new
  `btree_<newtype>.c` AND a new install SQL row in the next
  `btree_gist--<v>--<v+1>.sql`. Forgetting either half is the
  classic mistake — the C side compiles but `CREATE INDEX`
  fails with "no operator class".
- **[INV-4]** KNN support means implementing
  `gbt_<type>_distance` AND adding the distance support function
  to the install SQL. Older opclasses lack KNN; don't assume
  every type has it.
- This extension is feature-stable but actively reviewed for
  correctness — Tomas Vondra has recent commits here per the
  audit.

## 7. Owners (as of 2026-06-12)

- Historical author: Teodor Sigaev + Oleg Bartunov (the GiST
  authors).
- Active recent committer: Tomas Vondra (per the backbone audit).
- Persona drivers: `tomas-vondra.md` (if present), GiST-area
  expertise.

## 8. Local reviewer reflexes

- Adding a new opclass: confirm `picksplit` quality with a
  synthetic build benchmark; bad splits double or quadruple
  index size.
- Touching `btree_utils_num.c` or `_var.c`: the change affects
  ALL opclasses in that family. Don't optimize one type's path
  at the cost of another's.
- KNN ordering: confirm transitive `<->` consistency
  — `picksplit` must keep nearby keys in the same page.
- Install-SQL change: confirm `gist_<type>_ops` and any new
  support functions are linked in the right opfamily.

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**27 files.**

| File |
|---|
| [`contrib/btree_gist/btree_bit.c`](../files/contrib/btree_gist/btree_bit.c.md) |
| [`contrib/btree_gist/btree_bool.c`](../files/contrib/btree_gist/btree_bool.c.md) |
| [`contrib/btree_gist/btree_bytea.c`](../files/contrib/btree_gist/btree_bytea.c.md) |
| [`contrib/btree_gist/btree_cash.c`](../files/contrib/btree_gist/btree_cash.c.md) |
| [`contrib/btree_gist/btree_date.c`](../files/contrib/btree_gist/btree_date.c.md) |
| [`contrib/btree_gist/btree_enum.c`](../files/contrib/btree_gist/btree_enum.c.md) |
| [`contrib/btree_gist/btree_float4.c`](../files/contrib/btree_gist/btree_float4.c.md) |
| [`contrib/btree_gist/btree_float8.c`](../files/contrib/btree_gist/btree_float8.c.md) |
| [`contrib/btree_gist/btree_gist.c`](../files/contrib/btree_gist/btree_gist.c.md) |
| [`contrib/btree_gist/btree_gist.h`](../files/contrib/btree_gist/btree_gist.h.md) |
| [`contrib/btree_gist/btree_inet.c`](../files/contrib/btree_gist/btree_inet.c.md) |
| [`contrib/btree_gist/btree_int2.c`](../files/contrib/btree_gist/btree_int2.c.md) |
| [`contrib/btree_gist/btree_int4.c`](../files/contrib/btree_gist/btree_int4.c.md) |
| [`contrib/btree_gist/btree_int8.c`](../files/contrib/btree_gist/btree_int8.c.md) |
| [`contrib/btree_gist/btree_interval.c`](../files/contrib/btree_gist/btree_interval.c.md) |
| [`contrib/btree_gist/btree_macaddr.c`](../files/contrib/btree_gist/btree_macaddr.c.md) |
| [`contrib/btree_gist/btree_macaddr8.c`](../files/contrib/btree_gist/btree_macaddr8.c.md) |
| [`contrib/btree_gist/btree_numeric.c`](../files/contrib/btree_gist/btree_numeric.c.md) |
| [`contrib/btree_gist/btree_oid.c`](../files/contrib/btree_gist/btree_oid.c.md) |
| [`contrib/btree_gist/btree_text.c`](../files/contrib/btree_gist/btree_text.c.md) |
| [`contrib/btree_gist/btree_time.c`](../files/contrib/btree_gist/btree_time.c.md) |
| [`contrib/btree_gist/btree_ts.c`](../files/contrib/btree_gist/btree_ts.c.md) |
| [`contrib/btree_gist/btree_utils_num.c`](../files/contrib/btree_gist/btree_utils_num.c.md) |
| [`contrib/btree_gist/btree_utils_num.h`](../files/contrib/btree_gist/btree_utils_num.h.md) |
| [`contrib/btree_gist/btree_utils_var.c`](../files/contrib/btree_gist/btree_utils_var.c.md) |
| [`contrib/btree_gist/btree_utils_var.h`](../files/contrib/btree_gist/btree_utils_var.h.md) |
| [`contrib/btree_gist/btree_uuid.c`](../files/contrib/btree_gist/btree_uuid.c.md) |

<!-- /files-owned:auto -->
## Cross-references

- `.claude/skills/access-method-apis/SKILL.md` — GiST opclass contracts (`amopclass`, `amproc`, `amop`).
- `.claude/skills/catalog-conventions/SKILL.md` — extension SQL for `CREATE OPERATOR CLASS` registration.
- `.claude/skills/fmgr-and-spi/SKILL.md` — opclass support functions as fmgr functions.
- `knowledge/subsystems/access-nbtree.md` — in-core B-tree (the operator semantics this extension borrows).
- `doc/src/sgml/btree-gist.sgml` — user-facing reference.
- `source/src/backend/access/gist/README` — GiST AM design discussion.
