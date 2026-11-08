# Part of PraetorX. See LICENSE file for full copyright and licensing details.
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AIUsageLine(models.Model):
    _name = "ai.usage.line"
    _description = "AI Usage"
    _order = "create_date desc, id desc"

    company_id = fields.Many2one("res.company", required=True, index=True)
    endpoint_id = fields.Many2one("ai.provider.endpoint", index=True, ondelete="set null")
    endpoint_code = fields.Char(index=True)
    model_name = fields.Char(index=True)
    caller = fields.Char(index=True, help="Module or feature that issued the request.")
    input_tokens = fields.Integer()
    output_tokens = fields.Integer()
    cached_tokens = fields.Integer()
    cost = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id")

    @api.model
    def _month_start(self):
        return fields.Datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    @api.model
    def _month_cost(self, company):
        self.env.cr.execute(
            "SELECT COALESCE(SUM(cost), 0) FROM ai_usage_line WHERE company_id = %s AND create_date >= %s",
            (company.id, self._month_start()),
        )
        return self.env.cr.fetchone()[0]

    @api.model
    def _check_hard_budget(self, company):
        if company.ai_budget_hard and self._month_cost(company) >= company.ai_budget_hard:
            raise UserError(_(
                "The monthly AI budget of %(company)s (%(amount)s) is exhausted. "
                "Raise it in Settings > AI or wait for next month.",
                company=company.name, amount=company.ai_budget_hard,
            ))

    @api.model
    def _record(self, company, endpoint, model, usage, caller):
        line = self.create({
            "company_id": company.id,
            "endpoint_id": endpoint.id,
            "endpoint_code": endpoint.code,
            "model_name": model.technical_name,
            "caller": caller,
            "input_tokens": usage.get("input_tokens", 0) or 0,
            "output_tokens": usage.get("output_tokens", 0) or 0,
            "cached_tokens": usage.get("cached_tokens", 0) or 0,
            "cost": model._cost(usage),
        })
        self._notify_soft_budget(company)
        return line

    @api.model
    def _notify_soft_budget(self, company):
        if not company.ai_budget_soft:
            return
        month = fields.Date.today().strftime("%Y-%m")
        if company.ai_budget_notified_month == month:
            return
        if self._month_cost(company) < company.ai_budget_soft:
            return
        company.sudo().ai_budget_notified_month = month
        admin = self.env.ref("base.user_admin", raise_if_not_found=False)
        if not admin:
            return
        self.env["mail.activity"].sudo().create({
            "res_model_id": self.env["ir.model"]._get_id("res.partner"),
            "res_id": admin.partner_id.id,
            "user_id": admin.id,
            "activity_type_id": self.env.ref("mail.mail_activity_data_warning").id,
            "summary": _("AI budget: soft limit reached"),
            "note": _(
                "%(company)s has spent %(spent).2f of its monthly AI budget (soft limit %(soft).2f).",
                company=company.name, spent=self._month_cost(company), soft=company.ai_budget_soft,
            ),
        })

    @api.autovacuum
    def _gc_usage_lines(self):
        cutoff = fields.Datetime.now() - timedelta(days=365)
        self.search([("create_date", "<", cutoff)]).unlink()
