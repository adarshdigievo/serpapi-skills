import json
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

from doc_contracts import SKILL_ROOT, code_blocks, json_samples, links, load_yaml, matching_paths, response_paths, unclosed_fences, validate_skill
from verify_doc_examples import run_syntax_check
from verify_engine_catalog import EngineDoc, Invocation, document_engine_references, parse_catalog, parse_engine_doc, python_invocations, shell_invocations, validate_invocation
import verify_live_responses as live


@pytest.fixture
def docs():
    names = {
        "google_light": ("q output no_cache async start num", {"q"}),
        "google_flights": ("departure_id arrival_id outbound_date return_date type", {"departure_id", "arrival_id", "outbound_date"}),
        "google_maps_reviews": ("data_id place_id", set()),
    }
    return {name: EngineDoc(name, "https://serpapi.com/example.md", dict.fromkeys(("engine api_key " + params).split(), "description"), required | {"engine", "api_key"}, "") for name, (params, required) in names.items()}


@pytest.mark.parametrize("params", [
    {"q": "coffee"},
    {"engine": "not_an_engine", "q": "coffee"},
    {"engine": "google_light"},
    {"engine": "google_light", "q": ""},
    {"engine": "google_light", "q": "coffee", "imaginary": "true"},
    {"engine": "google_light", "q": "coffee", "output": "markdown"},
    {"engine": "google_light", "q": "coffee", "as_qdr": "invalid"},
    {"engine": "google_light", "q": "coffee", "start": "one"},
    {"engine": "google_light", "q": "coffee", "async": "true", "no_cache": "true"},
    {"engine": "google_flights", "departure_id": "JFK", "arrival_id": "LAX", "outbound_date": "2027-01-01"},
    {"engine": "google_flights", "departure_id": "JFK", "arrival_id": "LAX", "outbound_date": "2027-02-30", "type": "2"},
    {"engine": "google_maps_reviews"},
])
def test_invalid_requests_fail(params, docs):
    assert validate_invocation(Invocation(params, "test"), docs)


@pytest.mark.parametrize("params", [
    {"engine": "google_light", "q": "coffee", "output": "md"},
    {"engine": "google_light", "q": "$QUERY", "as_qdr": "w2"},
    {"engine": "google_maps_reviews", "place_id": "$PLACE_ID"},
    {"engine": "google_flights", "departure_id": "JFK", "arrival_id": "LAX", "outbound_date": "2027-01-01", "type": "2"},
    {"engine": "google_flights", "departure_id": "JFK", "arrival_id": "LAX", "outbound_date": "2027-01-01", "return_date": "2027-01-05"},
])
def test_valid_requests_pass(params, docs):
    assert not validate_invocation(Invocation(params, "test"), docs)


def test_shell_calls_do_not_merge_across_lines_or_pipelines():
    source = """serpapi search engine=google_light \\
 q='coffee engine=fake' --jq '.organic_results | .[0]' &
serpapi search engine=google_flights departure_id=JFK arrival_id=LAX type=2 outbound_date=2027-01-01
wait
"""
    calls = shell_invocations(source, "test")
    assert len(calls) == 2
    assert calls[0].params == {"engine": "google_light", "q": "coffee engine=fake"}
    assert calls[1].params["type"] == "2"
    assert "q" not in calls[1].params


def test_curl_url_and_encoded_arguments_are_parsed():
    calls = shell_invocations('curl -G "https://serpapi.com/search.json?engine=google_light" --data-urlencode "q=coffee shop"', "test")
    assert calls[0].params == {"engine": "google_light", "q": "coffee shop"}


def test_python_request_dictionary_excludes_mcp_wrapper_and_locals():
    calls = python_invocations('search(params={"engine": "google_light", "q": query}, mode="compact")', "test")
    assert calls[0].params == {"engine": "google_light", "q": None}


def test_unknown_engines_in_mapping_tables_are_not_silently_dropped():
    text = "| Use Case | Primary Engine | Secondary Engines |\n|---|---|---|\n| Research | `google_light` | `invented_engine` |"
    assert document_engine_references(text) == {"google_light", "invented_engine"}


CATALOG = """# Engines
Complete list of 1 SerpApi search engines.
## Web (1 engine)
| Engine | Purpose | Key Parameters |
|---|---|---|
| [`google_light`](https://serpapi.com/google-light-api.md) | Search | q |
"""


def test_catalog_parses_linked_row():
    rows, errors = parse_catalog(CATALOG)
    assert not errors
    assert rows["google_light"] == ("https://serpapi.com/google-light-api.md", {"q"})


@pytest.mark.parametrize("text", [
    "", CATALOG.replace("1 SerpApi", "2 SerpApi"),
    CATALOG.replace("1 engine)", "2 engines)"),
    CATALOG.replace(" | Search | q |", " | Search |"),
    CATALOG.replace("[`google_light`](https://serpapi.com/google-light-api.md)", "`google_light`"),
    CATALOG + CATALOG.splitlines()[-1] + "\n",
])
def test_malformed_catalog_fails_closed(text):
    assert parse_catalog(text)[1]


def test_api_schema_and_structured_paths_come_from_different_sections():
    text = '''---
engine: google_light
---
## API Parameters
| Parameter | Required | Description |
|---|---|---|
| `engine` | Yes | Engine identifier |
| `api_key` | Yes | Authentication |
| `q` | Yes | The word imaginary_field in prose is not a response field. |
## Example
```json
{"organic_results": [{"title": "Coffee", "nested": {"count": 3}}]}
```
'''
    doc = parse_engine_doc("https://serpapi.com/example.md", text)
    assert doc.required == {"engine", "api_key", "q"}
    assert matching_paths("organic_results.nested.count", doc.paths)
    assert not matching_paths("organic_results.imaginary_field", doc.paths)
    with pytest.raises(ValueError):
        parse_engine_doc("https://serpapi.com/example.md", text.replace("| `q` |", "| not-code |"))


def test_nested_paths_cannot_match_a_field_under_the_wrong_parent():
    paths = response_paths({"organic_results": [{"title": "Coffee"}], "other_results": [{"count": 3}]})
    assert matching_paths("organic_results[0].title", paths)
    assert not matching_paths("organic_results.count", paths)
    assert not matching_paths("organic_results.title.count", paths)


def test_official_json_examples_allow_comments_and_elided_items():
    values = json_samples('```json\n{"results": [{"title": "Coffee"},\n...\n], /* note */}\n```')
    assert values == [{"results": [{"title": "Coffee"}]}]


def test_skill_metadata_and_duplicate_yaml():
    path = Path("/skills/example/SKILL.md")
    text = "---\nname: example\ndescription: A valid test skill.\n---\nInstructions.\n"
    assert not validate_skill(path, text)
    assert validate_skill(path, text.replace("name: example", "name: other"))
    assert validate_skill(path, text.replace("name: example", "name: example\nname: other"))
    assert validate_skill(path, text.replace("description:", "unknown_field: true\ndescription:"))
    assert validate_skill(path, text + "\n" * 200)
    with pytest.raises(ValueError, match="duplicate"):
        load_yaml("name: one\nname: two")


def test_markdown_nested_links_fences_and_inline_backticks():
    assert links("[![badge](https://example.com/badge)](LICENSE)") == ["LICENSE", "https://example.com/badge"]
    text = "Use inline ` ``` ` safely.\n\n~~~python\nprint('ok')\n~~~\n"
    assert not unclosed_fences(text)
    assert code_blocks(text)[0].source == "print('ok')\n"
    assert unclosed_fences("```python\nprint('ok')\n") == [1]


def test_valid_yaml_shell_and_python_are_syntax_checked_without_execution():
    assert not run_syntax_check("python", "import missing_package\nprint('not executed')\n")
    assert run_syntax_check("python", "def broken(:")
    assert run_syntax_check("bash", "if true; then")
    assert run_syntax_check("yaml", "key: one\nkey: two")
    assert not run_syntax_check("toml", '[mcp_servers.serpapi]\nurl="https://mcp.serpapi.com/mcp"')
    assert run_syntax_check("toml", 'key = "one"\nkey = "two"')


def test_parameter_json_recipes_are_validated(docs):
    from doc_contracts import ROOT
    from verify_engine_catalog import document_invocations
    text = '```json\n{"engine":"google_light","q":"coffee","imaginary":true}\n```'
    calls = document_invocations(ROOT / "example.md", text, set(docs))
    assert len(calls) == 1
    assert "unsupported google_light parameter imaginary" in validate_invocation(calls[0], docs)


def test_catalog_refresh_preserves_descriptions_and_mappings(docs):
    from refresh_engine_catalog import render_catalog
    source = CATALOG + '\n## Result Key by Engine\n\n| Engine Category | Result Key |\n|---|---|\n| Web (`google_light`) | `organic_results` |\n'
    catalog = render_catalog(source, {"google_light": docs["google_light"]})
    assert "| Search | q |" in catalog
    assert "Web (`google_light`)" in catalog
    rows, errors = parse_catalog(catalog)
    assert not errors
    assert rows["google_light"] == (docs["google_light"].url, {"q"})
    assert render_catalog(catalog, {"google_light": docs["google_light"]}) == catalog


@pytest.mark.parametrize("roots", [(), ("best_flights",), ("other_flights",), ("best_flights", "other_flights")])
@pytest.mark.skipif(not shutil.which("jq"), reason="jq is required for extraction checks; see AGENTS.md")
def test_actual_flight_extraction_handles_either_result_section(roots):
    blocks = code_blocks((SKILL_ROOT / "references/recipes.md").read_text())
    line = next(line for block in blocks for line in block.source.splitlines() if "engine=google_flights" in line and "--jq" in line)
    tokens = shlex.split(line)
    expression = tokens[tokens.index("--jq") + 1]
    data = {root: [{"price": 120, "flights": [{"airline": "Test Air"}]}] for root in roots}
    result = subprocess.run(["jq", expression], input=json.dumps(data), text=True, capture_output=True, check=True)
    assert json.loads(result.stdout) == [{"price": 120, "airline": "Test Air"}] * len(roots)


def test_live_flights_accept_other_flights_but_require_a_complete_group():
    check = next(check for check in live.build_checks() if check.name == "Google Flights")
    item = {"price": 120, "total_duration": 200, "flights": [{"airline": "Test Air"}]}
    assert live.validate(check, {"other_flights": [item]}) is None
    assert live.validate(check, {"best_flights": [{"price": 120}], "other_flights": [{"total_duration": 200}]})
    assert live.validate(check, {"error": "Upstream error"}) == "Upstream error"


def test_live_hotels_accept_a_later_property_with_complete_prices():
    check = next(check for check in live.build_checks() if check.name == "Google Hotels")
    unpriced = {"name": "Unavailable hotel", "overall_rating": 4.9}
    priced = {"name": "Available hotel", "overall_rating": 4.8, "rate_per_night": {"extracted_lowest": 120}, "total_rate": {"extracted_lowest": 240}}
    assert live.validate(check, {"properties": [unpriced, priced]}) is None
    assert live.validate(check, {"properties": [unpriced]})
    assert live.validate(check, {"properties": [priced], "error": "Upstream error"}) == "Upstream error"
    # Both rates and the identifying fields must belong to the same property.
    nightly_only = {key: value for key, value in priced.items() if key != "total_rate"}
    total_only = {key: value for key, value in priced.items() if key != "rate_per_night"}
    assert live.validate(check, {"properties": [nightly_only, total_only]})
    for field in ("name", "overall_rating"):
        assert live.validate(check, {"properties": [{key: value for key, value in priced.items() if key != field}]})


@pytest.mark.parametrize("properties", [None, [], {}, [None], "invalid"])
def test_live_hotels_reject_missing_or_malformed_properties(properties):
    check = next(check for check in live.build_checks() if check.name == "Google Hotels")
    assert live.validate(check, {"properties": properties})
    assert live.validate(check, {})


def test_live_expected_value_checks_equality_not_only_presence():
    check = live.Check("echo", {}, (), expected_values=(("search_parameters.as_qdr", "w"),))
    assert live.validate(check, {"search_parameters": {"as_qdr": "w"}}) is None
    assert live.validate(check, {"search_parameters": {"as_qdr": "d"}})


@pytest.mark.parametrize("raises", [False, True])
def test_live_errors_do_not_disclose_credentials(monkeypatch, raises):
    def fetch(params, key):
        if raises:
            raise RuntimeError(f"request failed: {key}")
        return {"error": f"upstream echoed {key}"}
    monkeypatch.setattr(live, "fetch", fetch)
    _, error = live.run_check(live.Check("redaction", {}, ()), "fake-key-for-test")
    assert "fake-key-for-test" not in error
    assert "[REDACTED]" in error
