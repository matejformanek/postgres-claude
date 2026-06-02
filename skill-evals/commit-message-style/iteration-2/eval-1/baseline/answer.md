(Baseline = no PG skill knowledge; identical to iter-1 baseline.)

```
fix(pg_dump): handle empty --exclude-schema argument

Previously, passing an empty string to --exclude-schema caused a
NULL pointer dereference and crashed pg_dump. This patch validates
the argument and emits a clear error instead.

Changes:
- Added empty-string check in pg_dump option parsing
- Updated tests to cover the empty pattern case

Reported-by: Bob Smith <bob@example.com>
Reviewed-by: Tom Lane <tgl@sss.pgh.pa.us>
Discussion: https://www.postgresql.org/message-id/CAB7nPqTexample@mail.gmail.com

Co-Authored-By: Claude <noreply@anthropic.com>
Signed-off-by: Committer Name <committer@example.com>
```
