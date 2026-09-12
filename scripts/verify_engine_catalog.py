#!/usr/bin/env python3
"""Check catalog coverage, request examples, and structured response paths."""

from __future__ import annotations

import ast
import concurrent.futures
import datetime as dt
import functools
import json
import re
import shlex
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from doc_contracts import DOCUMENTS, ROOT, SKILL_ROOT, code_blocks, inline_code, json_samples, load_yaml, matching_paths, response_paths, section, table_rows

CATALOG_PATH = SKILL_ROOT / "references/engines.md"
SKILL_PATH = SKILL_ROOT / "SKILL.md"
RESPONSE_PATH = CATALOG_PATH
LLMS_URL = "https://serpapi.com/llms.txt"
DOC_URL_RE = re.compile(r"\((https://serpapi\.com/[a-z0-9-]+\.md)\)")
ENGINE_RE = re.compile(r"\bengine[\"']?\s*[=:]\s*[\"']?([a-z0-9_]+)")
NESTED_ENGINE_DOCS = {
    "google_about_this_result": "https://serpapi.com/google-about-this-result",
    "google_ads_transparency_center_ad_details": "https://serpapi.com/google-ads-transparency-center-ad-details",
    "google_jobs_listing": "https://serpapi.com/google-jobs-listing-api",
    "google_maps_photo_meta": "https://serpapi.com/google-maps-photo-meta-api",
    "google_scholar_cite": "https://serpapi.com/google-scholar-cite-api",
    "google_shopping_filters": "https://serpapi.com/google-shopping-filters-api",
    "google_trends_news": "https://serpapi.com/google-trends-news",
    "walmart_product_sellers": "https://serpapi.com/walmart-product-sellers-api",
}
EXTRA_RESPONSE_DOCS = {
    "google": ("https://serpapi.com/direct-answer-box-api",),
    "google_maps": ("https://serpapi.com/maps-place-results",),
}


@functools.lru_cache(maxsize=None)
def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "serpapi-skills-check/2"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


@dataclass
class EngineDoc:
    name: str
    url: str
    descriptions: dict[str, str]
    required: set[str]
    text: str
    paths: set[str] = field(default_factory=set)

    @property
    def supported(self) -> set[str]:
        return set(self.descriptions)


def parse_engine_doc(url: str, text: str, engine: str | None = None) -> EngineDoc:
    descriptions = {}
    required = set()
    if url.endswith(".md"):
        meta = load_yaml(text.split("---", 2)[1])
        engine = meta["engine"]
        for _, cells in table_rows(section(text, "## API Parameters")):
            if cells[0] == "Parameter":
                continue
            if len(cells) < 3 or not re.fullmatch(r"\x60[A-Za-z_][A-Za-z0-9_]*\x60", cells[0]):
                raise ValueError(f"unparsed parameter row in {url}: {cells}")
            name = cells[0].strip(chr(96))
            if name in descriptions:
                raise ValueError(f"duplicate parameter {name} in {url}")
            descriptions[name] = "|".join(cells[2:])
            if "Yes" in cells[1]:
                required.add(name)
    else:
        soup = BeautifulSoup(text, "html.parser")
        if f"engine={engine}" not in text:
            raise ValueError(f"missing engine identifier in {url}")
        for node in soup.select("p.param-name"):
            name = node.get_text(strip=True)
            parent = node.parent
            descriptions[name] = parent.get_text(" ", strip=True)
            marker = parent.select_one(".param-req")
            if marker and marker.get_text(strip=True) == "Required":
                required.add(name)
    if not engine or not {"engine", "api_key"} <= set(descriptions):
        raise ValueError(f"incomplete parameter schema in {url}")
    paths = set().union(*(response_paths(sample) for sample in json_samples(text)))
    return EngineDoc(engine, url, descriptions, required, text, paths)


def load_engine_docs(errors: list[str] | None = None) -> dict[str, EngineDoc]:
    failures: list[str] = []
    urls = sorted(set(DOC_URL_RE.findall(section(fetch(LLMS_URL), "## API Documentation"))))
    if not urls:
        raise ValueError("llms.txt contains no API Markdown links")
    def read(url: str, engine: str | None = None) -> EngineDoc | None:
        try:
            return parse_engine_doc(url, fetch(url), engine)
        except Exception as error:
            failures.append(f"{url}: {error}")
            return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        docs = list(executor.map(read, urls))
    by_engine = {}
    for doc in docs:
        if doc is None:
            continue
        if doc.name in by_engine:
            failures.append(f"duplicate canonical docs for {doc.name}")
            continue
        by_engine[doc.name] = doc
    for engine, url in NESTED_ENGINE_DOCS.items():
        if engine not in by_engine:
            doc = read(url, engine)
            if doc is not None:
                by_engine[engine] = doc
    if errors is not None:
        errors.extend(failures)
    elif failures:
        raise ValueError("Incomplete engine documentation: " + "; ".join(sorted(failures)))
    return by_engine


def parse_catalog(text: str) -> tuple[dict[str, tuple[str, set[str]]], list[str]]:
    text = text.split("## Result Key by Engine", 1)[0]
    rows, errors, counts = {}, [], {}
    section_name = ""
    for number, line in enumerate(text.splitlines(), 1):
        heading = re.fullmatch(r"## (.+) \((\d+) engines?\)", line)
        if heading:
            section_name = heading[1]
            counts[section_name] = [int(heading[2]), 0]
        if not line.startswith("|") or line.startswith(("| Engine |", "|---")):
            continue
        cells = line.split("|")[1:-1]
        if len(cells) != 3 or not all(cell.strip() for cell in cells):
            errors.append(f"line {number}: malformed catalog row")
            continue
        match = re.fullmatch(r"\s*\[\x60?([a-z0-9_]+)\x60?\]\((https://serpapi\.com/[a-z0-9.-]+)\)\s*", cells[0])
        if not match:
            errors.append(f"line {number}: engine must link to its canonical docs")
            continue
        engine, url = match.groups()
        if engine in rows:
            errors.append(f"duplicate catalog engine: {engine}")
        rows[engine] = (url, set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", cells[2])))
        if not section_name:
            errors.append(f"line {number}: engine outside a counted section")
        else:
            counts[section_name][1] += 1
    count = re.search(r"Complete list of (\d+) SerpApi search engines", text)
    if not count or int(count[1]) != len(rows):
        errors.append(f"catalog header count does not match {len(rows)} parsed engines")
    errors.extend(f"{name}: declares {declared}, parsed {actual}" for name, (declared, actual) in counts.items() if declared != actual)
    return rows, errors


@dataclass
class Invocation:
    params: dict[str, str | None]
    origin: str


def shell_invocations(source: str, origin: str) -> list[Invocation]:
    # Preserve command boundaries, including newlines, before tokenizing words.
    source = source.replace("\\\n", " ")
    calls = []
    for line in source.splitlines():
        lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        tokens = list(lexer)
        for index, token in enumerate(tokens):
            is_cli = token == "serpapi" and tokens[index + 1:index + 2] == ["search"]
            if not is_cli and token != "curl":
                continue
            params = {}
            following = iter(tokens[index + (2 if is_cli else 1):])
            for arg in following:
                if arg in {";", "&", "&&", "|", "||", "(", ")"}:
                    break
                if arg in {"--jq", "--fields", "--max-pages", "--api-key"}:
                    value = next(following, None)
                    if value is None:
                        raise ValueError(f"{origin}: missing value for {arg}")
                    if arg == "--fields":
                        params["json_restrictor"] = value
                    continue
                if not is_cli and arg.startswith("https://serpapi.com/search"):
                    params.update(dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(arg).query)))
                if re.match(r"[A-Za-z_][A-Za-z0-9_]*=", arg):
                    key, value = arg.split("=", 1)
                    params[key] = value
            if params:
                calls.append(Invocation(params, origin))
    return calls


def python_invocations(source: str, origin: str) -> list[Invocation]:
    calls = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Dict):
            continue
        params = {}
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                params[key.value] = str(value.value) if isinstance(value, ast.Constant) else None
        if "engine" in params:
            calls.append(Invocation(params, origin))
    return calls


def document_invocations(path, text: str, engines: set[str]) -> list[Invocation]:
    calls = []
    for block in code_blocks(text):
        origin = f"{path.relative_to(ROOT)}:{block.line}"
        if block.language in {"bash", "sh"}:
            calls.extend(shell_invocations(block.source, origin))
        elif block.language == "python" or (not block.language and block.source.startswith("search(params=")):
            calls.extend(python_invocations(block.source, origin))
        elif block.language == "json":
            value = json.loads(block.source)
            if isinstance(value, dict) and "engine" in value:
                calls.append(Invocation({key: str(item).lower() if isinstance(item, bool) else str(item) for key, item in value.items()}, origin))
    for fragment in inline_code(text):
        origin = str(path.relative_to(ROOT)) + " (inline)"
        if fragment.startswith(("serpapi search ", "curl ")):
            calls.extend(shell_invocations(fragment, origin))
        elif fragment.split(" ", 1)[0] in engines and "=" in fragment:
            calls.extend(shell_invocations("serpapi search engine=" + fragment, origin))
    return calls


def document_engine_references(text: str) -> set[str]:
    references = set(ENGINE_RE.findall(text))
    columns = []
    for _, cells in table_rows(text):
        headers = [index for index, cell in enumerate(cells) if cell in {"Engine", "Engine Category", "Primary Engine", "Secondary Engines"}]
        if headers:
            columns = headers
        elif cells[0] in {"Parameter", "Param", "Code"}:
            columns = []
        else:
            for index in columns:
                if index < len(cells):
                    references.update(value for value in inline_code(cells[index]) if re.fullmatch(r"[a-z0-9_]+", value))
    return references


def dynamic(value: str | None) -> bool:
    return value is None or bool(re.search(r"\$|<|\.\.\.|YYYY-MM-DD", value)) or value in {"X", "Y"}


def validate_invocation(call: Invocation, docs: dict[str, EngineDoc]) -> list[str]:
    if "engine" not in call.params:
        return ["request must specify an engine"]
    engine = call.params.get("engine")
    if dynamic(engine):
        return []
    if engine not in docs:
        return [f"unknown engine {engine}"]
    doc, params, errors = docs[engine], call.params, []
    allowed = doc.supported | {"api_key"}
    if engine == "google_light":
        allowed.add("as_qdr")  # Covered by the live value-echo check.
    errors.extend(f"unsupported {engine} parameter {key}" for key in sorted(set(params) - allowed))
    required = doc.required - {"engine", "api_key"}
    errors.extend(f"{engine} requires {key}" for key in sorted(required) if key not in params or params[key] == "")
    for key, value in params.items():
        if dynamic(value):
            continue
        enum = None
        if key == "output":
            enum = {"json", "html", "md"}
        elif key in {"async", "no_cache", "zero_trace"}:
            enum = {"true", "false"}
        elif engine == "google_flights" and key == "type":
            enum = {"1", "2", "3"}
        elif engine == "google_hotels" and key == "sort_by":
            enum = {"3", "8", "13"}
        if enum and value.lower() not in enum:
            errors.append(f"invalid {engine} {key}={value}; expected {sorted(enum)}")
        if key in {"start", "num", "page", "adults"} and not re.fullmatch(r"\d+", value):
            errors.append(f"{key} must be an integer")
        if engine == "google_light" and key == "as_qdr" and not re.fullmatch(r"[dwmy](?:[1-9][0-9]*)?", value):
            errors.append(f"invalid as_qdr={value}")
        if engine == "google" and key == "tbs" and value.startswith("qdr:") and not re.fullmatch(r"qdr:[hdwmy](?:[1-9][0-9]*)?", value):
            errors.append(f"invalid tbs={value}")
        if key in {"outbound_date", "return_date", "check_in_date", "check_out_date"}:
            try:
                dt.date.fromisoformat(value)
            except ValueError:
                errors.append(f"{key} must be YYYY-MM-DD")
    if str(params.get("no_cache", "")).lower() == "true" and str(params.get("async", "")).lower() == "true":
        errors.append("no_cache=true and async=true cannot be combined")
    if engine == "google_flights" and params.get("type", "1") == "1" and not params.get("return_date"):
        errors.append("round-trip flights require return_date; use type=2 for one-way")
    if engine == "google_maps_reviews" and not any(params.get(key) for key in ("data_id", "place_id")):
        errors.append("Google Maps reviews require data_id or place_id")
    return errors


def response_claims() -> list[tuple[str, str]]:
    claims = []
    for _, cells in table_rows(section(RESPONSE_PATH.read_text(), "## Result Key by Engine")):
        if cells[0] == "Engine Category":
            continue
        if len(cells) != 2:
            raise ValueError("malformed response table row")
        engines = re.findall(r"\x60([a-z0-9_]+)\x60", cells[0])
        keys = set(re.findall(r"\x60([a-z0-9_]+)\x60", cells[1])) - {"type", "data_type"}
        claims.extend((engine, key) for engine in engines for key in keys)
    for _, cells in table_rows(section(SKILL_PATH.read_text(), "## Engine selection")):
        if cells[0] == "Intent":
            continue
        if len(cells) != 4:
            raise ValueError("malformed skill engine-selection row")
        engines = re.findall(r"\x60([a-z0-9_]+)\x60", cells[1])
        roots = re.findall(r"\x60([a-z0-9_]+)\x60", cells[2])
        fields = re.findall(r"\x60\.([^\x60]+)\x60", cells[3])
        if not engines or not roots:
            raise ValueError(f"unparsed engine/result-key row: {cells[0]}")
        claims.extend((engine, root + ("." + tail if tail else "")) for engine in engines for root in roots for tail in ["", *fields])
    return sorted(set(claims))


def check_response_claims(claims, docs, errors) -> int:
    checked = 0
    loaded_paths, failed_urls = {}, set()
    for engine, claim in claims:
        if engine not in docs:
            errors.append(f"{engine}: cannot verify response path {claim} without a loaded schema")
            continue
        doc = docs[engine]
        urls = ([doc.url.removesuffix(".md")] if doc.url.endswith(".md") else []) + list(EXTRA_RESPONSE_DOCS.get(engine, ()))
        for url in urls:
            if matching_paths(claim, doc.paths):
                break
            if url in failed_urls:
                continue
            if url not in loaded_paths:
                try:
                    loaded_paths[url] = set().union(*(response_paths(sample) for sample in json_samples(fetch(url))))
                except Exception as error:
                    failed_urls.add(url)
                    errors.append(f"response documentation unavailable ({url}): {error}")
                    continue
            doc.paths.update(loaded_paths[url])
        if matching_paths(claim, doc.paths):
            checked += 1
        elif failed_urls.intersection(urls):
            errors.append(f"{engine}: cannot verify response path {claim} because supplemental documentation is unavailable")
        else:
            checked += 1
            errors.append(f"{engine}: response path {claim} not found in structured official examples ({doc.url})")
    return checked


def main() -> int:
    try:
        catalog, errors = parse_catalog(CATALOG_PATH.read_text())
        docs = load_engine_docs(errors)
    except Exception as error:
        print(f"Catalog source/parse failure: {error}", file=sys.stderr)
        return 1
    errors.extend(f"documented engine missing from catalog: {name}" for name in sorted(set(docs) - set(catalog)))
    errors.extend(f"catalog engine without a loaded current schema: {name}" for name in sorted(set(catalog) - set(docs)))
    for engine, (url, params) in catalog.items():
        if engine not in docs:
            continue
        doc = docs[engine]
        if url != doc.url:
            errors.append(f"{engine}: canonical link should be {doc.url}")
        errors.extend(f"{engine}: unsupported catalog parameter {key}" for key in params - doc.supported)
        errors.extend(f"{engine}: catalog omits required parameter {key}" for key in doc.required - params - {"engine", "api_key"})
    calls = []
    for path in DOCUMENTS:
        try:
            text = path.read_text()
            calls.extend(document_invocations(path, text, set(docs) | set(catalog)))
            for engine in document_engine_references(text) - set(docs) - set(catalog):
                errors.append(f"{path.relative_to(ROOT)}: unknown engine {engine}")
        except Exception as error:
            errors.append(f"{path.relative_to(ROOT)}: {error}")
    checked_calls = 0
    for call in calls:
        if call.params.get("engine") in catalog and call.params["engine"] not in docs:
            errors.append(f"{call.origin}: request cannot be verified without the {call.params['engine']} schema")
            continue
        checked_calls += 1
        errors.extend(f"{call.origin}: {error}" for error in validate_invocation(call, docs))
    try:
        claims = response_claims()
    except Exception as error:
        errors.append(f"response contract parse failure: {error}")
        claims = []
    checked_claims = check_response_claims(claims, docs, errors)
    if errors:
        print("Catalog and contract checks failed:", file=sys.stderr)
        for error in sorted(set(errors)):
            print(f"- {error}", file=sys.stderr)
    print(f"Checked {len(set(catalog) & set(docs))}/{len(catalog)} catalog rows against {len(docs)} loaded engines, {checked_calls}/{len(calls)} request examples across {len(DOCUMENTS)} Markdown files, and {checked_claims}/{len(claims)} response paths.")
    print("Dynamic values and prose are not executable contracts.")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
