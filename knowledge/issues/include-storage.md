# Issues — `src/include/storage` (core)

Per-subsystem issue register for the **storage core header layer** — buffer manager, read stream, lmgr, lwlock, predicate-lock, semaphore, spinlock, condition variable, plus the PG18 subsystem-registration headers and the page-checksum implementation. 30 headers / ~22 entries (A15-4 baseline + A19-D additions 2026-06-11).

**Parent docs:** `knowledge/files/src/include/storage/*` (61 docs total after A15).
**Sibling registers:** `knowledge/issues/storage-aio.md` (PG18 AIO subsystem, 11 entries), `knowledge/issues/storage-buffer.md` (the synthesized subsystem doc; 5 entries).

## Headlines

1. **`bufmgr.h` exposes two silent-corruption-tolerant read paths** — `READ_BUFFERS_IGNORE_CHECKSUM_FAILURES` + `RBM_ZERO_ON_ERROR`. Must remain superuser-only wherever exposed via SQL.
2. **`bufmgr.h` `EB_SKIP_EXTENSION_LOCK` correctness-by-comment flag** — 3-case correctness contract documented only in comment; no Assert. Misuse during concurrent activity silently corrupts the relation.
3. **`read_stream.h` no in-API validation that callback-returned BlockNumber is in-range** — caller-only contract; defensive Assert would catch buggy callbacks.
4. **`lwlocklist.h` is the canonical INCLUDE-trick** — silently-coupled 3-file edit requirement (header + `wait_event_names.txt` + generate-lwlocknames.pl). No CI cross-check. Adding/removing locks without matching the names file causes silent gaps in `pg_stat_activity` wait reporting.
5. **`pg_locks` exposes per-tuple LOCKTAG info** (block, offset of locked tuple) to unprivileged users — monitoring-as-extraction cluster (A11/A14 echo).
6. **`LOCKTAG_OBJECT.objsubid` is 16 bits**, narrower than `pg_depend` storage; values > 65535 silently truncate at `SET_LOCKTAG_OBJECT`.
7. **`large_object.h` `lo_compat_privileges` GUC** = server-wide LO permission bypass for backwards-compat. Known trade-off but worth tagging.
8. **`predicate.h` SSI rollback** reachable via attacker-induced read patterns under SERIALIZABLE — DoS by induced serialization-failure on innocent victims (documented cost).

## Entries

### Buffer manager / read stream
- [ISSUE-security: `READ_BUFFERS_IGNORE_CHECKSUM_FAILURES` + `RBM_ZERO_ON_ERROR` silent-corruption-tolerant read paths; must remain superuser-only at SQL wrapper sites (nit)] — `bufmgr.h:126,51`
- [ISSUE-correctness: `EB_SKIP_EXTENSION_LOCK` 3-case correctness contract documented only in comment; no Assert (maybe)] — `bufmgr.h:75`
- [ISSUE-defense-in-depth: `EvictRelUnpinnedBuffers` / `MarkDirtyAllUnpinnedBuffers` need per-call privilege check at SQL wrapper sites (nit)] — `bufmgr.h:357-372`
- [ISSUE-correctness: read_stream has no in-API validation that callback-returned BlockNumber is in-range (nit)] — `read_stream.h:77-80`
- [ISSUE-documentation: read_stream `READ_STREAM_USE_BATCHING` constraints (no blocking, no nested batch) load-bearing for deadlock avoidance; static-analysis tag would help (nit)] — `read_stream.h:45-62`

### Item id / large object
- [ISSUE-correctness: `ItemIdSetNormal` silently truncates lp_off / lp_len via 15-bit bitfields; Assert (off < BLCKSZ && len <= BLCKSZ) would catch overflow (nit)] — `itemid.h:140-145`
- [ISSUE-defense-in-depth: `lo_compat_privileges` GUC is server-wide LO permission bypass for backwards-compat (nit)] — `large_object.h:82`

### Lock manager
- [ISSUE-security: pg_locks exposes per-tuple LOCKTAG info (block + offset of locked tuple) to unprivileged users (nit, monitoring-as-oracle A11/A14 echo)] — `lmgr.h:122-125`, `locktag.h:34-50`
- [ISSUE-correctness: LOCKTAG_OBJECT objsubid is 16 bits, narrower than pg_depend storage; values > 65535 silently truncate at SET_LOCKTAG_OBJECT (nit)] — `locktag.h:155-168`
- [ISSUE-api-shape: lwlocklist.h IDs and wait_event_names.txt silently coupled — adding/removing locks without matching names file causes silent gaps in pg_stat_activity (nit; could be CI-enforced)] — `lwlocklist.h:27-28`
- [ISSUE-documentation: "three coordinated edits" requirement for new built-in LWLocks (lwlocklist.h + wait_event_names.txt + generate-lwlocknames.pl) only documented inline (nit)] — `lwlocklist.h:22-31`

### Predicate (SSI) / proc
- [ISSUE-security: SSI rollback path reachable via attacker-induced read patterns under SERIALIZABLE; DoS by induced serialization-failure on innocent victims (nit, documented cost)] — `predicate.h:64-71`
- [ISSUE-security: pg_locks exposes predicate-lock TIDs of other sessions; reveals read patterns (nit, A11/A14 echo)] — `predicate.h:47`
- [ISSUE-documentation: ProcNumber 3-byte storage in inval.c hides ceiling at MAX_BACKENDS < 2^23-1 (nit, not currently reached)] — `procnumber.h:29-36`

### Proclist (added A19-D)
- [ISSUE-undocumented-invariant: "not in any list" sentinel is literal `0`, not `INVALID_PROC_NUMBER`; the distinction is load-bearing for `proclist_contains_offset`'s O(1) fast-path (nit)] — `proclist.h:152`, `proclist_types.h:20-27`
- [ISSUE-undocumented-invariant: at-most-one-proclist-per-PGPROC-node rule is documented in comment only; no Assert (nit)] — `proclist.h:142-147`
- [ISSUE-correctness: extension hooks reusing one PGPROC `proclist_node` across two proclists would corrupt silently (maybe)] — `proclist.h:145-167`
- [ISSUE-undocumented-invariant: `proclist_foreach_modify` allows ONLY deletion of `iter.cur`; macro doesn't enforce (nit)] — `proclist.h:206-217`
- [ISSUE-undocumented-invariant: "zero-init implies not-in-any-list" depends on PGPROC remaining a `MemSet`-able POD allocation (nit)] — `proclist_types.h:20-27`

### Page checksum implementation (added A19-D)
- [ISSUE-undocumented-invariant: `checksum_block_internal.h` deliberately lacks an `#ifndef` guard; well-meaning header cleanup tools (clang-tidy llvm-header-guard) would silently break SIMD multi-versioning (nit)] — `checksum_block_internal.h:15`
- [ISSUE-style: guard-less header trips automatic-cleanup tooling (nit, same root cause as above)] — `checksum_block_internal.h:15`
- [ISSUE-undocumented-invariant: `checksum_impl.h` is also an external-program ABI (`pg_rewind`/3rd-party tools embed it); changing `N_SUMS`/seeds is a frontend ABI break with no build-system signal (nit)] — `checksum_impl.h:1-17`
- [ISSUE-correctness: `pg_checksum_page` transiently writes 0 to caller's `pd_checksum`; needs caller-side exclusive access, no Assert (nit)] — `checksum_impl.h:181-189`
- [ISSUE-undocumented-invariant: implicit `BLCKSZ % (sizeof(uint32) * N_SUMS) == 0` constraint, not StaticAsserted (nit)] — `checksum_impl.h:113-117`
- [ISSUE-style: `pg_checksum_page` takes mutable `char *page` only for the transient zero-write; const-friendly variant would simplify frontend use (nit)] — `checksum_impl.h:172`

### Shmem-internal / subsystem registration (added A19-D, PG18-era)
- [ISSUE-api-shape: `pg_get_shmem_pagesize` is `PGDLLIMPORT`-exported from an "internal" header — either move to `shmem.h` or document the carve-out (nit)] — `shmem_internal.h:45`
- [ISSUE-doc-drift: `#ifdef EXEC_BACKEND` guards in `shmem_internal.h` lack a comment noting this is the Windows fork-emulation path (nit)] — `shmem_internal.h:32-43`
- [ISSUE-undocumented-invariant: `subsystemlist.h` ordering is load-bearing; only LWLock-first / AIO-last are commented, the rest encode dep edges nowhere written (maybe)] — `subsystemlist.h:19-21`
- [ISSUE-undocumented-invariant: LWLock-first is required for post-startup extension registrations (`SHMEM_CALLBACKS_ALLOW_AFTER_STARTUP`), not just startup ordering (nit)] — `subsystemlist.h:24-26`
- [ISSUE-api-shape: misspelling a name in `subsystemlist.h` / `subsystems.h` surfaces only as obscure link errors; could be StaticAssert-guarded (nit)] — `subsystemlist.h`, `subsystems.h`
- [ISSUE-style: `#ifdef`-gated entry pattern (only `USE_INJECTION_POINTS` today) is not documented in head comment (nit)] — `subsystemlist.h:82-84`
- [ISSUE-style: `subsystems.h` is intentionally minimal; future cleanup pressure to inline into `ipci.c` would regress the "automatic tools" use case (nit)] — `subsystems.h`

### Standby WAL defs (added A19-D)
- [ISSUE-undocumented-invariant: `oldestRunningXid` vs `oldestXmin` distinction documented in a one-line inline comment only; struct readers in isolation could conflate (nit)] — `standbydefs.h:53`
- [ISSUE-doc-drift: `standbydefs.h` claims frontend exposure but depends on `xl_standby_lock` declared in backend's `standby.h` (maybe)] — `standbydefs.h:41`
- [ISSUE-api-shape: only `xl_invalidations` exposes a `MinSizeOf*` helper; `xl_standby_locks` and `xl_running_xacts` should follow suit (nit)] — `standbydefs.h:38-70`
- [ISSUE-question: is `xl_invalidations.tsId` still consumed during redo, or vestigial? (nit)] — `standbydefs.h:60-70`

## Cross-sweep references

- `knowledge/subsystems/storage-buffer.md`, `storage-aio.md`, `storage-lmgr.md`, `storage-ipc.md` — synthesized subsystem docs already exist; these headers are their API surface.
- A11/A14 monitoring-as-extraction cluster — pg_locks per-tuple disclosure.
- A8 logical-replication slot — predicate-lock interaction (cross-link).
- A7 to_char / A13 tablefunc / A14 basebackup_to_shell text-injection cluster references stringinfo not here.
