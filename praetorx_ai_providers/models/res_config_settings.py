# Part of PraetorX. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ai_currency_id = fields.Many2one(related="company_id.currency_id")
    ai_budget_soft = fields.Monetary(
        related="company_id.ai_budget_soft", readonly=False, currency_field="ai_currency_id")
    ai_budget_hard = fields.Monetary(
        related="company_id.ai_budget_hard", readonly=False, currency_field="ai_currency_id")
    ai_month_cost = fields.Monetary(related="company_id.ai_month_cost", currency_field="ai_currency_id")
    ai_model_choose_id = fields.Many2one(
        "ai.provider.model", string="Model for choosing",
        config_parameter="praetorx_ai.model_choose",
        help="Small, cheap: pick one value from a list.",
    )
    ai_model_read_id = fields.Many2one(
        "ai.provider.model", string="Model for reading",
        config_parameter="praetorx_ai.model_read",
        help="Reads files and fills a schema.",
    )
    ai_model_embed_id = fields.Many2one(
        "ai.provider.model", string="Model for embeddings",
        config_parameter="praetorx_ai.model_embed",
    )

    def action_open_ai_endpoints(self):
        return self.env["ir.actions.actions"]._for_xml_id("praetorx_ai_providers.action_ai_provider_endpoint")

    def action_open_ai_usage(self):
        return self.env["ir.actions.actions"]._for_xml_id("praetorx_ai_providers.action_ai_usage_line")
