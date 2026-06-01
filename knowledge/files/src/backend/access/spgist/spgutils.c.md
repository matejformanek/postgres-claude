# spgutils.c

- **Source path:** `source/src/backend/access/spgist/spgutils.c` (1367 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Hosts `spghandler` (the AM vtable), the `SpGistState` opclass cache, page-allocation logic with **triple-parity placement**, metapage init, last-used-page cache, redirect/placeholder helpers, and reloption handling. The largest file in spgist after `spgdoinsert.c`. [from-comment, spgutils.c:1-13]

## `spghandler`

Registers SP-GiST as: `amgettuple`, `amgetbitmap`, `amcanorderbyop=true` (KNN), `amcanunique=false`, `amcanmulticol=false`, `amsearchnulls=true`, `amparallelscan=true`, `amclusterable=false`, INCLUDE columns supported (`amcaninclude=true`).

## Key functions

| Function | Role |
|---|---|
| `spghandler` (PG_FUNCTION) | The AM vtable |
| `initSpGistState` | Lookup opclass procs, cache in `SpGistState` |
| `SpGistNewBuffer` | Get a fresh buffer for the right "purpose" (leaf / inner / nulls-leaf / nulls-inner) honoring triple-parity. Uses last-used-page cache in metapage; falls back to FSM or extend |
| `SpGistGetBuffer` | Get a buffer for a specific page, with conditional locking for the deadlock-avoidance protocol |
| `SpGistUpdateMetaPage` | Flush last-used-page cache back to metapage (not WAL-logged) |
| `SpGistInitMetapage` | Initial metapage construction |
| `SpGistInitPage` / `SpGistInitBuffer` | Init a fresh SpGist page (type-tagged) |
| `spgFormLeafTuple` / `spgFormInnerTuple` / `spgFormDeadTuple` | Tuple constructors |
| `SpGistPageAddNewItem` | PageAddItem wrapper that prefers to overwrite a PLACEHOLDER (preserving offsets) before extending |
| `SpGistGetXidHorizon` | Compute conflict horizon for redirect/dead tuples |
| `spgoptions` | Reloption parser |

## Triple-parity placement

`SpGistNewBuffer` picks a page where `(N+1) mod 3 == M mod 3`. The last-used-page cache stores **three** candidate inner pages (one per parity class) so any new child page can be allocated parity-correct. [from-README, README:234-244; verified-by-code]

## Placeholder/redirect helpers

- `SpGistPageAddNewItem` overwrites a PLACEHOLDER slot if available; otherwise appends. This is what keeps offsets stable when tuples are added/removed.
- The PLACEHOLDER tail is trimmed at VACUUM time (`spgvacuum.c`).

## Last-used-page cache

Stored in metapage. Updated in-memory by `SpGistNewBuffer` results; flushed to metapage occasionally (and at index close). **Not WAL-logged** — README §"Last Used Page Management" says incorrect cache values are harmless (just allocate a new page). [from-README, README:376-383]

## Cross-references

- **Called from:** every spgist source file.
- **Calls into:** `storage/bufmgr.c`, `storage/indexfsm.c`, fmgr for opclass procs.

Tags: [from-comment, spgutils.c:1-13]; [from-README, README:234-244, 376-383].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
