# `src/backend/tsearch/ts_utils.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~110
- **Source:** `source/src/backend/tsearch/ts_utils.c`

Path resolution for tsearch dict/affix files. `get_tsearch_config_filename
(basename, ext)` resolves a base name (relative to `$SHAREDIR/tsearch_data/`)
into a full path with the given extension. Used by every dictionary
template when loading external files (`.dict`, `.affix`, `.stop`,
`.syn`, `.ths`). Validates that the resulting path stays under the
share dir — no `..` escape. [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
