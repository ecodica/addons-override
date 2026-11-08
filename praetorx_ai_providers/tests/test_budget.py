# Part of PraetorX. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.ai.utils.llm_api_service import LLMApiService

from .common import AIProvidersCase


@tagged("praetorx_ai_providers", "post_install", "-at_install")
class TestBudget(AIProvidersCase):

    def setUp(self):
        super().setUp()
        self.endpoint = self._endpoint("openai_chat", code="chat")
        self.company.write({"ai_budget_soft": 0, "ai_budget_hard": 0, "ai_budget_notified_month": False})

    def _call(self, caller=None, usage=None):
        env = self.env if caller is None else self.env(context=dict(self.env.context, ai_caller=caller))
        with self._http(self.chat_text("ok", usage=usage)):
            LLMApiService(env, "chat").request_llm("big-model", [], ["q"])

    def test_usage_line_with_cost(self):
        usage = {"prompt_tokens": 1_000_000, "completion_tokens": 100_000,
                 "prompt_tokens_details": {"cached_tokens": 200_000}}
        self._call(caller="praetorx_tabularium", usage=usage)
        line = self.Usage.search([("company_id", "=", self.company.id)], limit=1)
        self.assertEqual(line.caller, "praetorx_tabularium")
        self.assertEqual(line.model_name, "big-model")
        self.assertEqual((line.input_tokens, line.cached_tokens, line.output_tokens),
                         (1_000_000, 200_000, 100_000))
        # 800k fresh * 3 + 200k cached * 0.3 + 100k out * 15  → per 1M
        self.assertAlmostEqual(line.cost, 0.8 * 3 + 0.2 * 0.3 + 0.1 * 15, places=4)
        self.assertAlmostEqual(self.company.ai_month_cost, line.cost, places=4)

    def test_default_caller_is_odoo(self):
        self._call()
        self.assertEqual(self.Usage.search([], limit=1).caller, "odoo")

    def test_hard_budget_refuses(self):
        self.company.ai_budget_hard = 1.0
        self._call(usage={"prompt_tokens": 1_000_000, "completion_tokens": 0})  # cost 3.0
        with self.assertRaises(UserError):
            self._call()
        self.assertEqual(self.Usage.search_count([]), 1, "the refused request must not be recorded")

    def test_soft_budget_notifies_once(self):
        self.company.ai_budget_soft = 1.0
        admin = self.env.ref("base.user_admin")
        Activity = self.env["mail.activity"]
        domain = [("res_model", "=", "res.partner"), ("res_id", "=", admin.partner_id.id),
                  ("summary", "ilike", "AI budget")]
        before = Activity.search_count(domain)
        self._call(usage={"prompt_tokens": 1_000_000, "completion_tokens": 0})
        self._call(usage={"prompt_tokens": 1_000_000, "completion_tokens": 0})
        self.assertEqual(Activity.search_count(domain) - before, 1)
        self.assertTrue(self.company.ai_budget_notified_month)

    def test_autovacuum_keeps_a_year(self):
        self._call()
        line = self.Usage.search([], limit=1)
        self.env.cr.execute("UPDATE ai_usage_line SET create_date = create_date - interval '400 days' WHERE id = %s", (line.id,))
        line.invalidate_recordset()
        self.Usage._gc_usage_lines()
        self.assertFalse(line.exists())
