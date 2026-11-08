# Part of PraetorX. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    ai_budget_soft = fields.Monetary(
        string="AI budget, soft limit (monthly)",
        help="When reached, the administrator gets an activity. Requests continue.",
    )
    ai_budget_hard = fields.Monetary(
        string="AI budget, hard limit (monthly)",
        help="When reached, AI requests are refused until next month. 0 = no limit.",
    )
    ai_budget_notified_month = fields.Char(copy=False)
    ai_month_cost = fields.Monetary(compute="_compute_ai_month_cost", string="AI cost this month")

    def _compute_ai_month_cost(self):
        Usage = self.env["ai.usage.line"].sudo()
        for company in self:
            company.ai_month_cost = Usage._month_cost(company)
