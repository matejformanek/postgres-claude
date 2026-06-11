# `src/bin/pg_combinebackup/reconstruct.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~35
- **Source:** `source/src/bin/pg_combinebackup/reconstruct.h`

Single-function header for `reconstruct.c`. Declares
`reconstruct_from_incremental_file()` and pulls in
`load_manifest.h`, `copy_file.h`, and `common/checksum_helper.h`.
[verified-by-code]

## API / entry points

- `reconstruct_from_incremental_file(...)` — see
  `reconstruct.c.md` for the full parameter list and contract.
  [verified-by-code]

## Notable invariants / details

- Pulls in `load_manifest.h` for `manifest_data *`. The transitive
  include set means consumers do not need to include
  `load_manifest.h` themselves. [verified-by-code]

## Potential issues

- None notable.
