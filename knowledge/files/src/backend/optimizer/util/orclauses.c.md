# orclauses.c — single-rel restriction extraction from join OR clauses

- **Source:** 345 lines · **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

`extract_restriction_or_clauses(root)` (74) walks the join-clause list
looking for `OR` clauses where every disjunct mentions some baserel
(possibly different ones), and synthesizes a single-rel restriction
clause for each such baserel. Example: `WHERE (a.x=1 AND b.y=2) OR
(a.x=3 AND b.y=4)` → adds `a.x IN (1,3)` and `b.y IN (2,4)` as scan-level
quals. Helps when the OR is selective enough to enable index scans.
[verified-by-code]

Called by `query_planner` after EC and join-removal passes
(planmain.c:269).
