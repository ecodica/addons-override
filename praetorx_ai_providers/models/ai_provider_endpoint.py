# Part of PraetorX. See LICENSE file for full copyright and licensing details.
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.ai.utils.llm_providers import Provider

from ..utils import patch

DIALECTS = [
    ("openai_responses", "OpenAI Responses API (OpenAI, Azure OpenAI, proxies)"),
    ("openai_chat", "OpenAI Chat Completions (Ollama, vLLM, Mistral, OpenRouter, Groq)"),
    ("anthropic", "Anthropic Messages API (Claude)"),
]

CAPABILITIES = ("choose", "read", "embed")


class AIProviderEndpoint(models.Model):
    _name = "ai.provider.endpoint"
    _description = "AI Provider Endpoint"
    _order = "sequence, id"

    name = fields.Char(required=True)
    code = fields.Char(
        required=True, copy=False,
        help="Technical provider name Odoo's AI layer uses to address this endpoint. "
             "Lowercase letters, digits and underscores.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    dialect = fields.Selection(DIALECTS, required=True, default="openai_chat")
    base_url = fields.Char(
        required=True,
        help="Root of the API, e.g. https://api.anthropic.com/v1 or http://ollama:11434/v1",
    )
    api_key = fields.Char(groups="base.group_system", copy=False)
    auth_header = fields.Selection(
        [("bearer", "Authorization: Bearer"), ("api-key", "api-key (Azure)")],
        default="bearer", required=True,
    )
    anthropic_version = fields.Char(default="2023-06-01")
    region = fields.Char(help="Where the data is processed, e.g. EU, US, on-premise.")
    zero_retention = fields.Boolean(
        string="Zero data retention",
        help="The provider has attested that prompts and files are not stored after processing.",
    )
    supports_web_search = fields.Boolean(
        help="Only for Responses-API endpoints that offer OpenAI's web_search_preview tool.",
    )
    embedding_model = fields.Char(
        help="Embedding model served under /embeddings (1536 dimensions). Not available on Anthropic.",
    )
    max_text_chars = fields.Integer(
        default=60000,
        help="Chat-Completions endpoints get PDFs as extracted text; longer text is cut here.",
    )
    is_odoo_default = fields.Boolean(
        string="Default for Odoo AI",
        help="Serve every request Odoo issues to its built-in OpenAI provider — AI fields, "
             "agents, document auto-sort — through this endpoint instead.",
    )
    model_ids = fields.One2many("ai.provider.model", "endpoint_id", string="Models")
    default_model_id = fields.Many2one(
        "ai.provider.model", domain="[('endpoint_id', '=', id)]",
        help="Used when a caller asks for a model this endpoint does not serve.",
    )

    _code_unique = models.Constraint("UNIQUE(code)", "The endpoint code must be unique.")

    @api.constrains("code")
    def _check_code(self):
        for endpoint in self:
            if not re.fullmatch(r"[a-z][a-z0-9_]*", endpoint.code or ""):
                raise ValidationError(_("The code must be lowercase letters, digits and underscores."))
            if endpoint.code in {p.name for p in patch.BASE_PROVIDERS}:
                raise ValidationError(_("'%s' is reserved by Odoo.", endpoint.code))

    @api.constrains("is_odoo_default", "active")
    def _check_single_default(self):
        defaults = self.search_count([("is_odoo_default", "=", True), ("active", "=", True)])
        if defaults > 1:
            raise ValidationError(_("Only one active endpoint can be the default for Odoo AI."))

    @api.onchange("name")
    def _onchange_name(self):
        if self.name and not self.code:
            self.code = re.sub(r"[^a-z0-9]+", "_", self.name.lower()).strip("_")

    @api.onchange("dialect")
    def _onchange_dialect(self):
        if self.dialect == "anthropic" and not self.base_url:
            self.base_url = "https://api.anthropic.com/v1"

    # ------------------------------------------------------------------
    # registry sync
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        endpoints = super().create(vals_list)
        self._sync_provider_registry()
        return endpoints

    def write(self, vals):
        result = super().write(vals)
        self._sync_provider_registry()
        return result

    def unlink(self):
        result = super().unlink()
        self._sync_provider_registry()
        return result

    def _register_hook(self):
        super()._register_hook()
        self._sync_provider_registry()

    @api.model
    def _sync_provider_registry(self):
        tuples = []
        for endpoint in self.sudo().with_context(active_test=True).search([]):
            llms = [(m.technical_name, m.name) for m in endpoint.model_ids if m.active]
            if not llms:
                continue
            tuples.append(Provider(
                endpoint.code, endpoint.name,
                endpoint.embedding_model or f"{endpoint.code}:no-embeddings",
                {"max_batch_size": 100, "max_tokens_per_request": 100000},
                llms,
            ))
        patch.rebuild_provider_registry(tuples)

    # ------------------------------------------------------------------
    # resolution used by the LLMApiService extension
    # ------------------------------------------------------------------

    @api.model
    def _resolve(self, provider_name):
        """Endpoint for a provider name, or an empty recordset.

        ``openai`` resolves to the endpoint flagged as Odoo default so that
        Odoo's own callers are rerouted; ``google`` is never rerouted.
        """
        if provider_name == "openai":
            return self.search([("is_odoo_default", "=", True)], limit=1)
        if provider_name == "google":
            return self.browse()
        return self.search([("code", "=", provider_name)], limit=1)

    def _model_record(self, technical_name):
        """The model to use for a requested name: the exact model if this
        endpoint serves it, else the endpoint default."""
        self.ensure_one()
        models_ = self.model_ids.filtered("active")
        exact = models_.filtered(lambda m: m.technical_name == technical_name)
        if exact:
            return exact[0]
        fallback = self.default_model_id if self.default_model_id.active else models_[:1]
        if not fallback:
            raise UserError(_("AI endpoint '%s' has no active model configured.", self.name))
        return fallback

    @api.model
    def _service_for(self, capability):
        """``(LLMApiService, model_name)`` for a capability.

        Order: model configured in Settings for the capability → default
        endpoint's first model with that capability → Odoo's own OpenAI path.
        """
        from odoo.addons.ai.utils.llm_api_service import LLMApiService
        if capability not in CAPABILITIES:
            raise ValueError(f"unknown capability {capability!r}")
        Model = self.env["ai.provider.model"].sudo()
        param = self.env["ir.config_parameter"].sudo().get_param(f"praetorx_ai.model_{capability}")
        model = Model.browse(int(param)) if param and param.isdigit() else Model
        if not (model.exists() and model.active and model.endpoint_id.active):
            default = self._resolve("openai")
            active = default.model_ids.filtered("active")
            # A model made for the task wins over a general one; an embedding
            # request never goes to a general (chat) model.
            model = active.filtered(lambda m: m.capability == capability)[:1]
            if not model and capability != "embed":
                model = active.filtered(lambda m: m.capability == "any")[:1]
        if model:
            return LLMApiService(self.env, model.endpoint_id.code), model.technical_name
        # Odoo's own default when nothing is configured (ai_fields.tools.OPENAI_MODEL).
        return LLMApiService(self.env, "openai"), "gpt-4.1"

    def action_test_connection(self):
        self.ensure_one()
        from odoo.addons.ai.utils.llm_api_service import LLMApiService
        service = LLMApiService(self.env, self.code)
        model = self._model_record(self.default_model_id.technical_name if self.default_model_id else "")
        answer = service.request_llm(
            model.technical_name, ["Answer with the single word OK."], ["Ping."], temperature=0.0,
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": _("Endpoint answered: %s", " ".join(answer)[:80]),
                "sticky": False,
            },
        }
