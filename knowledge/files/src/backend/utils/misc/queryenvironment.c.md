# `src/backend/utils/misc/queryenvironment.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~144
- **Source:** `source/src/backend/utils/misc/queryenvironment.c`

Holds the per-query "ephemeral named relation" (ENR) registry — a
list of named tuplestores carrying delta data (e.g. the `OLD`/`NEW`
transition tables passed into AFTER STATEMENT triggers from row
modifications). Treated as an opaque struct so callers go through
the API rather than poke at the list. [from-comment] [verified-by-code]

## API

- `create_queryEnv(void)` — `palloc0_object(QueryEnvironment)`.
  Caller owns the lifetime; usually attached to a `QueryDesc` or
  `EState`. [verified-by-code]
- `register_ENR(QueryEnvironment *queryEnv, EphemeralNamedRelation enr)`
  — append to internal list. `Assert`s the name is not already
  registered. [verified-by-code]
- `unregister_ENR(QueryEnvironment *queryEnv, const char *name)` —
  remove by name; no-op if missing. [verified-by-code]
- `get_ENR(QueryEnvironment *queryEnv, const char *name)` — linear
  scan with `strcmp`; returns NULL if no match or if `queryEnv` is
  NULL. [verified-by-code]
- `get_visible_ENR_metadata(queryEnv, refname)` — convenience
  wrapper returning a pointer to the matched ENR's `md` field, or
  NULL. [verified-by-code]
- `ENRMetadataGetTupDesc(enrmd)` — returns the TupleDesc for an ENR.
  If `tupdesc` is filled directly use it; if the ENR is sourced from
  a catalog `reliddesc` OID, open the relation `NoLock` (relying on
  the caller's existing lock — "Locking here would be too late
  anyway"). [verified-by-code] [from-comment]

## Notable invariants / details

- Storage is a plain `List *` of `EphemeralNamedRelation` pointers.
  Header comment justifies this as "expected to be very small";
  switching to a hash needs no API change. [from-comment]
- Names are matched with `strcmp` (case-sensitive, byte-equal). No
  collation, no case-folding. Callers must lowercase quoted vs
  unquoted identifiers themselves before registering. [verified-by-code]
  [ISSUE-undocumented-invariant: case-sensitivity contract on ENR
  name is implicit (nit)]
- `ENRMetadataGetTupDesc` asserts exactly one of `reliddesc` and
  `tupdesc` is set — XOR invariant on ENR creation. [verified-by-code]
- The `table_open(reliddesc, NoLock)` then `table_close(reliddesc,
  NoLock)` pair returns `rd_att` — the TupleDesc is owned by the
  Relcache entry, so callers must not free it. If the underlying
  relation is closed while the TupleDesc is still in use, this is a
  use-after-free risk. The comment says "we count on that relation
  being used at the same time", placing the burden on the caller.
  [verified-by-code] [from-comment] [ISSUE-undocumented-invariant:
  TupleDesc lifetime tied to caller's existing relation handle
  (likely)]
- No `unregister_ENR` is needed in normal flow because the entire
  `QueryEnvironment` is discarded at end of query (palloc context
  cleanup). [inferred]

## Potential issues

- File-line: queryenvironment.c:138. Opening and immediately closing
  a relation with `NoLock` to fish out `rd_att` is a thin invariant
  — if relcache invalidations slip in between this call and use of
  the TupleDesc, the desc could become stale. Existing callers all
  hold the relation open separately, so this is safe today but
  fragile. [ISSUE-undocumented-invariant: TupleDesc returned from
  NoLock open relies on outer relation pin (maybe)]
- File-line: queryenvironment.c:109. Linear `strcmp` lookup means
  registering N ENRs and querying each is O(N²). Header acknowledges
  this; not an issue at expected sizes. [ISSUE-style: documented
  O(N) lookup; switch to hash if list grows (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils`](../../../../../issues/utils.md)
<!-- issues:auto:end -->
