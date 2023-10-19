# Copyright 2017 ForgeFlow S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    created_mrp_production_request_id = fields.Many2one(
        comodel_name="mrp.production.request", string="Created Production Request"
    )

    @api.model_create_multi
    def create(self, vals):
        for val in vals:
            if "production_id" in val:
                production = self.env["mrp.production"].browse(val["production_id"])
                if production.mrp_production_request_id:
                    val["propagate_cancel"] = False
        return super().create(vals)
