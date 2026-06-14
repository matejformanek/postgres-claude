---
description: Pull upstream master in both PG clones, diff against the last-verified commit, and list which corpus docs reference files that have changed. Surfaces the rot list before the corpus drifts silently. **Manual escape hatch** — the daily anchor-bump path is the `pg-anchor-refresh` cloud routine (per the 2026-06-12 backbone audit); use this command only when the routine is offline or a one-off targeted check is needed.
---

# refresh-upstream

The pg-claude corpus is anchored to a specific upstream commit (recorded in
each doc's "Last verified commit" line and in `progress/files-examined.md`).
Upstream master moves; without active maintenance, file:line citations can
become wrong without anyone noticing.

**Note on the routine vs this command.** As of 2026-06-10 the
`pg-anchor-refresh` cloud routine (`.claude/cloud/pg-anchor-refresh.md`)
runs daily and handles the structural-drift case (anchor bump + per-doc
re-verify queue + auto-edit of stale cites where confident). **Prefer
the routine** for the daily / scheduled refresh path. This command stays
as the manual escape hatch — useful when the routine is offline, when
you want to inspect the rot list before any auto-edits, or when chasing
a specific subsystem's drift.

This command:

1. Pulls upstream master in `postgresql/` (read-only ref).
2. Pulls in `postgresql-dev/` (mutable test field).
3. Reads the most-common last-verified commit from `progress/files-examined.md`.
4. Runs `git log <last-verified>..master --name-only` against the read-only
   clone to enumerate touched files.
5. Cross-references touched files against `progress/files-examined.md`'s
   registry to produce a `progress/refresh-<date>.md` report listing:
   - per-file: was it touched? at what depth was it documented? which docs
     cite it?
   - subsystems with the most churn since last verification
   - the recommended re-verify queue (deep-read files touched + their
     dependent docs)

Does NOT auto-edit any docs. The user (or a follow-up agent) decides which
re-verifies are worth doing now vs deferred.

## What to run

```bash
# 1. Pull upstream in both clones
git -C source pull --ff-only origin master
git -C dev pull --ff-only origin master

# 2. Find the most-common last-verified commit
ANCHOR=$(awk -F'|' '/^\| src/ {gsub(/ /, "", $4); print $4}' progress/files-examined.md | sort | uniq -c | sort -rn | head -1 | awk '{print $2}')
echo "Anchor commit: $ANCHOR"

# 3. Touched files
git -C source log --name-only --pretty=format: "$ANCHOR..origin/master" | sort -u | grep -v '^$' > /tmp/refresh-touched.txt
echo "Touched files since $ANCHOR: $(wc -l < /tmp/refresh-touched.txt)"

# 4. Cross-reference (use the small Python below or just grep)
DATE=$(date +%Y-%m-%d)
REPORT="progress/refresh-${DATE}.md"
# ... see report-generation step below
```

## Report-generation step

For each touched source-tree path, find which rows of `files-examined.md`
reference it, and which `knowledge/...` docs cite it. Write a markdown report
at `progress/refresh-<date>.md`:

```markdown
# Refresh report — <date>

- Anchor commit: <sha>
- New master commit: <sha>
- Touched files: <N>
- Touched files in corpus: <M>

## Touched files we have docs for, by depth

### deep-read files (re-verify these first)
| File | knowledge/files/ doc | other docs that cite it |
| --- | --- | --- |
| src/backend/storage/buffer/bufmgr.c | knowledge/files/.../bufmgr.c.md | knowledge/subsystems/storage-buffer.md, knowledge/architecture/wal.md |

### read files
... (same shape)

### skim files
... (same shape)

## Touched subsystems sorted by churn

(grouped by source dir, with count of touched files)

## Recommended re-verify queue

1. Highest-priority deep-reads
2. Subsystems with >= N touched files
3. Long-form docs whose citations may have rotted

## Untouched corpus

Files that haven't changed upstream since the anchor — no re-verify needed.
```

## How to actually generate the report

Use python (it's installed; no extra deps needed):

```python
import re, subprocess, json
from pathlib import Path
from collections import defaultdict

repo = Path("/Users/matej/Work/postgres/postgres-claude")
touched = set(Path(p).as_posix() for p in
              subprocess.check_output(["git", "-C", "source", "log",
                                       "--name-only", "--pretty=format:",
                                       f"{ANCHOR}..origin/master"],
                                      cwd=repo, text=True).split() if p)

# Parse registry rows
rows = []  # (path, depth, knowledge_doc)
for line in (repo / "progress/files-examined.md").read_text().splitlines():
    m = re.match(r"^\| (src/\S+) \| .* \| (\w+) \| .*\| (\S*) \|", line)
    if m: rows.append(m.groups())

# Cross-reference
out = defaultdict(list)
for path, depth, doc in rows:
    if path in touched: out[depth].append((path, doc))

# ... emit report
```

## After running

Print to the user:

- Top 10 touched-and-documented files by churn
- Count of files needing re-verify by depth tier (deep-read > read > skim)
- Recommend either `/document-subsystem <X>` for whole-subsystem refresh or
  manual re-anchor for individual files

## Troubleshooting

- **`git pull --ff-only` fails** — local commits in the clone. For `source/`
  (read-only) reset to upstream: `git -C source fetch origin && git -C source
  reset --hard origin/master`. For `dev/`, ask the user — there may be
  in-progress work.
- **No anchor commit found** — registry was wiped. Re-anchor everything by
  running `/document-subsystem` on each spine. The current anchor for the
  initial corpus is `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3`
  (2026-06-01).
- **`progress/refresh-<date>.md` already exists** — append `-r2`, `-r3` etc.
  to the filename. Don't overwrite previous refresh reports.

## When to run

- Weekly is fine for active development.
- Before starting a new long-form doc (so the citations you add aren't already
  stale).
- Before pushing pg-claude to GitHub when you've been on a long branch.

The corpus will rot silently otherwise.
