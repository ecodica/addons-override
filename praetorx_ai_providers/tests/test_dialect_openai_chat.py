# Part of PraetorX. See LICENSE file for full copyright and licensing details.
import json
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.ai.utils.llm_api_service import LLMApiService

from .common import AIProvidersCase


@tagged("praetorx_ai_providers", "post_install", "-at_install")
class TestOpenAIChatDialect(AIProvidersCase):

    def setUp(self):
        super().setUp()
        self.endpoint = self._endpoint("openai_chat", code="chat")

    def test_plain_request(self):
        with self._http(self.chat_text("Hi")) as calls:
            answer = LLMApiService(self.env, "chat").request_llm("small-model", ["Sys."], ["User."])
        self.assertEqual(answer, ["Hi"])
        call = calls[0]
        self.assertEqual(call["route"], "http://chat.test/v1/chat/completions")
        self.assertEqual(call["headers"]["Authorization"], "Bearer sk-test")
        self.assertEqual(call["body"]["messages"][0], {"role": "system", "content": "Sys."})
        self.assertEqual(call["body"]["messages"][1]["content"], [{"type": "text", "text": "User."}])

    def test_schema_uses_response_format(self):
        schema = {"type": "object", "properties": {"v": {"type": "string"}}, "required": ["v"]}
        with self._http(self.chat_text('{"v": "x"}')) as calls:
            answer = LLMApiService(self.env, "chat").request_llm("small-model", [], ["q"], schema=schema)
        self.assertEqual(json.loads(answer[0]), {"v": "x"})
        self.assertEqual(calls[0]["body"]["response_format"]["type"], "json_schema")
        self.assertEqual(calls[0]["body"]["response_format"]["json_schema"]["schema"], schema)

    def test_pdf_becomes_text_via_odoo_indexer(self):
        files = [{"mimetype": "application/pdf", "value": "UERG", "file_ref": "<f1>"},
                 {"mimetype": "image/jpeg", "value": "aW1n", "file_ref": "<f2>"}]
        with patch.object(type(self.env["ir.attachment"]), "_index", return_value="Invoice 4711 total 100"), \
                self._http(self.chat_text("ok")) as calls:
            LLMApiService(self.env, "chat").request_llm("small-model", [], ["Read."], files=files)
        content = calls[0]["body"]["messages"][0]["content"]
        self.assertEqual(content[1]["type"], "text")
        self.assertIn("Invoice 4711 total 100", content[1]["text"])
        self.assertEqual(content[2]["type"], "image_url")
        self.assertTrue(content[2]["image_url"]["url"].startswith("data:image/jpeg;base64,"))

    def test_pdf_text_is_cut_at_max_chars(self):
        self.endpoint.max_text_chars = 10
        files = [{"mimetype": "application/pdf", "value": "UERG", "file_ref": "<f1>"}]
        with patch.object(type(self.env["ir.attachment"]), "_index", return_value="x" * 100), \
                self._http(self.chat_text("ok")) as calls:
            LLMApiService(self.env, "chat").request_llm("small-model", [], ["Read."], files=files)
        text = calls[0]["body"]["messages"][0]["content"][1]["text"]
        self.assertEqual(text.split("\n", 1)[1], "x" * 10)

    def test_tool_loop(self):
        tools = {
            "lookup": ("Look up", False, lambda arguments: ("found " + arguments["q"], None),
                       {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]}),
        }
        first = {
            "choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "lookup", "arguments": json.dumps({"q": "abc"})}},
            ]}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5},
        }
        with self._http(first, self.chat_text("done")) as calls:
            answer = LLMApiService(self.env, "chat").request_llm("small-model", [], ["Go."], tools=tools)
        self.assertEqual(answer, ["done"])
        messages = calls[1]["body"]["messages"]
        self.assertEqual(messages[-2]["role"], "assistant")
        self.assertEqual(messages[-2]["tool_calls"][0]["id"], "call_1")
        self.assertEqual(messages[-1], {"role": "tool", "tool_call_id": "call_1", "content": "found abc"})
        self.assertEqual(calls[0]["body"]["tools"][0]["function"]["name"], "lookup")

    def test_embedding_uses_endpoint_model(self):
        self.endpoint.embedding_model = "nomic-embed-text"
        payload = {"data": [{"embedding": [0.1] * 4}], "usage": {}}
        with self._http(payload) as calls:
            LLMApiService(self.env, "chat").get_embedding(["a"], 1536, model="text-embedding-3-small")
        self.assertEqual(calls[0]["route"], "http://chat.test/v1/embeddings")
        self.assertEqual(calls[0]["body"]["model"], "nomic-embed-text")
