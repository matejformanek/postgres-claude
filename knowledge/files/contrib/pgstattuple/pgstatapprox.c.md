# pgstatapprox.c

Covers `source/contrib/pgstattuple/pgstatapprox.c` (372 lines): the
visibility-map-aware fast-path stats walker for heap tables. Skips
pages whose VM bit says "all visible" and approximates their tuple
length from the FSM instead of reading them.

## One-line summary

`pgstattuple_approx(regclass)` scans only the heap pages whose VM
bit says they may contain dead-or-in-progress tuples; for
all-visible pages it asks the FSM for free space and approximates
`tuple_len = BLCKSZ - free_space`. Returns the same shape as
`pgstattuple` plus `scanned_percent` showing how many pages were
actually read.

## Public API / entry points

- `pgstattuple_approx(regclass)` —
  `source/contrib/pgstattuple/pgstatapprox.c:279`. Pre-1.5 has
  superuser check.
- `pgstattuple_approx_v1_5(regclass)` — `:299`. v1.5+, no C check;
  relies on `GRANT … TO pg_stat_scan_tables` in
  `pgstattuple--1.4--1.5.sql:118-119`.
- Internal: `pgstattuple_approx_internal` — `:307`. The relation
  opener / validator.
- Internal: `statapprox_heap` — `:116`. The scan workhorse.
- Internal: `statapprox_heap_read_stream_next` — `:71`. The
  read-stream callback that checks VM and decides per-block
  whether to read.

## Key invariants

- INV-1: Same predefined-role pattern: pre-1.5 entry has
  `superuser()` check; v1.5+ relies on the SQL GRANT.
- INV-2: Heap-AM-only (`:348-350`): rejects non-`HEAP_TABLE_AM_OID`.
- INV-3: Only `RELKIND_RELATION` / `MATVIEW` / `TOASTVALUE` (`:339-346`)
  — restricts to relkinds that have both a visibility map AND a
  free space map. Sequences and indexes excluded (despite being
  heap-backed in some sense).
- INV-4: Non-local temp rejection (`:330-333`).
- INV-5: `OldestXmin = GetOldestNonRemovableTransactionId(rel)`
  (`:124`) — same horizon VACUUM uses. The visibility judgement
  uses `HeapTupleSatisfiesVacuum(tuple, OldestXmin, buf)`
  (`:212`), NOT SnapshotDirty / SnapshotAny. **Different from
  `pgstattuple.c` which uses SnapshotDirty.**

## Notable internals

**VM-driven skip via read-stream callback.** `:70-103`: the
read-stream callback walks blocks 0..nblocks. For each block:

- `VM_ALL_VISIBLE(rel, blkno, &vmbuffer)` (`:89`) — checks the VM
  bit. If set, get `freespace = GetRecordedFreeSpace(rel, blkno)`,
  add `BLCKSZ - freespace` to `tuple_len` and `freespace` to
  `free_space`, and continue (skip this block).
- Otherwise increment `scanned` and return the block number — the
  read-stream will fetch and the consumer will lock + decode it.

**Why no `READ_STREAM_USE_BATCHING`.** Comment at `:137-142`: "the
callback accesses the visibility map which may need to read VM
pages. While this shouldn't cause deadlocks, we err on the side of
caution." So this uses `READ_STREAM_FULL` alone.

**Per-tuple visibility uses VACUUM semantics.** `:212-228`:
`HeapTupleSatisfiesVacuum` returns one of:
- `HEAPTUPLE_LIVE` / `HEAPTUPLE_DELETE_IN_PROGRESS` → live tuple
- `HEAPTUPLE_DEAD` / `HEAPTUPLE_RECENTLY_DEAD` /
  `HEAPTUPLE_INSERT_IN_PROGRESS` → dead tuple
- Anything else → `elog(ERROR, "unexpected HeapTupleSatisfiesVacuum
  result")` (`:225-227`).

**INSERT_IN_PROGRESS counted as dead.** Comment at `:206-210`: "We
follow VACUUM's lead in counting INSERT_IN_PROGRESS tuples as
'dead' while DELETE_IN_PROGRESS tuples are 'live'." This is the
opposite of `pgstattuple.c:353` which uses SnapshotDirty (treats
INSERT_IN_PROGRESS as live). **Same module, two different
definitions of "live".**

**`vac_estimate_reltuples` for extrapolation.** `:247`: applies
VACUUM's extrapolation logic to project the visited-pages count to
whole-table count. Same algorithm autovacuum uses.

**Skipped pages contribute "all live" estimate.** `:92-93`: for
skipped (all-visible) pages, we add `BLCKSZ - freespace` to
`tuple_len`. This treats every byte not marked as free space as a
live tuple — including line pointer overhead and special-area
bytes. The estimate is high by a small constant per page. Comment
at `:241-246` notes "There should be no dead tuples in all-visible
pages."

**VM buffer release.** `:264-268`: explicit
`ReleaseBuffer(p.vmbuffer)` after the loop. The VM buffer was
pinned by `VM_ALL_VISIBLE` and must be released; failure to do so
leaks a buffer pin across the SRF return.

## Trust boundary / Phase D surface

**VM trust — the data-integrity hinge.** The whole fast-path
correctness rests on `VM_ALL_VISIBLE` returning truth. If the VM
is corrupted (a bit set to 1 when the page actually has dead or
in-progress tuples), `pgstattuple_approx` will:
- Skip the page (no actual read).
- Add `BLCKSZ - freespace` to live `tuple_len`.
- Add `freespace` to `free_space`.
- Never see any dead tuple on that page.

Result: corrupted VM bits → silently wrong stats, no warning.
**This is the same fail-open pattern as A11 pg_amcheck calling out
in its critique** — trusting a derived structure without
verification.
**[ISSUE-security: pgstatapprox fast-path silently trusts VM
bits; corrupt VM = wrong stats, no diagnostic. Same fail-open
vector as A11 pg_amcheck noted (confirmed)]** —
`source/contrib/pgstattuple/pgstatapprox.c:89-94`.

**FSM trust (similar but less impactful).** `:91`:
`GetRecordedFreeSpace(rel, blkno)` returns the FSM's claim about
the page's free space. FSM is known to be approximate (writes
happen lazily; readers are not authoritative). If the FSM is
stale, `freespace` will be wrong, so `tuple_len` and `free_space`
diverge from reality. Less impactful than VM corruption because
FSM is *expected* to drift; the function name says "approx."

**RLS bypass / row-count leak.** Same as `pgstattuple.c`: a
`pg_stat_scan_tables` member learns the live-tuple count of any
RLS-protected table. With the `_approx` variant, the count is even
faster to obtain (no full scan needed for mostly-static tables).
**[ISSUE-security: pgstattuple_approx exposes RLS-bypassed row
count cheaply via VM-skipped scan; lower latency vector than
pgstattuple proper for mostly-static tables (confirmed)]**.

**Cost amplification — MUCH lower.** This is the entire point of
the `_approx` variant. On a quiescent table where most pages have
VM bits set, the function reads almost nothing. Admins should
prefer this for monitoring; pgstattuple proper should be reserved
for diagnostic deep-dives.

**Definition of "dead" differs from pgstattuple.c.** Same module,
different semantics:
- `pgstattuple.c`: SnapshotDirty → INSERT_IN_PROGRESS = live.
- `pgstatapprox.c`: HeapTupleSatisfiesVacuum → INSERT_IN_PROGRESS
  = dead.
A monitoring tool comparing the two outputs over time will see
inconsistent counts on a write-heavy table.
**[ISSUE-correctness: pgstattuple_approx and pgstattuple disagree
on INSERT_IN_PROGRESS classification within the same module
(maybe; documented but easy to miss)]** —
`source/contrib/pgstatapprox.c:212-228` vs
`source/contrib/pgstattuple/pgstattuple.c:341-353`.

**`pgstattuple_approx_internal` is publicly callable.** `:307`:
declared `Datum pgstattuple_approx_internal(Oid relid,
FunctionCallInfo fcinfo)` without `static`. Other extensions
could link against it. Probably intentional (consistency with
`pgstatginindex_internal`), but it means the relkind/AM checks at
`:330-350` are the trust boundary for any third-party caller.

**Lock posture.** `AccessShareLock` on the relation (`:323`).
Same as pgstattuple — doesn't conflict with autovacuum. The VM
buffer is pinned-only (`:135, :264`), not locked, so VM bits can
change under us. Comment doesn't address torn VM reads, but VM
bit updates are 8-bit atomic so torn reads are not an issue.

**`vmbuffer` reuse across blocks.** `:135`: initialized to
`InvalidBuffer`; `VM_ALL_VISIBLE` keeps it pinned across calls
that hit the same VM page. Released at the end (`:264-268`).
This is the buffer-management subtlety that read-stream's
`vmbuffer` parameter exists to handle.

## Cross-references

- `source/src/backend/access/heap/visibilitymap.c` —
  `visibilitymap_get_status`, the macro `VM_ALL_VISIBLE` resolves
  to.
- `source/src/backend/access/heap/heapam_visibility.c` —
  `HeapTupleSatisfiesVacuum`.
- `source/src/backend/storage/freespace/freespace.c` —
  `GetRecordedFreeSpace`.
- `source/src/backend/commands/vacuum.c` —
  `vac_estimate_reltuples`.
- `source/src/backend/utils/time/snapmgr.c` —
  `GetOldestNonRemovableTransactionId`.
- `source/src/backend/storage/aio/read_stream.c` — the
  `read_stream_begin_relation` / `read_stream_next_buffer` API
  used here.
- `knowledge/files/contrib/pgstattuple/pgstattuple.c.md` — the
  full-scan counterpart with different "live" semantics.

## Issues spotted

- **[ISSUE-security: pgstatapprox silently trusts VM bits; corrupt
  VM = wrong stats, no diagnostic. Fail-open vector matching A11
  pg_amcheck critique (confirmed)]** —
  `source/contrib/pgstattuple/pgstatapprox.c:89-94`.
- **[ISSUE-correctness: counts INSERT_IN_PROGRESS as dead, opposite
  of pgstattuple.c in same module; monitoring tools comparing
  outputs see false trends on write-heavy tables (maybe)]** —
  `:212-228`.
- **[ISSUE-security: cheap-VM-skip path makes RLS row-count
  extraction faster than `pgstattuple` proper (confirmed; design
  trade-off)]**.
- **[ISSUE-api-shape: `pgstattuple_approx_internal` is non-static
  but undocumented as an extension API; any third-party caller
  must replicate the relkind/AM gate at `:330-350` (nit)]**.
- **[ISSUE-correctness: skipped-page tuple_len estimate includes
  line pointer + special-area bytes, slight upward bias (nit;
  documented as approximate)]** — `:92-93`.
- **[ISSUE-defense-in-depth: no check that VM was last verified
  recently; admins should pair pgstattuple_approx with periodic
  `VACUUM (DISABLE_PAGE_SKIPPING)` to catch VM drift (nit;
  operational concern)]**.
