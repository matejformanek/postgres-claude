#!/usr/bin/env python3
"""Build the persona ↔ scenario/subsystem linkage.

For each persona doc under `knowledge/personas/`, extract the
source-tree paths named in the `## Domain ownership` section
(e.g. `src/backend/executor/`, `src/backend/optimizer/`).

For each such owned path:

  - Find scenarios whose §Files section touches a file under that
    path → the persona is a likely REVIEWER of a patch on that
    scenario.
  - Find subsystems whose `## Files owned` block includes any file
    under that path → the persona is a domain-expert on that
    subsystem.

Emit:

  1. Per persona: `## Scenarios I'd review` + `## Subsystems I know`
     sections (bracketed by `<!-- persona-scenarios:auto -->` /
     `<!-- persona-subsystems:auto -->` markers).
  2. Per scenario: `## Likely reviewers` section (bracketed by
     `<!-- persona-reviewers:auto -->`).
  3. Central `progress/persona-scenario-matrix.md`.

Idempotent: re-runs replace blocks between markers, same as siblings.
"""
from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from pathlib import Path


def _repo_root() -> Path:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path(__file__).resolve().parent,
            text=True,
        )
        return Path(out.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path(__file__).resolve().parent.parent


ROOT = _repo_root()
PERSONAS = ROOT / "knowledge" / "personas"
SCENARIOS = ROOT / "knowledge" / "scenarios"
SUBSYSTEMS = ROOT / "knowledge" / "subsystems"
MATRIX_OUT = ROOT / "progress" / "persona-scenario-matrix.md"

# Persona domain-path pattern:  `src/backend/executor/` or  `src/backend/executor`
# Also match `contrib/foo/` and `src/include/…`, etc.
DOMAIN_PATH = re.compile(
    r"`(?:source/)?((?:src|contrib)/[A-Za-z0-9_./+-]+?)/?`"
)

# Source paths in scenarios (both prefixed and bare forms).
SOURCE_PATH_PREFIXED = re.compile(
    r"`?source/([A-Za-z0-9_./+-]+?\.[A-Za-z0-9_+-]+)(?::\d+(?:-\d+)?)?`?"
)
SOURCE_PATH_BARE = re.compile(
    r"(?<![/\w])`?((?:src|contrib)/[A-Za-z0-9_./+-]+?\.[A-Za-z0-9_+-]+)(?::\d+(?:-\d+)?)?`?"
)


def _paths_in(text: str) -> set[str]:
    return set(SOURCE_PATH_PREFIXED.findall(text)) | set(SOURCE_PATH_BARE.findall(text))


PERSONA_SCENARIOS_BLOCK = re.compile(
    r"\n*## Scenarios I'd review\s*\n<!-- persona-scenarios:auto -->.*?<!-- /persona-scenarios:auto -->\n*",
    re.DOTALL,
)
PERSONA_SUBSYSTEMS_BLOCK = re.compile(
    r"\n*## Subsystems I know\s*\n<!-- persona-subsystems:auto -->.*?<!-- /persona-subsystems:auto -->\n*",
    re.DOTALL,
)
SCENARIO_REVIEWERS_BLOCK = re.compile(
    r"\n*## Likely reviewers\s*\n<!-- persona-reviewers:auto -->.*?<!-- /persona-reviewers:auto -->\n*",
    re.DOTALL,
)

PERSONA_INSERT_BEFORE = re.compile(
    r"\n(## (What to expect|Common reviewer|References|See also|Sources)\b[^\n]*)"
)
SCENARIO_INSERT_BEFORE = re.compile(
    r"\n(## (Related scenarios|References|Historical commits|See also|Idioms invoked)\b[^\n]*)"
)


SKIP_PERSONA_FILES = {
    "committer-map.md",
    "contributor-map.md",
    "archive-participants.md",
    "domain-ownership.md",
    "readme.md",
    "_index.md",
}


def _slug_ok(name: str) -> bool:
    return name.lower() not in SKIP_PERSONA_FILES and not name.startswith("_")


def extract_persona_domains(text: str) -> set[str]:
    """Extract source paths listed in the ## Domain ownership section."""
    # Find the ## Domain ownership section body, up to next ##.
    m = re.search(
        r"##\s*Domain ownership\s*\n(.*?)(?=\n##\s|\Z)",
        text,
        re.DOTALL,
    )
    if not m:
        return set()
    body = m.group(1)
    hits = set(DOMAIN_PATH.findall(body))
    # Normalize: strip trailing slashes, ensure no path with dot (file), only dirs.
    dirs = set()
    for h in hits:
        # If the last segment has a dot, it's a file — but for a persona domain
        # we treat any prefix as a directory the persona owns.
        h = h.strip("/")
        if h:
            dirs.add(h)
    return dirs


def path_is_under(file_path: str, prefix: str) -> bool:
    """True if `file_path` is under directory `prefix` (or is that file)."""
    file_path = file_path.strip("/")
    prefix = prefix.strip("/")
    return file_path == prefix or file_path.startswith(prefix + "/")


def load_personas() -> dict[str, dict]:
    data: dict[str, dict] = {}
    if not PERSONAS.exists():
        return data
    for p in sorted(PERSONAS.glob("*.md")):
        if not _slug_ok(p.name):
            continue
        text = p.read_text()
        m = re.search(r"^# (Persona:\s*)?(.+?)$", text, re.M)
        title = m.group(2).strip() if m else p.stem
        data[p.stem] = {
            "path": p,
            "title": title,
            "domains": extract_persona_domains(text),
        }
    return data


def load_scenarios() -> dict[str, dict]:
    data: dict[str, dict] = {}
    for p in sorted(SCENARIOS.glob("*.md")):
        if p.name.lower() in {"readme.md", "_index.md", "_template.md", "template.md"}:
            continue
        text = p.read_text()
        data[p.stem] = {
            "path": p,
            "files": _paths_in(text),
        }
    return data


def load_subsystems() -> dict[str, dict]:
    data: dict[str, dict] = {}
    for p in sorted(SUBSYSTEMS.glob("*.md")):
        if p.name.lower() in {"readme.md", "_index.md", "template.md"}:
            continue
        text = p.read_text()
        # Extract source paths from the ## Files owned block if present.
        m = re.search(
            r"## Files owned\s*\n<!-- files-owned:auto -->(.*?)<!-- /files-owned:auto -->",
            text,
            re.DOTALL,
        )
        owned = _paths_in(m.group(1)) if m else _paths_in(text)
        data[p.stem] = {
            "path": p,
            "files": owned,
        }
    return data


def render_link(target_slug: str, kind: str) -> str:
    if kind == "scenario":
        return f"[`{target_slug}`](../scenarios/{target_slug}.md)"
    if kind == "subsystem":
        return f"[`{target_slug}`](../subsystems/{target_slug}.md)"
    if kind == "persona":
        return f"[`{target_slug}`](../personas/{target_slug}.md)"
    return f"`{target_slug}`"


def build_persona_scenarios_section(scenario_map: dict[str, list[str]]) -> str:
    lines = [
        "## Scenarios I'd review",
        "<!-- persona-scenarios:auto -->",
        "",
        "*Derived from Domain-ownership paths overlapping each scenario's §Files section. If this persona claims a directory and a scenario mentions any file under it, they're a likely reviewer.*",
        "*Refresh via `scripts/build-persona-scenario-matrix.py`.*",
        "",
    ]
    if not scenario_map:
        lines.append("_(none — persona has no owned paths that overlap any scenario's files)_")
        lines.append("")
        lines.append("<!-- /persona-scenarios:auto -->")
        return "\n".join(lines) + "\n"
    lines.append("| Scenario | Via path(s) |")
    lines.append("|---|---|")
    for slug in sorted(scenario_map.keys()):
        paths = scenario_map[slug]
        preview = ", ".join(f"`{p}`" for p in paths[:2])
        if len(paths) > 2:
            preview += f" (+{len(paths)-2})"
        lines.append(f"| {render_link(slug, 'scenario')} | {preview} |")
    lines.append("")
    lines.append("<!-- /persona-scenarios:auto -->")
    return "\n".join(lines) + "\n"


def build_persona_subsystems_section(subsystem_map: dict[str, list[str]]) -> str:
    lines = [
        "## Subsystems I know",
        "<!-- persona-subsystems:auto -->",
        "",
        "*Derived from Domain-ownership paths overlapping each subsystem's `## Files owned` block.*",
        "*Refresh via `scripts/build-persona-scenario-matrix.py`.*",
        "",
    ]
    if not subsystem_map:
        lines.append("_(none)_")
        lines.append("")
        lines.append("<!-- /persona-subsystems:auto -->")
        return "\n".join(lines) + "\n"
    for slug in sorted(subsystem_map.keys()):
        lines.append(f"- {render_link(slug, 'subsystem')}")
    lines.append("")
    lines.append("<!-- /persona-subsystems:auto -->")
    return "\n".join(lines) + "\n"


def build_scenario_reviewers_section(persona_map: dict[str, list[str]]) -> str:
    lines = [
        "## Likely reviewers",
        "<!-- persona-reviewers:auto -->",
        "",
        "*Personas whose Domain-ownership paths overlap this scenario's §Files. Reflect who might catch this on hackers-list.*",
        "*Refresh via `scripts/build-persona-scenario-matrix.py`.*",
        "",
    ]
    if not persona_map:
        lines.append("_(none — no domain-ownership overlap detected)_")
        lines.append("")
        lines.append("<!-- /persona-reviewers:auto -->")
        return "\n".join(lines) + "\n"
    lines.append("| Persona | Overlapping path(s) |")
    lines.append("|---|---|")
    # Sort by strength (num paths) then name.
    ranked = sorted(persona_map.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    for slug, paths in ranked:
        preview = ", ".join(f"`{p}`" for p in paths[:2])
        if len(paths) > 2:
            preview += f" (+{len(paths)-2})"
        lines.append(f"| {render_link(slug, 'persona')} | {preview} |")
    lines.append("")
    lines.append("<!-- /persona-reviewers:auto -->")
    return "\n".join(lines) + "\n"


def upsert(text: str, section: str, block_re: re.Pattern, insert_before: re.Pattern) -> str:
    if block_re.search(text):
        return block_re.sub("\n\n" + section, text)
    m = insert_before.search(text)
    if m:
        return text[: m.start()] + "\n\n" + section + text[m.start():]
    return text.rstrip() + "\n\n" + section


def build_matrix_doc(
    personas: dict,
    scenarios: dict,
    scenario_to_personas: dict[str, dict[str, list[str]]],
    persona_to_scenarios: dict[str, dict[str, list[str]]],
    persona_to_subsystems: dict[str, dict[str, list[str]]],
) -> str:
    lines = [
        "# Persona ↔ Scenario matrix",
        "",
        "Who's likely to review a patch on each change-class. Derived from the personas' `## Domain ownership` sections + the scenarios' §Files sections + subsystems' `## Files owned` blocks.",
        "",
        "**Refresh via `scripts/build-persona-scenario-matrix.py`.**",
        "",
        "## Scenarios and their likely reviewers",
        "",
        "| Scenario | # reviewers | Top reviewers |",
        "|---|---:|---|",
    ]
    for sc in sorted(scenarios.keys()):
        pmap = scenario_to_personas.get(sc, {})
        ranked = sorted(pmap.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        top = [f"[`{p}`](../knowledge/personas/{p}.md)" for p, _ in ranked[:5]]
        more = f" +{len(ranked)-5}" if len(ranked) > 5 else ""
        lines.append(f"| [`{sc}`](../knowledge/scenarios/{sc}.md) | {len(ranked)} | {', '.join(top)}{more} |")

    lines.append("")
    lines.append("## Reverse: what each persona reviews")
    lines.append("")
    lines.append("| Persona | Scenarios | Subsystems |")
    lines.append("|---|---|---|")
    for p_slug in sorted(personas.keys()):
        scs = sorted(persona_to_scenarios.get(p_slug, {}).keys())
        subs = sorted(persona_to_subsystems.get(p_slug, {}).keys())
        sc_txt = ", ".join(f"[`{s}`](../knowledge/scenarios/{s}.md)" for s in scs[:4])
        if len(scs) > 4:
            sc_txt += f" +{len(scs)-4}"
        sub_txt = ", ".join(f"[`{s}`](../knowledge/subsystems/{s}.md)" for s in subs[:4])
        if len(subs) > 4:
            sub_txt += f" +{len(subs)-4}"
        lines.append(f"| [`{p_slug}`](../knowledge/personas/{p_slug}.md) | {sc_txt} | {sub_txt} |")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    personas = load_personas()
    scenarios = load_scenarios()
    subsystems = load_subsystems()

    print(f"Personas:  {len(personas)}")
    print(f"Scenarios: {len(scenarios)}")
    print(f"Subsystems: {len(subsystems)}")
    print()

    # scenario slug → {persona → [matching paths]}
    scenario_to_personas: dict[str, dict[str, list[str]]] = defaultdict(dict)
    # persona slug → {scenario → [matching paths]}
    persona_to_scenarios: dict[str, dict[str, list[str]]] = defaultdict(dict)
    # persona slug → {subsystem → [matching paths]}
    persona_to_subsystems: dict[str, dict[str, list[str]]] = defaultdict(dict)

    for p_slug, p_data in personas.items():
        domains = p_data["domains"]
        if not domains:
            continue
        for sc_slug, sc_data in scenarios.items():
            matching = [
                d for d in domains
                if any(path_is_under(f, d) for f in sc_data["files"])
            ]
            if matching:
                scenario_to_personas[sc_slug][p_slug] = matching
                persona_to_scenarios[p_slug][sc_slug] = matching
        for sub_slug, sub_data in subsystems.items():
            matching = [
                d for d in domains
                if any(path_is_under(f, d) for f in sub_data["files"])
            ]
            if matching:
                persona_to_subsystems[p_slug][sub_slug] = matching

    # Write per-persona sections
    updated_personas = 0
    for p_slug, p_data in personas.items():
        text = p_data["path"].read_text()
        sc_map = persona_to_scenarios.get(p_slug, {})
        sub_map = persona_to_subsystems.get(p_slug, {})
        sec1 = build_persona_scenarios_section(sc_map)
        sec2 = build_persona_subsystems_section(sub_map)
        # Insert both, scenarios first then subsystems.
        new = upsert(text, sec1, PERSONA_SCENARIOS_BLOCK, PERSONA_INSERT_BEFORE)
        new = upsert(new, sec2, PERSONA_SUBSYSTEMS_BLOCK, PERSONA_INSERT_BEFORE)
        if new != text:
            p_data["path"].write_text(new)
            updated_personas += 1

    # Write per-scenario sections
    updated_scenarios = 0
    for sc_slug, sc_data in scenarios.items():
        text = sc_data["path"].read_text()
        pmap = scenario_to_personas.get(sc_slug, {})
        section = build_scenario_reviewers_section(pmap)
        new = upsert(text, section, SCENARIO_REVIEWERS_BLOCK, SCENARIO_INSERT_BEFORE)
        if new != text:
            sc_data["path"].write_text(new)
            updated_scenarios += 1

    # Write central matrix
    MATRIX_OUT.parent.mkdir(parents=True, exist_ok=True)
    MATRIX_OUT.write_text(build_matrix_doc(personas, scenarios, scenario_to_personas, persona_to_scenarios, persona_to_subsystems))

    total_edges = sum(len(pm) for pm in scenario_to_personas.values())
    print(f"Personas updated: {updated_personas}")
    print(f"Scenarios updated: {updated_scenarios}")
    print(f"Total persona→scenario edges: {total_edges}")
    print(f"Matrix written to: {MATRIX_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
