# Issues — `storage-large-object`

Per-subsystem issue register for `src/backend/storage/large_object/`
(the server-side legacy LO API: `inv_create`, `inv_open`, `inv_read`,
`inv_write`, `inv_seek`, `inv_tell`, `inv_truncate`, `inv_drop`).

See `knowledge/issues/README.md` for the tag convention, severity scale,
and workflow.

**Parent subsystem doc:** (none yet; per-file docs under
`knowledge/files/src/backend/storage/large_object/`)

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | storage/large_object/inv_api.c:226 | security | maybe | `lo_open(INV_WRITE)` only checks `ACL_UPDATE`, but historically also grants read; a user with UPDATE but not SELECT can read the LO via `lo_open(INV_WRITE) + loread` | open | knowledge/files/src/backend/storage/large_object/inv_api.c.md §Potential issues |
| 2026-06-11 | storage/large_object/inv_api.c:64 | undocumented-invariant | nit | `lo_heap_r` / `lo_index_r` file-static Relation caches mean the LO API is not reentrant across processes; parallel workers cannot use it | open | knowledge/files/src/backend/storage/large_object/inv_api.c.md §Potential issues |
| 2026-06-11 | storage/large_object/inv_api.c:56 | undocumented-invariant | nit | `lo_compat_privileges` GUC disarms all LO ACL checks for both read and write — the only path that bypasses the whole permission system | open | knowledge/files/src/backend/storage/large_object/inv_api.c.md §Potential issues |
| 2026-06-11 | storage/large_object/inv_api.c:329 | stale-todo | nit | `inv_drop` always returns 1 "for historical reasons"; callers ignore the return — dead contract | open | knowledge/files/src/backend/storage/large_object/inv_api.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| | | | | | |

## Notes

- The `INV_WRITE`-grants-read behaviour (line 226-228 comment:
  "Historically, no difference is made between (INV_WRITE) and
  (INV_WRITE | INV_READ)") is the most notable finding. It's
  intentional and documented in-code, but a user holding `ACL_UPDATE`
  on an LO can read its contents without `ACL_SELECT`. Whether this is
  a security bug or a documented quirk depends on interpretation of
  the `lo_compat_privileges` design — the comment frames it as a
  client-API compatibility constraint, not a security policy choice.
  Worth raising on hackers before classifying as `confirmed`.
- The file-static `Relation` caches (lines 64-66) are an interesting
  historical artifact — they predate the broader use of
  TopTransactionResourceOwner ownership transfer. A modern rewrite
  would likely use per-call opens, but the current design is
  measurably cheaper for write-heavy LO workloads.
- All other findings are nit-level documentation gaps. The chunked-IO
  invariants in `inv_write` / `inv_truncate` / `inv_read` are correct
  and well-commented.
