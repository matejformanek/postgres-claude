# Issues — `contrib/citext`

Per-subsystem issue register for **citext**, the case-insensitive
text type. 1 source file / 412 LOC.

**Parent doc:** `knowledge/files/contrib/citext/citext.md`.

**Source:** 5 entries surfaced 2026-06-09 by A13-4.

## Headlines

1. **Collation mismatch between equality and ordering** —
   `citext_eq` calls `str_tolower(..., DEFAULT_COLLATION_OID)` +
   bitwise compare; `citext_lt`/`citext_cmp` call
   `str_tolower(..., DEFAULT_COLLATION_OID)` + input-collation
   `varstr_cmp`. **Under Turkish/ICU-tailored collations,
   `a = b` does NOT imply `not (a < b) and not (a > b)`.** The
   DEFAULT-collation choice for equality is deliberate (so equality
   and hashing stay collation-independent — comment at
   `citext.c:45-51`), but the asymmetry is a latent footgun.

2. **`varstr_cmp` against ICU custom-rules collation** (A7
   `pg_locale_icu` finding) may interact unpredictably with
   `str_tolower(DEFAULT)`. Cross-link to A7's ICU CVE history.

3. **`citext_pattern_cmp` (memcmp-on-lower, collation-independent)
   vs `citext_cmp` (collation-aware)** — two opclasses on same
   column give different orderings. Documentation / footgun.

4. **`~`/`!~` SQL wrappers only lowercase the LEFT side** —
   `column ~ 'A'` always false on lowered storage. User-error /
   documentation.

## Cross-sweep references

- **A7 `pg_locale_icu` ICU CVE history** — citext's lower-case
  comparison routes through that subsystem; custom-rules collation
  paths share the surface.
- **A13-3 btree_gist `btree_text`** — same collation-vs-byte-order
  family of issues; btree_gist explicitly disables truncation for
  text precisely because of this class.

## Entries (5)

- [ISSUE-correctness: citext_eq uses default-collation downcase +
  memcmp, citext_lt uses default-collation downcase + input-
  collation varstr_cmp; breaks ordering vs equality invariant under
  tailored collations (maybe — documented in comment)] —
  `source/contrib/citext/citext.c:45-51`.
- [ISSUE-security: cross-link A7 — varstr_cmp against ICU custom-
  rules collation may interact unpredictably with
  str_tolower(DEFAULT) (maybe)].
- [ISSUE-documentation: citext_pattern_cmp (memcmp-on-lower,
  collation-independent) vs citext_cmp (collation-aware) — two
  opclasses on same column give different orderings (nit)].
- [ISSUE-documentation: ~/!~ SQL wrappers only lowercase the LEFT
  side; `column ~ 'A'` always false on lowered storage (nit)].
- [ISSUE-defense-in-depth: citext functions accept up to
  MaxAllocSize inputs; same as text (nit)].
