"""Shared document parsing and response-path checks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import json5
import yaml
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills/serpapi-web-search"
SKILL_ROOTS = [path.parent for path in sorted((ROOT / "skills").glob("*/SKILL.md"))]
DOCUMENTS = [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "CONTRIBUTING.md", *sorted((ROOT / "skills").rglob("*.md"))]
MARKDOWN = MarkdownIt("commonmark")


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def load_yaml(text: str) -> Any:
    return yaml.load(text, Loader=UniqueKeyLoader)


def validate_skill(path: Path, text: str) -> list[str]:
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.DOTALL)
    if not match:
        return ["missing or unclosed YAML frontmatter"]
    try:
        meta = load_yaml(match.group(1))
    except (yaml.YAMLError, ValueError) as error:
        return [f"invalid frontmatter: {error}"]
    if not isinstance(meta, dict):
        return ["frontmatter must be a mapping"]
    errors = []
    allowed = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
    if set(meta) - allowed:
        errors.append(f"unsupported frontmatter fields: {sorted(set(meta) - allowed)}")
    name = meta.get("name")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64:
        errors.append("name must be 1-64 lowercase letters, digits, and single hyphens")
    if name != path.parent.name:
        errors.append("name must match the skill directory")
    for field, maximum in (("description", 1024), ("compatibility", 500)):
        if field == "compatibility" and field not in meta:
            continue
        value = meta.get(field)
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
            errors.append(f"{field} must be a non-empty string of at most {maximum} characters")
    if "metadata" in meta and (not isinstance(meta["metadata"], dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in meta["metadata"].items())):
        errors.append("metadata must map strings to strings")
    for field in ("license", "allowed-tools"):
        if field in meta and not isinstance(meta[field], str):
            errors.append(f"{field} must be a string")
    if len(text.splitlines()) >= 200:
        errors.append("SKILL.md must stay under 200 lines")
    return errors


@dataclass(frozen=True)
class CodeBlock:
    language: str
    source: str
    line: int


def code_blocks(text: str) -> list[CodeBlock]:
    return [CodeBlock(token.info.split()[0].lower() if token.info else "", token.content, token.map[0] + 1) for token in MARKDOWN.parse(text) if token.type == "fence"]


def unclosed_fences(text: str) -> list[int]:
    lines = text.splitlines()
    errors = []
    for token in MARKDOWN.parse(text):
        if token.type != "fence":
            continue
        start, end = token.map
        closing = lines[end - 1].strip()
        if end - start < 2 or not re.fullmatch(re.escape(token.markup[0]) + "{" + str(len(token.markup)) + ",}", closing):
            errors.append(start + 1)
    return errors


def inline_code(text: str) -> list[str]:
    return [child.content for token in MARKDOWN.parse(text) for child in (token.children or []) if child.type == "code_inline"]


def links(text: str) -> list[str]:
    result = []
    for token in MARKDOWN.parse(text):
        for child in token.children or []:
            target = child.attrGet("href") if child.type == "link_open" else child.attrGet("src") if child.type == "image" else None
            if target:
                result.append(target)
    return result


def section(text: str, heading: str) -> str:
    return text.split(heading, 1)[1].split("\n## ", 1)[0]


def table_rows(text: str) -> list[tuple[int, list[str]]]:
    result = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if all(re.fullmatch(r":?-+:?", cell.replace(" ", "")) for cell in cells):
            continue
        result.append((number, cells))
    return result


def json_samples(text: str) -> list[Any]:
    blocks = [block.source for block in code_blocks(text) if block.language in {"json", "jsonc", "json5"}]
    if "<pre" in text:
        blocks.extend(pre.get_text() for pre in BeautifulSoup(text, "html.parser").find_all("pre"))
    samples = []
    for block in blocks:
        # Official examples sometimes elide array members with a standalone ellipsis.
        block = re.sub(r"^\s*\.\.\.,?\s*$", "", block, flags=re.MULTILINE).strip()
        if not block.startswith(("{", "[")):
            continue
        try:
            value = json5.loads(block)
        except ValueError:
            continue
        if isinstance(value, (dict, list)):
            samples.append(value)
    return samples


def response_paths(value: Any, prefix: str = "") -> set[str]:
    paths = {prefix} if prefix else set()
    if isinstance(value, dict):
        for key, child in value.items():
            paths.update(response_paths(child, f"{prefix}.{key}" if prefix else key))
    elif isinstance(value, list):
        for child in value:
            paths.update(response_paths(child, prefix + "[]"))
    return paths


def normalize_path(path: str) -> str:
    return re.sub(r"\[\d+\]", "[]", path.lstrip("."))


def matching_paths(claim: str, available: set[str]) -> bool:
    # Tables describe fields relative to either an object or an array item.
    claim = normalize_path(claim)
    if claim in available:
        return True
    root, separator, tail = claim.partition(".")
    return bool(separator and f"{root}[].{tail}" in available)
