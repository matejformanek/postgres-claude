# contrib-hstore (key/value type, pre-JSONB)

- **Source path:** `source/contrib/hstore/`
- **Last verified commit:** `e18b0cb7344` (2026-06-12 anchor)
- **Extension version:** `1.8` (per `hstore.control`)
- **Trusted:** yes
- **Header:** `source/contrib/hstore/hstore.h`

## 1. Purpose

A SQL type for `text → text` maps. Predates JSONB by years and is
still used in production where: (a) the data is naturally flat
(no nesting), (b) GIN-indexed `?` / `?&` / `?|` key-existence
queries dominate, (c) compatibility with existing schemas matters.
Mostly stable / maintenance-class — new development should default
to `jsonb` unless one of those reasons applies.

## 2. Mental model

- **An hstore is an array of HEntry headers + a single string area.**
  Each key and each value is one `HEntry`, in pairs. The `HEntry`
  carries an offset to the **end** of the string in the heap; the
  start is the previous entry's end (or 0 for the first entry).
  [verified-by-code `hstore.h:17-33`]
- **NULL values are first-class.** Keys cannot be NULL; values can.
  The `HENTRY_ISNULL` bit on the value-side `HEntry` encodes it.
- **Two index AMs supported.**
  - **GIN** (`hstore_gin.c`) — primary; one entry per key (and
    optionally per `key=>value` pair via `hstore_ops` /
    `hstore_hash_ops`).
  - **GiST** (`hstore_gist.c`) — signature-based; less common.
- **Subscripting** (`hstore_subs.c`) — added in PG 14 era;
  allows `h['key']` syntax in assignment contexts. Reading
  subscripts goes through normal fmgr.

## 3. Key files

- `hstore.h` — `HEntry`, `HSE_*` macros, `HStore` layout.
- `hstore_io.c` — input/output, `hstore(text[], text[])` constructor,
  `hstore_to_jsonb`, `hstore_to_json`, `populate_record`.
- `hstore_op.c` — operators: `->`, `?`, `?&`, `?|`, `||`, `-`,
  `@>`, `<@`, `=`.
- `hstore_gist.c` — GiST opclass (`gist_hstore_ops`).
- `hstore_gin.c` — GIN opclass (`gin_hstore_ops`).
- `hstore_compat.c` — backwards-compat reader for pre-9.0 hstore
  binary on-disk format.
- `hstore_subs.c` — subscripting handler.

## 4. Key data structures

- **`HEntry`** (`hstore.h:17-20`):
  ```c
  typedef struct { uint32 entry; } HEntry;
  ```
  Bit layout (`hstore.h:22-24`):
  - `0x80000000` — `HENTRY_ISFIRST` (this is the first key or value
    in the array — its `endpos` is the absolute end).
  - `0x40000000` — `HENTRY_ISNULL` (this slot is NULL).
  - `0x3FFFFFFF` — `HENTRY_POSMASK` (end offset within the string
    area; max ~1 GB).
  Accessors `HSE_ISFIRST` / `HSE_ISNULL` / `HSE_OFF` / `HSE_LEN`
  via macros at `hstore.h:27-33`.

- **`HStore`** (varlena) — header + `pairs` count + `entries[2 *
  pairs]` (key+value interleaved) + string-area bytes.

## 5. SQL surface (highlights)

- Type: `hstore`.
- Operators: `->` (lookup), `?` / `?&` / `?|` (key existence),
  `||` (concat), `-` (delete key), `@>` / `<@` (contains).
- Functions: `akeys`, `avals`, `each`, `exists`, `defined`,
  `hstore_to_array`, `hstore_to_json[b]`, `populate_record`,
  `slice`, `delete`.
- Opclasses: `gist_hstore_ops`, `gin_hstore_ops`, plus the
  `hstore_hash_ops` variant for cheaper key-value GIN entries.
- Subscripting: `h['key'] := 'val'` works in assignment contexts.

## 6. Invariants and gotchas

- **[INV-1]** `HENTRY_POSMASK = 0x3FFFFFFF` caps the string-area
  size at ~1 GB — same as the varlena-1GB cap, so academic.
  [from-comment `hstore.h:35-40`]
- **[INV-2]** Keys are sorted on input. Lookup is therefore
  binary search via `hstoreFindKey` — don't add a code path that
  produces an unsorted `HStore`.
- **[INV-3]** `hstore_compat.c` reads pre-9.0 on-disk hstore
  values (those bytes are still in existing tables, surviving
  pg_upgrade). Never remove that code path without an explicit
  upgrade-blocker note.
- New JSON / JSONB work should NOT live here — `src/backend/utils/adt/`
  jsonb is the canonical home. This module is feature-frozen
  except for compat / bug-fix work.

## 7. Owners (as of 2026-06-12)

Historical author: Oleg Bartunov + Teodor Sigaev. Active
committers in the area are mostly doing bug fixes — Tom Lane,
Andrew Dunstan, Daniel Gustafsson.

## 8. Local reviewer reflexes

- Any input-path change: the sorted-keys invariant must hold;
  `hstoreUniquePairs` is the canonical de-dup helper.
- Any new operator: confirm GIN strategy number reservation in
  the install SQL; the GIN opclass uses strategies 7/9/10/11
  for `?` / `?&` / `?|` / `@>`.
- Any pg_upgrade-affecting change: walk `hstore_compat.c` and
  the install SQL versioning carefully.


## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**7 files.**

| File |
|---|
| [`contrib/hstore/hstore.h`](../files/contrib/hstore/hstore.h.md) |
| [`contrib/hstore/hstore_compat.c`](../files/contrib/hstore/hstore_compat.c.md) |
| [`contrib/hstore/hstore_gin.c`](../files/contrib/hstore/hstore_gin.c.md) |
| [`contrib/hstore/hstore_gist.c`](../files/contrib/hstore/hstore_gist.c.md) |
| [`contrib/hstore/hstore_io.c`](../files/contrib/hstore/hstore_io.c.md) |
| [`contrib/hstore/hstore_op.c`](../files/contrib/hstore/hstore_op.c.md) |
| [`contrib/hstore/hstore_subs.c`](../files/contrib/hstore/hstore_subs.c.md) |

<!-- /files-owned:auto -->

## Cross-references

- `.claude/skills/access-method-apis/SKILL.md` — GIN / GiST opclass contracts.
- `.claude/skills/fmgr-and-spi/SKILL.md` — operator fmgr implementations.
- `.claude/skills/parser-and-nodes/SKILL.md` — subscripting handler interaction with the parser.
- `.claude/skills/catalog-conventions/SKILL.md` — install-SQL opclass registration.
- `doc/src/sgml/hstore.sgml` — user-facing reference.
- `source/src/backend/utils/adt/jsonb*.c` — the modern alternative most new work uses instead.
