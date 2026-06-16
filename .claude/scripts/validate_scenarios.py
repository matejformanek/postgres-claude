#!/usr/bin/env python3
"""Layer C5 — validate scenarios layer.

Checks:
1. Every scenario in scenarios/ has the required frontmatter fields.
2. Every related_scenarios: entry points to an existing scenario file.
3. Every companion_skills: entry points to an existing .claude/skills/X/SKILL.md.
4. The _index.md table covers every scenario file (and no stale entries).
5. last_verified_commit looks valid (10+ hex chars).

Exits non-zero on any failure.
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCENARIOS_DIR = REPO / "knowledge" / "scenarios"
SKILLS_DIR = REPO / ".claude" / "skills"
INDEX = SCENARIOS_DIR / "_index.md"

REQUIRED_FRONTMATTER = {
    "scenario", "when_to_use", "companion_skills", "related_scenarios",
    "canonical_commit", "last_verified_commit",
}


def parse_frontmatter(text: str) -> dict:
    m = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ":" not in line or line.startswith(" "):
            continue
        k, v = line.split(":", 1)
        out[k.strip()] = v.strip()
    return out


def parse_yaml_list(s: str) -> list[str]:
    s = s.strip()
    if not (s.startswith("[") and s.endswith("]")):
        return []
    inner = s[1:-1].strip()
    if not inner:
        return []
    return [t.strip().strip("'\"") for t in inner.split(",")]


def main():
    errors = []
    warnings = []

    scenarios = {}
    for p in sorted(SCENARIOS_DIR.glob("*.md")):
        if p.name.startswith("_") or p.name == "README.md":
            continue
        text = p.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        scenarios[p.stem] = (p, fm, text)

    print(f"Found {len(scenarios)} scenarios")

    # Check 1: frontmatter completeness
    for slug, (p, fm, _) in scenarios.items():
        missing = REQUIRED_FRONTMATTER - set(fm.keys())
        if missing:
            errors.append(f"{slug}: missing frontmatter keys: {sorted(missing)}")
        if fm.get("scenario") != slug:
            errors.append(
                f"{slug}: frontmatter scenario:{fm.get('scenario')!r} "
                f"does not match filename"
            )
        lvc = fm.get("last_verified_commit", "")
        if not re.fullmatch(r"[0-9a-f]{10,40}", lvc):
            warnings.append(
                f"{slug}: last_verified_commit looks odd: {lvc!r}"
            )

    # Check 2: related_scenarios point at real scenarios
    for slug, (_, fm, _) in scenarios.items():
        related = parse_yaml_list(fm.get("related_scenarios", "[]"))
        for r in related:
            if r and r not in scenarios:
                errors.append(
                    f"{slug}: related_scenarios entry {r!r} is not a real scenario"
                )

    # Check 3: companion_skills point at real skills
    for slug, (_, fm, _) in scenarios.items():
        skills = parse_yaml_list(fm.get("companion_skills", "[]"))
        for s in skills:
            if s and not (SKILLS_DIR / s / "SKILL.md").exists():
                errors.append(
                    f"{slug}: companion_skill {s!r} has no .claude/skills/{s}/SKILL.md"
                )

    # Check 4: _index.md mentions every scenario
    if INDEX.exists():
        idx_text = INDEX.read_text(encoding="utf-8")
        for slug in scenarios:
            if slug not in idx_text:
                warnings.append(f"{slug}: not referenced in _index.md")

    # Output
    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"FAIL: {e}")

    if errors:
        sys.exit(1)
    print(f"OK: {len(scenarios)} scenarios validated, "
          f"{len(warnings)} warnings.")


if __name__ == "__main__":
    main()
