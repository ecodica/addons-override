# Copyright 2021-2023 Tecnativa - Víctor Martínez
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    landed_cost_ids = fields.One2many(
        comodel_name="stock.landed.cost",
        inverse_name="purchase_id",
        string="Landed Costs",
    )
    landed_cost_number = fields.Integer(compute="_compute_landed_cost_number")

    def _compute_landed_cost_number(self):
        if not self.ids:
            for item in self:
                item.landed_cost_number = 0
            return
        groups = self.env["stock.landed.cost"]._read_group(
            domain=[("purchase_id", "in", self.ids)],
            groupby=["purchase_id"],
            aggregates=["__count"],
        )
        landed_cost_dict = {po.id: count for po, count in groups}
        for item in self:
            item.landed_cost_number = landed_cost_dict.get(item.id, 0)

    def _prepare_landed_cost_values(self, picking):
        return {
            "purchase_id": self.id,
            "picking_ids": [(4, picking.id)],
        }

    def _create_picking_with_stock_landed_cost(self, picking):
        # We need to use sudo() because only Inventory > Administrator have
        # permissions on stock.landed.cost
        self.ensure_one()
        landed_cost = (
            self.env["stock.landed.cost"]
            .with_company(self.company_id)
            .sudo()
            .create(self._prepare_landed_cost_values(picking))
        )
        self.sudo().write({"landed_cost_ids": [(4, landed_cost.id)]})

    def _create_picking(self):
        all_pickings = self.mapped("picking_ids")
        res = super()._create_picking()
        for order in self:
            order_pickings = order.picking_ids - all_pickings
            if order_pickings:
                order._create_picking_with_stock_landed_cost(next(iter(order_pickings)))
        return res

    def action_view_stock_landed_cost(self):
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "stock_landed_costs.action_stock_landed_cost"
        )
        action["context"] = {"search_default_purchase_id": self.id}
        return action


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def _create_or_update_picking(self):
        all_pickings = self.mapped("order_id.picking_ids")
        res = super()._create_or_update_picking()
        for order in self.mapped("order_id"):
            order_pickings = order.picking_ids - all_pickings
            if order_pickings:
                order._create_picking_with_stock_landed_cost(next(iter(order_pickings)))
        return res
