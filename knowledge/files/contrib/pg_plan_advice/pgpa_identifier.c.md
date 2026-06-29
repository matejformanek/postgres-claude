# `contrib/pg_plan_advice/pgpa_identifier.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~481
- **Source:** `source/contrib/pg_plan_advice/pgpa_identifier.c`

Constructs unique, human-readable, *replay-stable* identifiers for range
table entries. This is the central correctness primitive of `pg_plan_advice`:
the round-trip guarantee (generate-then-apply advice without ambiguity) relies
on every RTE having a name that can be reconstructed during a future planning
cycle. Identifier format documented in the file header:
`alias_name#occurrence_number/partnsp.partrel@plan_name`, with all but
`alias_name` optional. [verified-by-code] [from-comment]

## API / entry points

- `pgpa_identifier_string(rid)` (line 80): assembles the textual identifier
  from a `pgpa_identifier`. Uses `quote_identifier` for each piece. Omits
  occurrence when it's 1, partition fields when `partrel` is NULL, plan
  name when NULL. [verified-by-code]
- `pgpa_compute_identifier_by_rti(root, rti, *rid)` (line 115): the live-planning
  variant. Walks up `append_rel_array` to find the topmost RTE_RELATION parent
  (so partitioned-child identifiers use the parent's alias). Counts prior
  occurrences of the same alias *within the same subquery* (skipping RTE_JOIN,
  NULL, and partitioned-children-of-relations). [verified-by-code]
- `pgpa_compute_identifiers_by_relids(root, relids, rids)` (line 220): bulk
  variant — iterates a bitmapset, skips RTE_JOIN, returns count of identifiers
  written. `Assert(count > 0)` — caller's responsibility to never pass an
  all-JOIN relid set. [verified-by-code]
- `pgpa_create_identifiers_for_planned_stmt(pstmt)` (line 244): the
  post-planning variant. Iterates the *flattened* rtable, walking through
  `SubPlanRTInfo` entries to assign each RTE its correct `plan_name` based
  on which subquery it originated from. Returns a `pgpa_identifier` array
  indexed by `rti - 1`. [verified-by-code]
- `pgpa_compute_rti_from_identifier(rtable_length, rt_identifiers, rid)`
  (line 352): inverse — given an array of identifiers from the post-planning
  walk and a user-supplied identifier from advice, find the matching RTI
  (or 0 if no match or multiple matches). Schema-wildcarding applies.
  [verified-by-code]

## Notable invariants / details

- **Use `rt_fetch` not `planner_rt_fetch`.** The file header (line 45-48)
  is emphatic: join removal and self-join elimination remove rels from
  `planner_rt_fetch`'s arrays; `rt_fetch` is needed for stable identifier
  reconstruction. All call sites in this file use `rt_fetch`. [from-comment]
  [verified-by-code]
- **Subquery names must be unique and known before subquery planning.**
  This is the substrate for `plan_name` qualifier in identifiers
  (line 38-40). The PlannerInfo's `plan_name` field is the source.
  [from-comment]
- **Occurrence number is counted within a subquery.** The flat-rtable walk
  in `pgpa_create_identifiers_for_planned_stmt` resets the occurrence count
  per `SubPlanRTInfo` slice via the `rtoffset` (`pgpa_occurrence_number`
  line 446). Children-of-partitioned-tables don't increment occurrence —
  they're disambiguated by partition name instead. [verified-by-code]
- `pgpa_create_top_rti_map` (line 407): "Parents always precede their
  children in the AppendRelInfo list, so this should work out." This is
  load-bearing — the single-pass O(n) build of the child→top-parent map
  depends on it. [from-comment]
- The `nextrtinfo` advance loop (line 291) is guarded by a `while` (not
  `if`) defensively, with a comment that it "probably shouldn't ever
  iterate more than once". [from-comment]
- `Assert(rte->rtekind != RTE_JOIN)` (line 151, 152): identifiers are never
  computed for joins; advice never refers to them. The README says joins
  are referred to by their constituents. [from-README] [verified-by-code]

## Potential issues

- `pgpa_identifier.c:289` — `nextrtinfo` advance loop comment: "this loop
  probably shouldn't ever iterate more than once". If it ever did, the
  in-between subquery would have no RTI mapping. Defensive `Assert(false)`
  inside the loop would catch the bug, but isn't there. [ISSUE-question:
  defensive Assert for "shouldn't happen" inner-loop iteration absent (nit)]
- `pgpa_identifier.c:415-430` — single-pass `top_rti_map` construction
  assumes parents precede children in `appinfos`. There is no `Assert`
  enforcing this. A buggy generator of AppendRelInfo list could produce
  silently wrong identifiers. [ISSUE-undocumented-invariant: parent-before-child
  appinfo ordering assumed without runtime check (maybe)]
- `pgpa_identifier.c:235-237` — comment says "we don't care about" RTE_JOIN
  identifiers, but the `Assert(count > 0)` at line 235 will fail if the
  caller passes a relids bitmapset containing *only* joins. Currently
  every caller filters or knows that's impossible. [ISSUE-undocumented-invariant:
  caller contract "must contain at least one non-JOIN" (nit)]
- `pgpa_identifier.c:378-388` — `pgpa_compute_rti_from_identifier` returns
  0 both for "no match" and "multiple matches" (ambiguous). Callers can't
  distinguish — they probably want both cases to behave the same, but a
  WARNING for the ambiguous case might help debugging. [ISSUE-question:
  0-return ambiguity between no-match and multi-match (nit)]
- `pgpa_identifier.c:204` — the live-planning variant sets
  `rid->plan_name = root->plan_name` *unconditionally* — including NULL
  for the top-level PlannerInfo. The flat-rtable variant routes through
  `SubPlanRTInfo->plan_name` instead. The two paths must agree on the
  string identity of every plan_name; only equality of the C strings is
  checked, not the source. [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_plan_advice`](../../../issues/pg_plan_advice.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pg_plan_advice.md](../../../subsystems/contrib-pg_plan_advice.md)
