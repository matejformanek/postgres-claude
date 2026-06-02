# Queue: pg-file-backfiller

Format: `[status] <repo-path> loc=<n> priority=<H|M|L>`
Refill rule: walk `progress/files-examined.md` for rows with
`depth in [skim, unread]`, sort by `LOC × subsystem-priority` desc,
take top 50.

## Entries

[done:1547425] src/backend/access/heap/heapam_visibility.c loc=1900 priority=H
[done:cloud/pg-file-backfiller/2026-06-02] src/backend/access/transam/twophase.c loc=2700 priority=H
[pending] src/backend/access/transam/multixact.c loc=3700 priority=H
[pending] src/backend/storage/buffer/freelist.c loc=700 priority=H
[pending] src/backend/storage/ipc/procarray.c loc=4900 priority=H
[pending] src/backend/storage/lmgr/predicate.c loc=5100 priority=H
[pending] src/backend/optimizer/path/costsize.c loc=6700 priority=H
[pending] src/backend/optimizer/plan/createplan.c loc=7400 priority=H
[pending] src/backend/executor/nodeHashjoin.c loc=2000 priority=H
[pending] src/backend/replication/logical/reorderbuffer.c loc=6300 priority=H
[pending] src/backend/replication/walsender.c loc=4400 priority=H
[pending] src/backend/postmaster/autovacuum.c loc=3700 priority=M
[pending] src/backend/utils/cache/relcache.c loc=7000 priority=M
[pending] src/backend/utils/cache/catcache.c loc=2600 priority=M
[pending] src/backend/utils/time/snapmgr.c loc=2300 priority=M
