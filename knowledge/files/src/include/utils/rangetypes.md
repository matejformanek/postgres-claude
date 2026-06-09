# utils/rangetypes.h — RangeType varlena + bound flags

Source: `source/src/include/utils/rangetypes.h` (170 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

On-disk RangeType varlena header, the flag-byte bit layout, internal `RangeBound` representation, and the full set of range op internal functions.

## Public API / on-disk format

```
<vl_len_>     varlena header
<rangetypid>  Oid
<lower bound> 0..1 bound values (variable)
<upper bound> 0..1 bound values (variable)
<flags>       1-byte trailing flags
```

`rangetypes.h:21-30` [from-comment]. The flags byte is the discriminator:

- `RANGE_EMPTY     0x01` — empty range, no bounds present
- `RANGE_LB_INC    0x02` — lower bound inclusive `[`
- `RANGE_UB_INC    0x04` — upper bound inclusive `]`
- `RANGE_LB_INF    0x08` — lower bound is -inf, no value present
- `RANGE_UB_INF    0x10` — upper bound is +inf, no value present
- `RANGE_LB_NULL   0x20` — NOT USED (reserved)
- `RANGE_UB_NULL   0x40` — NOT USED (reserved)
- `RANGE_CONTAIN_EMPTY 0x80` — GiST internal marker

(`rangetypes.h:38-46`).

## Invariants

- **INV-range-empty-no-bounds** [verified-by-code, `rangetypes.h:48-50`]: if `RANGE_EMPTY`, `RANGE_LB_NULL`, or `RANGE_LB_INF` set, no lower bound value is present in the varlena. Symmetric for upper.
- **INV-range-LB_NULL-UB_NULL-unused** [from-comment, `rangetypes.h:43-44`]: the NULL bits are reserved but never set by current code; receivers should still tolerate them or reject explicitly.
- **INV-range-flag-byte-trailing** [from-comment, `rangetypes.h:29`]: flags byte comes AFTER the bound values, not before. `range_deserialize` walks varlena left-to-right relying on this.
- **INV-range-CONTAIN_EMPTY-GiST-only** [from-comment, `rangetypes.h:45-46`]: 0x80 is meaningful only in GiST internal pages; leaf ranges never set it.

## Notable internals

- `RangeBound` (`rangetypes.h:62-68`) is the in-memory bound, not on-disk: holds `Datum val`, `infinite`/`inclusive`/`lower` flags.
- `range_serialize` takes `escontext` (`rangetypes.h:145-147`) — soft-error capable.
- Operator strategy numbers (`RANGESTRAT_*` at `rangetypes.h:97-106`) alias the RT* numbers from access methods so GiST/SP-GiST opclasses can share names.

## Trust-boundary / Phase-D surface

- **range_recv** [inferred — header silent]: binary recv must validate that the flag byte is consistent with the buffer length (e.g. `RANGE_LB_INF | <bound bytes present>` is malformed). Header doesn't surface this.
- **Reserved `LB_NULL`/`UB_NULL` bits** (`rangetypes.h:43-44`): an attacker controlling binary input could set these; current code path treats them as "unused" but downstream `RANGE_HAS_LBOUND` masks them OUT (line 48), which means a malformed input claiming "LB_NULL" would silently behave as if the bound were missing. That's defensible but not documented as a security choice.
- **`range_serialize` `escontext` is opt-in** (`rangetypes.h:145-147`): callers that omit it get hard ereport; binary input paths must pass escontext.

## Cross-refs

- `knowledge/files/src/include/utils/multirangetypes.md` — companion containing multiple RangeType structs.
- `source/src/backend/utils/adt/rangetypes.c` — implementation, including `range_recv`.

## Issues

- `[ISSUE-DOC: range_recv flag-vs-length consistency not surfaced (medium)]` — A receiver that sees `RANGE_EMPTY | RANGE_LB_INC` (contradictory) or `RANGE_LB_INF` with bound bytes present should reject; header doesn't tell callers this.
- `[ISSUE-INVARIANT: LB_NULL/UB_NULL reserved but masked silently (low)]` — `RANGE_HAS_LBOUND` (line 48) treats RANGE_LB_NULL identically to RANGE_LB_INF; consider rejecting the reserved bits in `range_deserialize` instead of silent acceptance.
