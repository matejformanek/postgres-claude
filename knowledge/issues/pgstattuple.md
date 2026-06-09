# Issues — `contrib/pgstattuple`

Per-subsystem issue register for **pgstattuple**, the table/index
statistics extension. 3 source files / ~1 800 LOC. Gated by
`pg_stat_scan_tables` predefined role.

**Parent docs:** `knowledge/files/contrib/pgstattuple/*` (3 docs:
`pgstattuple.c.md`, `pgstatindex.c.md`, `pgstatapprox.c.md`).

**Source:** ~13 entries surfaced 2026-06-09 by A12-2.

## Headlines

1. **VM-trust fail-open in `pgstatapprox`** — silently trusts VM
   bits → corrupt VM = wrong stats, no diagnostic. **Direct echo of
   A11 pg_amcheck critique.**

2. **Module disagrees with itself on "live"** — `pgstattuple.c`
   uses SnapshotDirty (counts INSERT_IN_PROGRESS as live);
   `pgstatapprox.c` uses HeapTupleSatisfiesVacuum (counts
   INSERT_IN_PROGRESS as dead). Same module, opposite semantics.

3. **Module disagrees with itself on corruption** — `pgstatindex.c`
   hash scan errors on corruption with ERRCODE_INDEX_CORRUPTED;
   `pgstattuple.c` hash silently swallows. Inconsistent policy.

4. **RLS row-count leak through `pg_stat_scan_tables`** — confirmed
   and inherent to the design. "Monitoring access" = "precise
   RLS-protected row-count extraction."

5. **Cost-amplification DoS** — full-scan operations are unrate-
   limited; `pgstattuple('huge_relation')` is essentially a
   sequential scan with no LIMIT. Same for `pgstatindex`.

## Cross-sweep references

- **A11 pg_amcheck (A6) fail-open pattern** has its second concrete
  echo here in `pgstatapprox`'s VM-trust.
- **Cross-module within A12**: pgstattuple is more disciplined than
  pageinspect (which has no `pg_stat_scan_tables` GRANT pattern at
  all).

## Entries

### pgstattuple.c

- [ISSUE-security: reveals RLS-bypassed row count to
  `pg_stat_scan_tables` members (confirmed)].
- [ISSUE-security: full-scan + per-page buffer-lock churn → cost-
  amplification DoS (likely)].
- [ISSUE-correctness: SnapshotDirty counts INSERT_IN_PROGRESS as
  live (differs from VACUUM) (nit)].
- [ISSUE-concurrency: `LockRelationForExtension(ExclusiveLock)`
  just to call `RelationGetNumberOfBlocks` (nit)].
- [ISSUE-api-shape: heap-AM-only (nit)].

### pgstatindex.c

- [ISSUE-security: leaf metrics enable row-count estimation of
  RLS-protected tables (maybe)].
- [ISSUE-security: pgstatginindex pending-list leaks recent-insert
  rate (nit)].
- [ISSUE-defense-in-depth: hash scan errors on corruption while
  pgstattuple's hash silently swallows — inconsistent policy in
  same module (nit)].
- [ISSUE-concurrency: does NOT take extension-lock (inconsistent
  with pgstattuple.c) (nit)].
- [ISSUE-security: full B-tree/hash scans = cost-amplification DoS
  (likely)].

### pgstatapprox.c

- [ISSUE-security: silently trusts VM bits → corrupt VM = wrong
  stats, no diagnostic. Same fail-open as A11 pg_amcheck
  (confirmed)].
- [ISSUE-correctness: counts INSERT_IN_PROGRESS as dead — opposite
  of pgstattuple.c in same module (maybe)].
- [ISSUE-security: cheap-VM-skip makes RLS row-count extraction
  faster than pgstattuple proper (confirmed)].
- [ISSUE-api-shape: `pgstattuple_approx_internal` non-static but
  undocumented as extension API (nit)].
- [ISSUE-defense-in-depth: no recency check on VM (nit)].
