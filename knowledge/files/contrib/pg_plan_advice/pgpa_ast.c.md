# `contrib/pg_plan_advice/pgpa_ast.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~357
- **Source:** `source/contrib/pg_plan_advice/pgpa_ast.c`

Supporting code for the plan-advice AST produced by the bison parser
(`pgpa_parser.y`) and flex scanner (`pgpa_scanner.l`). Provides
tag-name (de)stringification, advice-target formatting, identifier-vs-target
matching, and the `pgpa_itm_type` set-relation classifier used to drive
all advice-application logic in `pgpa_planner.c`. [verified-by-code]

## API / entry points

- `pgpa_cstring_advice_tag(tag)` (line 29): big switch turning every
  `pgpa_advice_tag_type` enum value into its UPPER_CASE string spelling.
  Ends with `pg_unreachable()`. [verified-by-code]
- `pgpa_parse_advice_tag(tag, *fail)` (line 87): inverse — expects a
  already-downcased C string; returns the enum, sets `*fail` and returns
  an arbitrary value on no-match. Switch is keyed on first character to
  prune the search. [verified-by-code]
- `pgpa_format_advice_target(StringInfo, target)` (line 170): recursively
  serializes a `pgpa_advice_target`. Uses `()` for ordered lists,
  `{}` for unordered lists, and `pgpa_identifier_string` for identifiers.
  [verified-by-code]
- `pgpa_format_index_target(StringInfo, itarget)` (line 206): renders
  `schema.name` (or just `name`) with `quote_identifier`. [verified-by-code]
- `pgpa_index_targets_equal(i1, i2)` (line 218): strict equality, treating
  two NULL schemas as equal. [verified-by-code]
- `pgpa_identifier_matches_target(rid, target)` (line 235): walks an advice
  target recursively; for identifier targets, requires alias_name +
  occurrence match and conditionally matches partition/plan fields. A NULL
  partition schema in the target matches any. [verified-by-code]
- `pgpa_identifiers_match_target(nrids, rids, target)` (line 283): classifies
  the relation between a *set* of identifiers and a target as one of
  `PGPA_ITM_EQUAL` / `KEYS_ARE_SUBSET` / `TARGETS_ARE_SUBSET` /
  `INTERSECTING` / `DISJOINT`. This is the core primitive consumed by
  `pgpa_planner_apply_*` to decide whether advice applies, fully or partially.
  [verified-by-code]

## Notable invariants / details

- The asymmetry in `pgpa_identifier_matches_target` (line 260): if the
  identifier (live RTE side) has `partnsp != NULL` and the target also
  specifies one, they must match — but a NULL on the target side is a
  wildcard. This is the user-friendly "schema-optional" parser behavior
  documented in the README. [verified-by-code] [from-README]
- `Assert(rid->partnsp != NULL || rid->partrel == NULL)` (line 259): a
  partition name without a schema is forbidden on the *generated* side
  (i.e. RTE-derived identifiers). Targets parsed from user input may have
  this combination. [verified-by-code]
- `pgpa_identifiers_cover_target` (static helper, line 327) returns true
  iff every target leaf matches at least one identifier; sets `rids_used[i]`
  per identifier. From this and a tally of used vs not-used, the public
  function derives the 5-way classification. [verified-by-code]
- The `PGPA_ITM_DISJOINT` case (line 316) is only returned when no overlap
  is found at all. Callers in `pgpa_planner.c` `Assert(itm != PGPA_ITM_DISJOINT)`
  in some paths — relying on the trove having already pre-filtered. [verified-by-code]

## Potential issues

- `pgpa_ast.c:163` — `pgpa_parse_advice_tag` on failure returns
  `PGPA_TAG_SEQ_SCAN` "an arbitrary value to unwind the call stack". Any
  caller that doesn't check `*fail` will silently get bogus advice. Static
  analysis won't catch the misuse. [ISSUE-correctness: arbitrary sentinel
  return value risks silent misinterpretation if caller forgets to check
  *fail (maybe)]
- `pgpa_ast.c:289` — `palloc0_array(bool, nrids)` for `rids_used` is allocated
  on every call and never freed; relies on the calling memory context being
  short-lived. [ISSUE-leak: per-call bool-array allocation never freed,
  relies on caller's context discipline (nit)]
- `pgpa_ast.c:73-77` — the trailing `pg_unreachable(); return NULL;` pattern in
  `pgpa_cstring_advice_tag` is correct but bypasses the more idiomatic
  `default: pg_unreachable()` inside the switch. Style-only. [ISSUE-style:
  pg_unreachable outside switch differs from typical PG convention (nit)]
- `pgpa_ast.c:266` — comment says "partition name and schema can be NULL
  on either side, but NULL only matches another NULL" — but at line 260-262
  the rule is *different* for partition schema vs name. The schema is a
  wildcard when NULL; the name must match exactly (or both be NULL). The
  comment correctly describes both rules in tandem, but the contrast between
  schema and name behavior is subtle. [from-comment]
- `pgpa_ast.c:209-211` — `quote_identifier` is called on `indnamespace` even
  when it might already be quoted by the parser. Not a bug; it's idempotent
  for unquoted-safe identifiers. [verified-by-code]
