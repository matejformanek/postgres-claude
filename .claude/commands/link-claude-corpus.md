---
description: Wire pg-claude into an EXISTING PostgreSQL dev tree. Asks whether to point this repo at your dev clone, or expose this repo's skills inside your dev clone. Idempotent.
---

# link-claude-corpus

Use this when you **already have a PostgreSQL dev clone somewhere** (e.g. you've
been hacking on PG in `/Users/foo/work/postgres-dev/` for years) and you want to
plug pg-claude into it instead of cloning a separate `postgresql-dev/` sibling.

Skip this command if you have no PG clone yet — use `/init-pg-dev` instead.

## What this command does

Interactively ask the user which of two wiring patterns they want, then do it.

```
┌─ Pattern A (recommended for most cases) ─────────────────────────────────┐
│  postgres-claude/dev  → symlink → <user's existing PG dev tree>           │
│                                                                          │
│  Pros: all build artifacts land inside the user's tree (no duplication). │
│        Slash commands `/setup-pg`, `/pg-start`, ... all "just work" by   │
│        targeting `dev/...` paths which resolve into the user's tree.     │
│                                                                          │
│  Cons: user must run Claude Code from this `postgres-claude/` dir to get │
│        the skills + commands. If they open Claude in their own dev tree, │
│        they don't get the corpus.                                        │
└──────────────────────────────────────────────────────────────────────────┘

┌─ Pattern B (for users who live in their own tree) ───────────────────────┐
│  <user's PG dev tree>/.claude → symlink → postgres-claude/.claude         │
│  <user's PG dev tree>/CLAUDE.md → symlink → postgres-claude/CLAUDE.md     │
│                                                                          │
│  Pros: open Claude Code anywhere inside the user's dev tree and the full │
│        skills + commands + agents are available, transparently.          │
│                                                                          │
│  Cons: knowledge/ corpus uses `source/...` cites that won't resolve from │
│        the user's tree (they'd need a `source -> .` self-symlink, which  │
│        this command can set up if requested).                            │
└──────────────────────────────────────────────────────────────────────────┘

┌─ Pattern C (both) ───────────────────────────────────────────────────────┐
│  Combine A + B: postgres-claude/dev → user-tree, AND user-tree/.claude → │
│  postgres-claude/.claude. The most "everything works everywhere" choice. │
└──────────────────────────────────────────────────────────────────────────┘
```

## Steps

### Step 1 — Find the user's existing PG tree

Ask the user for the absolute path. Sanity-check:

```bash
test -d "$USER_PG/.git" || die "Not a git repo: $USER_PG"
test -f "$USER_PG/src/backend/storage/buffer/README" || \
  die "Doesn't look like a PG checkout (no storage/buffer/README): $USER_PG"
git -C "$USER_PG" log -1 --format='%H %s'
```

Show the commit so the user can confirm it's the right tree.

### Step 2 — Ask which pattern

Use `AskUserQuestion` to present A / B / C. Default suggestion: **C** (both),
since it has the lowest "wait, I forgot a step" surface area. Explain trade-offs
in 1 sentence each. Don't ask if it's already obvious from context — if the user
typed `/link-claude-corpus dev` with the path, assume Pattern A.

### Step 3a — Pattern A wiring (postgres-claude/dev → user's tree)

If `postgres-claude/dev` already exists and is a symlink elsewhere:
- Show the user what it currently points at.
- Ask before overwriting.

```bash
cd /Users/matej/Work/postgres/postgres-claude  # this dir
if [ -L dev ]; then
  CURRENT=$(readlink dev)
  echo "dev currently points at: $CURRENT"
  echo "About to repoint at: $USER_PG"
  echo "OK? (yes/no)"
  # if yes:
  rm dev
fi
[ -e dev ] && die "dev exists and is not a symlink: refusing"
ln -s "$USER_PG" dev
ls -la dev
```

Also add the standard local-exclude entries inside `$USER_PG/.git/info/exclude`
so meta files never leak into a patch:

```bash
grep -qxF '.claude/' "$USER_PG/.git/info/exclude" || cat >> "$USER_PG/.git/info/exclude" <<'EOF'

# pg-claude meta repo artifacts — never commit upstream
.claude/
CLAUDE.md
build-debug/
install-debug/
data-debug/
EOF
```

### Step 3b — Pattern B wiring (user's tree gains a .claude/ symlink)

If `$USER_PG/.claude` already exists, ask the user what it is — could be from a
different Claude config, in which case we should NOT overwrite.

```bash
if [ -e "$USER_PG/.claude" ]; then
  echo "$USER_PG/.claude already exists."
  ls -la "$USER_PG/.claude"
  echo "Refusing to overwrite. Move or rename it first if you want pg-claude here."
  exit 1
fi
ln -s /Users/matej/Work/postgres/postgres-claude/.claude "$USER_PG/.claude"
ln -s /Users/matej/Work/postgres/postgres-claude/CLAUDE.md "$USER_PG/CLAUDE.md"
```

Then offer to add a `source` self-symlink inside the user's tree so the
`knowledge/` corpus's `source/...` cites resolve when Claude Code is opened from
the user's tree directly:

```bash
echo "Want to make 'source -> .' inside your dev tree so knowledge/ cites resolve?"
echo "This is a self-link; it never recurses. (yes/no)"
# if yes:
[ -e "$USER_PG/source" ] || ln -s . "$USER_PG/source"
```

### Step 3c — Pattern C

Run 3a then 3b.

### Step 4 — Verify

Regardless of pattern:

```bash
# From postgres-claude/, the symlink must resolve:
ls source/src/backend/storage/buffer/README   # source link (untouched)
ls dev/src/backend/storage/buffer/README      # dev link (now → user's tree)
```

And if Pattern B/C, from inside the user's tree:

```bash
ls "$USER_PG/.claude/skills/build-and-run/SKILL.md"
ls "$USER_PG/CLAUDE.md"
```

### Step 5 — Recap

Print what was wired and what to do next:

- If A: open Claude Code in `postgres-claude/`. `/setup-pg`, `/pg-start`, ... all
  target `dev/...` which is the user's tree.
- If B: open Claude Code in `$USER_PG/`. All skills + commands available.
  Note that `/setup-pg` etc. assume the dir layout from this repo's CLAUDE.md;
  if the user's tree is configured differently (different build dir name, etc.)
  they may need to override `dev/` references in commands.
- If C: open anywhere; everything works.

Also tell the user: if they later want to undo this, just `rm` the symlinks.
Nothing was modified inside their actual source tree besides the
`.git/info/exclude` append, which is local-only.

## Troubleshooting

- **`ln: dev: File exists`** — `postgres-claude/dev` was already a real dir, not
  a symlink. Investigate before deleting — it may contain a half-cloned tree
  with uncommitted work. Show contents to the user and ask.
- **`readlink: illegal option -- f`** on macOS — use `readlink dev` (no `-f`).
  POSIX `readlink` is enough for what we need here.
- **User's tree is a worktree of another repo** — Pattern A still works (you're
  just symlinking to it). Pattern B works too but the `.claude/` symlink will
  be visible across all worktrees of that repo, which is usually what you want
  but worth flagging.
- **Mixed-mode confusion** — if the user does Pattern A then later does
  Pattern B too, that's just Pattern C; nothing breaks.
