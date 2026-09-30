# Copyright 2025-2026 Tecnativa - Víctor Martínez
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _get_route_area(self):
        # Return the route area to be used from RMA
        if self.rma_receiver_ids:
            return self.sudo().rma_receiver_ids[0].reception_route_area_id
        elif (
            not self.rma_id
            and self.move_orig_ids
            and any(move.rma_receiver_ids for move in self.move_orig_ids)
        ):
            # Although route_planning_stock could handle this part, it is not possible
            # because the condition for route_planning_sale_stock would be met, and
            # the route_area_id for the sale would be retrieved incorrectly.
            move = self.move_orig_ids.sudo().filtered(lambda x: x.rma_receiver_ids)[0]
            return move.picking_id.route_area_id
        elif self.rma_id:
            return self.sudo().rma_id.route_area_id
        return super()._get_route_area()

    def _set_locations_from_record_route_area(self):
        # We define the appropriate destination location associated with the rma
        res = super()._set_locations_from_record_route_area()
        for item in self.filtered(lambda x: x.rma_id or x.rma_receiver_ids):
            if item.rma_id:
                custom_location = item.rma_id._get_location_final()
            else:
                receiver = item.rma_receiver_ids[:1]
                custom_location = (
                    receiver.reception_route_area_id.location_id or receiver.location_id
                )
            item.location_dest_id = custom_location
            # location_dest_id is a computed field in v19 (computed from the
            # picking), so we also set the final location to keep the expected
            # destination after any recomputation.
            item.location_final_id = custom_location
            item.move_line_ids.location_dest_id = custom_location
            item.env.flush_all()
            item.invalidate_recordset()
        return res
