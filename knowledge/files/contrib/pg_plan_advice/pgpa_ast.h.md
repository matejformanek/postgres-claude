# `contrib/pg_plan_advice/pgpa_ast.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~186
- **Source:** `source/contrib/pg_plan_advice/pgpa_ast.h`

Defines the in-memory AST emitted by `pgpa_parser.y` and consumed by
`pgpa_trove.c` / `pgpa_planner.c`: the advice tag enum (`pgpa_advice_tag_type`),
the target/identifier/index-target structs (`pgpa_advice_target`,
`pgpa_index_target`), the per-item record (`pgpa_advice_item`), and the
identifiers-vs-target set classifier enum (`pgpa_itm_type`). [verified-by-code]

## API / entry points

- `pgpa_target_type` enum (line 25): `PGPA_TARGET_IDENTIFIER` |
  `PGPA_TARGET_ORDERED_LIST` (parenthesized) | `PGPA_TARGET_UNORDERED_LIST`
  (brace-wrapped, for `JOIN_ORDER` unordered sub-lists). [verified-by-code]
- `pgpa_index_target` struct (line 35): `indnamespace` (optional) +
  `indname`. [verified-by-code]
- `pgpa_advice_target` struct (line 47): tagged union — `rid` (when leaf
  identifier), `itarget` (set only for INDEX_SCAN / INDEX_ONLY_SCAN target
  leaves), `children` (a List of `pgpa_advice_target *` for list targets).
  [verified-by-code]
- `pgpa_advice_tag_type` enum (line 80): all 20 supported advice tags. Header
  warns: keep `pgpa_parse_advice_tag` and `pgpa_cstring_advice_tag` in sync.
  [from-comment]
- `pgpa_advice_item` struct (line 112): a `tag` + a `targets` List. Output
  of `pgpa_yyparse`. [verified-by-code]
- `pgpa_itm_type` enum (line 141): 5-way classification — `EQUAL` /
  `KEYS_ARE_SUBSET` (identifiers ⊆ target) / `TARGETS_ARE_SUBSET` (target
  ⊆ identifiers) / `INTERSECTING` / `DISJOINT`. Comments give per-value
  semantics for advice-application. [from-comment]
- Bison/flex glue: `pgpa_yylex`, `pgpa_yyerror`, `pgpa_scanner_init/finish`
  declarations plus the `yyscan_t` typedef guard. [verified-by-code]
- `pgpa_parse(advice_string, &error)` (line 169): the convenience wrapper
  defined in `pgpa_parser.y` that ties scanner + parser together and
  returns a list of `pgpa_advice_item *`. [verified-by-code]

## Notable invariants / details

- The header explicitly warns that changes to `pgpa_advice_tag_type` must
  be mirrored in `pgpa_parse_advice_tag` and `pgpa_cstring_advice_tag`
  (lines 76-78). There is no compile-time enforcement; reviewers must
  catch it. [from-comment]
- `itarget` lives on the `pgpa_advice_target` even though it's only ever
  set for two tag types; this keeps the struct uniform. [verified-by-code]
- `pgpa_advice_target.children` is a `List *` not a NULL-terminated array
  — uses `nodes/pg_list.h` (`foreach_ptr` consumers expect this).
  [verified-by-code]

## Potential issues

- `pgpa_ast.h:76-78` — the "if you change anything here, also update X and Y"
  comment is the only safeguard. A new tag added without updating both
  functions will trip `pg_unreachable()` only at runtime. Worth a
  static-array-of-strings keyed by enum value, plus
  `StaticAssertStmt(lengthof(arr) == NUM_TAGS, ...)`. [ISSUE-undocumented-invariant:
  no compile-time enforcement of tag-enum / string-table coherence (maybe)]
- `pgpa_ast.h:60-64` — `itarget` is only valid when `ttype == PGPA_TARGET_IDENTIFIER`
  AND the tag is INDEX_SCAN/INDEX_ONLY_SCAN, but the struct doesn't make this
  obvious. Callers must know the contract. [ISSUE-undocumented-invariant:
  itarget field is conditionally meaningful, not flagged in struct (nit)]
- `pgpa_ast.h:152-155` — the `yyscan_t` typedef guard is necessary because
  bison-generated headers also emit it. Standard idiom but worth noting for
  anyone adding includes. [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_plan_advice`](../../../issues/pg_plan_advice.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pg_plan_advice.md](../../../subsystems/contrib-pg_plan_advice.md)
