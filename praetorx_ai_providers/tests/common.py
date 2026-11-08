# Part of PraetorX. See LICENSE file for full copyright and licensing details.
import json
from contextlib import contextmanager
from unittest.mock import patch

from odoo.tests import TransactionCase


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.text = json.dumps(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class AIProvidersCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Endpoint = cls.env["ai.provider.endpoint"]
        cls.Usage = cls.env["ai.usage.line"]

    def _endpoint(self, dialect, code=None, **extra):
        code = code or f"test_{dialect}"
        vals = {
            "name": f"Test {dialect}",
            "code": code,
            "dialect": dialect,
            "base_url": {
                "anthropic": "https://api.anthropic.test/v1",
                "openai_chat": "http://chat.test/v1",
                "openai_responses": "https://responses.test/v1",
            }[dialect],
            "api_key": "sk-test",
            "model_ids": [
                (0, 0, {
                    "technical_name": "small-model", "name": "Small", "capability": "choose",
                    "price_in": 1.0, "price_out": 5.0, "price_cached": 0.1,
                }),
                (0, 0, {
                    "technical_name": "big-model", "name": "Big", "capability": "read",
                    "price_in": 3.0, "price_out": 15.0, "price_cached": 0.3,
                }),
            ],
        }
        vals.update(extra)
        endpoint = self.Endpoint.create(vals)
        endpoint.default_model_id = endpoint.model_ids[0]
        return endpoint

    @contextmanager
    def _http(self, *payloads):
        """Patch ``requests.request`` inside Odoo's service; yields the call list."""
        calls = []
        responses = list(payloads)

        def fake_request(method, route, params=None, headers=None, json=None, data=None, timeout=None, files=None):
            calls.append({"method": method, "route": route, "headers": headers, "body": json})
            return FakeResponse(responses.pop(0) if len(responses) > 1 else responses[0])

        with patch("odoo.addons.ai.utils.llm_api_service.requests.request", side_effect=fake_request):
            yield calls

    @staticmethod
    def anthropic_text(text, usage=None):
        return {
            "content": [{"type": "text", "text": text}],
            "usage": usage or {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 0},
        }

    @staticmethod
    def chat_text(text, usage=None):
        return {
            "choices": [{"message": {"role": "assistant", "content": text}}],
            "usage": usage or {"prompt_tokens": 100, "completion_tokens": 20,
                               "prompt_tokens_details": {"cached_tokens": 0}},
        }

    @staticmethod
    def responses_text(text, usage=None):
        return {
            "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
            "usage": usage or {"input_tokens": 100, "output_tokens": 20,
                               "input_tokens_details": {"cached_tokens": 0}},
        }
