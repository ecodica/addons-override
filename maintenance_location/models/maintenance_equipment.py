# Copyright 2019 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    # not location_id: core stock_maintenance defines that one on stock.location
    maintenance_location_id = fields.Many2one(
        "maintenance.location", string="Maintenance Location", tracking=True
    )
    location = fields.Char(string="Location Old")

    def _prepare_request_from_plan(self, maintenance_plan, next_maintenance_date):
        res = super()._prepare_request_from_plan(
            maintenance_plan, next_maintenance_date
        )
        location = maintenance_plan.location_id or self.maintenance_location_id
        res.update({"location_id": location.id})
        return res
