# Part of PraetorX. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AIProviderModel(models.Model):
    _name = "ai.provider.model"
    _description = "AI Provider Model"
    _order = "endpoint_id, sequence, id"
    _rec_name = "name"

    endpoint_id = fields.Many2one("ai.provider.endpoint", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    technical_name = fields.Char(required=True, help="Model name as the API expects it.")
    name = fields.Char(required=True, help="Label shown in model pickers.")
    capability = fields.Selection(
        [
            ("any", "Any"),
            ("choose", "Choose — pick a value from a list"),
            ("read", "Read — read files and fill a schema"),
            ("embed", "Embed"),
        ],
        default="any", required=True,
        help="Which kind of task this model is the right size for.",
    )
    max_output_tokens = fields.Integer(default=4096, help="Required by the Anthropic Messages API.")
    price_in = fields.Float(string="Price per 1M input tokens", digits=(12, 4))
    price_out = fields.Float(string="Price per 1M output tokens", digits=(12, 4))
    price_cached = fields.Float(string="Price per 1M cached input tokens", digits=(12, 4))
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, required=True,
    )

    _name_per_endpoint_unique = models.Constraint(
        "UNIQUE(endpoint_id, technical_name)", "A model name must be unique per endpoint.",
    )

    def _cost(self, usage):
        """Cost of a usage dict in this model's currency."""
        self.ensure_one()
        cached = usage.get("cached_tokens", 0) or 0
        fresh = max((usage.get("input_tokens", 0) or 0) - cached, 0)
        out = usage.get("output_tokens", 0) or 0
        return (fresh * self.price_in + cached * self.price_cached + out * self.price_out) / 1_000_000
