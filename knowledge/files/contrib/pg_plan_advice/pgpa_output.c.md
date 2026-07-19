# `contrib/pg_plan_advice/pgpa_output.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~606
- **Source:** `source/contrib/pg_plan_advice/pgpa_output.c`

Renders the textual advice string from a populated `pgpa_plan_walker_context`.
Walks each of: `toplevel_unrolled_joins` (emitting `JOIN_ORDER(...)`),
`walker->join_strategies[*]` (one section per strategy), `walker->scans[*]`
(one section per non-ordinary scan strategy), `walker->query_features[*]`
(one per Gather/SEMIJOIN_*), `walker->no_gather_scans`, and
`walker->do_not_scan_identifiers`. Includes a configurable line-wrap at
column 76 to keep `EXPLAIN (PLAN_ADVICE)` output readable in an 80-col psql.
[verified-by-code]

## API / entry points

- `pgpa_output_advice(buf, walker, rt_identifiers)` (line 80): the only
  public entry. Stringifies all identifiers up front into a `rid_strings[]`
  array, then emits each section. Wrap column hardcoded to 76 (line 114).
  [verified-by-code]

## Notable invariants / details

- One `JOIN_ORDER(...)` per `toplevel_unrolled_join`. Items can't be merged
  across sub-joins: "JOIN_ORDER(a b c d) is totally different from
  JOIN_ORDER(a b) and JOIN_ORDER(c d)" — sequence semantics. [from-comment]
- `pgpa_output_join_member` (line 190) outputs unrolled sub-joins in `(...)`
  parens and bare scans by name, except multi-relation scans get wrapped in
  `{...}` (unordered braces) — used when a single scan covers multiple
  relations (custom scan, partitionwise). The braces signal "no inner/outer
  preference". [verified-by-code] [from-README]
- `PGPA_SCAN_ORDINARY` is skipped (line 152) — ordinary scans aren't worth
  emitting because the planner has no meaningful alternative to recommend.
  [verified-by-code]
- `pgpa_output_simple_strategy` (line 351) is reused for every join strategy
  (HASH_JOIN, NESTED_LOOP_*, MERGE_JOIN_*). The "simple" name refers to the
  `tag(item ...)` shape with bitmapset entries; not "tag is straightforward
  in concept". [from-comment]
- `pgpa_cstring_scan_strategy` (line 495) returns `"FOREIGN_JOIN"` for
  `PGPA_SCAN_FOREIGN` — the user-facing tag intentionally differs from the
  internal enum spelling. [verified-by-code]
- `pgpa_maybe_linebreak` (line 559) uses the StringInfo's `cursor` field as a
  remembered insertion point — clever: the caller calls it at every "good
  break point" and the function only inserts a newline if the line has grown
  past `wrap_column`. Avoids two-pass formatting. [verified-by-code]
- The buffer is *prepended* with `'\n'` between sections (lines 129, 230,
  308, 359, 396, 414) iff non-empty — so output is `\n`-separated, not
  `\n`-terminated. [verified-by-code]

## Potential issues

- `pgpa_output.c:114` — wrap column hardcoded to 76. Comment proposes making
  it a GUC. Low priority. [ISSUE-style: hardcoded magic 76 for line wrap (nit)]
- `pgpa_output.c:451` — `elog(ERROR, "no identifier for RTI %d", rti)` if
  rid_strings[rti-1] is NULL. This is defensive; should never trigger if
  the walker only references RTIs in the rtable. Could be `Assert` instead.
  [ISSUE-style: error vs assertion choice (nit)]
- `pgpa_output.c:283-292` — `pgpa_output_relation_name` always
  schema-qualifies; this matches the README rule "generated advice always
  includes partition_schema". For indexes, it forces schema even if the
  parsed advice originally omitted it. Round-trip-stable. [from-README]
- `pgpa_output.c:538-540` — the trailing blank line between
  `case PGPAQF_SEMIJOIN_UNIQUE: return "SEMIJOIN_UNIQUE";` and the
  `pg_unreachable()` is a stylistic nit. [ISSUE-style: extra blank line in
  switch (nit)]
- `pgpa_output.c:596-606` — `pgpa_maybe_linebreak`'s `memmove`+null-terminate
  manipulates StringInfo internals (`buf->data[++buf->len] = '\0'`). Direct
  field manipulation is allowed but bypasses `appendStringInfo*`; future
  changes to StringInfo internals could break this. [ISSUE-style: direct
  StringInfo field write skips the standard API (nit)]
- `pgpa_output.c:280-284` — relation-name output for index-OID lookup uses
  `get_rel_name(relid)` which can return NULL if the relation OID is bogus
  (e.g. dropped between planning and EXPLAIN). Would produce a NULL deref
  in `appendStringInfoString`. [ISSUE-correctness: get_rel_name NULL not
  checked (maybe)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_plan_advice`](../../../issues/pg_plan_advice.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pg_plan_advice.md](../../../subsystems/contrib-pg_plan_advice.md)
