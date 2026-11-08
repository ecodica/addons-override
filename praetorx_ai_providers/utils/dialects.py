# Part of PraetorX. See LICENSE file for full copyright and licensing details.
"""Request dialects for endpoints Odoo's ``LLMApiService`` does not speak itself.

Odoo 19's service talks the OpenAI *Responses* API and Google's
``generateContent``. Two more dialects are needed to reach the rest of the
market:

* ``openai_chat`` — ``POST /chat/completions``: Ollama, LM Studio, vLLM,
  Mistral, OpenRouter, Groq and every other "OpenAI-compatible" server. This
  dialect has no file input, so PDFs are turned into text with Odoo's own
  indexer (``ir.attachment._index``) and images travel as ``image_url``.
* ``anthropic`` — the native Messages API (``POST /messages``): PDFs as
  ``document`` blocks, images as ``image`` blocks, JSON output enforced through
  a forced tool call, tool calling through ``tool_use`` / ``tool_result``.
  Anthropic's OpenAI compatibility layer was measured on 2026-09-07 to ignore
  both ``type: file`` and ``response_format`` — hence the native API.

Every function returns ``((responses, to_call, next_inputs), usage)`` so the
caller can hand the first part to Odoo's tool loop unchanged and the second to
the usage ledger.
"""
import base64
import json
import logging

from odoo.addons.ai.utils.ai_logging import api_call_logging

_logger = logging.getLogger(__name__)

# Name of the synthetic tool that carries structured output on Anthropic.
JSON_OUTPUT_TOOL = "praetorx_json_output"
REQUEST_TIMEOUT = 120


def _pdf_to_text(env, b64_value, max_chars):
    """Text of a base64 PDF through Odoo's own attachment indexer, or ''."""
    try:
        text = env["ir.attachment"]._index(base64.b64decode(b64_value), "application/pdf")
    except Exception:  # noqa: BLE001 — a broken PDF must not break the request
        _logger.info("AI Providers: PDF text extraction failed", exc_info=True)
        return ""
    return (text or "")[:max_chars]


def _usage_from(usage, in_key, out_key, cached_key, cached_parent=None):
    usage = usage or {}
    cached = usage.get(cached_key, 0)
    if cached_parent:
        cached = (usage.get(cached_parent) or {}).get(cached_key, 0)
    return {
        "input_tokens": usage.get(in_key, 0) or 0,
        "output_tokens": usage.get(out_key, 0) or 0,
        "cached_tokens": cached or 0,
    }


# --------------------------------------------------------------------------
# openai_chat
# --------------------------------------------------------------------------

def request_openai_chat(
    service, llm_model, system_prompts, user_prompts, tools=None,
    files=None, schema=None, temperature=0.2, inputs=(), web_grounding=False,
):
    endpoint = service.endpoint
    messages = []
    if system_prompts:
        messages.append({"role": "system", "content": "\n\n".join(system_prompts)})

    content = [{"type": "text", "text": prompt} for prompt in user_prompts]
    for file in files or ():
        mimetype = file["mimetype"]
        if mimetype == "text/plain":
            content.append({"type": "text", "text": file["value"]})
        elif mimetype.startswith("image/"):
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mimetype};base64,{file['value']}"},
            })
        elif mimetype == "application/pdf":
            text = _pdf_to_text(service.env, file["value"], endpoint.max_text_chars)
            content.append({
                "type": "text",
                "text": f"[Attached PDF, extracted text]\n{text}" if text
                else "[Attached PDF: no extractable text layer]",
            })
    messages.append({"role": "user", "content": content})
    messages.extend(inputs or ())

    body = {"model": llm_model, "messages": messages, "temperature": temperature}
    if schema:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "json_schema", "schema": schema, "strict": True},
        }
    if tools:
        body["tools"] = [{
            "type": "function",
            "function": {"name": name, "description": description, "parameters": parameters},
        } for name, (description, __, __, parameters) in tools.items()]
        body["tool_choice"] = "auto"
    if web_grounding:
        _logger.debug("AI Providers: web grounding is not available on %s, ignored", endpoint.code)

    with api_call_logging(messages, tools) as record_response:
        llm_response = service._request(
            method="post", endpoint="/chat/completions",
            headers=service._get_base_headers(), body=body, timeout=REQUEST_TIMEOUT,
        )
        message = ((llm_response.get("choices") or [{}])[0]).get("message") or {}
        response, to_call, next_inputs = [], [], list(inputs or ())
        if message.get("tool_calls"):
            next_inputs.append({
                "role": "assistant",
                "content": message.get("content") or None,
                "tool_calls": message["tool_calls"],
            })
            for call in message["tool_calls"]:
                function = call.get("function") or {}
                try:
                    arguments = json.loads(function.get("arguments") or "{}")
                except json.JSONDecodeError:
                    _logger.error("AI Providers: malformed tool arguments: %s", call)
                    continue
                to_call.append((function.get("name", ""), call.get("id"), arguments))
        elif message.get("content"):
            response.append(message["content"])
        usage = _usage_from(
            llm_response.get("usage"), "prompt_tokens", "completion_tokens",
            "cached_tokens", cached_parent="prompt_tokens_details",
        )
        if record_response:
            record_response(to_call, response, usage)
    return (response, to_call, next_inputs), usage


# --------------------------------------------------------------------------
# anthropic
# --------------------------------------------------------------------------

def _as_blocks(content):
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return list(content or ())


def _merge_consecutive_roles(messages):
    """Anthropic requires strictly alternating roles; Odoo's tool loop appends
    one ``tool_result`` message per call. Merge neighbours of the same role."""
    merged = []
    for message in messages:
        if merged and merged[-1]["role"] == message["role"]:
            merged[-1]["content"] = _as_blocks(merged[-1]["content"]) + _as_blocks(message["content"])
        else:
            merged.append({"role": message["role"], "content": _as_blocks(message["content"])})
    return merged


def request_anthropic(
    service, llm_model, system_prompts, user_prompts, tools=None,
    files=None, schema=None, temperature=0.2, inputs=(), web_grounding=False,
):
    endpoint = service.endpoint
    content = [{"type": "text", "text": prompt} for prompt in user_prompts]
    for file in files or ():
        mimetype = file["mimetype"]
        if mimetype == "text/plain":
            content.append({"type": "text", "text": file["value"]})
        elif mimetype.startswith("image/"):
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": mimetype, "data": file["value"]},
            })
        elif mimetype == "application/pdf":
            content.append({
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": file["value"]},
            })
    messages = _merge_consecutive_roles([{"role": "user", "content": content}, *(inputs or ())])

    model = endpoint._model_record(llm_model)
    body = {
        "model": llm_model,
        "max_tokens": model.max_output_tokens or 4096,
        "messages": messages,
        # Anthropic accepts 0..1 only; Odoo callers use 0.2 by default.
        "temperature": min(max(temperature, 0.0), 1.0),
    }
    if system_prompts:
        body["system"] = "\n\n".join(system_prompts)

    anthropic_tools = [{
        "name": name, "description": description, "input_schema": parameters,
    } for name, (description, __, __, parameters) in (tools or {}).items()]
    if schema:
        # Structured output as a forced tool call: the API validates the input
        # against the schema, and the answer arrives as a parsed object.
        anthropic_tools.append({
            "name": JSON_OUTPUT_TOOL,
            "description": "Return the final answer as JSON matching the schema exactly.",
            "input_schema": schema,
        })
        body["tool_choice"] = {"type": "any"} if tools else {"type": "tool", "name": JSON_OUTPUT_TOOL}
    if anthropic_tools:
        body["tools"] = anthropic_tools
    if web_grounding:
        _logger.debug("AI Providers: web grounding is not available on %s, ignored", endpoint.code)

    with api_call_logging(messages, tools) as record_response:
        llm_response = service._request(
            method="post", endpoint="/messages",
            headers=service._get_base_headers(), body=body, timeout=REQUEST_TIMEOUT,
        )
        blocks = llm_response.get("content") or []
        response, to_call, next_inputs = [], [], list(inputs or ())
        for block in blocks:
            if block.get("type") == "text" and block.get("text"):
                response.append(block["text"])
            elif block.get("type") == "tool_use":
                if block.get("name") == JSON_OUTPUT_TOOL:
                    response.append(json.dumps(block.get("input") or {}))
                else:
                    to_call.append((block.get("name", ""), block.get("id"), block.get("input") or {}))
        if to_call:
            # Text that came with a tool call is not an answer yet.
            response = []
            next_inputs.append({"role": "assistant", "content": blocks})
        usage = _usage_from(
            llm_response.get("usage"), "input_tokens", "output_tokens", "cache_read_input_tokens",
        )
        if record_response:
            record_response(to_call, response, usage)
    return (response, to_call, next_inputs), usage


def tool_call_response(dialect, tool_call_id, return_value):
    """Message that feeds a tool result back, in the endpoint's dialect."""
    if dialect == "openai_chat":
        return {"role": "tool", "tool_call_id": tool_call_id, "content": str(return_value)}
    if dialect == "anthropic":
        return {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_call_id, "content": str(return_value)}],
        }
    # openai_responses — Odoo's own shape
    return {"type": "function_call_output", "call_id": tool_call_id, "output": str(return_value)}
