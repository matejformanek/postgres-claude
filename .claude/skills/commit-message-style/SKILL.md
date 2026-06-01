---
name: commit-message-style
description: How to write a commit message that matches upstream PostgreSQL house style — imperative single-line title (no conventional-commits prefix), paragraph-form body wrapped near 76 chars, the Author / Reviewed-by / Reported-by / Discussion / Backpatch-through trailer block, and what is conspicuously absent (no Co-Authored-By, no emoji, no ticket numbers, no bullet-heavy bodies). Use whenever drafting a commit for any patch intended to look like upstream PG.
---

# commit-message-style

PostgreSQL has a strong, consistent commit-message house style. It is not
"conventional commits" and it is not GitHub-flavored. Match it whenever
the change is meant to plausibly land on `master`.

## 1. Anatomy

```
<imperative one-line summary, under ~64 chars>

<one or more paragraphs of prose, wrapped near 72–76 chars,
explaining the why and the what — not a diff recap>

Author: First Last <email@example.com>
Reviewed-by: First Last <email@example.com>
Reported-by: First Last <email@example.com>
Discussion: https://postgr.es/m/<message-id>
Backpatch-through: <branch>
```

The order is: subject, blank line, narrative paragraphs, blank line,
trailer block. The trailer block always ends the message.
[from-wiki: Commit_Message_Guidance — "Summary line / Blank line /
Narrative (with paragraphs separated by blank lines) / Tags section"]

## 2. The title line

- Imperative mood: "Fix X", "Improve Y", "Add Z" — not "Fixes" or "Fixed".
- Capitalize the first word. No trailing period.
- Under ~64 characters when possible (email subject-line limit).
  [from-wiki: Commit_Message_Guidance — "Keep under 64 characters"]
- No prefix tag *unless* the change is scoped to a specific subsystem
  that has an established prefix in the log. Common observed prefixes:
  `doc:`, `libpq:`, `psql:`, `pg_dump:`, `postgres_fdw:`, `pg_upgrade:`,
  `pgbench:`, `pg_basebackup:`. Module name + colon, lowercase.
  [verified-by-code: `git log --oneline -50` shows
  `doc: Correct the timeline for OAuth's shutdown_cb` (08127c641c0),
  `libpq: Fix grease error message style` (5ca41e4125e),
  `postgres_fdw: Fix whitespace violation in connection.c` (af23353a73d)]
- **Do not** use conventional-commits style: no `feat:`, `fix:`,
  `chore:`, `refactor:`. [verified-by-code: zero matches for `^feat:`
  or `^chore:` in `git log --oneline -200`.]

## 3. The body

- Wrap at 72–76 columns. Inspection of recent commits shows lines mostly
  ≤76. [verified-by-code: see body of `db5ed03217b`, `5fee7cab1b8`,
  `89d243d5218` — all wrap in that range.]
- Paragraph form, not bullets. Bullets do appear occasionally (e.g.
  numbered repro scenarios) but the default is prose. [verified-by-code:
  `5fee7cab1b8` uses a numbered 1)–7) reproduction list, surrounded by
  prose paragraphs. Pure-bullet bodies are rare.]
- Explain **why** the change is needed and **what** approach was taken.
  Do not restate the diff line-by-line.
- When fixing a regression, name the introducing commit. Use **9-char
  SHA** so the web UI hyperlinks it. [from-wiki: Committing_checklist —
  "it's a good idea to use the first 9 chars of the commit SHA. Fewer
  than 9 means there will be no hyperlink in the HTTP interface."
  verified-by-code: `7dc5bbcf220` body says "Introduced by 7dadd38cda9
  (json format for COPY TO)."]

## 4. The trailer block

Format: `Tag: Name <email> [(optional short context)]`, one tag per line,
each starting at column 0. Repeat the tag for multiple people; do **not**
comma-separate. [from-wiki: Commit_Message_Guidance]

Standard tags, in roughly the order you'll see them:

| Tag                | Meaning                                              |
| ------------------ | ---------------------------------------------------- |
| `Author:`          | Patch author. Omit if the committer is sole author.  |
| `Co-authored-by:`  | Additional patch authors (PG variant — lowercase `a`).|
| `Reported-by:`     | Person who found the bug / suggested the feature.    |
| `Suggested-by:`    | Specifically suggested an approach.                  |
| `Diagnosed-by:`    | Root-caused it without writing the patch.            |
| `Analyzed-by:`     | Did notable analysis (variant of Diagnosed-by).      |
| `Reviewed-by:`     | Did meaningful patch review.                         |
| `Tested-by:`       | Verified the fix.                                    |
| `Bug:`             | Bug number (`#NNNN`).                                |
| `Discussion:`      | `https://postgr.es/m/<message-id>` to the thread.    |
| `Backpatch-through:` | Oldest branch this is being backpatched to.        |

[from-wiki: Commit_Message_Guidance; all observed in recent log
verified-by-code — see `db5ed03217b` (Author + 3x Reviewed-by +
Discussion), `b1901e2895e` (Reported-by + 2x Analyzed-by + Discussion).]

Notes:

- Attribution is **cut-and-paste from the email From: header**,
  unaltered. Don't normalize names or emails. [from-wiki:
  Commit_Message_Guidance]
- `Discussion:` URL uses the `postgr.es/m/...` shortener, **not** the
  raw archives URL. [verified-by-code: every Discussion line in `git
  log -20` uses `https://postgr.es/m/`.]
- `Backpatch-through:` value is the **oldest** branch that gets the
  fix, expressed as a major-version number: `18`, `15`, `14`.
  [verified-by-code: `08127c641c0` has `Backpatch-through: 18`;
  `89d243d5218` has `Backpatch-through: 14`. from-wiki:
  Commit_Message_Guidance — "use oldest branch version (e.g., '15'),
  range format (e.g., '13-15'), or 'only' for single branches".]
- For master-only commits, omit `Backpatch-through:` entirely.
  [from-wiki: Commit_Message_Guidance]

## 5. What is NOT in PG commit messages

Verified by `git log --grep` over recent history; absence is real:

- **No `Co-Authored-By:` (capital A B Y)** — that's the GitHub /
  Claude Code convention. PG uses `Co-authored-by:` (lowercase `a` /
  `b`). [verified-by-code: search of recent log shows lowercase form
  only.] **Do not add the `Co-Authored-By: Claude` trailer to PG
  commits.**
- **No conventional-commits prefix.** No `feat:`, `fix:`, `chore:`,
  `refactor:`, `BREAKING CHANGE:`. [verified-by-code: 0 matches in
  recent log.]
- **No emoji.** [verified-by-code: scan of `git log -50 --format=%s%n%b`
  — none present.]
- **No ticket numbers / issue refs from external trackers.** PG uses
  the mailing list and its `Bug: #NNNN` form for community bug numbers,
  not GitHub issue links. [from-wiki + verified-by-code.]
- **No "Signed-off-by:".** PG is not a DCO project.
  [verified-by-code: 0 occurrences in recent log.]
- **No diff recap bullets** ("- changed foo\n- added bar"). The body
  explains intent. [verified-by-code: see examples in §6.]

## 6. Three verbatim examples

### Example A — straightforward fix with reviewer credit

```
Avoid leaking system path from pg_available_extensions

The documentation says that when extension_control_path is set to an
empty string, the default '$system' path is still assumed.  However,
get_extension_control_directories() added the system extension directory
with a NULL macro in that case.  As a result, pg_available_extensions
could expose the expanded system directory path instead of reporting
'$system' as the location.

Record the implicitly-added system directory with the '$system' macro, so
pg_available_extensions reports the documented symbolic location and does
not leak the actual system path.

Update the extension_control_path TAP test to check the reported location
directly.

Author: Chao Li <lic@highgo.com>
Reviewed-by: Lu Feng <fnlo1995@gmail.com>
Reviewed-by: Matheus Alcantara <matheusssilv97@gmail.com>
Reviewed-by: Jim Jones <jim.jones@uni-muenster.de>
Discussion: https://postgr.es/m/357C774A-ECE9-4455-B641-315205D4D9A1@gmail.com
```

[verified-by-code: `git show db5ed03217b`]

### Example B — bugfix with named introducing commit

```
Apply encoding conversion in COPY TO FORMAT JSON

CopyToJsonOneRow() sent the output of composite_to_json() directly
via CopySendData() without encoding conversion.  The text and CSV
paths convert per-attribute via pg_server_to_any() when
need_transcoding is true, but the JSON path skipped this entirely.

This meant COPY ... TO ... WITH (FORMAT json, ENCODING 'LATIN1') on
a UTF-8 server silently produced UTF-8 output, and COPY TO STDOUT
with a non-UTF-8 client_encoding would send unconverted bytes to
the client.

Apply pg_server_to_any() to the whole JSON buffer after
composite_to_json() returns, converting to the requested file
encoding when it differs from the server encoding.  Tests cover
both the explicit ENCODING option and the implicit case where
file_encoding is inherited from client_encoding.

Introduced by 7dadd38cda9 (json format for COPY TO).

Author: Ayush Tiwari <ayushtiwari.slg01@gmail.com>
Reviewed-by: Andrew Dunstan <andrew@dunslane.net>
Discussion: https://postgr.es/m/CAJTYsWX-jsLzxGRAb-dWnEpGYRPbDYHwce8LctVE92LiDfM2Jw@mail.gmail.com
```

[verified-by-code: `git show 7dc5bbcf220`]

### Example C — backpatched fix, doc-prefix subject

```
doc: Correct the timeline for OAuth's shutdown_cb

During original feature development, the OAuth validator shutdown
callback was invoked via before_shmem_exit(). That was changed to use a
reset callback before commit, but I forgot to update the documentation
for validator developers.

Correct this and backport to 18, where OAuth was introduced. The
callback is invoked whenever the server is "finished" with token
validation. (We make no stronger guarantees here, in the hopes that this
API might successfully navigate future multifactor authentication
support and/or changes to the server threading model.)

Reported-by: Zsolt Parragi <zsolt.parragi@percona.com>
Reviewed-by: Zsolt Parragi <zsolt.parragi@percona.com>
Reviewed-by: Chao Li <li.evan.chao@gmail.com>
Discussion: https://postgr.es/m/CAN4CZFOuMb_gnLvCwRdMybg_k8WRNJTjcij%2BPoQkuQHDUzxGWg%40mail.gmail.com
Backpatch-through: 18
```

[verified-by-code: `git show 08127c641c0`]

## 7. Catalog-version bumps

If your patch changes anything that affects on-disk format or system
catalog layout, you bump `CATALOG_VERSION_NO` (and possibly
`PG_CONTROL_VERSION`, `XLOG_PAGE_MAGIC`, `PGSTAT_FILE_FORMAT_ID`).
The bump itself is a one-line `#define` change usually done by the
committer at apply time; you do **not** put a paragraph about it in the
commit body, but the bump is included in the same commit. [from-wiki:
Committing_checklist — "Consider… CATALOG_VERSION_NO, PG_CONTROL_VERSION,
XLOG_PAGE_MAGIC, PGSTAT_FILE_FORMAT_ID."]

## 8. Backpatching mechanics

When the same fix lands on multiple branches, **the commit message must
be identical across branches** so tooling can match them up for release
notes. The only thing that varies between the branches is the diff
itself (resolved conflicts). [from-wiki: Committing_checklist —
"Commit messages for multiple branches should be identical when
back-patching, in order to have tooling recognize the redundancy for
purposes of compiling release notes."]

The trailer `Backpatch-through: 14` appears on **all** the cherry-picked
copies, naming the **oldest** branch — not "Backpatch from master" or
similar.

## 9. Checklist before `git commit`

1. Subject is imperative, capitalized, no period, under ~64 chars.
2. Subject has a subsystem prefix only if the change is scoped to one.
3. Body wraps near 72–76 cols and explains **why**.
4. Trailer block: `Author:` (if not you), `Reported-by:` /
   `Reviewed-by:` as applicable, `Discussion: https://postgr.es/m/...`,
   `Backpatch-through:` only if backpatching.
5. No `Co-Authored-By: Claude`, no `Signed-off-by:`, no emoji, no
   conventional-commits prefix.
6. If the diff touches catalog layout, the same commit bumps
   `CATALOG_VERSION_NO`.

When uncertain, run `git log --format='%n----- %h %s%n%n%b' -20` and
mirror the style of the most recent committer in that subsystem.
