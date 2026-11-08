# Part of PraetorX. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.ai.utils.llm_api_service import LLMApiService
from odoo.addons.ai.utils.llm_providers import PROVIDERS, get_provider

from .common import AIProvidersCase


@tagged("praetorx_ai_providers", "post_install", "-at_install")
class TestRouting(AIProvidersCase):

    def test_no_endpoint_keeps_odoo_behaviour(self):
        service = LLMApiService(self.env, "openai")
        self.assertIsNone(service.endpoint)
        self.assertEqual(service.base_url, "https://api.openai.com/v1")
        with self.assertRaises(NotImplementedError):
            LLMApiService(self.env, "nobody")

    def test_endpoint_by_code(self):
        endpoint = self._endpoint("anthropic", code="claude_eu")
        service = LLMApiService(self.env, "claude_eu")
        self.assertEqual(service.endpoint, endpoint)
        self.assertEqual(service.provider, "claude_eu")
        self.assertEqual(service.base_url, "https://api.anthropic.test/v1")

    def test_default_reroutes_odoo_openai_calls(self):
        endpoint = self._endpoint("anthropic", is_odoo_default=True)
        service = LLMApiService(self.env, "openai")
        self.assertEqual(service.endpoint, endpoint, "Odoo's 'openai' must resolve to the default endpoint")
        # google is never rerouted
        self.assertIsNone(LLMApiService(self.env, "google").endpoint)

    def test_single_default_enforced(self):
        self._endpoint("anthropic", code="a", is_odoo_default=True)
        with self.assertRaises(ValidationError):
            self._endpoint("openai_chat", code="b", is_odoo_default=True)

    def test_reserved_codes(self):
        with self.assertRaises(ValidationError):
            self._endpoint("openai_chat", code="openai")
        with self.assertRaises(ValidationError):
            self._endpoint("openai_chat", code="Bad Code")

    def test_unknown_model_falls_back_to_default(self):
        endpoint = self._endpoint("anthropic")
        self.assertEqual(endpoint._model_record("gpt-4.1").technical_name, "small-model")
        self.assertEqual(endpoint._model_record("big-model").technical_name, "big-model")
        endpoint.model_ids.write({"active": False})
        with self.assertRaises(UserError):
            endpoint._model_record("gpt-4.1")

    def test_provider_registry_sync(self):
        endpoint = self._endpoint("openai_chat", code="ollama_x", embedding_model="nomic-embed")
        names = [p.name for p in PROVIDERS]
        self.assertIn("ollama_x", names)
        self.assertEqual(get_provider(self.env, "big-model"), "ollama_x")
        selection = dict(self.env["ai.embedding"]._fields["embedding_model"].get_description(self.env)["selection"])
        self.assertIn("nomic-embed", selection)
        endpoint.active = False
        self.assertNotIn("ollama_x", [p.name for p in PROVIDERS])

    def test_service_for_capability(self):
        endpoint = self._endpoint("anthropic", is_odoo_default=True)
        service, model = self.Endpoint._service_for("choose")
        self.assertEqual((service.endpoint, model), (endpoint, "small-model"))
        service, model = self.Endpoint._service_for("read")
        self.assertEqual(model, "big-model")
        # explicit setting wins
        other = self._endpoint("openai_chat", code="chat")
        self.env["ir.config_parameter"].sudo().set_param(
            "praetorx_ai.model_read", str(other.model_ids[0].id))
        service, model = self.Endpoint._service_for("read")
        self.assertEqual((service.endpoint, model), (other, "small-model"))
        with self.assertRaises(ValueError):
            self.Endpoint._service_for("fly")

    def test_specific_model_wins_over_general(self):
        endpoint = self._endpoint("openai_chat", code="chat", is_odoo_default=True)
        endpoint.model_ids[0].capability = "any"
        embed = self.env["ai.provider.model"].create({
            "endpoint_id": endpoint.id, "technical_name": "emb", "name": "Emb", "capability": "embed", "sequence": 99})
        __, model = self.Endpoint._service_for("embed")
        self.assertEqual(model, embed.technical_name)
        __, model = self.Endpoint._service_for("read")
        self.assertEqual(model, "big-model")
        __, model = self.Endpoint._service_for("choose")
        self.assertEqual(model, "small-model", "no 'choose' model: the general one answers")

    def test_service_for_without_endpoint_is_odoo(self):
        service, model = self.Endpoint._service_for("read")
        self.assertIsNone(service.endpoint)
        self.assertEqual(service.provider, "openai")
        self.assertEqual(model, "gpt-4.1")

    def test_missing_key(self):
        endpoint = self._endpoint("anthropic", api_key=False)
        with self.assertRaises(UserError):
            LLMApiService(self.env, endpoint.code)._get_api_token()
        self._endpoint("openai_chat", code="local", api_key=False)
        self.assertEqual(LLMApiService(self.env, "local")._get_api_token(), "")
        self.assertNotIn("Authorization", LLMApiService(self.env, "local")._get_base_headers())
