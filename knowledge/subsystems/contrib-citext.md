# contrib-citext (case-insensitive text)

- **Source path:** `source/contrib/citext/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.8` (per `citext.control`)
- **Trusted:** yes (`trusted = true`)

## 1. Purpose

A **case-insensitive variant of `text`** — `citext` strings
that compare equal to their case-variants ("Hello" = "hello").
Implemented by overriding all the equality / comparison / hash
operators to lowercase-then-compare. Native text type, BTree
+ Hash indexable.

The classic motivation: email-address columns, where
"Alice@example.com" and "alice@EXAMPLE.com" should compare
equal but legacy `text COLLATE "C"` doesn't.

## 2. The implementation strategy

[verified-by-code `citext.c:107-280`]

Every operator (eq, ne, lt, le, gt, ge, cmp, hash) overrides
the standard text version:

```c
Datum
citext_eq(PG_FUNCTION_ARGS)
{
    text *a = PG_GETARG_TEXT_PP(0);
    text *b = PG_GETARG_TEXT_PP(1);
    char *lowered_a = str_tolower(VARDATA_ANY(a), VARSIZE_ANY_EXHDR(a));
    char *lowered_b = str_tolower(VARDATA_ANY(b), VARSIZE_ANY_EXHDR(b));
    /* memcmp the lowercased versions */
    PG_RETURN_BOOL(memcmp(...) == 0);
}
```

(abstracted)

The literal storage is the **original case** — citext doesn't
mangle data. Comparison is done by lowercasing on the fly.

## 3. The hash strategy

```c
PG_FUNCTION_INFO_V1(citext_hash);
```

[verified-by-code `citext.c:141`]

For HASH indexes (and hash joins / aggregates), citext's hash
function lowercases the input before applying the standard
hash. Equal-case strings hash to the same value; B-tree and
hash indexes both find them.

`citext_hash_extended` is the 64-bit variant used internally
by partition routing and aggregation.

## 4. The pattern_cmp variant

`citext_pattern_cmp` [verified-by-code `citext.c:124`]
implements **collation-independent** comparison — the kind
used by `text_pattern_ops` for LIKE prefix matching. Same
lowercase-then-compare approach but using `pg_strncasecmp`
internally to handle locale-sensitive case-folding.

For non-ASCII case-fold equivalence (e.g. German ß ↔ SS),
results depend on the database's collation. citext defers to
PG's `pg_strncasecmp` which uses the current collation.

## 5. Cost characteristics

- **Every comparison is O(N)** — lowercase-then-compare costs
  more than direct memcmp.
- **Indexes work normally** — BTREE / HASH consult the
  citext-overridden operators.
- **Function-call overhead** is significant on short strings
  — for tens-of-millions of comparisons (e.g. on a hash
  join), the cumulative cost is measurable.

For high-performance case-insensitive matching:

- Consider `LOWER(col) =` with an expression index instead.
- Or use ICU collation with `deterministic = false` (PG 12+)
  which is "case-insensitive at the catalog level."

## 6. Casts and operators

```sql
CREATE TABLE users (email citext UNIQUE);
INSERT INTO users (email) VALUES ('alice@EXAMPLE.com');
SELECT * FROM users WHERE email = 'Alice@example.com';
-- returns the row
```

Implicit cast from `text` and `varchar` to `citext`. Comparisons
between `citext` and `text` use the citext operators (citext
takes precedence due to the explicit cast preferences).

## 7. The catalog tricks

citext is **NOT** a domain over text — it's a fully separate
type. The catalog defines it with `typcategory = 'S'`
(string-like) and a custom set of comparison operators.

Statistics + selectivity estimates work because citext's
operators are explicitly labeled as the type's comparison
operators in `pg_opclass`.

## 8. Production-use guidance

- **For email columns**, citext is the canonical PG solution.
- **For larger text** (descriptions, long fields), the
  per-comparison cost may be too high; use `LOWER(col)`
  expression index instead.
- **For modern installations**, consider ICU
  `non-deterministic collation` (PG 12+) which is the
  catalog-level case-insensitive solution — supports
  collation-aware case-folding for many languages.

## 9. Invariants

- **[INV-1]** Storage preserves original case; comparison is
  case-folded.
- **[INV-2]** Hash + comparison both lowercase first; equal
  hashes for case-variants.
- **[INV-3]** Implicit cast from `text` / `varchar`.
- **[INV-4]** Locale-sensitive (uses `pg_strncasecmp`); results
  depend on collation.
- **[INV-5]** Trusted extension.

## 10. Useful greps

- All operators:
  `grep -n 'PG_FUNCTION_INFO_V1' source/contrib/citext/citext.c`
- The strncasecmp call site:
  `grep -n 'pg_strncasecmp\|str_tolower' source/contrib/citext/citext.c`
- The catalog registration:
  `head -50 source/contrib/citext/citext--1.8.sql`

## 11. Cross-references

- `knowledge/subsystems/contrib-fuzzystrmatch.md` —
  companion text-similarity contrib (different mechanism).
- `knowledge/subsystems/contrib-pg_trgm.md` — trigram-based
  text matching (closer to fuzzy matching).
- `knowledge/subsystems/access-nbtree.md` — BTREE for
  citext indexes.
- `.claude/skills/fmgr-and-spi/SKILL.md` — function override
  pattern.
- `source/contrib/citext/citext.c` — implementation.
