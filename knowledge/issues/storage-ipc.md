# Issues — `storage-ipc`

Per-subsystem issue register for `src/backend/storage/ipc/` files
surfaced during the file-by-file deep-corpus phase. See
`knowledge/issues/README.md` for the tag convention, severity scale,
and workflow.

**Parent subsystem doc:** (none yet; per-file docs under
`knowledge/files/src/backend/storage/ipc/`)

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | storage/ipc/shmem_hash.c:152 | undocumented-invariant | nit | `shmem_hash_allocator` stack-local lifetime contract is implicit — must outlive dynahash creation but no comment states this | open | knowledge/files/src/backend/storage/ipc/shmem_hash.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| | | | | | |

## Notes

- `shmem_hash.c` is a small, well-tested layer over `dynahash.c`. The
  only nit is an implicit-lifetime contract on the local allocator
  struct, which works today because `hash_create` finishes before the
  outer `shmem_hash_create` returns. A future refactor that deferred
  initial entry allocation could break this without warning.
- A handful of other files under `storage/ipc/` (`ipc.c`, `dsm.c`,
  `barrier.c`, `procsignal.c`, etc.) already have per-file knowledge
  docs from earlier sweeps; this register can absorb future findings
  from those as needed.
