---
path: src/bin/pg_dump/pg_backup_null.c
anchor_sha: 4b0bf0788b0
loc: 224
depth: deep
---

# pg_backup_null.c

- **Source path:** `source/src/bin/pg_dump/pg_backup_null.c`
- **Lines:** 224
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `pg_backup_archiver.h` (defines the function-pointer slots populated here), `pg_backup_archiver.c` (`ahwrite`/`ahprintf` it calls), `pg_dump.c` (uses `archNull` for `-Fp` plain-text mode).

## Purpose

The "null" archive format — used by `pg_dump -Fp` to emit plain SQL directly to stdout/file. It is **write-only** (line 69-70: `if (AH->mode == archModeRead) pg_fatal("this format cannot be read")`) and stores nothing on disk as a structured archive: every TOC entry's defn is emitted as it arrives, and data is forwarded to `ahwrite()`. [verified-by-code, pg_backup_null.c:47-71]

This is the **primary surface for "what gets written to the .sql"** — every plain-text dump goes through these callbacks. Phase D's "auditing the emitted SQL" should center here plus the `_printTocEntry` / `RestoreArchive` flow in archiver.c.

## Top-of-file comment
> "Implementation of an archive that is never saved; it is used by pg_dump to output a plain text SQL script instead of saving a real archive." [from-comment, pg_backup_null.c:4-8]

## Public surface

Single exported function: `InitArchiveFmt_Null(ArchiveHandle *AH)` (47). Populates the function-pointer slots on AH:

- `WriteDataPtr = _WriteData` — forwards to `ahwrite()`. [verified-by-code, pg_backup_null.c:80-85]
- `EndDataPtr = _EndData` — emits `"\n\n"` separator.
- `WriteBytePtr = _WriteByte` — **no-op** (returns 0). The plain-text format has no archive-structure bytes to write.
- `WriteBufPtr = _WriteBuf` — **no-op**.
- `ClosePtr = _CloseArchive` — no-op.
- `PrintTocDataPtr = _PrintTocData` — calls the dumper's `dataDumper(arc, dataDumperArg)`. [verified-by-code, pg_backup_null.c:188-205]
- `StartLOsPtr / StartLOPtr / EndLOPtr / EndLOsPtr` — emit `BEGIN; … SELECT pg_catalog.lo_open(…); … SELECT pg_catalog.lo_close(0); … COMMIT;` framing.
- `ArchiveEntryPtr`, `ReadExtraTocPtr`, `WriteExtraTocPtr`, `PrintExtraTocPtr` — left NULL (no per-entry format state).
- `ClonePtr / DeClonePtr` — NULL (no parallel mode).

## Key behaviors

### LO emission (`_StartLO`, `_WriteLOData`, `_EndLO`) [security-relevant]

For each large object:

1. `_StartLO` (138-157) — pg_fatal if `oid == 0` (invalid OID). For pre-1.12 archives, emits `SELECT pg_catalog.lo_open(pg_catalog.lo_create('%u'), %d);\n` using `INV_WRITE`. **The OID is formatted with `%u`**, which is safe (integer). It also reroutes `AH->WriteDataPtr = _WriteLOData`. [verified-by-code, pg_backup_null.c:137-157]
2. `_WriteLOData` (91-107) — builds a bytea literal via `appendByteaLiteralAHX(buf, data, dLen, AH)` then emits `SELECT pg_catalog.lowrite(0, %s);\n`. The bytea literal goes through PG-standard escaping (`\\x...` hex form when std_strings on) — this is the **canonical sink** for binary LO content into SQL. As long as `appendByteaLiteral` is correct, no injection is possible from LO content.
3. `_EndLO` (164-170) — emits `SELECT pg_catalog.lo_close(0);\n\n` and restores `WriteDataPtr = _WriteData`.

### `_PrintTocData` (188-205)

For BLOBS entries: calls `_StartLOs` / `te->dataDumper(arc, arg)` / `_EndLOs` (the `BEGIN`/`COMMIT` framing). For non-BLOBS data entries: just calls the dumper.

The interesting thing here: there is **no schema-level emission in this file**. All `te->defn` printing happens up in `_printTocEntry` in archiver.c — this format module only handles the data side. The data-side emissions are LO-only; row data goes through `ahwrite()` → `CompressFileHandle->write_func` → the plain output file.

## Phase D notes [SQL injection surface]

- **`ahprintf(AH, "SELECT pg_catalog.lo_open(pg_catalog.lo_create('%u'), %d);\n", oid, INV_WRITE)`** (150) — `oid` is a `Oid` (uint32) from the dumper. `%u` is integer-safe; no quote injection. `[fine]`
- **`ahprintf(AH, "SELECT pg_catalog.lowrite(0, %s);\n", buf->data)`** (103) — `buf->data` came from `appendByteaLiteralAHX`. The escape logic is PG's standard and treats every byte (including `'`, `\`, NUL) correctly. Trust depends on `appendByteaLiteral` being airtight; the file's only contribution is calling it via the correct macro that passes `AH->encoding` and `AH->std_strings`. `[fine]`
- **No path-handling, no symlink-handling, no length-headers.** This format reads no archive, so there's no attacker-controlled-archive surface here. The entire Phase D risk class around "hostile archive" is **N/A** for null. `[fine]`
- **`pg_fatal("invalid OID for large object")`** (143) — defensive. A dump path could in principle yield OID 0 if pg_largeobject_metadata had been corrupted; here we refuse rather than emit `lo_open('0', …)`. `[fine]`
- **`ahprintf` is `pg_attribute_printf(2,3)` (declared in archiver.h)** — gcc/clang format-string checking applies to every emission. Any literal format string with %s-of-untrusted-content is caught at compile time if the field changes type. `[fine]`

## Cross-references

- `_printTocEntry` (archiver.c:3945) — the schema-side emitter that the null format relies on. Most of the "is this SQL safe?" auditing should target that.
- `appendByteaLiteralAHX` macro (pg_backup_archiver.h:443) — the binary-safe bytea formatter.
- `DropLOIfExists` (pg_backup_db.c:611-619) — emits `SELECT pg_catalog.lo_unlink(oid) FROM pg_catalog.pg_largeobject_metadata WHERE oid = '%u';`.

## Open questions

- The `--inserts`/`--column-inserts` path goes through `ExecuteSimpleCommands` in db.c when restoring, but during dump-to-plain (this file's domain) the INSERT statements are emitted via dumper's `WriteData → ahwrite → CompressFileHandle->write_func`. The escaping for INSERT data is handled by pg_dump.c's `dumpTableData_insert`, not here. [inferred — phase D should check those sites separately]
- Could a hostile dataDumper emit raw SQL meta-commands (e.g. `\!`) via `WriteData`? In null format, `WriteData → _WriteData → ahwrite` writes verbatim. The `\restrict KEY` token in plain-text mode (archiver.c:479-481) is the explicit defense; meta-commands inside row data are still gated by being inside a COPY block, but the threat model document (archiver.c:471-481) says malicious *source server response* is the concern, not malicious *dumper*. `[maybe — phase D-adjacent]`

## Confidence tag tally
`[verified-by-code]=12 [from-comment]=1 [from-readme]=0 [inferred]=1 [unverified]=0 [maybe]=1 [fine]=5`
