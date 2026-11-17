# Copyright 2020 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DeliveryTimeWindow(models.Model):
    _name = "partner.delivery.time.window"
    _inherit = "time.window.mixin"
    _description = "Preferred delivery time windows"
    _time_window_overlap_check_field = "partner_id"
    _check_company_auto = True

    partner_id = fields.Many2one(
        "res.partner", required=True, index=True, ondelete="cascade"
    )
    # the partners are shared: each company keeps its own delivery days
    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    tz = fields.Selection(related="partner_id.tz")

    @api.constrains(
        "time_window_start",
        "time_window_end",
        "time_window_weekday_ids",
        "partner_id",
        "company_id",
    )
    def check_window_no_overlaps(self):
        # replaces the check of time.window.mixin, whose SQL compares every
        # window of the partner: the windows of other companies may share days
        for window in self:
            if window.time_window_start > window.time_window_end:
                raise ValidationError(
                    self.env._(
                        "%(end_time)s must be > %(start_time)s",
                        end_time=self.float_to_time_repr(window.time_window_end),
                        start_time=self.float_to_time_repr(window.time_window_start),
                    )
                )
            if not window.time_window_weekday_ids:
                raise ValidationError(
                    self.env._("At least one time.weekday is required")
                )
            other = self.search(window._get_overlapping_windows_domain(), limit=1)
            if other:
                raise ValidationError(
                    self.env._(
                        "%(record_name)s overlaps %(other_name)s",
                        record_name=window.display_name,
                        other_name=other.display_name,
                    )
                )

    def _get_overlapping_windows_domain(self):
        """Domain of the windows this window may not overlap: the windows of
        the partner in its company that share a day and a time."""
        self.ensure_one()
        return [
            ("id", "!=", self.id),
            ("partner_id", "=", self.partner_id.id),
            ("company_id", "=", self.company_id.id),
            ("time_window_weekday_ids", "in", self.time_window_weekday_ids.ids),
            ("time_window_start", "<", self.time_window_end),
            ("time_window_end", ">", self.time_window_start),
        ]
