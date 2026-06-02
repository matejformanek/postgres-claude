# Proposed SKILL.md edits — iteration 1

Based on iteration-1 grading. Skill currently scores 29/29 vs baseline 26/29. Net +3 pts, driven entirely by eval-1 (workflow specificity). Evals 2 and 3 are draws because the skill's surface text doesn't go beyond what a competent PG developer already knows for those tasks. The depth on syscache is buried in `knowledge/idioms/catalog-conventions.md` — the SKILL.md itself doesn't surface it.

## Proposed edits (DO NOT APPLY without review)

### 1. Add a "syscache lifecycle" mini-section to SKILL.md

Currently SKILL.md §6 just says:

> Add a `DECLARE_UNIQUE_INDEX` and `MAKE_SYSCACHE(NAME, idx, nbuckets)` to the header. Use the syscache from C with `SearchSysCacheN` + `ReleaseSysCache`.

That covers *declaring* a syscache but not *using* one safely. Add (next to or after §6):

```
### Using a syscache from C

- Every SearchSysCache* (non-Copy) MUST be paired with ReleaseSysCache(tup)
  before return. Unreleased pins log "cache reference leak" at txn end.
- Pointers into the tuple are only valid between SearchSysCache* and
  ReleaseSysCache. If you need them longer, either copy them out (pstrdup,
  datumCopy) or use SearchSysCacheCopy1 (palloc'd copy; free with
  heap_freetuple).
- Miss = NULL return (HeapTupleIsValid(tup) == false). NOT an error from
  the cache; the caller decides. Idioms:
    - "Should never happen": elog(ERROR, "cache lookup failed for X %u", oid)
    - User-triggerable:      ereport(ERROR, ERRCODE_UNDEFINED_<thing>, ...)
- Existence-only check: SearchSysCacheExists1 (no release needed).
- OID-only fetch:       GetSysCacheOid1.
```

Why: this is the most common syscache mistake (#6 in current failure-modes section), but the skill text gives no positive guidance — just one inline mention. Surfacing the lifecycle rules makes the skill self-contained for eval-3 type questions.

### 2. Add "append at end of fixed-length section" to the column-addition workflow

In §3 "Edit the header" — currently just mentions CATALOG_VARLEN, BKI_LOOKUP, BKI_DEFAULT, EXPOSE_TO_CLIENT_CODE. Add a bullet:

```
- When adding a new fixed-length column to an existing catalog, append it
  at the end of the struct (before any CATALOG_VARLEN block). This minimises
  ABI churn for code that reads Form_pg_X->existing_field — offsets of
  pre-existing fields don't shift.
```

Why: this is the standard convention but isn't explicit in either SKILL.md or the idioms doc. Improves eval-2 baseline-vs-skill delta.

### 3. Tighten OID-policy phrasing in §2

Current text:

> Pick a *random* starting OID in **8000-9999** and a contiguous block big enough for your patch.

Add the *reason* in parens — baseline answer missed the range because it doesn't surface the reason:

```
Pick a random starting OID in 8000-9999 (a project convention designed to
minimise collisions with other in-flight patches; the 0-7999 range is
reserved for already-committed pins, and the committer renumbers your
patch down to a tidy low range via renumber_oids.pl at commit time).
```

Why: makes the rule sticky enough that an LLM reading the skill once carries the *reason* into its answer, not just the number.

### 4. Add explicit "don't write defaulted columns / computed columns" inline example

Current text in §4 buries this in two bullets:

> - Don't write columns that have a `BKI_DEFAULT` matching your value.
> - Don't write computed columns like `pronargs`.

Better as a worked example:

```
For a typical immutable strict int4->int4 function the .dat row is just:

    { oid => '8473', descr => 'frobnitz of an int',
      proname => 'frobnitz', prorettype => 'int4',
      proargtypes => 'int4', prosrc => 'my_new_func' },

Don't write: pronargs (computed by AddDefaultValues), provolatile (default
'i' = immutable), proisstrict (default 't'), proparallel (default 's' =
safe), prokind ('f'), and anything else matching BKI_DEFAULT in pg_proc.h.
Only write columns where you DIVERGE from the default.
```

Why: turns a rule into a copy-pasteable pattern. Baseline answer was vague here ("you can override defaults like provolatile if needed") — a concrete example would force precision.

## Edits NOT proposed

- The `description:` frontmatter line is already strong (clear triggers + clear anti-triggers). Don't touch.
- The pre-commit checklist is already tight. Don't lengthen.
- The "things that bite" / "common failure modes" section is the right length. Don't expand.

## Suggested iteration-2 evals

To test the proposed edits:

1. "What's the right way to declare a new syscache on pg_constraint indexed by (conrelid, conname)?" — tests new syscache §6 expansion.
2. "I'm adding a varlena column to pg_aggregate, what placement rules apply?" — tests §3 placement bullet.
3. "Show me a minimal pg_proc.dat entry for a stable strict int8 sum function" — tests §4 worked example.
