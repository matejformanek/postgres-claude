---
source_url: https://www.postgresql.org/docs/current/bloom.html
fetched_at: 2026-06-28T00:00:00Z
anchor_sha: 4abf411e2328
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — bloom (the canonical custom index AM example)

`contrib/bloom` is the cleanest end-to-end example of a **third-party index
access method** in the tree: it implements the full `IndexAmRoutine` callback
set against a signature (Bloom-filter) index, and is the module to read first
when writing a custom AM. It is a *lossy, signature-based* index — every match
is a candidate that **must** be rechecked against the heap tuple. `[from-docs]`

## What it is and when it wins

- Signature-based, **lossy** index: each index entry is a fixed-width bit
  signature built by hashing the indexed column values. A probe can report a
  false positive ("element may be in the set"), so **index results are always
  rechecked using the actual heap attribute values**. `[from-docs]`
- The sweet spot: a table with **many columns** where queries test *arbitrary
  combinations* of them with equality. One bloom index replaces N single-column
  btrees — the docs' worked example is **153 MB bloom vs 531 MB** for 6 separate
  btree indexes. `[from-docs]`
- **Equality only.** Bloom supports only the `=` operator; no inequality, no
  range, no ordering, no `NULL` searching, no `UNIQUE`. btree remains correct
  whenever the leading column(s) *are* constrained — bloom only beats it when
  they are not. `[from-docs]`

## The WITH options (exact defaults/limits)

- `length` — signature length in bits per index entry, **rounded up to the
  nearest multiple of 16**. Default **80**, max **4096**. `[from-docs]`
- `col1 … col32` — bits generated per indexed column. Default **2**, max
  **4095**. Up to 32 indexed columns. `[from-docs]`
- Example: `CREATE INDEX … USING bloom (i1,i2,i3) WITH (length=80, col1=2, col2=2, col3=4);` `[from-docs]`

## The AM-author angle (verified against source)

- The handler is a single SQL-callable function returning a stack/static
  `IndexAmRoutine`: `PG_FUNCTION_INFO_V1(blhandler)` at
  `source/contrib/bloom/blutils.c:32`; `blhandler(PG_FUNCTION_ARGS)` builds
  `static const IndexAmRoutine amroutine = { .type = T_IndexAmRoutine, … }` at
  `blutils.c:103-106`. `[verified-by-code]` This is the exact shape any new AM's
  `<am>handler` must follow — see `knowledge/docs-distilled/indexam.md` and
  `knowledge/docs-distilled/index-api.md`.
- The opclass interface bloom needs is minimal: **a hash function for the
  indexed type plus an equality operator**. Only `int4` and `text` opclasses
  ship with the module; supporting another type means adding an opclass with
  those two members. `[from-docs]`

## Links into corpus

- `[[knowledge/docs-distilled/indexam.md]]` — the `IndexAmRoutine` callback
  contract bloom implements (ambuild / aminsert / amgettuple / ambulkdelete …).
- `[[knowledge/docs-distilled/index-api.md]]` — the `<am>handler` entry-point
  convention bloom's `blhandler` is the textbook instance of.
- `[[knowledge/docs-distilled/indexes-types.md]]` — where bloom sits relative to
  btree/gin/gist/brin in the index-type taxonomy.
- `[[knowledge/docs-distilled/xindex.md]]` — opclass / strategy-number / support-
  function registration (bloom needs only hash + `=`).
- Skill: `access-method-apis` — bloom is the worked reference for "implement a
  pluggable index AM".
