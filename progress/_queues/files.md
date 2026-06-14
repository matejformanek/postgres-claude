# Queue: pg-file-backfiller

Format: `[status] <repo-path> loc=<n> priority=<H|M|L>`
Refill rule: walk `progress/files-examined.md` for rows with
`depth in [skim, unread]`, sort by `LOC × subsystem-priority` desc,
take top 50.

> **2026-06-03 queue audit (cloud/pg-file-backfiller):** the prior head
> block (multixact/freelist/procarray/predicate/costsize/createplan/
> nodeHashjoin/reorderbuffer/walsender/autovacuum/relcache/catcache/
> snapmgr) was **stale** — every one of those files already has a deep
> per-file doc under `knowledge/files/` from the 2026-06-01 reconciliation
> backfill (anchor `ef6a95c7c64`, which per STATE.md §"Source commit at
> last verification" carried only 1 build-system trailing commit → no
> corpus impact, so no refresh needed). They are marked `[done:covered-
> 2026-06-01]` below. The genuine gap was recomputed by diffing the
> GitHub tree at anchor `4b0bf0788b0` against `knowledge/files/` (1 322
> uncovered .c/.h; biggest priority cluster = `src/backend/utils/adt/`,
> 101 files). This run pops from that cluster.

## Entries

[done:1547425] src/backend/access/heap/heapam_visibility.c loc=1900 priority=H
[done:5b50725] src/backend/access/transam/twophase.c loc=2700 priority=H
[done:covered-2026-06-01] src/backend/access/transam/multixact.c loc=3014 priority=H
[done:covered-2026-06-01] src/backend/storage/buffer/freelist.c loc=700 priority=H
[done:covered-2026-06-01] src/backend/storage/ipc/procarray.c loc=4900 priority=H
[done:covered-2026-06-01] src/backend/storage/lmgr/predicate.c loc=5100 priority=H
[done:covered-2026-06-01] src/backend/optimizer/path/costsize.c loc=6700 priority=H
[done:covered-2026-06-01] src/backend/optimizer/plan/createplan.c loc=7400 priority=H
[done:covered-2026-06-01] src/backend/executor/nodeHashjoin.c loc=2000 priority=H
[done:covered-2026-06-01] src/backend/replication/logical/reorderbuffer.c loc=6300 priority=H
[done:covered-2026-06-01] src/backend/replication/walsender.c loc=4400 priority=H
[done:covered-2026-06-01] src/backend/postmaster/autovacuum.c loc=3700 priority=M
[done:covered-2026-06-01] src/backend/utils/cache/relcache.c loc=7000 priority=M
[done:covered-2026-06-01] src/backend/utils/cache/catcache.c loc=2600 priority=M
[done:covered-2026-06-01] src/backend/utils/time/snapmgr.c loc=2300 priority=M

## src/backend/utils/adt/ scalar-type cluster (recomputed gap, 2026-06-03)

[done:2484dbd] src/backend/utils/adt/bool.c loc=274 priority=H
[done:2484dbd] src/backend/utils/adt/char.c loc=196 priority=H
[done:2484dbd] src/backend/utils/adt/name.c loc=286 priority=H
[done:2484dbd] src/backend/utils/adt/xid.c loc=300 priority=H
[done:2484dbd] src/backend/utils/adt/tid.c loc=388 priority=H
[done:2484dbd] src/backend/utils/adt/oid8.c loc=107 priority=M
[done:2484dbd] src/backend/utils/adt/arrayutils.c loc=220 priority=H
[done:2484dbd] src/backend/utils/adt/pg_lsn.c loc=219 priority=H
[done:2484dbd] src/backend/utils/adt/uuid.c loc=674 priority=H
[done:2484dbd] src/backend/utils/adt/mac.c loc=332 priority=M
[done:2484dbd] src/backend/utils/adt/mac8.c loc=405 priority=M
[done:2484dbd] src/backend/utils/adt/enum.c loc=550 priority=H
[done:2484dbd] src/backend/utils/adt/cash.c loc=912 priority=M
[done:2484dbd] src/backend/utils/adt/numutils.c loc=1020 priority=H
[done:2484dbd] src/backend/utils/adt/encode.c loc=801 priority=H
[done:2484dbd] src/backend/utils/adt/quote.c loc=92 priority=H
[done:2484dbd] src/backend/utils/adt/ascii.c loc=159 priority=M

## Next-up (remaining utils/adt/ scalar + encoding gap, for future runs)

> **2026-06-04 queue audit (cloud/pg-file-backfiller):** this entire
> block was **stale** — all 8 files already have deep per-file docs under
> `knowledge/files/src/backend/utils/adt/` (verified on disk this run;
> `varbit.c.md`, `bytea.c.md`, `oracle_compat.c.md`, `regproc.c.md`,
> `format_type.c.md`, `domains.c.md`, `datum.c.md`, `expandeddatum.c.md`
> all present). Marked `[done:covered-prior]`. Per the refill rule (queue
> depth < 5), refilled from `progress/coverage-gaps.md` suggested attack
> order item 10 (`src/fe_utils`, 0/18 docs) — also closes the A4-flagged
> `string_utils.c` + `astreamer_tar.c` corpus gaps.

[done:covered-prior] src/backend/utils/adt/varbit.c loc=1465 priority=M
[done:covered-prior] src/backend/utils/adt/bytea.c loc=1106 priority=H
[done:covered-prior] src/backend/utils/adt/oracle_compat.c loc=841 priority=M
[done:covered-prior] src/backend/utils/adt/regproc.c loc=1708 priority=H
[done:covered-prior] src/backend/utils/adt/format_type.c loc=431 priority=H
[done:covered-prior] src/backend/utils/adt/domains.c loc=424 priority=H
[done:covered-prior] src/backend/utils/adt/datum.c loc=560 priority=H
[done:covered-prior] src/backend/utils/adt/expandeddatum.c loc=130 priority=H

## src/fe_utils/ frontend-shared utilities (refill, 2026-06-04)

Source path: `src/fe_utils/`. Anchor `4b0bf0788b0`. 18 .c files, 0 docs.
Frontend-shared helpers linked into psql, pg_dump, pg_basebackup, etc.
High-value: `string_utils.c` (fmtId + processSQLNamePattern chokepoint —
A4 gap), `astreamer_tar.c` (tar-stream trust — A4 gap), `recovery_gen.c`
(writes `primary_conninfo` with password — secret-scrub theme), the
`astreamer_{gzip,lz4,zstd}.c` decompression-bomb cluster (A5 theme).

[done:a11-fe_utils-2026-06-04] src/fe_utils/string_utils.c loc=1300 priority=H
[done:a11-fe_utils-2026-06-04] src/fe_utils/option_utils.c loc=120 priority=H
[done:a11-fe_utils-2026-06-04] src/fe_utils/query_utils.c loc=70 priority=H
[done:a11-fe_utils-2026-06-04] src/fe_utils/simple_list.c loc=120 priority=M
[done:a11-fe_utils-2026-06-04] src/fe_utils/conditional.c loc=130 priority=M
[done:a11-fe_utils-2026-06-04] src/fe_utils/cancel.c loc=190 priority=H
[done:a11-fe_utils-2026-06-04] src/fe_utils/connect_utils.c loc=160 priority=H
[done:a11-fe_utils-2026-06-04] src/fe_utils/recovery_gen.c loc=210 priority=H
[done:a11-fe_utils-2026-06-04] src/fe_utils/version.c loc=80 priority=M
[done:a11-fe_utils-2026-06-04] src/fe_utils/archive.c loc=100 priority=M
[done:a11-fe_utils-2026-06-04] src/fe_utils/astreamer_file.c loc=400 priority=M
[done:a11-fe_utils-2026-06-04] src/fe_utils/astreamer_tar.c loc=560 priority=H
[done:a11-fe_utils-2026-06-04] src/fe_utils/astreamer_gzip.c loc=380 priority=M
[done:a11-fe_utils-2026-06-04] src/fe_utils/astreamer_lz4.c loc=420 priority=M
[done:a11-fe_utils-2026-06-04] src/fe_utils/astreamer_zstd.c loc=360 priority=M
[done:a11-fe_utils-2026-06-04] src/fe_utils/mbprint.c loc=300 priority=M
[done:a11-fe_utils-2026-06-04] src/fe_utils/parallel_slot.c loc=470 priority=M
[done:a11-fe_utils-2026-06-04] src/fe_utils/print.c loc=2700 priority=M

## Next-up (src/include/fe_utils headers — companions to the A11 sweep, seeded 2026-06-04)

16 headers under `src/include/fe_utils/` (0 docs). Natural follow-on to
the A11 `src/fe_utils/*.c` sweep — most are small API-surface headers
declaring the structs/protos for the just-documented .c files. `print.h`
and `astreamer.h` carry the load-bearing struct definitions
(`printTableContent`, the `astreamer` vtable/ops). Refill source:
`progress/coverage-gaps.md` src/include → fe_utils 0/16.

> **2026-06-05 (cloud/pg-file-backfiller):** all 16 `src/include/fe_utils`
> headers documented this run → `knowledge/files/src/include/fe_utils/*.md`
> (companions to the A11 `.c` sweep). 3 new header-level
> undocumented-invariant issues filed (`print.h:202` mutable
> `pg_utf8format`, `astreamer.h:94` base-must-be-first-member,
> `psqlscan_int.h:121` BEGIN/END 4-identifier heuristic). `src/include/fe_utils`
> now 16/16. Marked `[done:fe_utils-headers-2026-06-05]`.

[done:fe_utils-headers-2026-06-05] src/include/fe_utils/print.h loc=238 priority=M
[done:fe_utils-headers-2026-06-05] src/include/fe_utils/astreamer.h loc=231 priority=M
[done:fe_utils-headers-2026-06-05] src/include/fe_utils/string_utils.h loc=69 priority=H
[done:fe_utils-headers-2026-06-05] src/include/fe_utils/conditional.h loc=102 priority=M
[done:fe_utils-headers-2026-06-05] src/include/fe_utils/psqlscan_int.h loc=155 priority=M
[done:fe_utils-headers-2026-06-05] src/include/fe_utils/psqlscan.h loc=93 priority=M
[done:fe_utils-headers-2026-06-05] src/include/fe_utils/parallel_slot.h loc=84 priority=M
[done:fe_utils-headers-2026-06-05] src/include/fe_utils/simple_list.h loc=71 priority=M
[done:fe_utils-headers-2026-06-05] src/include/fe_utils/connect_utils.h loc=48 priority=M
[done:fe_utils-headers-2026-06-05] src/include/fe_utils/option_utils.h loc=34 priority=M
[done:fe_utils-headers-2026-06-05] src/include/fe_utils/mbprint.h loc=30 priority=M
[done:fe_utils-headers-2026-06-05] src/include/fe_utils/recovery_gen.h loc=30 priority=M
[done:fe_utils-headers-2026-06-05] src/include/fe_utils/cancel.h loc=32 priority=M
[done:fe_utils-headers-2026-06-05] src/include/fe_utils/query_utils.h loc=24 priority=M
[done:fe_utils-headers-2026-06-05] src/include/fe_utils/version.h loc=23 priority=M
[done:fe_utils-headers-2026-06-05] src/include/fe_utils/archive.h loc=21 priority=M

## src/port platform-shim sweep (refill, 2026-06-05)

Source path: `src/port/`. Anchor `4b0bf0788b0`. 70 .c/.h files, 0 docs
(`progress/coverage-gaps.md` src/port 0/64 — file count drifted up to 70
incl. win32* shims). Refill per the queue depth<5 rule after the
fe_utils-headers run emptied the pending block. **Security-relevant
first** (Phase-D secret-scrub + crypto theme): `explicit_bzero.c` (the
in-tree scrub primitive the SecretBuf proposal would standardize on),
`pg_strong_random.c` (CSPRNG behind gen_random_uuid/SCRAM nonces),
`timingsafe_bcmp.c` (constant-time compare — pairs with the A11 pgcrypto
non-constant-time finding). Then the broadly-used string/format/path
shims. The ~22 `win32*.c` shims are low-priority platform glue — left for
a later batch, not seeded here.

> **2026-06-06 (cloud/pg-file-backfiller):** src/port security+broadly-used
> shim block processed — 14 per-file docs under `knowledge/files/src/port/`
> (the security trio `explicit_bzero`/`pg_strong_random`/`timingsafe_bcmp` are
> the in-tree SecretBuf/constant-time primitives; `path.c` is the
> archive-extraction path-traversal gate). New `knowledge/issues/port.md`
> register (3 open: nit/maybe). LOC corrected from queue estimates where they
> drifted (path.c 1165, snprintf.c 1515, pg_bitutils.c 194, chklocale.c 383).
> `getaddrinfo.c` is **deleted upstream** (404 at anchor) → `[skipped:deleted]`.
> Marked `[done:5025355]`.

[done:5025355] src/port/explicit_bzero.c loc=73 priority=H
[done:5025355] src/port/pg_strong_random.c loc=179 priority=H
[done:5025355] src/port/timingsafe_bcmp.c loc=43 priority=H
[done:5025355] src/port/snprintf.c loc=1515 priority=M
[done:5025355] src/port/path.c loc=1165 priority=H
[done:5025355] src/port/quotes.c loc=51 priority=M
[done:5025355] src/port/tar.c loc=235 priority=M
[done:5025355] src/port/strlcpy.c loc=71 priority=M
[done:5025355] src/port/strlcat.c loc=61 priority=M
[done:5025355] src/port/pgmkdirp.c loc=148 priority=M
[done:5025355] src/port/pgcheckdir.c loc=92 priority=M
[done:5025355] src/port/pg_bitutils.c loc=194 priority=M
[done:5025355] src/port/chklocale.c loc=383 priority=M
[skipped:deleted] src/port/getaddrinfo.c (404 at anchor 4b0bf0788b0 — removed upstream)
[done:5025355] src/port/getpeereid.c loc=78 priority=H

## src/timezone sweep (refill, 2026-06-06)

Source path: `src/timezone/`. Anchor `4b0bf0788b0`. PG-authored glue +
vendored IANA library. `pgtz.c` (the integration layer: zone load/cache,
case-insensitive tzfile open, session/log zone GUCs, enumeration) documented
this run. Remaining: the small PG/vendored headers (`pgtz.h`, `tzfile.h`,
`private.h`) then the large vendored IANA C files (`localtime.c` ~1600 LOC,
`strftime.c` ~500, `zic.c` ~3000 — the zone compiler; lowest doc-value as
near-verbatim upstream imports). The ~22 `src/port/win32*.c` shims remain
deferred as low-priority platform glue.

[done:5025355] src/timezone/pgtz.c loc=497 priority=H
[done:5025355] src/timezone/pgtz.h loc=81 priority=M
[done:5025355] src/timezone/tzfile.h loc=110 priority=M
[done:06b42c6] src/timezone/private.h loc=155 priority=M
[done:06b42c6] src/timezone/localtime.c loc=2023 priority=M
[done:06b42c6] src/timezone/strftime.c loc=582 priority=L
[done:06b42c6] src/timezone/zic.c loc=4022 priority=L

## src/backend/libpq backend-connection-security sweep (refill, 2026-06-07)

> **2026-06-08 queue audit (cloud/pg-file-backfiller):** this entire block was
> **STALE on refill** — all 17 `src/backend/libpq/*.c` files already have deep
> per-file docs under `knowledge/files/src/backend/libpq/` from the **A2
> libpq-stack sweep (2026-06-03, PR #41)**. `coverage-gaps.md` line 45 still
> listed "libpq 17 | 0 | 0.0%" (contradicting its own A2 note at line 99 for the
> *headers*), and the 2026-06-07 timezone-sweep refill copied that stale 0/17
> into the queue without checking the `.c` dir. Verified 2026-06-08 by listing
> `knowledge/files/src/backend/libpq/` (17 `.c.md` docs present, deep, anchored
> at `4b0bf0788b0`) and spot-reading `auth.c.md`/`crypt.c.md`/`auth-scram.c.md`/
> `hba.c.md`/`be-secure-openssl.c.md`. Marked `[done:covered-2026-06-03]`. The
> genuine gap was recomputed by diffing the GitHub tree at anchor against
> `knowledge/files/` (1 127 uncovered .c/.h). This run pops the
> `src/backend/storage/aio` cluster (PG18 AIO subsystem — flagged in STATE.md as
> the top `knowledge/subsystems/storage-aio.md` candidate, demand-signalled 4×
> by pg-user-question-harvester).

[done:covered-2026-06-03] src/backend/libpq/auth.c loc=1900 priority=H
[done:covered-2026-06-03] src/backend/libpq/crypt.c loc=350 priority=H
[done:covered-2026-06-03] src/backend/libpq/auth-scram.c loc=1300 priority=H
[done:covered-2026-06-03] src/backend/libpq/hba.c loc=2200 priority=H
[done:covered-2026-06-03] src/backend/libpq/be-secure-openssl.c loc=1800 priority=H
[done:covered-2026-06-03] src/backend/libpq/be-secure-gssapi.c loc=650 priority=M
[done:covered-2026-06-03] src/backend/libpq/be-gssapi-common.c loc=110 priority=M
[done:covered-2026-06-03] src/backend/libpq/auth-sasl.c loc=180 priority=H
[done:covered-2026-06-03] src/backend/libpq/auth-oauth.c loc=900 priority=M
[done:covered-2026-06-03] src/backend/libpq/be-secure.c loc=280 priority=H
[done:covered-2026-06-03] src/backend/libpq/be-secure-common.c loc=350 priority=M
[done:covered-2026-06-03] src/backend/libpq/pqcomm.c loc=1500 priority=M
[done:covered-2026-06-03] src/backend/libpq/pqformat.c loc=550 priority=M
[done:covered-2026-06-03] src/backend/libpq/pqmq.c loc=280 priority=L
[done:covered-2026-06-03] src/backend/libpq/pqsignal.c loc=80 priority=L
[done:covered-2026-06-03] src/backend/libpq/ifaddr.c loc=300 priority=L
[done:covered-2026-06-03] src/backend/libpq/be-fsstubs.c loc=600 priority=M

## src/backend/storage/aio — PG18 AIO subsystem sweep (refill, 2026-06-08)

Source path: `src/backend/storage/aio/` + the 4 companion headers under
`src/include/storage/`. Anchor `4b0bf0788b0`. Complete-the-directory run: the
10 `.c` files of the AIO engine plus `aio.h`/`aio_internal.h`/`aio_types.h`/
`aio_subsys.h`. **Top `knowledge/subsystems/storage-aio.md` candidate** per
STATE.md (AIO / read-stream / io_uring cluster flagged 4× by
pg-user-question-harvester #71). Core engine first (`aio.c` — handle state
machine), then callbacks/io/target/init/funcs, then the IO methods
(`method_worker.c`, `method_io_uring.c`, `method_sync.c`), then the
`read_stream.c` helper (the most-asked-about file). Headers carry the struct +
state-machine invariants.

[done:aio-2026-06-08] src/backend/storage/aio/aio.c loc=1358 priority=H
[done:aio-2026-06-08] src/backend/storage/aio/aio_callback.c loc=333 priority=H
[done:aio-2026-06-08] src/backend/storage/aio/aio_io.c loc=235 priority=H
[done:aio-2026-06-08] src/backend/storage/aio/aio_target.c loc=122 priority=M
[done:aio-2026-06-08] src/backend/storage/aio/aio_init.c loc=255 priority=M
[done:aio-2026-06-08] src/backend/storage/aio/aio_funcs.c loc=230 priority=M
[done:aio-2026-06-08] src/backend/storage/aio/method_sync.c loc=47 priority=L
[done:aio-2026-06-08] src/backend/storage/aio/method_worker.c loc=1031 priority=H
[done:aio-2026-06-08] src/backend/storage/aio/method_io_uring.c loc=812 priority=H
[done:aio-2026-06-08] src/backend/storage/aio/read_stream.c loc=1471 priority=H
[done:aio-2026-06-08] src/include/storage/aio.h loc=369 priority=H
[done:aio-2026-06-08] src/include/storage/aio_internal.h loc=421 priority=H
[done:aio-2026-06-08] src/include/storage/aio_types.h loc=137 priority=M
[done:aio-2026-06-08] src/include/storage/aio_subsys.h loc=34 priority=L

## src/backend/access/rmgrdesc — WAL-record-description routines (refill, 2026-06-08)

Source path: `src/backend/access/rmgrdesc/`. Anchor `4b0bf0788b0`. 22 `.c`
files (one `*desc.c` per resource manager) + the shared `rmgrdesc_utils.c`,
0 docs. These render WAL records for `pg_waldump` + rmgr debug logging;
several are the **canonical shared deserializers** between backend redo and
frontend waldump (`xactdesc.c` commit/abort/prepare parsers, `heapdesc.c`
prune+freeze deserializer, `standbydesc.c` shared-inval renderer). Done this
run: the 6 highest WAL-format value (shared helper + xlog/xact/heap/clog/
standby). The remaining 16 (per-AM descs) are queued for the next cloud run.

[done:rmgrdesc-2026-06-08] src/backend/access/rmgrdesc/rmgrdesc_utils.c loc=61 priority=H
[done:rmgrdesc-2026-06-08] src/backend/access/rmgrdesc/xlogdesc.c loc=425 priority=H
[done:rmgrdesc-2026-06-08] src/backend/access/rmgrdesc/xactdesc.c loc=517 priority=H
[done:rmgrdesc-2026-06-08] src/backend/access/rmgrdesc/heapdesc.c loc=475 priority=H
[done:rmgrdesc-2026-06-08] src/backend/access/rmgrdesc/clogdesc.c loc=59 priority=M
[done:rmgrdesc-2026-06-08] src/backend/access/rmgrdesc/standbydesc.c loc=140 priority=H
[done:rmgrdesc-cloud-2026-06-09] src/backend/access/rmgrdesc/nbtdesc.c loc=230 priority=M
[done:rmgrdesc-cloud-2026-06-09] src/backend/access/rmgrdesc/gindesc.c loc=200 priority=M
[done:rmgrdesc-cloud-2026-06-09] src/backend/access/rmgrdesc/gistdesc.c loc=95 priority=M
[done:rmgrdesc-cloud-2026-06-09] src/backend/access/rmgrdesc/hashdesc.c loc=160 priority=M
[done:rmgrdesc-cloud-2026-06-09] src/backend/access/rmgrdesc/spgdesc.c loc=140 priority=M
[done:rmgrdesc-cloud-2026-06-09] src/backend/access/rmgrdesc/brindesc.c loc=90 priority=M
[done:rmgrdesc-cloud-2026-06-09] src/backend/access/rmgrdesc/mxactdesc.c loc=85 priority=M
[done:rmgrdesc-cloud-2026-06-09] src/backend/access/rmgrdesc/committsdesc.c loc=42 priority=L
[done:rmgrdesc-cloud-2026-06-09] src/backend/access/rmgrdesc/dbasedesc.c loc=60 priority=L
[done:rmgrdesc-cloud-2026-06-09] src/backend/access/rmgrdesc/genericdesc.c loc=45 priority=L
[done:rmgrdesc-cloud-2026-06-09] src/backend/access/rmgrdesc/logicalmsgdesc.c loc=46 priority=L
[done:rmgrdesc-cloud-2026-06-09] src/backend/access/rmgrdesc/relmapdesc.c loc=35 priority=L
[done:rmgrdesc-cloud-2026-06-09] src/backend/access/rmgrdesc/replorigindesc.c loc=44 priority=L
[done:rmgrdesc-cloud-2026-06-09] src/backend/access/rmgrdesc/seqdesc.c loc=34 priority=L
[done:rmgrdesc-cloud-2026-06-09] src/backend/access/rmgrdesc/smgrdesc.c loc=45 priority=L
[done:rmgrdesc-cloud-2026-06-09] src/backend/access/rmgrdesc/tblspcdesc.c loc=42 priority=L

## src/include/executor/ thin nodeXxx.h decl headers (refill, 2026-06-09 cloud)

> **2026-06-11 queue audit (cloud/pg-file-backfiller):** this entire
> block was **STALE** — all 33 `src/include/executor/nodeXxx.h` headers
> already have deep per-file docs under
> `knowledge/files/src/include/executor/`, written under the `<name>.md`
> convention (without the `.h`, e.g. `nodeBitmapAnd.md`,
> `nodeSeqscan.md`) — *not* the `<name>.h.md` the 2026-06-09 refill note
> below requested. Verified on disk this run (spot-read
> `nodeBitmapAnd.md` + `nodeSeqscan.md`: both document the
> `src/include/executor/*.h` headers, pinned at `4b0bf0788b0`). STATE.md
> already records `src/include/executor` as 100% (A15+A17). Marked
> `[done:covered-prior]`. Genuine gap recomputed by diffing the GitHub
> tree at anchor `e18b0cb7344` against `knowledge/files/` (457 uncovered
> .c/.h). Highest-priority *real* cluster this run:
> `src/interfaces/libpq-oauth` (OAuth device-flow client — credential
> surface) + the `src/interfaces/libpq/test` tail. New block appended at
> the bottom.

> **2026-06-09 queue refill (cloud/pg-file-backfiller):** the
> `src/backend/access/rmgrdesc/` block above is now **fully drained** —
> all 22 WAL-descriptor files covered (6 high-value on 2026-06-08 + the
> 16 per-AM descs this run). Per the refill rule (queue depth < 5), the
> next-priority gap was recomputed by diffing the GitHub tree at anchor
> `4b0bf0788b0` against `knowledge/files/src/include/executor/` (with
> name normalization for the `nodeAgg.h.md` vs `execAsync.md` split that
> the A15 sweep left behind): **33 uncovered thin `nodeXxx.h`
> plan-node execution declaration headers**, exactly the set A15
> explicitly deferred to cloud. Each is a 1-3 line `ExecInitXxx` /
> `ExecXxx` / `ExecEndXxx` prototype header; expect to batch many per
> run. Load the `executor-and-planner` skill. NB: write docs as
> `<name>.h.md` (keep the `.h`) to match the majority convention and
> avoid widening the naming split.

[done:covered-prior] src/include/executor/nodeBitmapAnd.h loc=26 priority=M
[done:covered-prior] src/include/executor/nodeBitmapHeapscan.h loc=57 priority=M
[done:covered-prior] src/include/executor/nodeBitmapIndexscan.h loc=45 priority=M
[done:covered-prior] src/include/executor/nodeBitmapOr.h loc=26 priority=M
[done:covered-prior] src/include/executor/nodeCtescan.h loc=24 priority=M
[done:covered-prior] src/include/executor/nodeCustom.h loc=48 priority=M
[done:covered-prior] src/include/executor/nodeForeignscan.h loc=50 priority=M
[done:covered-prior] src/include/executor/nodeFunctionscan.h loc=26 priority=M
[done:covered-prior] src/include/executor/nodeGather.h loc=26 priority=M
[done:covered-prior] src/include/executor/nodeGatherMerge.h loc=30 priority=M
[done:covered-prior] src/include/executor/nodeGroup.h loc=24 priority=M
[done:covered-prior] src/include/executor/nodeIncrementalSort.h loc=43 priority=M
[done:covered-prior] src/include/executor/nodeIndexonlyscan.h loc=64 priority=M
[done:covered-prior] src/include/executor/nodeLimit.h loc=23 priority=M
[done:covered-prior] src/include/executor/nodeLockRows.h loc=24 priority=M
[done:covered-prior] src/include/executor/nodeMaterial.h loc=28 priority=M
[done:covered-prior] src/include/executor/nodeMemoize.h loc=39 priority=M
[done:covered-prior] src/include/executor/nodeMergeAppend.h loc=25 priority=M
[done:covered-prior] src/include/executor/nodeNamedtuplestorescan.h loc=26 priority=M
[done:covered-prior] src/include/executor/nodeNestloop.h loc=24 priority=M
[done:covered-prior] src/include/executor/nodeProjectSet.h loc=25 priority=M
[done:covered-prior] src/include/executor/nodeRecursiveunion.h loc=27 priority=M
[done:covered-prior] src/include/executor/nodeResult.h loc=27 priority=M
[done:covered-prior] src/include/executor/nodeSamplescan.h loc=25 priority=M
[done:covered-prior] src/include/executor/nodeSeqscan.h loc=52 priority=M
[done:covered-prior] src/include/executor/nodeSetOp.h loc=26 priority=M
[done:covered-prior] src/include/executor/nodeSubqueryscan.h loc=26 priority=M
[done:covered-prior] src/include/executor/nodeTableFuncscan.h loc=26 priority=M
[done:covered-prior] src/include/executor/nodeTidrangescan.h loc=57 priority=M
[done:covered-prior] src/include/executor/nodeTidscan.h loc=24 priority=M
[done:covered-prior] src/include/executor/nodeUnique.h loc=23 priority=M
[done:covered-prior] src/include/executor/nodeValuesscan.h loc=23 priority=M
[done:covered-prior] src/include/executor/nodeWorktablescan.h loc=24 priority=M

## src/interfaces/libpq-oauth + libpq/test (refill, 2026-06-11 cloud)

Source paths: `src/interfaces/libpq-oauth/` (5 files) +
`src/interfaces/libpq/test/` (2 files). Anchor `e18b0cb7344`. Selected as
the highest-value uncovered cluster after the stale executor block was
drained: the libpq-oauth module is the client-side OAuth Device
Authorization (RFC 8628) engine — a credential/data-leak surface squarely
on the Phase D theme. The `src/interfaces/libpq` directory itself was
already covered (32 `.c`/`.h` docs from a prior run); these 2 `test/`
files complete it. New `knowledge/issues/libpq-oauth.md` register (5 open:
nit/maybe). NB: docs written as `<name>.c.md`/`<name>.h.md` (keeping the
extension), matching the libpq-oauth sibling convention.

[done:cloud-2026-06-11] src/interfaces/libpq-oauth/oauth-curl.c loc=3163 priority=H
[done:cloud-2026-06-11] src/interfaces/libpq-oauth/oauth-curl.h loc=24 priority=M
[done:cloud-2026-06-11] src/interfaces/libpq-oauth/oauth-utils.c loc=155 priority=H
[done:cloud-2026-06-11] src/interfaces/libpq-oauth/oauth-utils.h loc=52 priority=M
[done:cloud-2026-06-11] src/interfaces/libpq-oauth/test-oauth-curl.c loc=527 priority=M
[done:cloud-2026-06-11] src/interfaces/libpq/test/libpq_testclient.c loc=37 priority=L
[done:cloud-2026-06-11] src/interfaces/libpq/test/libpq_uri_regress.c loc=84 priority=M

## Next-up (for the next cloud run — genuine gap recomputed 2026-06-11)

457 .c/.h uncovered at anchor `e18b0cb7344`. Biggest clusters (after this
run): src/interfaces/ecpg 127 (low Phase D); src/test/modules 60;
src/backend/snowball 56 + src/include/snowball 56 (generated stemmers —
defer); src/include/port 25; **src/backend/utils 22 (all
mb/conversion_procs encoding converters — encoding-smuggling theme, good
next target)**; src/backend/jit 5 + src/include/jit 5; src/backend/port 10
(sema/shmem + win32). Recompute from the tree before refilling — the
per-subdir 0% rows in coverage-gaps.md remain unreliable (executor and
libpq client were both already done).

## A23 close-gap update — 2026-06-12 (recomputed)

Foreground sweep landed `src/backend/jit/` (5/5), `src/backend/utils/mb/conversion_procs/`
(directory doc + 3 deep), `src/include/port/atomics/` (7/7), `src/include/port/win32/`
(12/12), `src/backend/snowball/` (directory doc + dict_snowball.c deep — 111 mechanical
files conceptually covered by the directory README and excluded from per-file queue).

**Remaining gap = ~240 files**, all on the cloud routine queue (NOT foreground):

### priority H — src/interfaces/ecpg (~127)
Embedded SQL preprocessor + runtime. Lower Phase-D relevance than libpq-oauth
(which is done) but still real cite surface. Order: `ecpg/preproc/` (the
.c bison/yacc-generated + helpers), then `ecpg/pgtypeslib/`, then `ecpg/ecpglib/`,
then `ecpg/include/`. Skip the `ecpg/test/*` SQL files (not .c/.h).

### priority M — src/test (~74)
Test scaffolding. Order: `src/test/modules/` (the real C modules — injection_points,
test_oat_hooks, test_decoding, etc. — each has cite-worthy invariants), then
`src/test/regress/` (regression-test C helpers like `regress.c`), then
`src/test/perl/` (mostly .pm — skip those, only the .c files matter).

### priority L — assorted stragglers (~10-15)
- `src/backend/jit/*.h` (1-2 if not covered by Agent 1)
- Any new files added upstream since 2026-06-10 anchor — `pg-anchor-refresh` will
  flag them via the audit queue once it starts running.

### Snowball — explicitly NOT in this queue
The 112 snowball files (55 .c + 55 .h + dict_snowball.c + snowball_runtime.h)
are documented as a unit via the directory README. Per-file docs would be
wasted on the 111 autogen files. If a stemmer needs special attention later,
the `pg-quality-auditor` can be asked to write a one-off per-file doc — but
the default is "directory-doc coverage".

## src/interfaces/ecpg — runtime libraries (cloud/pg-file-backfiller, 2026-06-12)

> Queue was empty (0 pending) at run start. Refilled per the refill rule
> from the priority-H `src/interfaces/ecpg` gap (A23 close-gap update,
> ordered preproc → pgtypeslib → ecpglib → include). This run took the
> **runtime-library trilogy** (ecpglib + pgtypeslib + compatlib = 20
> files) as one coherent fanout — the libraries a compiled ecpg program
> links against — leaving the `preproc` compiler + `include/` headers for
> the next runs. Anchor e18b0cb7344. New register: knowledge/issues/ecpg.md.

[done:ee88d24] src/interfaces/ecpg/ecpglib/connect.c loc=746 priority=H
[done:ee88d24] src/interfaces/ecpg/ecpglib/data.c loc=962 priority=H
[done:ee88d24] src/interfaces/ecpg/ecpglib/descriptor.c loc=1008 priority=H
[done:ee88d24] src/interfaces/ecpg/ecpglib/execute.c loc=2316 priority=H
[done:ee88d24] src/interfaces/ecpg/ecpglib/error.c loc=346 priority=H
[done:ee88d24] src/interfaces/ecpg/ecpglib/misc.c loc=599 priority=M
[done:ee88d24] src/interfaces/ecpg/ecpglib/prepare.c loc=662 priority=H
[done:ee88d24] src/interfaces/ecpg/ecpglib/sqlda.c loc=592 priority=M
[done:ee88d24] src/interfaces/ecpg/ecpglib/memory.c loc=176 priority=M
[done:ee88d24] src/interfaces/ecpg/ecpglib/typename.c loc=145 priority=M
[done:ee88d24] src/interfaces/ecpg/ecpglib/ecpglib_extern.h loc=270 priority=M
[done:ee88d24] src/interfaces/ecpg/pgtypeslib/dt_common.c loc=3027 priority=H
[done:ee88d24] src/interfaces/ecpg/pgtypeslib/numeric.c loc=1588 priority=H
[done:ee88d24] src/interfaces/ecpg/pgtypeslib/interval.c loc=1091 priority=M
[done:ee88d24] src/interfaces/ecpg/pgtypeslib/timestamp.c loc=921 priority=M
[done:ee88d24] src/interfaces/ecpg/pgtypeslib/datetime.c loc=713 priority=M
[done:ee88d24] src/interfaces/ecpg/pgtypeslib/common.c loc=148 priority=M
[done:ee88d24] src/interfaces/ecpg/pgtypeslib/dt.h loc=343 priority=M
[done:ee88d24] src/interfaces/ecpg/pgtypeslib/pgtypeslib_extern.h loc=45 priority=L
[done:ee88d24] src/interfaces/ecpg/compatlib/informix.c loc=1054 priority=H

## Next-up (for the next cloud run — ecpg remainder + src/test)

> ecpg runtime libraries DONE 2026-06-12. Remaining ecpg = `preproc/` (14
> .c/.h — the .y/.l-driven compiler: c_keywords.c, descriptor.c, ecpg.c,
> keywords.c, output.c, parser.c, type.c, util.c, variable.c + the
> *_extern.h / *_kwlist.h / type.h headers) and `include/` (19 installed
> headers: ecpglib.h, ecpgtype.h, sqlca.h, sqlda*.h, pgtypes_*.h, etc.).
> Take preproc next (priority H — load `parser-and-nodes` skill; the
> bison/flex .y/.l files are generated so skip those, document the .c
> helpers). Then the include/ headers as a cheap header batch. After ecpg:
> src/test/modules (~60, priority M).

## src/interfaces/ecpg/preproc — the ECPG preprocessor/compiler (cloud/pg-file-backfiller, 2026-06-13)

> Queue was fully drained (0 pending) at run start. Refilled per the
> refill rule from the priority-H `src/interfaces/ecpg` remainder
> (A23 close-gap; the runtime libraries landed 2026-06-12). This run
> takes the **preproc compiler** (the `ecpg` binary that translates
> embedded-SQL `.pgc` → `.c`): the 9 .c helpers named in the prior
> next-up note + `ecpg_keywords.c` + the 4 declaration/kwlist headers
> = 14 files. The flex scanner `pgc.l`, the bison grammar pieces
> (`ecpg.addons`/`.header`/`.trailer`/`.tokens`/`.type`) and `parse.pl`
> are generated/grammar-fragment inputs → NOT per-file documented.
> Load `parser-and-nodes`. Anchor e18b0cb7344.

[done:cloud-2026-06-13] src/interfaces/ecpg/preproc/ecpg.c loc=470 priority=H
[done:cloud-2026-06-13] src/interfaces/ecpg/preproc/type.c loc=700 priority=H
[done:cloud-2026-06-13] src/interfaces/ecpg/preproc/variable.c loc=560 priority=H
[done:cloud-2026-06-13] src/interfaces/ecpg/preproc/descriptor.c loc=290 priority=H
[done:cloud-2026-06-13] src/interfaces/ecpg/preproc/parser.c loc=250 priority=H
[done:cloud-2026-06-13] src/interfaces/ecpg/preproc/output.c loc=190 priority=M
[done:cloud-2026-06-13] src/interfaces/ecpg/preproc/util.c loc=190 priority=M
[done:cloud-2026-06-13] src/interfaces/ecpg/preproc/type.h loc=190 priority=M
[done:cloud-2026-06-13] src/interfaces/ecpg/preproc/preproc_extern.h loc=170 priority=M
[done:cloud-2026-06-13] src/interfaces/ecpg/preproc/c_keywords.c loc=55 priority=M
[done:cloud-2026-06-13] src/interfaces/ecpg/preproc/c_kwlist.h loc=55 priority=L
[done:cloud-2026-06-13] src/interfaces/ecpg/preproc/ecpg_keywords.c loc=45 priority=M
[done:cloud-2026-06-13] src/interfaces/ecpg/preproc/ecpg_kwlist.h loc=70 priority=L
[done:cloud-2026-06-13] src/interfaces/ecpg/preproc/keywords.c loc=40 priority=M

## Next-up (for the next cloud run — ecpg include/ headers, then src/test)

> preproc compiler DONE 2026-06-13 (14 files: 9 .c + ecpg_keywords.c + 4
> headers). The flex `pgc.l`, the bison grammar fragments
> (`ecpg.addons/.header/.trailer/.tokens/.type`) and `parse.pl` are
> generated/grammar inputs → intentionally NOT per-file documented.
> **ecpg now: ecpglib + pgtypeslib + compatlib + preproc all covered;
> only `src/interfaces/ecpg/include/` remains** (19 installed headers:
> ecpglib.h, ecpgtype.h, sqlca.h, sqlda-compat.h, sqlda-native.h,
> sql3types.h, ecpgerrno.h, pgtypes_*.h, etc.). Take `include/` next as
> a cheap header batch (load no special skill; they're API-surface
> headers declaring the structs/codes the just-documented .c files emit).
> After ecpg fully drained: **src/test/modules** (~60 C modules —
> injection_points, test_oat_hooks, test_decoding, etc., priority M),
> then src/test/regress C helpers. Recompute the genuine gap from the
> GitHub tree at the current anchor before refilling.
