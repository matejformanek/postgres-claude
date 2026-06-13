# contrib-lo (Large Object reference-cleanup trigger)

- **Source path:** `source/contrib/lo/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.2` (per `lo.control`)
- **Trusted:** yes (`trusted = true`)

## 1. Purpose

A **single trigger function** that auto-deletes a Large Object
when the row holding its OID reference is deleted. Solves the
classic LO leak: an `lo` column stores an `oid` referencing a
row in `pg_largeobject`, but PG doesn't track this reference
— deleting the row leaves the LO orphaned.

The smallest extension in the tree: 114 LOC. Just one function.
But it's the canonical "trigger-based reference counting"
example.

## 2. The trigger function

```c
PG_FUNCTION_INFO_V1(lo_manage);
```

[verified-by-code `lo.c:24-27`]

`lo_manage()` fires as a BEFORE UPDATE or BEFORE DELETE
trigger on a row containing an `lo`-typed column. It:

- For DELETE: calls `lo_unlink(oid)` on the OID being
  deleted.
- For UPDATE: if the new value differs from the old, unlinks
  the OLD value.
- For INSERT: nothing — the new LO doesn't need cleanup.

## 3. The setup

```sql
CREATE EXTENSION lo;

CREATE TABLE doc (
    id    serial PRIMARY KEY,
    file  lo
);

CREATE TRIGGER lo_trigger
BEFORE UPDATE OR DELETE ON doc
FOR EACH ROW EXECUTE FUNCTION lo_manage(file);
```

The trigger argument names the `lo` column. Multiple
triggers (one per `lo` column) for tables with multiple
LO references.

## 4. The "Large Object" type

PG's Large Object system predates TOAST:

- **`pg_largeobject`** — system catalog storing LO chunks
  (one row per 2KB chunk).
- **`pg_largeobject_metadata`** — owner + ACL per LO.
- **`oid` references** — `lo` column type is an alias for
  `oid`; it stores the LO's identifier.

Created with `lo_creat()`; read with `lo_read()`; deleted
with `lo_unlink()`. These are libpq client-side functions
(`PQlo_*`) AND server-side SPI functions.

LOs are stored OUTSIDE the table — the `lo` column has
just the OID, not the data. So an LO can be referenced
from multiple rows / tables; the reference counting is
the application's job.

## 5. Why not just use bytea?

TOAST (introduced in PG 7.1) handles most large-data needs
inline; `bytea` columns up to 1GB are now routine. LOs are
mostly legacy.

LOs remain useful for:
- **Streaming I/O** — `lo_read` / `lo_write` support
  position-based access. `bytea` requires whole-value read.
- **Multi-row sharing** — the same LO can be referenced from
  many rows; `bytea` would duplicate the data.
- **Pre-9.x compatibility** — older codebases.

## 6. The orphan problem (and lo's solution)

Without the `lo` extension's trigger:

```sql
INSERT INTO doc (file) VALUES (lo_import('/path/to/big.pdf'));
-- LO oid is now stored in 'file' column

DELETE FROM doc WHERE id = 42;
-- Row deleted; LO still exists in pg_largeobject — orphaned!
```

VACUUM does NOT clean orphaned LOs. They sit forever,
consuming disk + bloating pg_largeobject.

With the trigger:

```sql
DELETE FROM doc WHERE id = 42;
-- Trigger fires; calls lo_unlink(file); LO removed.
```

The `vacuumlo` utility (also in contrib) can sweep up
orphaned LOs after the fact.

## 7. The lo_manage_columns trick

The trigger can be installed on multiple columns simultaneously
by passing each as an argument. But each column needs its own
trigger — `lo_manage` doesn't iterate.

For tables with many LO columns, the boilerplate adds up.
Most schemas use one LO per row.

## 8. Production-use guidance

- **For new schemas, prefer `bytea`** unless the LO
  features (streaming, sharing) are actually needed.
- **For existing LO-using schemas, install `lo`** trigger
  to prevent orphans.
- **`vacuumlo`** (in `source/contrib/vacuumlo/`) is a
  one-off cleanup tool for existing orphans.
- **LOs have per-LO ACL** (`pg_largeobject_metadata`) —
  more granular than table-level grants.

## 9. The single source file

[`source/contrib/lo/lo.c` — 114 LOC]

The implementation is straightforward: extract the trigger
context, validate it's a BEFORE UPDATE/DELETE, read the
relevant column from OLD, call `lo_unlink` on the OID.

[from-comment]

> not fired by trigger manager

The function ERRORs if called from anywhere other than the
trigger context — `CalledAsTrigger(fcinfo)` check.

## 10. Invariants

- **[INV-1]** Trigger must fire BEFORE UPDATE / DELETE.
- **[INV-2]** Column referenced must be `lo` (or compatible
  `oid`).
- **[INV-3]** UPDATE checks new vs old; INSERT skipped.
- **[INV-4]** `lo_unlink` is called inside the same xact;
  rollback cleans up.
- **[INV-5]** Trusted extension; CREATE EXTENSION without
  superuser.

## 11. Useful greps

- The trigger function:
  `grep -n 'lo_manage' source/contrib/lo/lo.c`
- The lo_unlink call site:
  `grep -n 'lo_unlink' source/contrib/lo/lo.c`
- The Large Object subsystem:
  `find source/src/backend/storage/large_object -type f`

## 12. Cross-references

- `knowledge/subsystems/storage-ipc.md` — Large Object
  storage is one of the legacy storage paths.
- `knowledge/idioms/toast-storage-strategies.md` — TOAST
  is the modern alternative.
- `knowledge/data-structures/heap-tuple-layout.md` — `oid`
  type and storage.
- `.claude/skills/extension-development/SKILL.md` —
  trigger-installing extension pattern.
- `source/contrib/lo/lo.c` — the single 114-LOC file.
- `source/contrib/vacuumlo/` — the orphan-cleanup utility
  (sibling).
