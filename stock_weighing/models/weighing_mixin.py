# Copyright 2024 Tecnativa - David Vidal
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models


class WeightMixin(models.AbstractModel):
    _name = "weighing.mixin"
    _description = "To be used by stock.move and stock.move.line"

    has_weight = fields.Boolean(
        compute="_compute_has_weight", search="_search_has_weight"
    )

    @api.model
    def _weight_uom_ids(self):
        """All UoMs whose root reference is gram (i.e. mass-like UoMs)."""
        gram = self.env.ref("uom.product_uom_gram")
        return self.env["uom.uom"].search(
            [("parent_path", "=like", f"{gram.id}/%")]
        )

    @api.model
    def _has_weigh_domain(self):
        """Plug in to change behavior"""
        return [("weighing_uom_id", "in", self._weight_uom_ids().ids)]

    @api.depends("weighing_uom_id")
    def _compute_has_weight(self):
        """Product UOM is a weighed one"""
        self.has_weight = False
        self.filtered_domain(self._has_weigh_domain()).has_weight = True

    def _search_has_weight(self, operator, value):
        return [("weighing_uom_id", "in", self._weight_uom_ids().ids)]
