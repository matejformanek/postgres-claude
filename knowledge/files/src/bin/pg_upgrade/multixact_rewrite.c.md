# multixact_rewrite.c

## Purpose

Converts pre-v19 `pg_multixact/offsets` and `/members` files into the
v19+ format with 64-bit `MultiXactOffset`. Reads the old format via
`OldMultiXactReader` (multixact_read_v18.c) and writes the new SLRUs
via `SlruSegState` (slru_io.c). The new members SLRU starts at
offset 1 regardless of the old cluster's offset range — saves space
and simplifies the writer.

## Role in pg_upgrade

Called from the per-version upgrade path in `pg_upgrade.c` (called
through the SLRU rewriting step for clusters older than v19, after
the catalog dump but before data transfer). The returned
`MultiXactOffset` is stamped into the new cluster's pg_control via
`pg_resetwal`.

## Key functions

- `rewrite_multixacts(from_multi, to_multi)` `:38` — driver. Allocates
  writer for both SLRUs, optionally reader (skipped if `from == to`
  for pre-9.2 fresh-start case), iterates multixids, calls
  `GetOldMultiXactIdSingleMember` for each. Returns the post-rewrite
  `next_offset`.
- `RecordMultiXactOffset(writer, multi, offset)` `:134` (static) —
  switches to the right page in the offsets SLRU, writes one 64-bit
  offset.
- `RecordMultiXactMembers(writer, offset, nmembers, members)` `:156`
  (static) — for each member, switches to its page in the members
  SLRU, writes the TransactionId and status flag bits at the right
  byte/bit offset.

## State / globals

None.

## Phase D notes

[from-code] **`from_multi == to_multi` short-circuit** (line 66) —
"if from_multi == to_multi, this initializes the new pg_multixact
files in the new format without trying to open any old files." This
is the pre-9.2 case where old multixact wasn't tracked the same
way. The new cluster gets empty multixact files at the right page.

[from-code] **Always uses long segment names on the members writer**
(line 59) — the v19+ format. The offsets writer uses short names
(line 55) because of the comment "The offsets aren't widened to
64-bit in their on-disk file naming, only the values."

[from-code] **`prev_multixid_valid`-tracking** (line 44, 99) — even
for an invalid multi, we still write its offset if the PREVIOUS
multi was valid. Reason (comment line 92-97): "when reading a
multixid, the number of members is calculated from the difference
between the two offsets." So you need the next offset to bracket
the previous one's members.

[from-code] **Wraparound handling** in the iteration (line 110-112):
"if (multi < FirstMultiXactId) multi = FirstMultiXactId;" — same as
the backend's wraparound. Means the loop terminates after at most
`MaxMultiXactId - FirstMultiXactId + 1` iterations.

[from-code] **Single-member-per-multi simplification** (comment
line 79-86): only one member is written per old multi. Justification
is that locking-only XIDs don't matter after upgrade because there
are no in-flight transactions. So `nmembers == 1` always (assertion
implicit in `RecordMultiXactMembers` design; line 153 documents this).

[ISSUE-correctness: members writer starts at `next_offset = 1` (line
51); but `MXOffsetToMemberPage(1)` and onwards uses the SAME group
layout macros as the reader. If the new backend's
`MULTIXACT_MEMBERS_PER_PAGE` ever diverged from the v18 reader's
constant, this would silently corrupt the new SLRU (low; both are
derived from BLCKSZ which is stable per-cluster)] — Verified that
`MULTIXACT_MEMBERS_PER_PAGE` in `access/multixact_internal.h` (the
header included on line 13) is the SAME formula as in
multixact_read_v18.c's defines — both use 4-byte flagbytes + 4
TransactionIds per group.

[ISSUE-trust-boundary: every member XID and status byte from the
OLD cluster's pg_multixact is written verbatim into the new
cluster's pg_multixact via this rewriter (by design)] — multixact_
rewrite.c:182,189. Cannot validate XIDs against the new heap pages
because the heap was hard-linked or copied unchanged.

[from-code] **`Assert(members[i].status <= MultiXactStatusUpdate)`**
(line 171) — debug-only sanity check. Production builds with no
asserts would silently accept malformed status bits.

[ISSUE-undocumented-invariant: caller assumed to pass `nmembers ==
1` only — function loops `for (int i = 0; i < nmembers; ...)` but
the comment says "Currently, this is only ever called with
nmembers == 1" (line 153) (low)] — Future caller passing > 1 would
work, but `RecordMultiXactOffset` would need updating to bracket
properly.
