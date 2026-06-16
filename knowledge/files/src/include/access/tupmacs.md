# `access/tupmacs.h` — tuple-pointer macros (alignment + null bitmap)

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/access/tupmacs.h`)

## Role
The walk-attributes-in-a-tuple primitives shared between heap tuples,
index tuples, and array internals: null-bitmap inspection (`att_isnull`,
`populate_isnull_array`, `first_null_attr`), alignment-aware fetch
(`fetch_att`, `fetchatt`, `align_fetch_then_add`), pointer advancement
(`att_align_*`, `att_addlength_*`), and `store_att_byval`.

## Public API
- `att_isnull(ATT, BITS)` (`tupmacs.h:27`) — note: 0 in bitmap = null.
- `populate_isnull_array(bits, natts, isnull)` (`tupmacs.h:42`) — bitmap
  → boolean array, processes 8 elements at a time.
- `first_null_attr(bits, natts)` (`tupmacs.h:243`) — find first NULL attnum.
- `fetchatt(A, T)` macro (`tupmacs.h:102`) — calls `fetch_att`.
- `fetch_att(T, attbyval, attlen)` (`tupmacs.h:107`) — error if unsupported
  byval length.
- `fetch_att_noerr(T, attbyval, attlen)` (`tupmacs.h:136`) — no error path,
  asserts only.
- `align_fetch_then_add(tupptr, *off, attbyval, attlen, attalignby)`
  (`tupmacs.h:171`) — combined align-fetch-advance for deform loops.
- `typalign_to_alignby(typalign)` (`tupmacs.h:301`) — TYPALIGN_xxx → bytes.
- `att_align_datum`, `att_datum_alignby`, `att_align_pointer`,
  `att_pointer_alignby`, `att_align_nominal`, `att_nominal_alignby`
  (`tupmacs.h:341`-`412`).
- `att_addlength_datum`, `att_addlength_pointer` (`tupmacs.h:419`-`446`).
- `store_att_byval(T, newdatum, attlen)` (`tupmacs.h:457`).

## Invariants
- `att_isnull`: **0 bit = NULL**, 1 bit = non-null (opposite of intuition).
  `[from-comment]` (`tupmacs.h:23`-`25`).
- `fetch_att` accepts byval lengths `sizeof(char|int16|int32|int64)`;
  any other size elog(ERROR). `[verified-by-code]` (`tupmacs.h:111`-`125`).
- `fetch_att_noerr` is safe **only** when attlen comes from
  `CompactAttribute`, because that struct's populator validates the
  length. Direct use with attacker-controlled attlen is undefined.
  `[from-comment]` (`tupmacs.h:131`-`135`).
- `att_align_pointer` exploits the **"zero byte = pad, non-zero = 1-byte
  varlena header"** convention to avoid aligning short varlenas.
  `[from-comment]` (`tupmacs.h:359`-`377`).
- `populate_isnull_array` populates **rounded up to multiple of 8** booleans.
  Caller must size the buffer accordingly. `[from-comment]` (`tupmacs.h:38`-`41`).
- `first_null_attr` requires that the bitmap contain at least one 0 bit
  (else the loop walks past the array). Documented hard precondition.
  `[from-comment]` (`tupmacs.h:235`-`241`).
- `align_fetch_then_add` handles attlen > 0 (fixed), attlen == -1 (varlena),
  attlen == -2 (cstring). `[verified-by-code]` (`tupmacs.h:177`-`223`).

## Notable internals
- `SPREAD_BITS_MULTIPLIER_32 = 0x204081U` — magic constant that, when
  multiplied by a 4-bit nibble, gives a 32-bit value with each bit of the
  nibble in the low bit of a separate byte (`tupmacs.h:58`-`87`). This
  vectorizes `populate_isnull_array`.
- `first_null_attr` walks bytes for `bytenum < natts/8`, then uses
  `pg_rightmost_one_pos32(~byte)` to find the bit. Validated against the
  slow loop under `USE_ASSERT_CHECKING` (`tupmacs.h:250`-`290`).
- FRONTEND build skips the inline functions that depend on Datum / elog
  (`tupmacs.h:89`, `:295`, `:448`-`477`).

## Trust-boundary / Phase D surface

These macros are the inner loop of every deform path. They take raw
pointers into a tuple buffer — every assumption (attlen, attalign,
attbyval) must match the tuple's actual layout. Drift between tupdesc and
on-disk format is the canonical "corrupt tuple → crash" pathway.

**[ISSUE-correctness: `fetch_att_noerr` skips length validation (low)]** —
Comment explicitly states it's safe ONLY with CompactAttribute attlen.
A future caller using a raw Form_pg_attribute attlen could pass an
unvalidated value. `tupmacs.h:131`-`135`.

**[ISSUE-correctness: `first_null_attr` walks past the bitmap if no 0 bit
exists in the array (low)]** — Documented precondition; if attacker
controls a tuple's null bitmap layout, this is reachable. Defense: callers
gate on `IndexTupleHasNulls` (or heap equivalent) before invoking.
`tupmacs.h:235`-`241`.

**[ISSUE-correctness: align macros use `cur_offset` as both uintptr_t and
char *` (informational)]** — Comments admit the type pun is "a bit of a
hack." Works because uintptr_t == sizeof(void *) on every supported
platform. `tupmacs.h:368`-`370`, `:427`-`428`.

**[ISSUE-resource: `populate_isnull_array` rounds natts up to multiple
of 8 (low)]** — Caller must allocate `natts + 7` booleans, not natts.
Mis-sized buffer → OOB write of up to 7 bytes. `tupmacs.h:38`-`41`.

**[ISSUE-defense-in-depth: `fetch_att` elog on unsupported byval length
is internal (informational)]** — A future attlen=128 byval type would
trip this; current code has no such type, so unreachable in practice.
`tupmacs.h:122`-`124`.

## Cross-refs
- `knowledge/files/src/include/access/itup.h` — `index_getattr` is a
  primary consumer.
- `access/htup_details.h` (not in this slice) — heap_deform_tuple
  primary consumer.
- `knowledge/idioms/memory-contexts.md` (not yet written).

<!-- issues:auto:begin -->
- [Issue register — `include-access`](../../../../issues/include-access.md)
<!-- issues:auto:end -->

## Issues
1. **[ISSUE-correctness: fetch_att_noerr length-validation contract is comment-only (low)]**
   — `tupmacs.h:131`-`135`.
2. **[ISSUE-correctness: first_null_attr walks past bitmap without a 0 bit (low)]**
   — `tupmacs.h:235`-`241`.
3. **[ISSUE-correctness: pointer/integer pun in align macros (informational)]**
   — `tupmacs.h:368`-`370`.
4. **[ISSUE-resource: populate_isnull_array rounds natts up by 7 (low)]**
   — `tupmacs.h:38`-`41`.
5. **[ISSUE-defense-in-depth: fetch_att elog on unsupported byval length (informational)]**
   — `tupmacs.h:122`-`124`.
