# `contrib/pg_plan_advice/pgpa_output.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~22
- **Source:** `source/contrib/pg_plan_advice/pgpa_output.h`

Single-function header — exports `pgpa_output_advice`. [verified-by-code]

## API / entry points

- `pgpa_output_advice(StringInfo buf, pgpa_plan_walker_context *walker,
  pgpa_identifier *rt_identifiers)` (line 18). See `pgpa_output.c` doc.

## Notable invariants / details

- Includes `pgpa_walker.h` directly because the `walker` parameter is
  consumed by name. [verified-by-code]

## Potential issues

(None.)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pg_plan_advice.md](../../../subsystems/contrib-pg_plan_advice.md)
