# cmdtag.c

- **Source:** `source/src/backend/tcop/cmdtag.c` (163 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (entire file)

## Purpose

Stores the static metadata table for every `CommandTag` enum value and
implements the lookup / formatting helpers used by `dest.c::EndCommand`,
the event-trigger code, and the rewriter. [from-comment] `:3-5`

## Mechanism

- The enum (`CMDTAG_*`) and the data table are both generated from
  `include/tcop/cmdtaglist.h` via the `PG_CMDTAG(tag, name, evtrgok, rwrok,
  rowcnt)` macro. `:30-37`
- `tag_behavior[]` is sorted by name so `GetCommandTagEnum` can do a
  binary search. `:83-107`

## API

| Symbol | Returns |
|---|---|
| `InitializeQueryCompletion` | zero out `QueryCompletion` |
| `GetCommandTagName(tag)` | C string, e.g. `"SELECT"` |
| `GetCommandTagNameAndLen(tag, &len)` | same + cached strlen |
| `command_tag_display_rowcount(tag)` | should `EndCommand` append nprocessed? |
| `command_tag_event_trigger_ok(tag)` | may an event trigger fire? |
| `command_tag_table_rewrite_ok(tag)` | is this tag valid as a table_rewrite event? |
| `GetCommandTagEnum(name)` | reverse lookup, returns `CMDTAG_UNKNOWN` on miss |
| `BuildQueryCompletionString(buff, qc, nameonly)` | format e.g. `"INSERT 0 5"` (the `0` is the legacy WITH-OIDS slot — always written as 0 now for protocol compat). [from-comment] `:140-145` |

## Headers

- `tcop/cmdtag.h` — `CommandTag`, `QueryCompletion`.
- `tcop/cmdtaglist.h` — the canonical PG_CMDTAG list, edit here to add a tag.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
