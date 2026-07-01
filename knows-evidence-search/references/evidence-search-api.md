# Evidence Search API Reference

Requests use this default API root:

- `https://api.nullht.com/v1`

`KNOWS_BASE_URL` is optional and overrides the default API root when set. `KNOWS_API_KEY` is optional. When it is missing, the gateway maps the request to an anonymous public user.

The public v1.0.0 skill supports query-only evidence search.

When searching multiple sources for one user request, the AI client should send separate single-source requests serially. Parallel source searches can hit HTTP 429 at the public OpenAPI gateway.

## Sources

| Source | Endpoint | Max items |
| --- | --- | --- |
| `paper_en` | `POST /evidences/ai_search_paper_en` | 40 |
| `paper_cn` | `POST /evidences/ai_search_paper_cn` | 40 |
| `meeting` | `POST /evidences/ai_search_meeting` | 5 |
| `guide` | `POST /evidences/ai_search_guide` | 5 |
| `trial` | `POST /evidences/ai_search_trial` | 5 |
| `package_insert` | `POST /evidences/ai_search_package_insert` | 5 |

## Request

```json
{
  "query": "..."
}
```

## Response

Search responses are passed through as returned by the API. Current responses include:

```json
{
  "question_id": "...",
  "evidences": []
}
```

Evidence objects may include `id`, `title`, `metadata`, and source-specific fields such as `abstract`, `has_pdf`, `publish_date`, `journal`, `authors`, `doi`, `study_type`, and related source metadata. Preserve any additional fields returned by the API.

## Access and Rate Limits

- Anonymous access: omit `KNOWS_API_KEY`; each site or IP address can send up to 3 requests per second to KnowS OpenAPI. Requests above this threshold receive a rate-limit error.
- Dedicated API key access: set `KNOWS_API_KEY`; each site can send up to 10 requests per second by default.
- Rate limits may be adjusted dynamically based on current resource usage.
- Higher limits are available by request. Email `knowssupport@nullht.cn`, or log in at `https://www.medknows.com` and contact the service assistant.

## Detail API Status

Evidence detail lookup is not part of the public v1.0.0 OpenAPI contract. The bundled `detail.js` command reports that the detail API is not available.
