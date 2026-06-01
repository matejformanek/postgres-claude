# `src/backend/storage/smgr/smgr.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 1128
- **Source:** `source/src/backend/storage/smgr/smgr.c`

## Purpose

The storage-manager switch. Every "block-level" operation that the buffer
manager (or other backend code) wants to perform on a relation file is
dispatched through `smgr*` calls here. Maintains the per-backend
`SMgrRelation` hashtable (cached file handles) and forwards the actual
work to one entry in `smgrsw[]` (currently only `md.c`).
[from-comment] (`smgr.c:3-18`)

## Top of file

Doc comment (lines 1–62) covers: SMgrRelation lifetime (valid until
end-of-transaction since PG 17 unless pinned by relcache), the
`PROCSIGNAL_BARRIER_SMGRRELEASE` mechanism for forcing FD-close, and the
requirement that interrupts be held across most calls so that a procsignal
processed mid-operation cannot tear down state being mutated.

## Public surface (declared in `smgr.h`)

- Init / lifecycle: `smgrinit`, `smgropen`, `smgrclose`, `smgrrelease`,
  `smgrreleaseall`, `smgrreleaserellocator`, `smgrdestroyall`, `smgrpin`,
  `smgrunpin`, `AtEOXact_SMgr`, `ProcessBarrierSmgrRelease`.
- Block ops: `smgrexists`, `smgrcreate`, `smgrextend`, `smgrzeroextend`,
  `smgrprefetch`, `smgrmaxcombine`, `smgrreadv`, `smgrstartreadv`,
  `smgrwritev`, `smgrwriteback`, `smgrnblocks`, `smgrnblocks_cached`,
  `smgrtruncate`, `smgrimmedsync`, `smgrregistersync`.
- Bulk-drop / bulk-sync: `smgrdosyncall`, `smgrdounlinkall`,
  `pgaio_io_set_target_smgr`.

## Types of note

- `f_smgr` (lines 88–126): function-pointer table of one storage-manager
  vtable. `smgr_unlink` is documented to use WARNING (not ERROR) because
  it runs during post-commit/abort cleanup. [from-comment] (`smgr.c:81-87`)
- `smgrsw[]` (lines 128–152): single entry hooking to `md*` functions.
- `aio_smgr_target_info` (lines 172–176): callback table for AIO,
  including `smgr_aio_reopen` so an IO worker can re-acquire the fd if it
  executes in a different process from the issuer.
- `SMgrRelationHash` (line 160): per-backend hashtable keyed by
  `RelFileLocatorBackend`; `unpinned_relns` (line 162) is the dlist of
  not-pinned entries, drained at end of transaction.

## Invariants / contracts

- Most public smgr funcs wrap their work in `HOLD_INTERRUPTS()` /
  `RESUME_INTERRUPTS()` because a procsignal mid-call can trigger
  `smgrreleaseall()` and most code below is not reentrant.
  [verified-by-code] (e.g. `smgr.c:466-470`, `483-485`, `623-638`)
- `smgropen()` only creates a hash entry and calls `smgr_open`; it does
  not actually open kernel files. [from-comment] (`smgr.c:237`)
- `smgrextend()` updates the cached `nblocks` value on success; if it
  doesn't match the expected increment it is invalidated.
  [verified-by-code] (`smgr.c:633-636`)
- `smgrnblocks_cached()` returns the cached size only during recovery —
  outside recovery there's no shared-invalidation mechanism so the cache
  is too unreliable to trust. [verified-by-code] (`smgr.c:849-857`)
- `smgrtruncate()` (lines 874–925) requires `AccessExclusiveLock` and
  expects to run in a critical section; sends `CacheInvalidateSmgr`
  *before* doing the actual truncation so other backends drop dangling
  references. [from-comment]
- `smgrdounlinkall()` (lines 538–607) drops buffers, sends sinval,
  closes smgr-level FDs, then unlinks files — in that order — for the
  same race-free-rename reasoning. [from-comment]

## Cross-refs

- Inbound: `bufmgr.c` for ReadBufferExtended path; relcache pins.
- Outbound: every `smgr_*` callback in `md.c`; `bufmgr.c` for
  `DropRelationBuffers`, `FlushRelationsAllBuffers`.
- Sinval: `CacheInvalidateSmgr` (utils/cache/inval.c).

## Open questions

- The `smgrwritev()` NB about checkpoint racing (lines 776–786) explicitly
  warns that callers must provide their own anti-race (buffer lock or
  RedoPtr-recheck pattern from `bulk_write.c`). I have not enumerated all
  callers to confirm. `[unverified]`
- The `smgr_aio_reopen` path (lines 1063–1098) re-derives the fd via
  `smgrfd()` for an IO worker; the invariant that the relfile cannot have
  been dropped between IO issue and IO execution is `[unverified]` —
  presumably guaranteed by the AIO ownership model.

## Tag tally

`[verified-by-code]` 4 / `[from-comment]` 6 / `[unverified]` 2.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
