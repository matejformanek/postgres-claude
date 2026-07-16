---
source_url: https://www.postgresql.org/docs/current/lo.html
fetched_at: 2026-07-16
anchor_sha: 572c3b2ddf8c
module: contrib/lo
---

# lo — Large-Object Maintenance (`lo` domain + `lo_manage` trigger)

Ships a typed marker for large-object reference columns plus a trigger that
garbage-collects the referenced large object when the referencing row is
updated or deleted. Solves the referential-integrity gap between PG's
independent-large-object model and JDBC/ODBC drivers that expect a BLOB to die
with its row. Trusted extension. Author: Peter Mount.

## Non-obvious claims

- The `lo` type is a **domain over `oid`**, not a distinct base type — it
  exists purely so a column holding a large-object OID is distinguishable from
  an ordinary OID column (and so ODBC drivers don't mistake it for something
  else). Anywhere an `oid` works, an `lo` value works.
  `[from-README]` — declared in `lo--1.1.sql` as `CREATE DOMAIN lo AS pg_catalog.oid`.
- `lo_manage()` is a trigger function that must be `BEFORE UPDATE OR DELETE …
  FOR EACH ROW`; on DELETE (or on UPDATE that changes the managed column) it
  calls `be_lo_unlink` via `DirectFunctionCall1` on the **old** OID, freeing
  the orphaned large object. `elog(ERROR)` if not fired by the trigger
  manager. `[verified-by-code source/contrib/lo/lo.c:24-39,86,106]`
- The managed column name is passed as the trigger argument
  (`EXECUTE FUNCTION lo_manage(raster)`). A column-scoped `BEFORE UPDATE OF
  raster` form avoids unlinking when unrelated columns change.
  `[from-README]`
- **Key correctness assumption:** `lo_manage` presumes **exactly one database
  reference per large object**. If two rows reference the same OID, deleting
  one row unlinks the object out from under the other — the module does no
  reference counting. `[from-README]`
- **Triggers do not fire on `DROP TABLE` or `TRUNCATE`**, so both leak every
  large object the table referenced. Mitigation the docs prescribe: `DELETE
  FROM tbl;` (which fires the per-row trigger) *before* dropping/truncating.
  `[from-README]`
- The large-object bytes live in the `pg_largeobject` system catalog (keyed by
  `loid`, chunked by `pageno`); `lo_manage` only manages the *reference
  lifecycle*, never the storage layout. `[from-README]`
- Belt-and-suspenders cleanup is the separate **`vacuumlo`** client program:
  it scans all `lo`/`oid` columns tree-wide and unlinks any `pg_largeobject`
  entry not referenced anywhere — the safety net for the DROP/TRUNCATE and
  frontend-tool-without-trigger gaps above. `[from-README]`

## Worked example (from the docs page)

```sql
CREATE TABLE image (title text, raster lo);
CREATE TRIGGER t_raster BEFORE UPDATE OR DELETE ON image
    FOR EACH ROW EXECUTE FUNCTION lo_manage(raster);
-- column-scoped variant (UPDATE only):
CREATE TRIGGER t_raster BEFORE UPDATE OF raster ON image
    FOR EACH ROW EXECUTE FUNCTION lo_manage(raster);
```

Multiple `lo` columns → one trigger each, with distinct trigger names.

## Links into corpus

- Large-object API + `pg_largeobject` storage: `be_lo_unlink` and the
  server-side lo functions live in `src/backend/libpq/be-fsstubs.c` /
  `src/backend/storage/large_object/inv_api.c`; see
  `[[knowledge/docs-distilled/lo-implementation.md]]` for the chunking model.
- Trigger firing semantics used by the BEFORE-row check:
  `[[knowledge/docs-distilled/trigger-interface.md]]`.
- `DirectFunctionCall1` fmgr entry used to invoke `be_lo_unlink`:
  `[[knowledge/docs-distilled/xfunc-c.md]]`.
