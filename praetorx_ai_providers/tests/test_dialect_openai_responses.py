# Part of PraetorX. See LICENSE file for full copyright and licensing details.
from odoo.tests import tagged

from odoo.addons.ai.utils.llm_api_service import LLMApiService

from .common import AIProvidersCase


@tagged("praetorx_ai_providers", "post_install", "-at_install")
class TestOpenAIResponsesDialect(AIProvidersCase):

    def test_custom_base_url_and_api_key_header(self):
        endpoint = self._endpoint("openai_responses", code="azure", auth_header="api-key")
        with self._http(self.responses_text("pong")) as calls:
            answer = LLMApiService(self.env, "azure").request_llm("big-model", ["s"], ["ping"])
        self.assertEqual(answer, ["pong"])
        call = calls[0]
        self.assertEqual(call["route"], "https://responses.test/v1/responses")
        self.assertEqual(call["headers"]["api-key"], "sk-test")
        self.assertNotIn("Authorization", call["headers"])
        self.assertEqual(call["body"]["model"], "big-model")
        self.assertEqual(call["body"]["input"][1]["content"][0], {"type": "input_text", "text": "ping"})
        line = self.Usage.search([("endpoint_id", "=", endpoint.id)])
        self.assertEqual(len(line), 1)
        self.assertEqual((line.input_tokens, line.output_tokens), (100, 20))

    def test_tool_schema_converted_like_openai(self):
        self._endpoint("openai_responses", code="proxy")
        tools = {
            "t": ("desc", False, lambda arguments: ("ok", None),
                  {"type": "object", "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
                   "required": ["a"]}),
        }
        with self._http(self.responses_text("x")) as calls:
            LLMApiService(self.env, "proxy").request_llm("big-model", [], ["q"], tools=tools)
        tool = calls[0]["body"]["tools"][0]
        self.assertEqual(sorted(tool["parameters"]["required"]), ["a", "b"])
        self.assertEqual(tool["parameters"]["properties"]["b"]["type"], ["string", "null"])

    def test_web_grounding_dropped_unless_supported(self):
        self._endpoint("openai_responses", code="proxy")
        with self._http(self.responses_text("x")) as calls:
            LLMApiService(self.env, "proxy").request_llm("big-model", [], ["q"], web_grounding=True)
        self.assertNotIn("tools", calls[0]["body"])
        self._endpoint("openai_responses", code="real", supports_web_search=True)
        with self._http(self.responses_text("x")) as calls:
            LLMApiService(self.env, "real").request_llm("big-model", [], ["q"], web_grounding=True)
        self.assertEqual(calls[0]["body"]["tools"][0]["type"], "web_search_preview")
