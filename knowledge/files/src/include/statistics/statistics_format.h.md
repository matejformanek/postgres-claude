# `src/include/statistics/statistics_format.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~47
- **Source:** `source/src/include/statistics/statistics_format.h`

JSON key-name constants for the **human-readable** wire format of
`pg_ndistinct` and `pg_dependencies` (the OUT format produced by
`pg_*_out` and consumable by `pg_*_in`). The actual serialized
bytea format is documented in `statistics.h` and its build code.
This file is sharable between frontend and backend ("usable by both
frontend and backend code" per the comment). [verified-by-code]

## API / declarations

- `pg_ndistinct` JSON keys:
  - `PG_NDISTINCT_KEY_ATTRIBUTES "attributes"`
  - `PG_NDISTINCT_KEY_NDISTINCT  "ndistinct"`
- `pg_dependencies` JSON keys:
  - `PG_DEPENDENCIES_KEY_ATTRIBUTES "attributes"`
  - `PG_DEPENDENCIES_KEY_DEPENDENCY "dependency"`
  - `PG_DEPENDENCIES_KEY_DEGREE     "degree"`

## Notable invariants / details

- The exposed text format is a JSON array with the keys above.
  Example (from comment):
  ```
  [{"ndistinct": 11, "attributes": [3,4]},
   {"ndistinct": 11, "attributes": [3,6]},
   ... ]
  ```
- These string constants are part of the SQL-visible interface —
  changing them breaks `pg_dump` of upgrade test fixtures and any
  user code that parses the output. [inferred]

## Potential issues

- No version field in the JSON; if a new key is added a future
  parser must accept the absence. [ISSUE-undocumented-invariant:
  JSON forward-compat of pg_*_out (nit)]
- The MCV equivalent (`pg_mcv_list_items`) does not get its keys
  defined here — its output is a SRF returning typed columns rather
  than a JSON blob. Not a bug, but the asymmetry could confuse a
  reviewer expecting a third block of constants.
  [ISSUE-question: should MCV have a parallel keys file? (nit)]
