# `src/include/access/multixact_internal.h`

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**137 lines.**

## Role

On-disk layout primitives for the **pg_multixact** SLRU pair (offsets
and members). Internal to `multixact.c` but exposed here for
`pg_upgrade` (and `multixact_read_v18.c`) to write/read these files
directly without going through the running multixact subsystem.
[verified-by-code] `source/src/include/access/multixact_internal.h:1-14`

Includes an unusual include-guard trick (lines 15-21): the header
declares `MULTIXACT_INTERNAL_H` and explicitly notes that
`multixact_read_v18.c` checks for it — i.e. "you have included the
internal API, you're now responsible for using it correctly."

## Public API

### Offset SLRU (pg_multixact/offsets)
- `MULTIXACT_OFFSETS_PER_PAGE = BLCKSZ / sizeof(MultiXactOffset)` —
  with 8 KB pages and 8-byte offsets, **1024 offsets per page**
  (line 32; the "8 bytes per offset" comment on line 31 confirms it
  is now a 64-bit type).
- `MultiXactIdToOffsetPage(multi)`, `MultiXactIdToOffsetEntry(multi)`,
  `MultiXactIdToOffsetSegment(multi)` — index a `MultiXactId` into
  the offsets SLRU (lines 34-50).

### Member SLRU (pg_multixact/members)
- `MXACT_MEMBER_BITS_PER_XACT = 8` — one flag byte per member xid.
- `MULTIXACT_FLAGBYTES_PER_GROUP = 4` → 4 members per group →
  `MULTIXACT_MEMBERGROUP_SIZE = 4*4 + 4 = 20` bytes (4 flag bytes +
  4 xids), and "**409 groups per page**" (8KB / 20B = 409 rem 12, see
  comment line 58) [verified-by-code] lines 64-78.
- `MXOffsetToMemberPage`, `MXOffsetToMemberSegment`,
  `MXOffsetToFlagsOffset`, `MXOffsetToFlagsBitShift`,
  `MXOffsetToMemberOffset` — index a `MultiXactOffset` into the
  members SLRU (lines 80-122).
- `MultiXactOffsetStorageSize(new, old)` — bytes consumed by a range
  of member offsets (lines 124-134); used by autovacuum to decide
  when to emergency-vacuum.

## Invariants

- **INV-multixact-id-width:** `MultiXactId` is 32-bit (a `TransactionId`
  alias), wraps at ~4 billion. `MultiXactOffset` is also 32-bit in
  current source (despite the "8 bytes per offset" wording, which
  refers to the **on-disk slot size**, not the type — confirm in
  `multixact.h`). The offsets-per-page math (BLCKSZ/sizeof) on line
  32 yields 1024 ONLY if `sizeof(MultiXactOffset) == 8` on this build;
  on 32-bit `MultiXactOffset` it'd be 2048. [unverified — cross-check
  needed against `multixact.h` typedef]
- **INV-group-layout:** "4 bytes of flags, and then the corresponding
  4 Xids" — never mixed [verified-by-code] lines 56-59. This is what
  makes `MXOffsetToFlagsOffset` and `MXOffsetToMemberOffset` arithmetic
  work.
- **INV-group-waste:** 8KB / 20B = 409 groups + 12 wasted bytes per
  page. "Simplicity (and performance) trumps space efficiency here"
  [verified-by-code] line 59.
- **INV-byte-offsets-not-array-index:** "the 'offset' macros work with
  byte offset, not array indexes, so arithmetic must be done using
  'char *' pointers." [verified-by-code] lines 61-62. Pointer math
  bug magnet.

## Notable internals

The 4-flag-bytes-then-4-xids grouping is a **wraparound-resistant
layout** — it keeps each 8-bit flag aligned to its xid without
introducing per-element padding. Per-member status bits encode lock
mode (`MultiXactStatusForKeyShare`, `MultiXactStatusForShare`,
`MultiXactStatusForNoKeyUpdate`, `MultiXactStatusForUpdate`,
`MultiXactStatusNoKeyUpdate`, `MultiXactStatusUpdate`).

`MultiXactOffsetStorageSize` is autovacuum's input: when emergency
autovacuum thresholds are crossed (`autovacuum_multixact_freeze_max_age`,
member-space exhaustion), the system reads this size and decides whether
to force a freeze.

## Trust-boundary / Phase D surface

**A8/A14 SLRU wraparound** anchor: `MultiXactId` is 32-bit and wraps.
If a backend creates multixacts faster than vacuum can freeze them,
the system enters emergency mode and (in extremis) shuts down to
prevent silent xid wraparound. Members can also exhaust their offset
space independently (a 32-bit `MultiXactOffset` over 5-byte-per-member
slots = ~21 GB of pg_multixact/members before wrap).

**pg_upgrade direct-write hazard:** because this header is exposed
specifically for pg_upgrade to write files directly, **a bug in
pg_upgrade can corrupt the on-disk layout in a way the running server
won't catch until a transaction tries to read a multixact**. Phase-D
risk: any tool that uses this header (pg_upgrade, future migrators)
must keep the layout invariants exact; any mismatch is silent data
corruption.

The `multixact_read_v18.c` reference (line 20) hints at version-aware
read paths — i.e. the layout HAS changed across versions, and the
internal API has historical compat code. Worth a follow-up read.

## Cross-refs

- `access/multixact.h` — the public API (`MultiXactIdSetOldestVisible`,
  `MultiXactIdExpand`, status enums).
- `access/slru.h` — the SLRU manager these macros index into.
- `src/backend/access/transam/multixact.c` — implementation.
- `src/bin/pg_upgrade/` — the privileged consumer.
- `subsystems/transam.md` (if/when written) — SLRU wraparound narrative.

## Issues

- **ISSUE-precision**: comment "8 bytes per offset" (line 31) refers
  to slot size — should clarify whether `MultiXactOffset` itself is
  64-bit yet, or if the slot is padded.
- **ISSUE-trust-boundary**: this header is the contract that
  pg_upgrade silently relies on. Any future change to the group
  layout must be coordinated with pg_upgrade and any `_read_v*`
  shim files.
