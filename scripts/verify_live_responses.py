#!/usr/bin/env python3
"""Run live, credential-safe checks for response structures used in the docs."""

from __future__ import annotations

import concurrent.futures
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


SEARCH_URL = "https://serpapi.com/search.json"


@dataclass(frozen=True)
class Check:
    name: str
    params: dict[str, str]
    required_paths: tuple[str, ...]
    any_paths: tuple[str, ...] = ()
    max_lengths: tuple[tuple[str, int], ...] = ()
    exact_top_level_keys: tuple[str, ...] = ()
    alternative_path_groups: tuple[tuple[str, ...], ...] = ()
    expected_values: tuple[tuple[str, Any], ...] = ()
    required_item_paths: tuple[tuple[str, tuple[str, ...]], ...] = ()


def first(value: Any) -> Any:
    if not isinstance(value, list) or not value:
        raise KeyError("expected a non-empty list")
    return value[0]


def resolve(data: Any, path: str) -> Any:
    value = data
    for part in path.split("."):
        list_item = part.endswith("[]")
        key = part[:-2] if list_item else part
        if not isinstance(value, dict) or key not in value:
            raise KeyError(path)
        value = value[key]
        if list_item:
            value = first(value)
    if value is None or value == "" or value == [] or value == {}:
        raise KeyError(path)
    return value


def has_path(data: Any, path: str) -> bool:
    try:
        resolve(data, path)
    except (KeyError, TypeError):
        return False
    return True


def build_checks() -> list[Check]:
    today = dt.date.today()
    flight_date = (today + dt.timedelta(days=30)).isoformat()
    check_in = (today + dt.timedelta(days=30)).isoformat()
    check_out = (today + dt.timedelta(days=32)).isoformat()
    return [
        Check("Google Light fields", {"engine": "google_light", "q": "coffee"}, ("organic_results[].title", "organic_results[].link", "organic_results[].snippet")),
        Check("Google fields", {"engine": "google", "q": "SerpApi"}, ("organic_results[].title", "organic_results[].link", "organic_results[].snippet")),
        Check("Google Light time filter", {"engine": "google_light", "q": "AI", "as_qdr": "w"}, ("search_parameters.as_qdr", "organic_results[]"), expected_values=(("search_parameters.as_qdr", "w"),)),
        Check("Google News Light", {"engine": "google_news_light", "q": "technology"}, ("news_results[].title", "news_results[].link", "news_results[].date")),
        Check("Google Images Light", {"engine": "google_images_light", "q": "sunset"}, ("images_results[].original", "images_results[].thumbnail")),
        Check("Google Images", {"engine": "google_images", "q": "sunset"}, ("images_results[].original", "images_results[].thumbnail")),
        Check("Google Shopping Light", {"engine": "google_shopping_light", "q": "headphones"}, ("shopping_results[].title", "shopping_results[].price", "shopping_results[].source")),
        Check("Google Shopping", {"engine": "google_shopping", "q": "headphones"}, ("shopping_results[].title", "shopping_results[].price", "shopping_results[].source")),
        Check("Google Scholar citation", {"engine": "google_scholar", "q": "attention is all you need"}, ("organic_results[].inline_links.cited_by.total",)),
        Check("Google Maps place", {"engine": "google_maps", "type": "search", "q": "The French Laundry Yountville California"}, ("place_results.phone", "place_results.address", "place_results.rating", "place_results.reviews")),
        Check("Google Maps list", {"engine": "google_maps", "type": "search", "q": "coffee shops Austin Texas"}, ("local_results[].title", "local_results[].address", "local_results[].rating", "local_results[].reviews")),
        Check("Google Maps reviews", {"engine": "google_maps_reviews", "data_id": "0x89c25090129c363d:0x40c6a5770d25022b"}, ("reviews[].rating", "reviews[].snippet", "reviews[].date")),
        Check("YouTube", {"engine": "youtube", "search_query": "machine learning tutorial"}, ("video_results[].title", "video_results[].link", "video_results[].views", "video_results[].length")),
        Check("Google Finance", {"engine": "google_finance", "q": "AAPL:NASDAQ"}, ("summary.price", "summary.extracted_price", "summary.exchange", "summary.currency", "graph[]", "news_results[]")),
        Check("Google Flights", {"engine": "google_flights", "departure_id": "JFK", "arrival_id": "LAX", "outbound_date": flight_date, "type": "2"}, (), alternative_path_groups=tuple(tuple(f"{root}[].{path}" for path in ("price", "total_duration", "flights[].airline")) for root in ("best_flights", "other_flights"))),
        Check("Google Hotels", {"engine": "google_hotels", "q": "hotels in Kyoto", "check_in_date": check_in, "check_out_date": check_out, "adults": "2", "sort_by": "8"}, (), required_item_paths=(("properties", ("name", "rate_per_night.extracted_lowest", "total_rate.extracted_lowest", "overall_rating")),)),
        Check("Google Jobs", {"engine": "google_jobs", "q": "software engineer"}, ("jobs_results[].title", "jobs_results[].company_name", "jobs_results[].location")),
        Check("Apple App Store", {"engine": "apple_app_store", "term": "Notion"}, ("organic_results[].title", "organic_results[].rating[].rating", "organic_results[].rating[].count", "organic_results[].developer.name")),
        Check("Bing", {"engine": "bing", "q": "coffee"}, ("organic_results[].title", "organic_results[].link", "organic_results[].snippet")),
        Check("Bing News", {"engine": "bing_news", "q": "technology"}, ("organic_results[].title", "organic_results[].link", "organic_results[].date")),
        Check("DuckDuckGo", {"engine": "duckduckgo", "q": "coffee"}, ("organic_results[].title", "organic_results[].link", "organic_results[].snippet")),
        Check("DuckDuckGo News", {"engine": "duckduckgo_news", "q": "technology"}, ("news_results[].title", "news_results[].link", "news_results[].date")),
        Check("Amazon", {"engine": "amazon", "k": "wireless headphones"}, ("organic_results[].title",)),
        Check("Walmart", {"engine": "walmart", "query": "wireless headphones"}, ("organic_results[].title",)),
        Check("eBay", {"engine": "ebay", "_nkw": "vintage watch"}, ("organic_results[].title",)),
        Check("Google Videos Light", {"engine": "google_videos_light", "q": "coffee"}, ("video_results[].title",)),
        Check("Google Trends", {"engine": "google_trends", "q": "coffee"}, ("interest_over_time",)),
        Check("Google Sports game", {"engine": "google_sports", "kgmid": "/g/11yf4mtmkl", "sp": "ft", "type": "game"}, ("game_results",)),
        Check("Search Index", {"engine": "search_index", "q": "serpapi documentation"}, ("organic_results[].title", "organic_results[].link", "organic_results[].snippet", "organic_results[].position")),
        Check("JSON Restrictor", {"engine": "google_light", "q": "coffee", "json_restrictor": "organic_results[0:3]"}, ("organic_results[]",), max_lengths=(("organic_results", 3),), exact_top_level_keys=("organic_results",)),
    ]


def fetch(params: dict[str, str], api_key: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({**params, "api_key": api_key})
    request = urllib.request.Request(f"{SEARCH_URL}?{query}", headers={"User-Agent": "serpapi-skills-live-check/1"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            try:
                detail = json.load(error).get("error", f"HTTP {error.code}")
            except Exception:
                detail = f"HTTP {error.code}"
            if error.code not in {429, 500, 502, 503, 504} or attempt == 1:
                raise RuntimeError(detail) from None
        except (TimeoutError, urllib.error.URLError) as error:
            if attempt == 1:
                raise RuntimeError(type(error).__name__) from None
        time.sleep(2)
    raise AssertionError("retry loop exhausted")


def validate(check: Check, data: dict[str, Any]) -> str | None:
    if "error" in data:
        return str(data["error"])
    missing = [path for path in check.required_paths if not has_path(data, path)]
    if missing:
        return f"missing or empty paths: {', '.join(missing)}"
    if check.any_paths and not any(has_path(data, path) for path in check.any_paths):
        return f"none of these paths exist: {', '.join(check.any_paths)}"
    if check.alternative_path_groups and not any(all(has_path(data, path) for path in group) for group in check.alternative_path_groups):
        return "no complete alternative response group found"
    for collection, paths in check.required_item_paths:
        try:
            items = resolve(data, collection)
        except KeyError:
            return f"missing or empty collection: {collection}"
        if not isinstance(items, list) or not any(all(has_path(item, path) for path in paths) for item in items):
            return f"no item in {collection} has all required paths: {', '.join(paths)}"
    for path, expected in check.expected_values:
        if not has_path(data, path) or resolve(data, path) != expected:
            return f"unexpected value at {path}; expected {expected!r}"
    for path, maximum in check.max_lengths:
        try:
            value = resolve(data, path)
        except KeyError:
            return f"missing path: {path}"
        if not hasattr(value, "__len__") or len(value) > maximum:
            return f"{path} exceeds length {maximum}"
    if check.exact_top_level_keys and set(data) != set(check.exact_top_level_keys):
        return f"top-level keys differ: {', '.join(sorted(data))}"
    return None


def run_check(check: Check, api_key: str) -> tuple[str, str | None]:
    try:
        error = validate(check, fetch(check.params, api_key))
    except Exception as error:
        message = str(error)
    else:
        message = error
    if message:
        message = message.replace(api_key, "[REDACTED]").replace(urllib.parse.quote_plus(api_key), "[REDACTED]")
    return check.name, message


def main() -> int:
    api_key = os.environ.get("SERPAPI_KEY", "")
    if not api_key:
        print("SERPAPI_KEY is required for live response checks.", file=sys.stderr)
        return 2
    checks = build_checks()
    failures: list[tuple[str, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(run_check, check, api_key) for check in checks]
        for future in concurrent.futures.as_completed(futures):
            name, error = future.result()
            print(f"{'FAIL' if error else 'PASS'} {name}")
            if error:
                failures.append((name, error))
    if failures:
        print("\nLive response checks failed:", file=sys.stderr)
        for name, error in sorted(failures):
            print(f"- {name}: {error}", file=sys.stderr)
        return 1
    print(f"\nVerified {len(checks)} live documentation response contracts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
