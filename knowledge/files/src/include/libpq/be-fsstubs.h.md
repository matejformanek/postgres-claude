# be-fsstubs.h

- **Source path:** `source/src/include/libpq/be-fsstubs.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Internal C-callable entry points to the large-object (LO) read/write path,
plus transaction-end cleanup hooks. The fmgr-callable LO functions are
declared elsewhere; these are the non-fmgr backdoors [from-comment].

## Public API surface

- `int lo_read(int fd, char *buf, int len)` — read from an LO descriptor.
- `int lo_write(int fd, const char *buf, int len)` — write to an LO
  descriptor. Comment notes the names "probably should have had the
  underscore-free names, but too late now..." [from-comment].
- `void AtEOXact_LargeObject(bool isCommit)` — close LO descriptors at
  transaction end.
- `void AtEOSubXact_LargeObject(bool isCommit, SubTransactionId mySubid,
  SubTransactionId parentSubid)` — subxact cleanup variant.

## Cross-refs

- Related backend: `src/backend/libpq/be-fsstubs.c`.
- Related: `knowledge/files/src/include/libpq/libpq-fs.h.md`
  (`INV_READ`/`INV_WRITE` flag bits).
- LO storage proper is `src/backend/storage/large_object/inv_api.c`.

## Potential issues

- **[ISSUE-stale-todo: naming wart frozen by ABI]** `be-fsstubs.h:19-21` —
  the comment explicitly admits the `lo_` underscore prefix is a historic
  mistake but "too late now". A genuine API rename is unlikely; the comment
  effectively is the TODO. Severity: maybe; only worth noting since the
  pattern hints at other LO-API freeze points.

## Tally

`[verified-by-code]=1 [from-comment]=2`
