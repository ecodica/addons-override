# Part of PraetorX. See LICENSE file for full copyright and licensing details.
"""Extension of ``odoo.addons.ai.utils.llm_api_service.LLMApiService``.

Odoo 19 hard-wires two providers into the service's ``__init__``. This module
resolves a provider name against ``ai.provider.endpoint`` first and only falls
back to Odoo's own code when no endpoint matches — so nothing changes for a
database without configured endpoints, and Odoo's own files stay untouched on
disk. This is the one place to re-check on every Odoo major.

Rerouting: when an endpoint is flagged *default for Odoo AI*, every request
Odoo itself issues under the provider name ``openai`` (AI fields, the AI-fields
cron, agents on an OpenAI model) is served by that endpoint instead.
"""
import logging
import os

from odoo.exceptions import UserError

from odoo.addons.ai.utils import llm_api_service as _service_module
from odoo.addons.ai.utils import llm_providers as _providers_module

from . import dialects

_logger = logging.getLogger(__name__)

LLMApiService = _service_module.LLMApiService
_ORIGINAL = {}
# Odoo's own provider tuples, kept so the registry can be rebuilt idempotently.
BASE_PROVIDERS = list(_providers_module.PROVIDERS)


def _endpoint_model(env):
    if "ai.provider.endpoint" not in env.registry:
        return None
    return env["ai.provider.endpoint"].sudo()


def _normalize_request_args(args, kwargs):
    names = (
        "llm_model", "system_prompts", "user_prompts", "tools", "files",
        "schema", "temperature", "inputs", "web_grounding",
    )
    params = dict(zip(names, args))
    params.update(kwargs)
    params.setdefault("tools", None)
    params.setdefault("files", None)
    params.setdefault("schema", None)
    params.setdefault("temperature", 0.2)
    params.setdefault("inputs", ())
    params.setdefault("web_grounding", False)
    return params


# --------------------------------------------------------------------------
# patched methods
# --------------------------------------------------------------------------

def __init__(self, env, provider="openai"):
    self.endpoint = None
    Endpoint = _endpoint_model(env)
    if Endpoint is not None:
        endpoint = Endpoint._resolve(provider)
        if endpoint:
            self.endpoint = endpoint
            self.provider = endpoint.code
            self.base_url = endpoint.base_url.rstrip("/")
            self.env = env
            return
    _ORIGINAL["__init__"](self, env, provider)


def _get_api_token(self):
    if not self.endpoint:
        return _ORIGINAL["_get_api_token"](self)
    key = self.endpoint.api_key or os.getenv(f"PRAETORX_AI_{self.endpoint.code.upper()}_KEY")
    if key:
        return key
    if self.endpoint.dialect == "openai_chat":
        # Local servers (Ollama, LM Studio) run without a key.
        return ""
    raise UserError(self.env._("No API key set for AI endpoint '%s'.", self.endpoint.name))


def _get_base_headers(self):
    if not self.endpoint:
        return _ORIGINAL["_get_base_headers"](self)
    headers = {"Content-Type": "application/json"}
    token = self._get_api_token()
    if self.endpoint.dialect == "anthropic":
        headers["x-api-key"] = token
        headers["anthropic-version"] = self.endpoint.anthropic_version or "2023-06-01"
    elif token:
        if self.endpoint.auth_header == "api-key":
            headers["api-key"] = token
        else:
            headers["Authorization"] = f"Bearer {token}"
    return headers


def _request_llm(self, *args, **kwargs):
    if not self.endpoint:
        return _ORIGINAL["_request_llm"](self, *args, **kwargs)

    params = _normalize_request_args(args, kwargs)
    endpoint = self.endpoint
    model = endpoint._model_record(params["llm_model"])
    params["llm_model"] = model.technical_name
    if not endpoint.supports_web_search:
        params["web_grounding"] = False

    Usage = self.env["ai.usage.line"].sudo()
    Usage._check_hard_budget(self.env.company)

    if endpoint.dialect == "openai_responses":
        self._last_usage = {}
        result = LLMApiService._request_llm_openai(self, **params)
        usage = self._last_usage
    elif endpoint.dialect == "openai_chat":
        result, usage = dialects.request_openai_chat(self, **params)
    elif endpoint.dialect == "anthropic":
        result, usage = dialects.request_anthropic(self, **params)
    else:
        raise UserError(self.env._("Unknown AI endpoint dialect '%s'.", endpoint.dialect))

    Usage._record(
        company=self.env.company, endpoint=endpoint, model=model, usage=usage,
        caller=self.env.context.get("ai_caller") or "odoo",
    )
    return result


def _request_llm_openai_helper(self, body, tools=None, inputs=()):
    response, to_call, next_inputs, usage = _ORIGINAL["_request_llm_openai_helper"](self, body, tools, inputs)
    self._last_usage = usage
    return response, to_call, next_inputs, usage


def _to_open_ai_tool_schema(self, schema):
    if self.endpoint and self.endpoint.dialect == "openai_responses":
        # Odoo converts the schema only for its literal 'openai' provider; a
        # Responses-API endpoint under another name needs the same conversion.
        provider, self.provider = self.provider, "openai"
        try:
            return _ORIGINAL["_to_open_ai_tool_schema"](self, schema)
        finally:
            self.provider = provider
    return _ORIGINAL["_to_open_ai_tool_schema"](self, schema)


def _build_tool_call_response(self, tool_call_id, return_value):
    if self.endpoint:
        return dialects.tool_call_response(self.endpoint.dialect, tool_call_id, return_value)
    return _ORIGINAL["_build_tool_call_response"](self, tool_call_id, return_value)


def get_embedding(self, input, dimensions, model="text-embedding-3-small", encoding_format=None, user=None):
    if self.endpoint:
        if self.endpoint.dialect == "anthropic":
            raise UserError(self.env._("Endpoint '%s' (Anthropic) offers no embeddings. Configure an "
                              "OpenAI-compatible endpoint for embeddings.", self.endpoint.name))
        if self.endpoint.embedding_model:
            model = self.endpoint.embedding_model
    return _ORIGINAL["get_embedding"](self, input, dimensions, model=model,
                                      encoding_format=encoding_format, user=user)


def apply():
    """Install the extension once per process."""
    if _ORIGINAL:
        return
    for name, func in (
        ("__init__", __init__),
        ("_get_api_token", _get_api_token),
        ("_get_base_headers", _get_base_headers),
        ("_request_llm", _request_llm),
        ("_request_llm_openai_helper", _request_llm_openai_helper),
        ("_to_open_ai_tool_schema", _to_open_ai_tool_schema),
        ("_build_tool_call_response", _build_tool_call_response),
        ("get_embedding", get_embedding),
    ):
        _ORIGINAL[name] = getattr(LLMApiService, name)
        setattr(LLMApiService, name, func)
    _logger.info("AI Providers: LLMApiService extension installed")


def rebuild_provider_registry(provider_tuples):
    """Replace the process-wide provider list with Odoo's own plus ours.

    ``PROVIDERS`` is a module-level list read by ``ai.agent`` (model selection,
    provider lookup) and ``ai.embedding``. It is process-global, so in a
    multi-database process the union of all databases' endpoints is visible;
    a request still resolves against the current database only.
    """
    _providers_module.PROVIDERS[:] = [*BASE_PROVIDERS, *provider_tuples]
