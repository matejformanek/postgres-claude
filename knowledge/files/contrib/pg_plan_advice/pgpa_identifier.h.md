# `contrib/pg_plan_advice/pgpa_identifier.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~52
- **Source:** `source/contrib/pg_plan_advice/pgpa_identifier.h`

Defines the `pgpa_identifier` struct that is the load-bearing primitive of
the module: every advice target ultimately resolves to one or more of these,
and every RTE in a plan gets one. Also provides the inline NULL-safe
string-compare helper `strings_equal_or_both_null` reused across the contrib.
[verified-by-code]

## API / entry points

- `pgpa_identifier` struct (line 19): `alias_name` (required), `occurrence`
  (1-based), `partnsp`, `partrel`, `plan_name`. All strings owned by
  caller-supplied memory. [verified-by-code]
- `strings_equal_or_both_null(a, b)` (line 30): inline; pointer-equal fast
  path, NULL-vs-non-NULL = false, otherwise `strcmp`. [verified-by-code]
- Declarations for `pgpa_identifier_string`,
  `pgpa_compute_identifier_by_rti`, `pgpa_compute_identifiers_by_relids`,
  `pgpa_create_identifiers_for_planned_stmt`,
  `pgpa_compute_rti_from_identifier`. See `pgpa_identifier.c` doc.

## Notable invariants / details

- All fields except `alias_name` may be NULL. `occurrence >= 1` is asserted
  in `pgpa_identifier_string`. [verified-by-code]
- `partrel` without `partnsp` is permitted from user input (advice strings)
  but not produced by generated identifiers. Asserted at multiple call sites
  in `pgpa_ast.c` and `pgpa_identifier.c`. [from-comment]

## Potential issues

- `pgpa_identifier.h:30-38` — `strings_equal_or_both_null` is defined
  `static inline` in a header; included from multiple `.c` files. PG style
  allows this but it diverges from the more common pattern of a single
  out-of-line definition. Not a bug. [verified-by-code]
- `pgpa_identifier.h` does NOT declare `pgpa_identifier_string` to be
  pure / const, even though it constructs a new psprintf chain each call.
  Returns `const char *` (caller can't free it; it's palloc'd). [ISSUE-style:
  const char * return suggests immutability but each call allocates fresh
  in current memory context (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_plan_advice`](../../../issues/pg_plan_advice.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pg_plan_advice.md](../../../subsystems/contrib-pg_plan_advice.md)
