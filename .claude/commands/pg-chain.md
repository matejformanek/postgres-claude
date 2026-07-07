---
description: Query the pg-claude knowledge graph — walk from a scenario / idiom / file / keyword to its neighborhood (adjacent scenarios, invoked idioms, call-site files, subsystem ownership, analogous past features). Uses `scripts/corpus-chain.py`.
argument-hint: --scenario <slug> | --idiom <slug> | --file <src-path> | --keywords "..."
---

Invoke the `corpus-chain` skill.

The user's args come after `/pg-chain`. Route as:

- If args start with `--scenario`, `--idiom`, `--file`, `--keywords`: pass through to `scripts/corpus-chain.py`.
- Otherwise: treat the whole thing as keywords.

Steps:

1. **Run the query.** Use the Bash tool:
   ```
   python3 scripts/corpus-chain.py <args>
   ```
   or
   ```
   python3 scripts/corpus-chain.py --keywords "<the user's text>"
   ```

2. **Read the output.** It's a markdown chain map — files, idioms, adjacent scenarios, subsystems, past features.

3. **Summarize for the user.** Don't paste the whole markdown output — extract the 3-5 most useful nodes and explain what each one means for their task:
   - "This scenario's file table gives you 16 initial files to plan for."
   - "The `wal-record-construction` idiom is the pattern you'll follow — see its call sites at `xloginsert.c:...`."
   - "Past feature `jsonpath_leak` in `planning/jsonpath_leak/` did something similar; the comparison.md is worth reading."

4. **Suggest the next graph move.** If the user landed on a scenario, offer to re-run `--idiom <top-idiom>` next. If on an idiom, offer `--file <top-callsite>`. Keep the walk moving.

Refresh order if the graph feels stale:

```
python3 scripts/populate-idiom-callsites.py
python3 scripts/build-scenario-idiom-matrix.py
```

Then re-query.

See `.claude/skills/corpus-chain/SKILL.md` for the full method.
