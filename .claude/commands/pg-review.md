---
description: Multi-agent comprehensive review of a PostgreSQL patch (CommitFest entry, GitHub PR, or local .patch file). Usage: /pg-review <CF# | PR# | path/to/file.patch> [--skip-build] [--no-flaky-isolation] [--subsystem=<name>]
---

# pg-review

Thin wrapper around the `pg-patch-review` skill. This command does the
**mechanical pre-amble** (fetch + apply + build + regress/iso/TAP);
then the skill takes over for project discovery → fan out 4 critic
sub-agents in parallel → synthesize one PG-house-style review email.

The v0 of this workflow was the manual CF #6402 walk on 2026-06-02
(`sessions/2026-06-02-cf6402-review-validation.md`). This is v1.

## Arguments

- `$1` — the patch reference, one of:
  - CF number: `6402` or `cf6402` or `#6402`
  - GitHub PR number: `pr 19234` or `pr19234` or `#19234`
  - Local file: `/tmp/v3-0001-foo.patch` or a directory of patches
- Optional flags:
  - `--skip-build` — patch already applied + built; skip stage 0 entirely
  - `--no-flaky-isolation` — skip `--suite isolation` (macOS sometimes flakes)
  - `--subsystem=<name>` — hint which `knowledge/subsystems/*.md` to load first

## Pre-flight checks

```bash
# Identify the patch reference and the kind
REF="$1"
shift
SKIP_BUILD=""
NO_FLAKY_ISO=""
SUBSYSTEM_HINT=""

for arg in "$@"; do
  case "$arg" in
    --skip-build) SKIP_BUILD="1";;
    --no-flaky-isolation) NO_FLAKY_ISO="1";;
    --subsystem=*) SUBSYSTEM_HINT="${arg#--subsystem=}";;
  esac
done

if [ -z "$REF" ]; then
  echo "Usage: /pg-review <CF# | PR# | path/to/file.patch> [--skip-build] [--no-flaky-isolation] [--subsystem=<name>]"
  echo "Examples:"
  echo "  /pg-review 6402                          # CommitFest entry"
  echo "  /pg-review cf6402                        # same"
  echo "  /pg-review pr19234                       # GitHub PR on postgres/postgres"
  echo "  /pg-review /tmp/v3-0001-foo.patch        # local file"
  echo "  /pg-review 6402 --subsystem=access-nbtree"
  exit 1
fi

# Classify the reference
KIND=""
NUM=""
case "$REF" in
  cf*|CF*|\#*)
    KIND="cf"
    NUM="${REF#cf}"; NUM="${NUM#CF}"; NUM="${NUM#\#}"
    ;;
  pr*|PR*)
    KIND="pr"
    NUM="${REF#pr}"; NUM="${NUM#PR}"
    ;;
  [0-9]*)
    # Bare number — assume CF (most common); user can prefix `pr` to override
    KIND="cf"
    NUM="$REF"
    ;;
  /*|./*|../*|*.patch)
    KIND="file"
    PATCH_PATH="$REF"
    ;;
  *)
    echo "Cannot classify reference: $REF"
    echo "Use cf<N>, pr<N>, or a path ending in .patch"
    exit 1
    ;;
esac

# Confirm dev/ is on master and clean, or accept a clean tip
if [ "$SKIP_BUILD" != "1" ]; then
  if [ ! -d dev ]; then
    echo "dev/ symlink missing. Run /setup-pg first."
    exit 1
  fi
  if ! git -C dev diff-index --quiet HEAD --; then
    echo "dev/ has uncommitted changes. Stash or commit first."
    git -C dev status --short
    exit 1
  fi
fi

# Derive the branch name + session-log path
DATE=$(date +%Y-%m-%d)
case "$KIND" in
  cf)   BRANCH="cf${NUM}-review"; LOG="sessions/${DATE}-cf${NUM}-review.md";;
  pr)   BRANCH="pr${NUM}-review"; LOG="sessions/${DATE}-pr${NUM}-review.md";;
  file) BRANCH="local-review-${DATE}"; LOG="sessions/${DATE}-local-review.md";;
esac

echo "Kind: $KIND"
echo "Ref:  $NUM (or $PATCH_PATH)"
echo "Branch: dev/$BRANCH"
echo "Log:    $LOG"
[ -n "$SUBSYSTEM_HINT" ] && echo "Subsystem hint: $SUBSYSTEM_HINT"
```

## Stage 0 — mechanical pre-amble (the slash command's main job)

Skip this whole stage if `--skip-build` was passed.

### Step 1 — fetch the patch

For CF entries: scrape commitfest.postgresql.org to get the latest
patch attachment URL. The CF page lists patches by version (`v1`,
`v2`, …); take the highest version's latest attachment. Save under
`/tmp/cf<N>-vNN-*.patch`.

```bash
if [ "$KIND" = "cf" ]; then
  # Fetch the CF entry page; extract the latest attachment URL
  CF_URL="https://commitfest.postgresql.org/patch/$NUM/"
  # Use WebFetch with prompt:
  #   "Extract the URL of the latest patch attachment (highest vN,
  #    most recent timestamp). Return ONLY the URL, no commentary."
  # Then curl -L -o /tmp/cf${NUM}-v${V}.patch "$URL"
fi

if [ "$KIND" = "pr" ]; then
  # Use gh to download the PR diff
  PATCH_PATH="/tmp/pr${NUM}.patch"
  gh pr diff "$NUM" --repo postgres/postgres > "$PATCH_PATH"
fi
```

### Step 2 — apply on a fresh review branch

```bash
git -C dev checkout master
git -C dev pull --ff-only origin master 2>/dev/null || true
# Refresh against our source/ pin if upstream tracking isn't set up
git -C dev branch -D "$BRANCH" 2>/dev/null || true
git -C dev checkout -b "$BRANCH"

# Multi-patch series: glob handles vN-NNNN-*.patch ordering
git -C dev am /tmp/cf${NUM}-v*.patch 2>&1 | tee /tmp/cf${NUM}-am.log
# (or single file: git -C dev am "$PATCH_PATH")
```

If `git am` fails with a hunk reject:
- Record the failing patch + the hunk.
- STOP — patch needs rebase. Report to the user; do NOT proceed.

### Step 3 — build

```bash
cd dev/build-debug && ninja install 2>&1 | tee /tmp/cf${NUM}-build.log | tail -20
```

If the build fails, STOP. The patch broke something mechanically.

If there are new warnings (no errors), continue but record them — the
style critic will flag them.

### Step 4 — run regress + isolation

```bash
# Regress: ~30-40s on M-series
meson test -C dev/build-debug --no-rebuild regress/regress 2>&1 \
  | tee /tmp/cf${NUM}-regress.log | tail -10

# Isolation (skip if --no-flaky-isolation)
if [ "$NO_FLAKY_ISO" != "1" ]; then
  meson test -C dev/build-debug --no-rebuild --suite isolation 2>&1 \
    | tee /tmp/cf${NUM}-iso.log | tail -10
fi
```

### Step 5 — targeted suites (if subsystem hint given)

For patches touching specific subsystems, run the matching extra suite:

```bash
# Examples — pick based on touched files or --subsystem hint:
# access-nbtree, access-heap, access-gin, etc. → no extra suite usually
# replication, recovery → meson test --suite recovery (TAP)
# wal-and-xlog → meson test --suite recovery
# pg_dump → meson test --suite pg_dump
```

### Step 6 — gather file list + commit message

```bash
PATCH_FILES=$(git -C dev diff --name-only master..HEAD)
PATCH_LOG=$(git -C dev log master..HEAD --pretty=format:"%n---%n%H%n%s%n%n%b%n")

echo "Stage 0 complete. Handing off to pg-patch-review skill."
echo "Files touched: $PATCH_FILES"
echo "Branch: dev/$BRANCH @ $(git -C dev rev-parse --short HEAD)"
```

## Hand-off to the pg-patch-review skill

After stage 0, this command's job is done. The next step is to invoke
the `pg-patch-review` skill (load it from
`.claude/skills/pg-patch-review/SKILL.md`) and pass it:

- The branch name (`dev/$BRANCH`)
- The list of touched files
- The patch's commit messages
- Stage 0 results (regress + iso + targeted suite pass/fail)
- The subsystem hint, if any
- The session-log path to write the review email to (`$LOG`)

The skill then runs stages 1-4: project discovery, parallel critic
fan-out, consolidation, synthesis.

## Expected output

- `$LOG` — review email + per-critic appendices + stage-0 log + wall-time
  budget. This is the deliverable.
- `dev/$BRANCH` — disposable PG branch with the patch applied. Safe to
  delete after the review email is sent.

## Boundaries

- This command does NO interpretation. Stage 0 is purely mechanical.
- This command does NOT commit anything to `postgres-claude/` (no
  `knowledge/` or `planning/` writes). The session log is the only
  durable artifact, and it's only committed if the user asks.
- This command does NOT push to GitHub or send email. It produces the
  draft for the user to review + send manually.

## Troubleshooting

- **`git am` fails on hunk reject**: Patch needs rebase. Tell the user;
  optionally suggest a "rebase needed" reply to pgsql-hackers.
- **Build fails**: Stop. Report the compile error to the user with
  enough context to identify the patch's bug.
- **`commitfest.postgresql.org` page is unreachable**: WebFetch will
  return an error. Try `https://www.postgresql.org/message-id/` for the
  thread link if it's in the CF entry, or ask the user to paste the
  patch URL directly.
- **PR exists on a fork (not postgres/postgres)**: `gh pr diff` against
  the fork's URL. Tell the user the patch is unofficial.
- **`pg_bsd_indent` not installed**: pgindent step gets skipped. For
  patches authored locally, the pre-commit hook (`/pg-install-hooks`)
  already ran pgindent — the style critic verifies the result rather
  than re-running pgindent fresh.
- **Pre-existing macOS flakes**: `recovery/040_standby_failover_slots_sync`
  fails on macOS ~30% of the time independent of patches. If it's the
  only failure and the patch doesn't touch replication code, dismiss
  with a note in the stage-0 log.

## Related

- Skill: `.claude/skills/pg-patch-review/SKILL.md` (the orchestration).
- Companion checklist: `.claude/skills/review-checklist/SKILL.md` (each
  critic walks the seven-phase scaffold inside its slice).
- For YOUR OWN patch pre-submission: use `patch-submission` skill, not
  this command.
