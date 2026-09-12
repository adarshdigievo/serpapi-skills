#!/usr/bin/env python3
"""Refresh canonical links, required inputs, and engine counts from official docs."""

import argparse
import re

from verify_engine_catalog import CATALOG_PATH, load_engine_docs


def render_catalog(existing, docs):
    # Preserve curated descriptions; source-derived fields have one refresh path.
    descriptions = {}
    for line in existing.split("## Result Key by Engine", 1)[0].splitlines():
        match = re.match(r"\| \[`([a-z0-9_]+)`\]\([^)]+\) \| ([^|]+) \|", line)
        if match:
            descriptions[match[1]] = match[2].strip()
    groups = {}
    for name, doc in sorted(docs.items()):
        group = name.split("_", 1)[0].title()
        groups.setdefault(group, []).append(doc)
    lines = ["# SerpApi engine catalog", "", f"Complete list of {len(docs)} SerpApi search engines. Prefer `_light` variants for faster, smaller responses. Read the selected engine's MCP resource or linked docs for conditional requirements and optional parameters. A dash means no unconditional input besides engine and authentication.", "", "Links, required inputs, and counts are refreshed from official docs by `scripts/refresh_engine_catalog.py` in the source repository. Descriptions and result mappings are curated."]
    for group, engines in groups.items():
        lines += ["", f"## {group} ({len(engines)} engines)", "", "| Engine | Description | Required inputs |", "|---|---|---|"]
        for doc in engines:
            purpose = descriptions.get(doc.name, doc.name.replace("_", " ").capitalize())
            required = ", ".join(sorted(doc.required - {"engine", "api_key"})) or "—"
            lines.append(f"| [`{doc.name}`]({doc.url}) | {purpose} | {required} |")
    mapping = existing.split("## Result Key by Engine", 1)[1].strip()
    return "\n".join(lines) + "\n\n## Result Key by Engine\n\n" + mapping + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report drift without writing")
    args = parser.parse_args()
    existing = CATALOG_PATH.read_text()
    updated = render_catalog(existing, load_engine_docs())
    if args.check:
        if existing != updated:
            raise SystemExit("Engine index drifted; run scripts/refresh_engine_catalog.py")
        print("Engine index matches current official documentation.")
    else:
        CATALOG_PATH.write_text(updated)
        print("Refreshed engine index; curated descriptions and response mappings preserved.")


if __name__ == "__main__":
    main()
