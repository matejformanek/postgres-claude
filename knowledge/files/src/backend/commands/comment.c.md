# comment.c

- **Source path:** `source/src/backend/commands/comment.c`
- **Lines:** 469
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"PostgreSQL object comments utility code." [from-comment, comment.c:4-5] `COMMENT ON object IS 'text'` and the underlying pg_description / pg_shdescription writers.

## Public surface

- `CommentObject` — top-level entry; resolves the ObjectAddress, checks ownership, calls `CreateComments` (regular objects) or `CreateSharedComments` (databases/roles/tablespaces — anything with shared catalog storage).
- `CreateComments` / `DeleteComments` / `CreateSharedComments` / `DeleteSharedComments` — pg_description / pg_shdescription mutators. Pass `NULL` comment to delete.
- `GetComment` — fetch; used by `\d+` via the SRF `obj_description`.

## Quirk: comments are not dependencies

A comment on an object lives in pg_description keyed by (classoid, objoid, objsubid). When the object is dropped, dependency.c's `getObjectDescription` makes a final pass to delete its comments — but a comment never blocks a DROP. This makes comments "weak" annotations, not first-class catalog entries.

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
