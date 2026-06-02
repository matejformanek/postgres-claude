# cmdtag.h

- **Source:** `source/src/include/tcop/cmdtag.h`
- **Depth:** read

## What's here

- `CommandTag` enum — generated from `tcop/cmdtaglist.h` via
  `PG_CMDTAG(tag, ...)`.
- `QueryCompletion` struct: `{ CommandTag commandTag; uint64 nprocessed; }`.
- `COMPLETION_TAG_BUFSIZE`.
- Lookup helpers: `InitializeQueryCompletion`, `GetCommandTagName`,
  `GetCommandTagNameAndLen`, `GetCommandTagEnum`,
  `command_tag_display_rowcount`, `command_tag_event_trigger_ok`,
  `command_tag_table_rewrite_ok`, `BuildQueryCompletionString`.

## See also

`tcop/cmdtaglist.h` — the canonical PG_CMDTAG list to edit when adding a
new command tag.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/tcop.md](../../../../subsystems/tcop.md)
