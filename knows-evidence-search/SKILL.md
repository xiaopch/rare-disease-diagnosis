---
name: knows-evidence-search
description: Search public KnowS medical evidence APIs for English papers, Chinese papers, meetings, guidelines, trials, and package inserts. Use when Codex needs to run source-specific evidence searches, call KnowS OpenAPI with the default API root or an optional KNOWS_BASE_URL override, use an optional KNOWS_API_KEY for higher limits, explain returned question_id and evidences, or check the skill release version.
---

# KnowS Evidence Search

Use this skill to call the public KnowS evidence search APIs.

## Quick Start

1. Identify the evidence source the user wants: `paper_en`, `paper_cn`, `meeting`, `guide`, `trial`, or `package_insert`.
2. Use the default API root `https://api.nullht.com/v1`. If `KNOWS_BASE_URL` is set, use it as an override.
3. Use `KNOWS_API_KEY` when present. If it is missing, call anonymously and let the gateway map the request to the public anonymous tier.
4. Run `scripts/search.js` from this skill directory with `--source` and `--query`.
5. Explain the response using `question_id`, `evidences`, and any additional fields returned by the API.

Do not require `KNOWS_BASE_URL` or `KNOWS_API_KEY`. Use the default API root when `KNOWS_BASE_URL` is not set, and call anonymously when `KNOWS_API_KEY` is not set.

If the user asks to search more than one source, the AI client should call `scripts/search.js` once per source and run those calls serially. Avoid parallel multi-source requests because the OpenAPI gateway may return HTTP 429 rate-limit errors when several source searches arrive at once.

Search responses are passed through as returned by the API. Do not drop unknown fields or coerce the response into a fixed model; preserve additional fields when summarizing or handing results to the user.

## Script Usage

```bash
node /absolute/path/to/knows-evidence-search/scripts/search.js \
  --source paper_en \
  --query "What evidence supports NPM1 mutation as a therapeutic predictor in MDS?"
```

For multiple sources, run separate single-source calls serially:

```bash
node /absolute/path/to/knows-evidence-search/scripts/search.js \
  --source paper_en \
  --query "What evidence supports NPM1 mutation as a therapeutic predictor in MDS?"

node /absolute/path/to/knows-evidence-search/scripts/search.js \
  --source paper_cn \
  --query "What evidence supports NPM1 mutation as a therapeutic predictor in MDS?"

node /absolute/path/to/knows-evidence-search/scripts/search.js \
  --source meeting \
  --query "What evidence supports NPM1 mutation as a therapeutic predictor in MDS?"
```

Check the latest public release:

```bash
node /absolute/path/to/knows-evidence-search/scripts/check-version.js
```

Evidence detail lookup is not available in v1.0.0:

```bash
node /absolute/path/to/knows-evidence-search/scripts/detail.js --evidence-id "<id>"
```

## Source Mapping

- `paper_en`: `POST /evidences/ai_search_paper_en`
- `paper_cn`: `POST /evidences/ai_search_paper_cn`
- `meeting`: `POST /evidences/ai_search_meeting`
- `guide`: `POST /evidences/ai_search_guide`
- `trial`: `POST /evidences/ai_search_trial`
- `package_insert`: `POST /evidences/ai_search_package_insert`

Read `references/evidence-search-api.md` for response field guidance.

## Access and Rate Limits

- Without `KNOWS_API_KEY`, each site or IP address can send up to 3 requests per second to KnowS OpenAPI. Requests above this threshold receive a rate-limit error.
- With `KNOWS_API_KEY`, each site can send up to 10 requests per second by default.
- Rate limits may be adjusted dynamically based on current resource usage.
- Higher limits are available by request. Email `knowssupport@nullht.cn`, or log in at `https://www.medknows.com` and contact the service assistant.
