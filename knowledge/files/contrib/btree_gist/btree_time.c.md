# btree_time.c

## One-line summary

GiST opclass for `time` and `timetz`. 16-byte key `[TimeADT|TimeADT]`
(TimeADT is int64 microseconds-since-midnight). Has separate `compress`
and `consistent` entry points for `time` vs `timetz` because timetz coerces
to time.

## Public API

`gbt_time_{compress,fetch,union,picksplit,consistent,distance,penalty,same,
sortsupport}` plus `gbt_timetz_compress`, `gbt_timetz_consistent`,
`gbt_timetz_sortsupport` `source/contrib/btree_gist/btree_time.c:21-32`.

## Key invariants

- Key: `[lower:TimeADT|upper:TimeADT]`, size 16 (`gbtreekey16`).
- `timetz` (time with time zone) is coerced to `time` for indexing — the
  timezone offset is discarded. **The index is on `time AT TIME ZONE 'UTC'`-ish
  semantics, not on the displayed local time.**
- KNN distance via `Interval` arithmetic + `INTERVAL_TO_SEC` macro.

## Trust boundary / Phase D surface

- **timetz timezone-loss:** if a column is `timetz` and indexed with
  `gist_timetz_ops`, comparisons use only the time-of-day component. Two
  rows `'10:00+02'` and `'09:00+01'` (the same instant) compare equal in
  the GiST index but differ in raw `=` comparison. **EXCLUDE on timetz
  with GiST has subtly different semantics from EXCLUDE with btree** —
  worth verifying. The PG docs note this is intentional.
- Time wraparound: TimeADT is 0..24h microseconds. No wraparound concerns.

## Issues spotted

- [ISSUE-SEMANTIC: `gist_timetz_ops` discards timezone for ordering but
  not for equality recheck. Phase D test target: insert `'10:00+02'` and
  `'09:00+01'`, see whether `EXCLUDE WITH =` rejects the second. (MED —
  documented divergence from btree, but easy to misuse)]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-btree_gist.md](../../../subsystems/contrib-btree_gist.md)
