# `src/include/storage/md.h`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 65

## Purpose

Declares the md (magnetic-disk) storage-manager API surface — the
function pointers that populate `smgrsw[0]` plus the sync-handler
callbacks consumed by `sync.c`. Also declares `aio_md_readv_cb`, the
AIO completion-callback table used by `mdstartreadv`.

## Surface

- smgrsw vtable: `mdinit`, `mdopen`, `mdclose`, `mdcreate`,
  `mdexists`, `mdunlink`, `mdextend`, `mdzeroextend`, `mdprefetch`,
  `mdmaxcombine`, `mdreadv`, `mdstartreadv`, `mdwritev`,
  `mdwriteback`, `mdnblocks`, `mdtruncate`, `mdimmedsync`,
  `mdregistersync`, `mdfd`.
- Sync handler callbacks: `mdsyncfiletag`, `mdunlinkfiletag`,
  `mdfiletagmatches`.
- Admin: `ForgetDatabaseSyncRequests`, `DropRelationFiles`.

## Tag tally

`[verified-by-code]` 1.
