# Issues — `src/include/port`

Per-subsystem issue register for the **cross-platform port header layer** — atomics, SIMD, pthread, iovec, CRC32C, byte order, NUMA, platform-specific shims. 22 top-level headers / ~25 entries surfaced 2026-06-09 by A16-4.

**Parent docs:** `knowledge/files/src/include/port/*` (22 docs — all top-level headers; 25 sub-dir files in `atomics/`, `win32/`, `win32_msvc/` deferred to cloud).

## Headlines

1. **`atomics.h` u64 fallback is invisible at call sites** — `pg_atomic_*_u64` silently becomes a spinlock array on platforms lacking native 64-bit atomics. No header signal; backend concurrency primitives for the WHOLE backend have no perf-cliff detection.
2. **CRC32C trust-boundary cluster echo (A11/A13/A14)** — `pg_crc32c` is trivially collidable but the type name and header give no "untrusted-input-unsafe" signal. Cross-trust-boundary uses (WAL from untrusted archive, 2PC files, replication frames) need audit.
3. **`pg_numa_query_pages(pid>0, ...)` exposes another process's working set** — SQL layer is the only gate, no C-level privilege check. A14 pg_buffercache NUMA finding echo at the dispatch header.
4. **Windows durability narrative is split across two headers** — `win32_port.h` defines `fsync = _commit` (weak); proper `pg_NtFlushBuffersFileEx` is in `win32ntdll.h`. Neither cross-references the other.
5. **`pg_popcount32`/`_64` is bithack, NOT hardware POPCNT** — only buffer-`pg_popcount` uses the optimized pointer. Easy to mis-read the API as hardware-accelerated.
6. **`DatumBigEndianToNative` silently assumes SIZEOF_DATUM == 8** — 32-bit-build path footgun.
7. **NEON `vector8_shift_*` returns 0 + Assert for unknown shift** — release builds silent-wrong-answer if new caller adds untested shift amount.

## Entries — cross-platform (11 headers)

### atomics.h
- [ISSUE-documentation: u64 atomic fallback invisible; silently spinlock on platforms lacking native 64-bit atomics (nit)] — `:460-462`
- [ISSUE-api-shape: no acquire/release-only atomic API; everything is unordered or full-barrier — leaves cycles on ARM/POWER (maybe, perf)] — `:107-118`
- [ISSUE-correctness: `pg_atomic_unlocked_write_u32/u64` differ from safe variants only by name; typo = torn-write hazard (nit)] — `:282-291`
- [ISSUE-documentation: `PG_HAVE_8BYTE_SINGLE_COPY_ATOMICITY` referenced without pointer to where it's set (nit)] — `:15`

### simd.h
- [ISSUE-correctness: NEON `vector8_shift_*` returns 0 + Assert for unknown shift; release silent-wrong-answer (maybe)] — `:556-601`
- [ISSUE-documentation: `sizeof(VectorN)` differs per platform; no public max-stride constant (nit)] — `:11-14`

### pg_crc32c.h
- [ISSUE-security: CRC32C is trivially collidable; cross-trust uses have no "untrusted-input-unsafe" signal (maybe, A11/A13/A14 cluster)] — `:38`
- [ISSUE-audit-gap: no inventory of CRC32C trust-boundary callsites; Phase-D follow-up needed (maybe)] — `:13-25`
- [ISSUE-documentation: PG has CRC32C (WAL) + FNV-1a (data pages) — header doesn't cross-ref (nit)] — `:1-32`

### pg_numa.h
- [ISSUE-security: `pg_numa_query_pages(pid>0, ...)` exposes another process's working set (maybe)] — `:18`
- [ISSUE-defense-in-depth: pg_buffercache NUMA columns pg_monitor-gated; any new SQL function must preserve grant (maybe, A14 echo)] — `:17-19`

### pg_iovec.h, pg_bitutils.h, pg_bswap.h
- [ISSUE-documentation: pg_iovec `iovcnt==1` fast-path silently becomes pread/pwrite; tracing tools observe different syscall (nit)] — `pg_iovec.h:55-63`
- [ISSUE-correctness: `Assert(word != 0)` is the only `word==0` guard in pg_bitutils; release silent wrong values (nit)] — `pg_bitutils.h:44,114`
- [ISSUE-documentation: `pg_popcount32/_64` is bithack, NOT hardware POPCNT; only buffer-pg_popcount uses optimized pointer (maybe)] — `pg_bitutils.h:302-307`
- [ISSUE-correctness: function-pointer dispatch (`pg_popcount_optimized`, `pg_comp_crc32c`) init-vs-extension `_PG_init` ordering undocumented (nit)] — `pg_bitutils.h:282-295`
- [ISSUE-correctness: `DatumBigEndianToNative` silently assumes SIZEOF_DATUM == 8 (maybe, 32-bit build)] — `pg_bswap.h:142-146`
- [ISSUE-defense-in-depth: pg_bswap signed-int warning is comment-only; no static-assert (nit)] — `pg_bswap.h:10-13`

### pg_pthread.h, pg_lfind.h
- [ISSUE-documentation: pg_pthread doesn't warn that pthread is unsafe with backend palloc/ereport/shared-memory (nit)] — `pg_pthread.h:1-10`
- [ISSUE-documentation: pg_lfind has no public guidance on "when to reach for it vs tight C loop" (nit)] — `pg_lfind.h:1-18`

## Entries — platform-specific shims (11 headers)

- [ISSUE-documentation: win32.h comment claims "Leave a higher value in place" but code unconditionally pins `_WIN32_WINNT = 0x0A00` (nit)] — `win32.h:13-20`
- [ISSUE-documentation: win32_port.h `fsync = _commit` is weaker than POSIX; durability-strict path is `pg_NtFlushBuffersFileEx` from win32ntdll.h, not documented at the define (maybe)] — `win32_port.h:82-83`
- [ISSUE-correctness: win32_port.h `S_IFLNK` steals `S_IFCHR` bit; future char-device handling on Windows breaks (nit)] — `win32_port.h:321-334`
- [ISSUE-defense-in-depth: win32ntdll.h depends on undocumented ntdll.dll exports; not flagged in header (nit)] — `win32ntdll.h:24-32`
- [ISSUE-documentation: linux.h `HAVE_LINUX_EIDRM_BUG` workaround dates to July 2007; worth re-validating against 6.x kernels (nit)] — `linux.h:3-13`
- [ISSUE-documentation: darwin.h doesn't link `HAVE_FSYNC_WRITETHROUGH` to "fsync alone is insufficient on macOS HFS+/APFS" durability narrative (nit)] — `darwin.h:5-8`

## Cross-sweep references

- **A11/A13/A14 signature-collision cluster** — pg_crc32c.h is the hardware-CRC anchor (NOT crypto hash).
- **A14 storage-aio** — pg_iovec.h is the IO scatter-gather API host.
- **A14 pg_buffercache NUMA finding** — pg_numa.h is the dispatch header.
- **A2 libpq wire format** — pg_bswap.h is the network byte order anchor.
- **A7 record_recv stack-depth + JSON parsing** — pg_lfind.h + simd.h are the fast-path anchors.
- **A8/A14 atomic-flag concurrency** — atomics.h is the load-bearing primitive.
