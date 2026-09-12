import pytest

import verify_engine_catalog as engines


def engine_doc(name, url, paths=()):
    return engines.EngineDoc(name, url, {"engine": "", "api_key": "", "q": ""}, {"engine", "api_key", "q"}, "", set(paths))


@pytest.mark.parametrize("failure", ["fetch", "parse"])
def test_engine_load_failure_preserves_other_engines_but_refresh_stays_strict(monkeypatch, failure):
    good_url = "https://serpapi.com/google-light-api.md"
    bad_url = "https://serpapi.com/youtube-search-api.md"
    def fetch(url):
        if url == engines.LLMS_URL:
            return f"## API Documentation\n- [Google]({good_url})\n- [YouTube]({bad_url})\n"
        if url == bad_url and failure == "fetch":
            raise OSError("page unavailable")
        return url
    def parse(url, text, engine=None):
        if url == bad_url:
            raise ValueError("parameter table changed")
        return engine_doc("google_light", url)
    monkeypatch.setattr(engines, "fetch", fetch)
    monkeypatch.setattr(engines, "parse_engine_doc", parse)
    monkeypatch.setattr(engines, "NESTED_ENGINE_DOCS", {})
    errors = []
    assert set(engines.load_engine_docs(errors)) == {"google_light"}
    assert len(errors) == 1 and bad_url in errors[0]
    with pytest.raises(ValueError, match="Incomplete engine documentation"):
        engines.load_engine_docs()


def test_failed_response_page_does_not_skip_later_claims_or_repeat_requests(monkeypatch):
    docs = {"google_light": engine_doc("google_light", "https://serpapi.com/google-light-api.md", {"organic_results"})}
    requests = []
    def fetch(url):
        requests.append(url)
        raise OSError("page unavailable")
    monkeypatch.setattr(engines, "fetch", fetch)
    errors = []
    claims = [("google_light", "missing_one"), ("google_light", "missing_two"), ("google_light", "organic_results")]
    assert engines.check_response_claims(claims, docs, errors) == 1
    assert len(requests) == 1
    assert sum("cannot verify" in error for error in errors) == 2


def test_catalog_command_reports_remaining_request_and_response_checks(monkeypatch, tmp_path, capsys):
    catalog = tmp_path / "catalog.md"
    catalog.write_text("""Complete list of 1 SerpApi search engines.
## Google (1 engine)
| Engine | Description | Required inputs |
|---|---|---|
| [`google_light`](https://serpapi.com/google-light-api.md) | Search | q |
""")
    example = tmp_path / "example.md"
    example.write_text('```json\n{"engine":"google_light","q":"coffee","unsupported":true}\n```')
    def load(errors):
        errors.append("another engine page unavailable")
        return {"google_light": engine_doc("google_light", "https://serpapi.com/google-light-api.md", {"organic_results"})}
    monkeypatch.setattr(engines, "ROOT", tmp_path)
    monkeypatch.setattr(engines, "CATALOG_PATH", catalog)
    monkeypatch.setattr(engines, "DOCUMENTS", [example])
    monkeypatch.setattr(engines, "load_engine_docs", load)
    monkeypatch.setattr(engines, "response_claims", lambda: [("google_light", "missing"), ("google_light", "organic_results")])
    def unavailable(url):
        raise OSError("supplement unavailable")
    monkeypatch.setattr(engines, "fetch", unavailable)
    assert engines.main() == 1
    output = capsys.readouterr()
    assert "another engine page unavailable" in output.err
    assert "unsupported google_light parameter unsupported" in output.err
    assert "1/1 request examples" in output.out
    assert "1/2 response paths" in output.out
