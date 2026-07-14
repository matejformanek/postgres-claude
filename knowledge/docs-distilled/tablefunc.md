---
source_url: https://www.postgresql.org/docs/current/tablefunc.html
fetched_at: 2026-07-13T20:53:00Z
anchor_sha: d92e98340fcb
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.42 tablefunc — functions returning tables (crosstab, connectby)"
maps_to_skill: fmgr-and-spi
---

# Docs distilled — tablefunc (SRF worked examples: crosstab, connectby, normal_rand)

The canonical study of **set-returning C functions that build their result via
SPI queries** and require a caller-supplied column-definition list. Every
function here returns `setof record` whose shape the *calling query* declares —
the pattern `fmgr-and-spi` describes in the abstract, shown end to end.

## Non-obvious claims

- **Three families of function.** `normal_rand(int, float8, float8)` (Box-Muller
  Gaussian generator) [[tablefunc.c:176]]; the `crosstab` pivot family; and
  `connectby` for hierarchical trees [[tablefunc.c:63]]. [from-docs] +
  [verified-by-code @ d92e98340fcb]
- **Two crosstab implementations behind one name.** The single-argument
  `crosstab(text)` [[tablefunc.c:358]] is a streaming pivot that groups
  *consecutive* input rows by `row_name` and fills output columns left-to-right;
  the two-argument `crosstab(text source_sql, text category_sql)` is a *different
  C function*, `crosstab_hash` [[tablefunc.c:636]], which first loads the
  category list into a hash table via `load_categories_hash` and then places
  each value in the column matching its category. [verified-by-code @ d92e98340fcb]
  Knowing which C entry point a SQL wrapper binds to (`'…','crosstab'` vs
  `'…','crosstab_hash'`) is the non-obvious bit when writing custom wrappers.
- **`crosstab(text)` demands `ORDER BY 1,2` and is positional, not
  category-aware.** It *ignores the category column's value* — it only uses it
  for ordering. So if two input rows for the same `row_name` share a category,
  or a category is missing, columns silently misalign. Missing trailing values
  become NULL; extra input rows past the declared column count are dropped.
  [from-docs] This is the #1 crosstab foot-gun.
- **`crosstab(text, text)` is category-aware and forgiving of gaps.** Unmatched
  categories in the data are ignored; categories present in `category_sql` but
  absent from a group's data yield NULL columns. "Extra" columns between
  `row_name` and the category/value pair are copied from the *first* row of each
  group and must be constant within the group. [from-docs]
- **`crosstabN` wrappers (`crosstab2/3/4`) exist only to skip the column-def
  list**, backed by predefined `tablefunc_crosstab_N` composite types (all-text).
  You can roll your own typed wrapper by defining a composite type and a
  `LANGUAGE C` function pointing at the C symbol `crosstab`. [from-docs]
- **`connectby` generates SQL by string-substituting your identifiers**, so
  mixed-case/special names need double-quoting, and `start_with` is always
  passed as a text literal regardless of the key's real type. Output columns
  are fixed-position: keyid, parent_keyid, level, then optional `branch` (only
  if `branch_delim` given) and optional serial (only if `orderby_fld` given).
  [from-docs]
- **Cycle detection is a substring test on the branch path — and it can
  false-positive.** `connectby` flags a cycle when the current key already
  appears in the accumulated branch string: `if (strstr(chk_branchstr.data,
  chk_current_key.data))` → `ereport(… "infinite recursion detected")`
  [[tablefunc.c:1339]]. Because it's a raw substring match on delimiter-joined
  keys, the **`branch_delim` must not occur inside any key value** or you get
  spurious recursion errors. [verified-by-code @ d92e98340fcb]

## Links into corpus

- [[knowledge/subsystems/contrib-tablefunc.md]] — the source-side companion.
- [[knowledge/idioms/fmgr.md]] — the SRF calling convention
  (ValuePerCall / Materialize, `TupleDesc` from the caller's column list).
- [[knowledge/idioms/spi.md]] — the SPI query execution both crosstab and
  connectby build on.
- [[knowledge/docs-distilled/xfunc-c.md]] — writing C-language functions,
  including composite/set returns.

## Confidence

The `normal_rand`/`crosstab`/`crosstab_hash`/`connectby` entry points, the
two-C-functions-behind-crosstab split, and the substring-based cycle detector
(`strstr` → "infinite recursion detected") are [verified-by-code @ d92e98340fcb]
against `contrib/tablefunc/tablefunc.c`. The positional-vs-category-aware
crosstab semantics, NULL/overflow handling, `crosstabN` wrappers, and connectby
column layout are [from-docs].
