# multixact_read_v18.c

## Purpose

Stand-alone reader for `pg_multixact/offsets` and `pg_multixact/
members` files written by PostgreSQL ≤ v18. Self-contained because
the v18 macros (32-bit `MultiXactOffset`, `MULTIXACT_OFFSETS_PER_PAGE`,
member-group layout) differ from current backend definitions; the
file explicitly refuses `multixact_internal.h` include (line 28).

## Role in pg_upgrade

Driven by `multixact_rewrite.c::rewrite_multixacts` which walks every
multixid in `[from_multi, to_multi)` and calls
`GetOldMultiXactIdSingleMember` to extract the single relevant member
per multi (updater, or first locker). The translated multixacts are
written via the v19+ writer to the new cluster.

## Key functions

- `AllocOldMultiXactRead(pgdata, nextMulti, nextOffset)` `:119` —
  formats `<pgdata>/pg_multixact/offsets` and `.../members`, opens
  both via `AllocSlruRead` (slru_io.c) with `long_segment_names=
  false` (short pre-v19 names).
- `GetOldMultiXactIdSingleMember(state, multi, &member)` `:161` —
  port of v18's `GetMultiXactIdMembers` simplified:
  - Only returns one member (the update, else first lock).
  - No locking (no concurrent activity during upgrade).
  - Tolerates invalid entries (post-crash leftovers) without aborting.
  - On `length < 0` (corrupt!), `pg_fatal` with
    `"multixact %u has an invalid length (%d)"`.
- `FreeOldMultiXactReader(state)` `:357` — frees both SLRU readers.

## Static helpers (copy-pasted from v18 multixact.c)

- `MultiXactIdToOffsetPage` / `MultiXactIdToOffsetEntry` `:36,42`
- `MXOffsetToMemberPage` `:77`
- `MXOffsetToFlagsOffset` / `MXOffsetToMemberOffset` /
  `MXOffsetToFlagsBitShift` `:84,95,105`

Constants `MULTIXACT_OFFSETS_PER_PAGE`,
`MULTIXACT_MEMBERS_PER_PAGE`, etc. (lines 33-73) match v18 layout
exactly. Comment at lines 17-29 emphasizes this MUST NOT silently
collide with the new definitions; the `#define MultiXactOffset
should_not_be_used` guard (line 30) ensures any accidental use of
the unguarded type name in this file is a compile error.

## State / globals

None — all state in caller-passed `OldMultiXactReader *`.

## Phase D notes

[from-comment] **Corner-case handling** documented in lines 181-205:

1. Latest-multixid: uses controldata's `chkpnt_nxtmxoff` as
   `nextMXOffset` endpoint instead of reading offset for `multi+1`.
2. Offset wraparound: zero-offset means "unset", and a member with
   `xactptr == 0` is treated as wraparound past zero (line 297-303).

[ISSUE-correctness: `length = nextMXOffset - offset` (line 256) is
signed `int` arithmetic on `MultiXactOffset32` values. If
`nextMXOffset` wraps around past UINT32_MAX from the OLD cluster,
the signed subtraction is UB before the `< 0` check (low; requires
old cluster near 4-billion multixids)] — `multixact_read_v18.c:256`.

[ISSUE-correctness: `for (int i = 0; i < length; i++, offset++)`
loop (line 278) — `offset` is `MultiXactOffset32` (uint32) and will
wrap to 0 after UINT32_MAX. Per design that's how the old format
handled wraparound, but the wraparound case is only detected via
the `*xactptr == 0` check (line 297) (low)] —
`multixact_read_v18.c:278`.

[from-code] **`pg_fatal` on corrupt multi** (line 264, 335) — these
are the two unrecoverable error paths. "more than one updating
member" should never happen even after a server crash; aborts the
upgrade.

[from-code] **`pfree` on the reader struct** (line 362) — wrong
allocator pairing? `pg_malloc_object` (line 122) pairs with
`pfree`. In frontend code `pfree` resolves to `pg_free` via
fe_memutils. Behavior is correct.

[ISSUE-trust-boundary: Multi member arithmetic on attacker-
controlled bytes from pg_multixact/members (maybe-medium)] —
`multixact_read_v18.c:278-345`. An attacker who has write access
to the OLD cluster's `pg_multixact/members` could craft `length`
values that pass the `>= 0` check but trigger huge loops. Mitigated
because the multixact range is bounded by `[from_multi, to_multi)`
in the caller (multixact_rewrite.c:74). Outer iteration bound is
fine; inner `length` is bounded by `nextMXOffset - offset` which is
at most `MULTIXACT_MEMBERS_PER_PAGE * num_pages`.

[from-code] **Invalid-entry tolerance** (line 215-219, 251-254) —
zero offset returns `false` without erroring. This is by design for
crash-survivor multixids that the old server never wrote.

[from-comment] **"We could return 'false' here, but we prefer to
continue reading"** (line 309-313) — explicit choice to preserve
evidence of corruption rather than fail-fast. Trade-off documented.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_upgrade`](../../../../issues/pg_upgrade.md)
<!-- issues:auto:end -->
