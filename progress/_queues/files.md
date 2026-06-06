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

[pending] src/port/explicit_bzero.c loc=55 priority=H
[pending] src/port/pg_strong_random.c loc=160 priority=H
[pending] src/port/timingsafe_bcmp.c loc=50 priority=H
[pending] src/port/snprintf.c loc=1400 priority=M
[pending] src/port/path.c loc=750 priority=H
[pending] src/port/quotes.c loc=60 priority=M
[pending] src/port/tar.c loc=200 priority=M
[pending] src/port/strlcpy.c loc=55 priority=M
[pending] src/port/strlcat.c loc=55 priority=M
[pending] src/port/pgmkdirp.c loc=130 priority=M
[pending] src/port/pgcheckdir.c loc=90 priority=M
[pending] src/port/pg_bitutils.c loc=450 priority=M
[pending] src/port/chklocale.c loc=460 priority=M
[pending] src/port/getaddrinfo.c loc=420 priority=M
[pending] src/port/getpeereid.c loc=90 priority=M
