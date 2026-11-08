# AI Providers for Odoo AI (`praetorx_ai_providers`)

Teaches Odoo 19's own AI layer (`ai`, `ai_fields`, agents, `ai_documents`) additional
providers — Anthropic Claude, any OpenAI-compatible Chat-Completions server, any
Responses-API URL — and adds usage tracking and a monthly budget per company.

Free. Depends on `ai` only. No Python dependencies beyond Odoo's.

## How it works

`odoo.addons.ai.utils.llm_api_service.LLMApiService` resolves its provider name in
`__init__` against two hard-wired names. This module wraps eight methods of that
class at import time (`utils/patch.py`) so a name is first looked up in
`ai.provider.endpoint`; when nothing matches, Odoo's original code runs. Odoo's
files are not modified on disk.

An endpoint flagged **Default for Odoo AI** answers everything Odoo issues under the
provider name `openai` — AI fields, the AI-fields cron, agents on an OpenAI model,
document auto-sort. Model names Odoo hard-codes (`gpt-4.1`) are replaced by the
endpoint's default model.

Three request dialects (`utils/dialects.py`):

| dialect | endpoint | files | schema | tools |
|---|---|---|---|---|
| `openai_responses` | Odoo's own path, custom base URL / header | `input_file`, `input_image` | `text.format json_schema` | native |
| `openai_chat` | `/chat/completions` | PDF → text via `ir.attachment._index`, images as `image_url` | `response_format json_schema` | native |
| `anthropic` | `/messages` | `document`, `image` blocks | forced tool call `praetorx_json_output` | `tool_use` / `tool_result` (consecutive results merged) |

## For module authors

```python
service, model = env["ai.provider.endpoint"]._service_for("read")   # or "choose", "embed"
answer = service.with_context(ai_caller="my_module").request_llm(model, [system], [user], files=..., schema=...)
```

`_service_for` returns Odoo's own OpenAI service when no endpoint is configured, so a
module works with or without this one. `ai_caller` in the context labels the usage line.

## Limits

- The provider registry (`llm_providers.PROVIDERS`) is process-global; in a
  multi-database process the union of all databases' endpoint names is visible.
  Requests always resolve against the current database.
- Anthropic has no embeddings endpoint.
- Web grounding (`web_search_preview`) is only passed to Responses-API endpoints
  that declare `supports_web_search`.

## Tests

31 tests, HTTP mocked at `requests.request`. Enterprise `ai` is required, so they run
locally, not on a bare GitHub runner:

```
odoo -d <db> -i praetorx_ai_providers --test-enable --test-tags /praetorx_ai_providers --stop-after-init
```
