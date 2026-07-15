---
source_url: https://www.postgresql.org/docs/current/hstore.html
fetched_at: 2026-07-14T20:50:00Z
anchor_sha: 1863452a4bfe
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.18 hstore — key/value store data type"
maps_to_skill: [access-method-apis, type-cache, jsonpath-and-jsonb]
---

# Docs distilled — hstore (key/value varlena type + GiST/GIN opclass)

The original PG key/value store type (predates `jsonb`). Interesting as a
compact worked example of a **varlena type carrying its own on-disk versioned
format** plus a **paired GiST-signature / GIN-inverted opclass** — the same
shape `access-method-apis` teaches, and a direct ancestor of the `jsonb`
containment operators.

## Non-obvious claims

- **On-disk format is a single varlena with a flags-and-count word, followed
  by a packed `HEntry` array (2 entries per pair: key then value).** The
  struct is `{ int32 vl_len_; uint32 size_; /* array of HEntry follows */ }`
  [[hstore.h:45]]; each `HEntry` is a single `uint32 entry` [[hstore.h:12]].
  Keys use array index `2*i`, values `2*i+1` [[hstore.h:75]].
  [verified-by-code @ 1863452a4bfe]
- **The `HEntry` word packs three things into 32 bits:** `HENTRY_ISFIRST
  0x80000000` (is this the first entry?), `HENTRY_ISNULL 0x40000000` (NULL
  value flag), `HENTRY_POSMASK 0x3FFFFFFF` (end-offset into the string pool)
  [[hstore.h:17]]. String length is the *difference* of adjacent end-offsets
  (`HSE_LEN`), so entries store no explicit length. [verified-by-code @ 1863452a4bfe]
- **Post-9.0 format is signalled by a top bit of `size_`.** `HS_FLAG_NEWVERSION
  0x80000000`; the pair count is `HS_COUNT(hsp) = size_ & 0x0FFFFFFF`
  [[hstore.h:52]]. Old (pre-9.0) data is still readable "with a slight
  performance penalty" until rewritten. Force the rewrite with
  `UPDATE t SET c = c || ''` or `ALTER TABLE … ALTER c TYPE hstore USING c || ''`
  (the ALTER path takes `ACCESS EXCLUSIVE` but avoids row-version bloat).
  [from-docs] + [verified-by-code @ 1863452a4bfe]
- **Values may be NULL; keys may not.** Keys are unique — declaring a duplicate
  keeps exactly one pair with *no guarantee which* (`'a=>1,a=>2'::hstore` →
  `"a"=>"1"`). Key/value are text only; pair order is not preserved on output.
  [from-docs]
- **Two index shapes, disjoint operator coverage.**
  - `USING GIST (h gist_hstore_ops)` — approximates the key/value set as a
    **bitmap signature**; opclass parameter `siglen` (bytes), **default 16**,
    range 1–2024. Indexes `@>`, `?`, `?&`, `?|`. [from-docs]
  - `USING GIN (h)` — inverted; indexes `@>`, `?`, `?&`, `?|`, and also `=`.
    [from-docs]
  - `USING BTREE`/`HASH` — support the `=` operator only (enables
    `GROUP BY`/`DISTINCT`/`UNIQUE` on whole hstores; sort order "not
    particularly useful"). [from-docs]
- **Subscripting is first-class** (`h['k']` fetch, `h['k'] := v` update). Fetch
  of a missing/NULL key returns NULL; **update with a NULL subscript raises an
  error** (the one place a NULL subscript is not silently tolerated).
  [from-docs]
- **PL transforms ship in the box**: `hstore_plperl(u)` ↔ Perl hash,
  `hstore_plpython3u` ↔ Python dict. The extension is **trusted** (installable
  by a non-superuser with `CREATE` on the DB). [from-docs]

## Operator → index quick table

| op | meaning | GiST | GIN |
|----|---------|------|-----|
| `@>` / `<@` | containment | ✓ | ✓ |
| `?` / `?&` / `?\|` | has key / all / any | ✓ | ✓ |
| `->` | value(s) for key(s) | — | ✓ |
| `=` | whole-hstore equality | — | ✓ (also btree/hash) |
| `-`, `\|\|`, `#=`, `%%`, `%#` | mutate/convert | — | — |

## Links into corpus

- `access-method-apis` skill — GiST signature opclass (`gist_hstore_ops`) and
  GIN inverted opclass are the same design pattern as `[[docs-distilled/pgtrgm.md]]`
  and `[[docs-distilled/btree-gin.md]]`.
- `[[docs-distilled/jsonpath-and-jsonb.md]]` sibling — `@>`/`?`/`?&`/`?|`
  containment operators map 1:1 onto the `jsonb` GIN opclass; hstore is the
  historical precursor.
- `[[knowledge/idioms/varlena-and-toast.md]]` — `HStore` is a TOAST-able
  varlena; the packed-offset `HEntry` layout mirrors the `jsonb` `JEntry`
  design in `[[knowledge/subsystems/toast-storage]]`.
