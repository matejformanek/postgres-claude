# Proposed edits — access-method-apis SKILL.md (iteration 1)

Iteration-1 grading: with_skill 23/23, baseline 11.5/23 → +50pp uplift.
The skill already covered every assertion that mattered. So the proposed
edits below are minor polish, not gap-closing. **Do not apply yet** — confirm
across additional iterations first.

## Minor polish candidates

1. **Make the `IndexBulkDeleteResult *` return type explicit.**
   Section "Function pointers — mandatory" describes `ambulkdelete` and
   `amvacuumcleanup` semantically but never names the return struct. Adding
   "(returns `IndexBulkDeleteResult *`)" once would let readers cross-reference
   `genam.h` without a grep.

2. **Promote the "ambeginscan must return RelationGetIndexScan's result" rule
   to its own labelled CAUTION block.** Today it's a paragraph at the end of
   the mandatory-callbacks subsection. Baseline got this partial because the
   rule reads as a soft convention. Lifting it to a fenced "GOTCHA"
   improves scannability when someone is writing an AM and only skims.

3. **Add a one-liner pointer to the `amparallelvacuumoptions` semantics.**
   Currently we list the field but don't say "set to 0 to opt out of parallel
   vacuum entirely". Useful for the common case where a new AM doesn't want
   to deal with parallel vacuum on day one.

4. **In the Table AM "All mandatory" subsection, repeat the count.**
   Lead-in already says "~45 callbacks" then "~30 Assert lines" — these can
   read as inconsistent. Reconcile to: "~45-callback struct; tableamapi.c
   asserts ~30 of them; the rest have soft 'may be NULL' contracts inside
   specific call sites." This came up implicitly in eval #3.

5. **Link the autovacuum-statistics leakage explicitly to `pg_stat_all_tables`
   counters.** The architecture doc has it; SKILL.md mentions VACUUM
   scheduling only in the "what heap-AM still leaks" implicit way. Adding a
   single line under "TID semantics" subsection would help a columnar
   implementer plan stats-faking from day one.

6. **Order of `aminsertcleanup` vs `aminsert` in lifecycle diagram.** Today:
   `(per row) aminsert → aminsertcleanup`. Reads as if cleanup is per-row.
   Clarify: `aminsertcleanup` is called once at end of the inserting query
   when non-NULL (used by btree for unique-violation deferred checks etc.).

## What NOT to change

- Length is fine. ~240 lines fits the 500-line ceiling with room.
- The two-table layout at the top is the right framing — keep it.
- Heap-leakage list in Table AM section is excellent; eval #3 confirmed it
  scored 8/8 against a moderately tricky prompt.

## Suggested next iteration

- Add prompts that hit narrower corners: opclass `amvalidate` vs
  `amadjustmembers` (deferred validation), `index_fetch_tuple` lifetime, and
  `tuple_lock` return-value `TM_Result` semantics under SSI. These would
  stress the parts of the skill that iteration 1 didn't probe deeply.
