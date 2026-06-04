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

[pending] src/backend/utils/adt/varbit.c loc=1465 priority=M
[pending] src/backend/utils/adt/bytea.c loc=1106 priority=H
[pending] src/backend/utils/adt/oracle_compat.c loc=841 priority=M
[pending] src/backend/utils/adt/regproc.c loc=1708 priority=H
[pending] src/backend/utils/adt/format_type.c loc=431 priority=H
[pending] src/backend/utils/adt/domains.c loc=424 priority=H
[pending] src/backend/utils/adt/datum.c loc=560 priority=H
[pending] src/backend/utils/adt/expandeddatum.c loc=130 priority=H
