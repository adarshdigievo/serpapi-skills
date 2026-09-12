---
name: serpapi-web-search
description: Search for structured web results, citations, local businesses, flights, hotels, shopping prices, jobs, and other current data through SerpApi's 100+ engines. Use google_light for general web searches. Consult serpapi-setup for first use or failed requests.
license: MIT
---

## Access

For first use or a failed SerpApi request, load [serpapi-setup](../serpapi-setup/SKILL.md). If the sibling link is unavailable, discover the installed skill by name. Reuse the route it verified: MCP, CLI, or raw cURL. An example for another route is not a reason to install or switch tools.

For MCP, use the discovered schema. To discover engine-specific requirements, read `serpapi://engines/<engine>` if that resource is exposed; otherwise follow the engine's official documentation link in the [catalog](references/engines.md).

For CLI and cURL, translate the same engine parameters using the [CLI](../serpapi-setup/references/cli.md) or [cURL](../serpapi-setup/references/curl.md) guide. Keep credentials in the source selected during setup.

## Engine selection

Prefer `_light` variants when you need a faster, smaller response.

| Intent | Engine | Result key | Key fields |
|---|---|---|---|
| General web (default) | `google_light` | `organic_results` | `.title`, `.link`, `.snippet` |
| Knowledge graph / featured snippets | `google` | `knowledge_graph`, `answer_box` | Top-level sections; fields vary by query. |
| News | `google_news_light` | `news_results` | `.title`, `.link`, `.date` |
| Images | `google_images_light` | `images_results` | `.original`, `.thumbnail` |
| Shopping / prices | `google_shopping_light` | `shopping_results` | `.title`, `.price`, `.source` |
| Academic papers | `google_scholar` | `organic_results` | `.title`, `.inline_links.cited_by.total` |
| Local businesses (list) | `google_maps` | `local_results` | `.title`, `.phone`, `.address`, `.rating`, `.reviews` |
| Local business (single) | `google_maps` | `place_results` | `.title`, `.phone`, `.address`, `.rating`, `.reviews` |
| Place reviews | `google_maps_reviews` | `reviews` | `.rating`, `.snippet`, `.date` |
| Video | `youtube` | `video_results` | `.title`, `.link`, `.views`, `.length` |
| Stock / ticker | `google_finance` | `summary` | `.price`, `.exchange`, `.currency` |
| Flights | `google_flights` | `best_flights`, `other_flights` | `.flights[].airline`, `.price`, `.total_duration` |
| Hotels | `google_hotels` | `properties` | `.name`, `.rate_per_night.extracted_lowest`, `.total_rate.extracted_lowest`, `.overall_rating` |
| Jobs | `google_jobs` | `jobs_results` | `.title`, `.company_name`, `.location` |
| App Store (iOS) | `apple_app_store` | `organic_results` | `.title`, `.rating[0].rating`, `.rating[0].count`, `.developer.name` |
| Alternative web | `bing`, `duckduckgo` | `organic_results` | `.title`, `.link`, `.snippet` |
| SerpApi's own index (preview) | `search_index` | `organic_results` | `.title`, `.link`, `.snippet` |

Fetch [SerpApi's documentation index](https://serpapi.com/llms.txt) to discover supported engines and links to their detailed API pages. Read the selected engine's page to verify the engine name, argument names, required inputs, accepted values, and conditional requirements. Use it to correct invalid or mismatched arguments before retrying a request. The [bundled catalog](references/engines.md) provides a quick reference for specialized engines and result keys.

## Use results

Read [gotchas](references/gotchas.md) for query-name differences, output modes, time filters, pagination, and response caveats. Read [recipes](references/recipes.md) for field selection, Maps reviews, AI Overview follow-ups, Flights extraction, and bounded parallel searches.

Use complete responses when you need search IDs or pagination; compact MCP output removes those metadata sections. Capture source links, selected fields, and the search ID when available in working notes before discarding a response.

Match records to the task before citing them: verify the business/location, product, travel dates, or paper title. Empty results from an unusual query do not by themselves establish a credential failure.

## Failures

On any failure, stop repeated calls and consult [serpapi-setup](../serpapi-setup/SKILL.md) with the route, engine, sanitized error, and original task. Setup diagnoses the cause, verifies the selected route, and retries the corrected original request. Parameter errors do not require a new key or installation. Keep unresolved task failures explicit even when the setup probe succeeds.
