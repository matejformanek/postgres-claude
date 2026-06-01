---
description: Document a PostgreSQL backend subsystem via the subsystem-documenter agent. Usage: /document-subsystem <subsystem-path>
---

# document-subsystem

Thin wrapper around the `subsystem-documenter` agent. Takes one argument: a
subsystem path under `source/src/backend/`, like `storage/buffer` or
`access/heap`.

## Argument

`$1` — the subsystem path, relative to `source/src/backend/`. Examples:
- `storage/buffer`
- `access/heap`
- `replication/logical`
- `optimizer/path`

If no argument is given, print usage and exit.

## Pre-flight checks

From the project root (`/Users/matej/Work/postgres/postgres-claude/`):

```bash
SUBSYS="$1"

if [ -z "$SUBSYS" ]; then
  echo "Usage: /document-subsystem <path-under-source/src/backend>"
  echo "Example: /document-subsystem storage/buffer"
  exit 1
fi

FULL="source/src/backend/$SUBSYS"

if [ ! -d "$FULL" ]; then
  echo "Subsystem directory not found: $FULL"
  echo "Listing nearby candidates:"
  ls source/src/backend/ 2>/dev/null | head -30
  exit 1
fi

echo "Documenting subsystem: $SUBSYS"
echo "Source path: $FULL"
```

## Method

1. Read `.claude/agents/subsystem-documenter.md` end-to-end — that file
   defines the procedure, doc template, confidence tags, and the
   `progress/STATE.md` + `progress/coverage.md` + `sessions/` updates the
   agent is responsible for.

2. Dispatch the agent with:
   - `subsystem_path`: `source/src/backend/<$SUBSYS>`
   - `output_path`: `knowledge/subsystems/<flattened-name>.md`
     (flatten by replacing `/` with `-`; e.g. `storage/buffer` →
     `knowledge/subsystems/storage-buffer.md`)
   - hint (optional): any emphasis the user mentioned (locking order,
     recovery, planning, …)

3. After the agent reports back, invoke the `memory-keeping` skill so
   `progress/STATE.md` and `progress/coverage.md` reflect the new doc and
   the session log is appended to `sessions/<date>-<subsystem>.md`. The
   agent does most of this itself per its spec, but `memory-keeping` is
   the cross-check.

## Expected output

- `knowledge/subsystems/<flattened>.md` — the durable doc, following the
  template in the agent spec (Purpose, Mental model, Key files, Key data
  structures, Control flow, Locking and invariants, Interactions, Tests,
  Open questions, Glossary).
- Updated `progress/coverage.md` row.
- Updated `progress/STATE.md` reflecting the new doc + last-verified commit.
- New `sessions/<date>-<subsystem>.md` log.

## Troubleshooting

- **"Subsystem directory not found"**: check `ls source/src/backend/` for
  the actual layout. Common confusion: `access/heap` exists but `access/btree`
  is `access/nbtree`; `storage/buffer` exists but `storage/buffermgr` doesn't.
- **Agent produced an empty / shallow doc**: re-invoke with a hint like
  "emphasize locking order" or "focus on the WAL interaction" to anchor the
  deep read.
- **`progress/STATE.md` not updated**: the agent should do this; if it
  didn't, run the `memory-keeping` skill manually to reconcile.
