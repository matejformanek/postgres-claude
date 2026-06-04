# src/backend/utils/adt/multixactfuncs.c

## Purpose

SQL surface for multixact internals — exposes
`pg_get_multixact_members(mxid)` (SRF returning per-member `(xid, status)`
rows) and `pg_get_multixact_stats()` (single-row counts + bytes used).

## Role in PG

- `pg_get_multixact_members` — `multixactfuncs.c:32-92`. Diagnostic /
  forensic use; resolves a MultiXactId to its constituent transaction
  ids and their lock status (`for-key-share`, `for-share`, etc., via
  `mxstatus_to_string`).
- `pg_get_multixact_stats` — `multixactfuncs.c:99-140`. Returns
  `(multixacts, members, members_bytes, oldest_multixact_id)`. Backs
  monitoring views.

## Key functions

- `pg_get_multixact_members(mxid)` (`:32`) — validates
  `mxid >= FirstMultiXactId`, then `GetMultiXactIdMembers(mxid,
  &multi->members, false, false)` and emits one row per element via the
  SRF protocol.
- `pg_get_multixact_stats()` (`:99`) — fills four datums via
  `GetMultiXactInfo(&multixacts, &nextOffset, &oldestMultiXactId,
  &oldestOffset)` then `MultiXactOffsetStorageSize(nextOffset,
  oldestOffset)`. **Privileged**: gates detail behind
  `has_privs_of_role(GetUserId(), ROLE_PG_READ_ALL_STATS)`
  (`:122-129`); non-members get an all-NULL row.

## State / globals

None local — all data comes from `multixact.c`.

## Phase D notes

- `pg_get_multixact_stats` correctly nulls every column for
  non-`pg_read_all_stats` callers. Good pattern — same role as the rest
  of the stats functions in `pgstatfuncs.c`.
- `pg_get_multixact_members` has **no role check** beyond grant.
  In a fresh cluster it appears to be PUBLIC-executable; a low-priv
  caller can enumerate transaction IDs participating in a multixact.
  Information disclosure is mild (you'd need to know the mxid, and
  knowing xids of participants in row-level locks is not normally
  considered sensitive). [unverified — re-check pg_proc.dat]

## Potential issues

- [ISSUE-info-disclosure: `pg_get_multixact_members` exposes raw xids
  of *other* sessions' row-level lock participation; combined with
  `txid_status()` could fingerprint app behaviour (low)]
- [ISSUE-dos: `mxid` argument is user-supplied; passing very large but
  in-range mxids could trigger expensive SLRU reads via
  `GetMultiXactIdMembers`. Bounded by SLRU size but a tight loop could
  thrash. No rate limit (low)]
