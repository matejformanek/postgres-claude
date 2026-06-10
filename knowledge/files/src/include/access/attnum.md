# `access/attnum.h` — AttrNumber typedef and helpers

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/access/attnum.h`)

## Role
The single typedef for column ordinals (`int16`) plus four classification
macros. Sentinels: 0 is invalid; negative values address system columns
(ctid, oid, xmin, …); positive values address user-defined columns starting
at 1.

## Public API
- `AttrNumber` typedef = `int16` (`attnum.h:21`).
- `InvalidAttrNumber = 0` (`attnum.h:23`).
- `MaxAttrNumber = 32767` (`attnum.h:24`) — `INT16_MAX`.
- `AttributeNumberIsValid(n)` (`attnum.h:34`) — `n != 0`.
- `AttrNumberIsForUserDefinedAttr(n)` (`attnum.h:41`) — `n > 0`.
- `AttrNumberGetAttrOffset(n)` (`attnum.h:51`) — `n - 1`, asserts user-defined.
- `AttrOffsetGetAttrNumber(off)` (`attnum.h:61`) — `off + 1`.

## Invariants
- `0` is reserved as InvalidAttrNumber. `[verified-by-code]` (`attnum.h:23`).
- User columns: `1 .. MaxAttrNumber`. System columns: `-1 .. -N`.
  `[from-comment]` (`attnum.h:19`-`20`, `:41`).
- `MaxAttrNumber = 32767` is the SQL standard's effective limit, but PG
  practically caps lower via `MaxHeapAttributeNumber = 1600` (see
  `htup_details.h`, not in this slice). `[inferred]`.
- `AttrNumberGetAttrOffset` is unsafe for system columns — asserts
  `n > 0`. Callers handling system columns must short-circuit. `[verified-by-code]`
  (`attnum.h:53`).

## Notable internals
- `int16` covers ±32767 — comfortably more than `MaxHeapAttributeNumber`.
- Negative range is unused for offset math; system-column handling is
  catalog-dispatched via `SystemAttributeDefinition` (in `tupdesc.h`).

## Trust-boundary / Phase D surface

Tiny header, mostly typedef. The risks live in callers.

**[ISSUE-correctness: AttrNumberGetAttrOffset on system column is Assert-only
(low)]** — A caller that passes a negative AttrNumber gets `(neg - 1)` in
production builds — silent OOB array index. `attnum.h:51`-`55`.

**[ISSUE-api-shape: MaxAttrNumber = INT16_MAX but practical limit is
MaxHeapAttributeNumber = 1600 (informational)]** — Two different caps in
the codebase; user code may import this header and assume 32767 is
reachable. `attnum.h:24`.

## Cross-refs
- `knowledge/files/src/include/access/tupmacs.h` — uses AttrNumber.
- `knowledge/files/src/include/access/itup.h` — INDEX_MAX_KEYS is a
  separate index-attr cap (32 by default).
- `access/htup_details.h` — `MaxHeapAttributeNumber=1600`.

## Issues
1. **[ISSUE-correctness: AttrNumberGetAttrOffset asserts only on system attrs (low)]**
   — `attnum.h:51`-`55`.
2. **[ISSUE-api-shape: type-level cap (32767) vs. practical cap (1600) divergence (informational)]**
   — `attnum.h:24`.
