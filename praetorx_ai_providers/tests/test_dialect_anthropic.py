# Part of PraetorX. See LICENSE file for full copyright and licensing details.
import json

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.ai.utils.llm_api_service import LLMApiService

from ..utils.dialects import JSON_OUTPUT_TOOL
from .common import AIProvidersCase


@tagged("praetorx_ai_providers", "post_install", "-at_install")
class TestAnthropicDialect(AIProvidersCase):

    def setUp(self):
        super().setUp()
        self.endpoint = self._endpoint("anthropic", is_odoo_default=True)

    def test_plain_request(self):
        with self._http(self.anthropic_text("Hello")) as calls:
            answer = LLMApiService(self.env, "openai").request_llm(
                "gpt-4.1", ["Be brief."], ["Say hello."])
        self.assertEqual(answer, ["Hello"])
        call = calls[0]
        self.assertEqual(call["route"], "https://api.anthropic.test/v1/messages")
        self.assertEqual(call["headers"]["x-api-key"], "sk-test")
        self.assertEqual(call["headers"]["anthropic-version"], "2023-06-01")
        self.assertNotIn("Authorization", call["headers"])
        body = call["body"]
        self.assertEqual(body["model"], "small-model", "unknown model is replaced by the endpoint default")
        self.assertEqual(body["system"], "Be brief.")
        self.assertEqual(body["max_tokens"], 4096)
        self.assertEqual(body["messages"], [{"role": "user", "content": [{"type": "text", "text": "Say hello."}]}])

    def test_files_become_document_and_image_blocks(self):
        files = [
            {"mimetype": "application/pdf", "value": "UERG", "file_ref": "<f1>"},
            {"mimetype": "image/png", "value": "aW1n", "file_ref": "<f2>"},
            {"mimetype": "text/plain", "value": "plain text", "file_ref": "<f3>"},
        ]
        with self._http(self.anthropic_text("ok")) as calls:
            LLMApiService(self.env, "openai").request_llm("big-model", [], ["Read."], files=files)
        content = calls[0]["body"]["messages"][0]["content"]
        types = [block["type"] for block in content]
        self.assertEqual(types, ["text", "document", "image", "text"])
        self.assertEqual(content[1]["source"], {"type": "base64", "media_type": "application/pdf", "data": "UERG"})
        self.assertEqual(content[2]["source"]["media_type"], "image/png")

    def test_schema_is_forced_tool_and_returns_json(self):
        schema = {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]}
        payload = {
            "content": [{"type": "tool_use", "id": "tu_1", "name": JSON_OUTPUT_TOOL, "input": {"value": "Invoice"}}],
            "usage": {"input_tokens": 50, "output_tokens": 5},
        }
        with self._http(payload) as calls:
            answer = LLMApiService(self.env, "openai").request_llm("x", [], ["Classify."], schema=schema)
        body = calls[0]["body"]
        self.assertEqual(body["tool_choice"], {"type": "tool", "name": JSON_OUTPUT_TOOL})
        self.assertEqual(body["tools"][0]["input_schema"], schema)
        self.assertEqual(json.loads(answer[0]), {"value": "Invoice"})

    def test_tool_loop_merges_tool_results(self):
        tools = {
            "add": ("Add two numbers", False,
                    lambda arguments: (arguments["a"] + arguments["b"], None),
                    {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                     "required": ["a", "b"]}),
        }
        first = {
            "content": [
                {"type": "text", "text": "Let me compute."},
                {"type": "tool_use", "id": "tu_1", "name": "add", "input": {"a": 2, "b": 3}},
                {"type": "tool_use", "id": "tu_2", "name": "add", "input": {"a": 1, "b": 1}},
            ],
            "usage": {"input_tokens": 10, "output_tokens": 10},
        }
        second = self.anthropic_text("5 and 2")
        with self._http(first, second) as calls:
            answer = LLMApiService(self.env, "openai").request_llm("x", [], ["Add."], tools=tools)
        self.assertEqual(answer, ["5 and 2"])
        self.assertEqual(len(calls), 2)
        messages = calls[1]["body"]["messages"]
        roles = [m["role"] for m in messages]
        self.assertEqual(roles, ["user", "assistant", "user"], "two tool results must merge into one user turn")
        results = [b for b in messages[2]["content"] if b["type"] == "tool_result"]
        self.assertEqual([r["tool_use_id"] for r in results], ["tu_1", "tu_2"])
        self.assertEqual([r["content"] for r in results], ["5", "2"])
        self.assertEqual(calls[1]["body"]["tools"][0]["name"], "add")
        self.assertNotIn("tool_choice", calls[1]["body"])

    def test_temperature_clamped_and_grounding_ignored(self):
        with self._http(self.anthropic_text("x")) as calls:
            LLMApiService(self.env, "openai").request_llm("x", [], ["q"], temperature=1.7, web_grounding=True)
        self.assertEqual(calls[0]["body"]["temperature"], 1.0)
        self.assertNotIn("web_search", json.dumps(calls[0]["body"]))

    def test_no_embeddings(self):
        with self.assertRaises(UserError):
            LLMApiService(self.env, "openai").get_embedding("text", 1536)

    def test_ai_field_value_goes_through_endpoint(self):
        """Odoo's AI fields call LLMApiService(env, 'openai') with a hard-coded
        model; with a default endpoint they must land on it."""
        if "ai_fields" not in self.env["ir.module.module"]._installed():
            self.skipTest("ai_fields not installed")
        from odoo.addons.ai_fields.tools import get_ai_value
        payload = {
            "content": [{"type": "tool_use", "id": "t", "name": JSON_OUTPUT_TOOL,
                         "input": {"value": "Berlin", "could_not_resolve": False, "unresolved_cause": None}}],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
        partner = self.env["res.partner"].create({"name": "Test Partner"})
        with self._http(payload) as calls:
            value = get_ai_value(partner, "char", "Which city?", [], {})
        self.assertEqual(value, "Berlin")
        self.assertEqual(calls[0]["route"], "https://api.anthropic.test/v1/messages")
        self.assertEqual(calls[0]["body"]["model"], "small-model")
