# Plan: SP7 — `tablefunc.connectby_text` identifier quoting

**Status:** READY. Single-phase plan.
**Pitch:** `knowledge/phase-d-pitches.md` SP7 + CB2
**Source pin:** `e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa` (master at 2026-06-10)
**Slug:** `sp7-tablefunc-quoting`
**Branch:** `feature_sp7_tablefunc_quoting` (in `dev/`)
**Expected commits:** 1 (single phase per R3 + R5)

## §1 Problem statement

`contrib/tablefunc/tablefunc.c:1227-1247` builds two SQL statements via `appendStringInfo` interpolating 4 user-supplied identifier arguments raw:

- `key_fld` (column name)
- `parent_key_fld` (column name)
- `relname` (table name, possibly schema-qualified)
- `orderby_fld` (column name, only in the SELECT-with-ORDERBY form)

Only `start_with` is quoted (`quote_literal_cstr`). The 4 identifier args reach SQL untransformed. Any application that exposes these args to user input (form fields, URL params) provides a direct SQL injection vector, gated only by SPI `read_only=true` (which still permits `pg_authid` reads, `pg_read_server_files`, and information disclosure via timing).

Surfaced 2026-06-09 by A13 sweep (foreground); catalogued as **CB2** + **SP7** in `knowledge/phase-d-pitches.md`.

## §2 Approach

Wrap each user-supplied identifier with the appropriate quoting helper:

- **Column-name args** (`key_fld`, `parent_key_fld`, `orderby_fld`): use `quote_identifier()` from `utils/ruleutils.h`. Returns the original string if quoting unnecessary, else a palloc'd quoted form. Cheap.
- **`relname`** (possibly schema-qualified): parse via `stringToQualifiedNameList()` (allows quoted identifiers, handles `schema.name`), produce a `RangeVar` via `makeRangeVarFromNameList()`, then format with `quote_qualified_identifier(rv->schemaname, rv->relname)`. Preserves backwards compatibility with users who pass `schema.table`.

The patch is minimal:
- 1 new include
- ~10 lines of pre-computed quoted-string variables near the top of `build_tuplestore_recursively`
- Replace the 4 raw identifiers in the two `appendStringInfo` calls (lines 1227 + 1238)

## §3 Files that change

| File | Change | LOC |
|---|---|---|
| `contrib/tablefunc/tablefunc.c` | Add include + pre-compute quoted identifiers + use them in 2 appendStringInfo calls | ~15 |
| `contrib/tablefunc/sql/tablefunc.sql` | Add 2 regression tests: (1) `connectby` with a column-name containing a single-quote should run cleanly (no injection); (2) `connectby` with schema-qualified relname `"public"."connectby_text"` should work | ~10 |
| `contrib/tablefunc/expected/tablefunc.out` | Regenerated to match the new test output | ~30 |

**Sites verified against current source:**
- `source/contrib/tablefunc/tablefunc.c:33-47` — include block (need to add `utils/ruleutils.h`)
- `source/contrib/tablefunc/tablefunc.c:1227-1233` — first appendStringInfo
- `source/contrib/tablefunc/tablefunc.c:1238-1247` — second appendStringInfo
- `source/contrib/tablefunc/tablefunc.c:1209-1214` — function header (good place for pre-compute)

## §4 Catalog impact

None. This is a defense-in-depth fix to existing behavior. No new SQL functions, no extension version bump (this is `contrib/tablefunc--1.0.sql`'s established function — internal hardening only).

## §5 Behavior changes

- Existing callers passing already-quoted identifiers (e.g., `'"My Column"'`) will see their input double-quoted. `quote_identifier` returns the input unchanged if it's already a valid simple-name token, but will re-quote a string that contains characters needing escaping. **Risk:** legitimate callers passing names with embedded double-quotes/backslashes may see different output. **Mitigation:** test the unchanged-input common case (column names without special chars).
- `relname` parsing via `stringToQualifiedNameList` rejects empty strings and trailing dots. Previously such inputs would produce a downstream SPI parse error; now they error earlier with a clearer message. **Acceptable behavior change.**

## §6 Test plan

Two new tests in `contrib/tablefunc/sql/tablefunc.sql`:

```sql
-- Test SP7: connectby with a column name containing single-quote (would be injection without quoting)
CREATE TABLE connectby_quote(keyid text, parent_keyid text);
INSERT INTO connectby_quote VALUES ('a', NULL), ('b', 'a');
-- This should treat 'keyid; DROP TABLE x; --' as a column name and error cleanly, not execute the DROP
SELECT * FROM connectby('connectby_quote', E'keyid; DROP TABLE x; --', 'parent_keyid', 'a', 0)
  AS t(keyid text, parent_keyid text, level int);  -- expect ERROR: column "keyid; DROP TABLE x; --" does not exist
DROP TABLE connectby_quote;

-- Test SP7: connectby with schema-qualified relname (backwards-compat)
SELECT * FROM connectby('public.connectby_text', 'keyid', 'parent_keyid', 'row2', 0, '~')
  AS t(keyid text, parent_keyid text, level int, branch text)
  ORDER BY keyid;
```

**Phase-end check:** `meson test --suite tablefunc` must pass.

## §7 Implementation sketch

```c
/* Add to includes (in alphabetical order with other utils/* includes) */
#include "utils/ruleutils.h"

/* In build_tuplestore_recursively, before the initStringInfo call at line 1222: */
const char *q_key_fld = quote_identifier(key_fld);
const char *q_parent_key_fld = quote_identifier(parent_key_fld);
const char *q_orderby_fld = (orderby_fld != NULL) ? quote_identifier(orderby_fld) : NULL;
/* Parse relname as a (potentially schema-qualified) name */
List       *namelist = stringToQualifiedNameList(relname, NULL);
RangeVar   *rv = makeRangeVarFromNameList(namelist);
const char *q_relname = quote_qualified_identifier(rv->schemaname, rv->relname);

/* Replace the two appendStringInfo calls — first form (no ORDERBY): */
appendStringInfo(&sql, "SELECT %s, %s FROM %s WHERE %s = %s AND %s IS NOT NULL AND %s <> %s",
                 q_key_fld,
                 q_parent_key_fld,
                 q_relname,
                 q_parent_key_fld,
                 quote_literal_cstr(start_with),
                 q_key_fld, q_key_fld, q_parent_key_fld);

/* And the ORDERBY form: */
appendStringInfo(&sql, "SELECT %s, %s FROM %s WHERE %s = %s AND %s IS NOT NULL AND %s <> %s ORDER BY %s",
                 q_key_fld,
                 q_parent_key_fld,
                 q_relname,
                 q_parent_key_fld,
                 quote_literal_cstr(start_with),
                 q_key_fld, q_key_fld, q_parent_key_fld,
                 q_orderby_fld);
```

**Include verification needed for `makeRangeVarFromNameList`:** check it's in `nodes/makefuncs.h` or `utils/lsyscache.h` (cite at impl time).

## §8 Phase-end check

```bash
cd dev
meson setup build-asan --buildtype=debug --auto-features=disabled -Dcassert=true 2>/dev/null || true
ninja -C build-asan contrib/tablefunc
meson test -C build-asan --suite tablefunc
```

Expected: green; no regressions in existing 4 `connectby` tests; 2 new tests pass with expected output.

Also run a broad `meson test` if the patch's adjacent area might affect (e.g., grep for callers of `quote_identifier` in other contrib for consistency).

## §9 Risk + reviewer concerns

**Anticipated reviewer pushback:**

1. *"Why parse relname instead of just `quote_identifier`-ing it?"* — Answer: backwards compat. Users have been passing `schema.table` for ~20 years; `quote_identifier("schema.table")` would emit `"schema.table"` as a single identifier, breaking those calls. RangeVar parsing handles both cases correctly.
2. *"Is `stringToQualifiedNameList` overkill for parsing a simple relation name?"* — Answer: it's the canonical PG identifier-list parser, used by `regclass_in`. Same correctness guarantees as user-typed SQL. No `text_to_cstring_immutable` style assumptions.
3. *"Why no behavior-change for `start_with`?"* — `start_with` is the value side of a `=` comparison (data, not identifier). Already correctly handled by `quote_literal_cstr`.
4. *"What about `branch_delim`?"* — Not interpolated into SQL; used only as a separator in the result strings (`tablefunc.c:1319-1347`).

**Known limitations after this patch:**
- `build_tuplestore_recursively` still lacks `check_stack_depth()` (only fragile `strstr`-based cycle check + `max_depth` guard) — addressed in a separate follow-up. The CB7 family.
- Hostile `start_with` values are quoted by `quote_literal_cstr` but enormous values could still cause memory growth — out of scope.

## §10 Cross-corpus echoes (this fix touches)

- A13 sweep finding (`knowledge/issues/tablefunc.md`)
- CB2 confirmed bug in `knowledge/phase-d-pitches.md`
- MP2 StringInfo quoting helpers — this patch is the canonical use case; future MP2 land would let us simplify by replacing the `quote_identifier(x)` calls with `appendStringInfoQuotedIdentifier(&sql, x)` directly.
- A11 cluster of "trust the column name" findings in dblink + postgres_fdw — similar shape, addressed by SP7-style patches per module.

## §11 Submission package

After implementation lands and tests pass:
- `git format-patch origin/master..feature_sp7_tablefunc_quoting --output-directory ../sp7-tablefunc-quoting/`
- Patch subject: `tablefunc: quote identifier arguments in connectby() SQL builder`
- Commit message body: cite the security implication (App + user-controlled identifier args = SQL injection); explain `quote_identifier` for columns + `stringToQualifiedNameList`/`makeRangeVarFromNameList` for relname; reference the 2 new test cases.
- Target: pgsql-hackers mailing list + commitfest 60 (January 2026).
- Backpatch candidate: yes (it's a security fix in already-released code). Plan to ship a patch series with master + back-branches if reviewers want backpatch.

## §12 Notes / surprises

(Empty at plan time. Populate in `notes.md` during implementation per R8.)
