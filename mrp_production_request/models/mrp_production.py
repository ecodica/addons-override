# Copyright 2017 ForgeFlow S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    mrp_production_request_id = fields.Many2one(
        comodel_name="mrp.production.request",
        string="Manufacturing Request",
        copy=False,
        readonly=True,
    )

    def _generate_finished_moves(self):
        """`move_dest_ids` is a One2many fields in mrp.production, thus we
        cannot indicate the same destination move in several MOs (which most
        probably would be the case with MRs).
        Storing them on the MR and writing them on the finished moves as it
        would happen if they were present in the MO, is the best workaround
        without changing the standard data model."""
        move = super()._generate_finished_moves()
        request = self.mrp_production_request_id
        if request and request.move_dest_ids:
            move.write({"move_dest_ids": [(4, x.id) for x in request.move_dest_ids]})
        return move

    def _get_default_picking_type(self):
        company_id = self.env.context.get('default_company_id', self.env.company.id)
        return self.env['stock.picking.type'].search([
            ('code', '=', 'mrp_operation'),
            ('warehouse_id.company_id', '=', company_id),
        ], limit=1).id

    def _get_default_location_src_id(self):
        location = False
        company_id = self.env.context.get('default_company_id', self.env.company.id)
        if self.env.context.get('default_picking_type_id'):
            location = self.env['stock.picking.type'].browse(self.env.context['default_picking_type_id']).default_location_src_id
        if not location:
            location = self.env['stock.warehouse'].search([('company_id', '=', company_id)], limit=1).lot_stock_id
        return location and location.id or False

    def _get_default_location_dest_id(self):
        location = False
        company_id = self.env.context.get('default_company_id', self.env.company.id)
        if self._context.get('default_picking_type_id'):
            location = self.env['stock.picking.type'].browse(self.env.context['default_picking_type_id']).default_location_dest_id
        if not location:
            location = self.env['stock.warehouse'].search([('company_id', '=', company_id)], limit=1).lot_stock_id
        return location and location.id or False
