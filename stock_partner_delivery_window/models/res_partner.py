# Copyright 2020 Camptocamp SA
# Copyright 2025 Jacques-Etienne Baudoux (BCIM) <je@bcim.be>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)

import datetime

import pytz

from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain

WORKDAYS = list(range(5))


class ResPartner(models.Model):
    _inherit = "res.partner"

    # the partners are shared: each company keeps its own preference; a
    # company-dependent field cannot be required, a company without a value
    # reads "Any time" (ir.default of the module)
    delivery_time_preference = fields.Selection(
        [
            ("anytime", "Any time"),
            ("time_windows", "Fixed time windows"),
            ("workdays", "Weekdays (Monday to Friday)"),
        ],
        string="Delivery time schedule preference",
        company_dependent=True,
        default="anytime",
        help="Define the scheduling preference for delivery orders:\n\n"
        "* Any time: Do not postpone deliveries\n"
        "* Fixed time windows: Postpone deliveries to the next preferred "
        "time window\n"
        "* Weekdays: Postpone deliveries to the next weekday",
    )

    delivery_time_window_ids = fields.One2many(
        "partner.delivery.time.window", "partner_id", string="Delivery time windows"
    )

    @api.constrains("delivery_time_preference", "delivery_time_window_ids")
    def _check_delivery_time_preference(self):
        for partner in self:
            if (
                partner.delivery_time_preference == "time_windows"
                and not partner._get_company_delivery_windows()
            ):
                raise ValidationError(
                    self.env._(
                        "Please define at least one delivery time window or change"
                        " preference to Any time"
                    )
                )

    def _get_company_delivery_windows(self):
        """Delivery time windows of the partner in the current company."""
        self.ensure_one()
        return self.delivery_time_window_ids.filtered(
            lambda window: window.company_id == self.env.company
        )

    def _get_delivery_windows(self, day_name=None):
        """
        Return the list of delivery windows by partner id for the given day

        :param day: The day name (see time.weekday, ex: 0,1,2,...)
        :return: dict partner: delivery_window recordset
        """
        domain = Domain("partner_id", "in", self.ids) & Domain(
            "company_id", "=", self.env.company.id
        )
        if day_name is not None:
            week_day_id = self.env["time.weekday"]._get_id_by_name(day_name)
            domain &= Domain("time_window_weekday_ids", "in", [week_day_id])
        windows = self.env["partner.delivery.time.window"].search(domain)
        return windows.grouped("partner_id")

    @property
    def delivery_time_weekdays(self):
        if not self:  # pragma: no cover
            return set()
        self.ensure_one()
        if self.delivery_time_preference == "anytime":
            weekdays = set(range(7))
        elif self.delivery_time_preference == "workdays":
            weekdays = set(range(5))
        else:
            windows = self._get_company_delivery_windows()
            weekdays = set(
                map(
                    int,
                    windows.time_window_weekday_ids.mapped("name"),
                )
            )
        return weekdays

    @property
    def delivery_window_tz(self):
        """Return the timezone used to interpret partner delivery windows."""
        self.ensure_one()
        return self.tz or self.env.company.partner_id.tz or "UTC"

    def _is_in_delivery_window(self, date):
        """
        Checks if provided date is in a delivery window for actual partner

        :param date: Datetime or Date object
        :return: Boolean
        """
        self.ensure_one()
        timezone = pytz.timezone(self.delivery_window_tz)
        if isinstance(date, datetime.datetime):
            date = pytz.utc.localize(date).astimezone(timezone)
        if self.delivery_time_preference == "workdays":
            if date.weekday() > 4:
                return False
            return True
        windows = self._get_delivery_windows(date.weekday()).get(self)
        if windows:
            if not isinstance(date, datetime.datetime):
                return True
            for w in windows:
                start_time = w.get_time_window_start_time()
                end_time = w.get_time_window_end_time()
                if start_time <= date.time() <= end_time:
                    return True
        return False

    def copy_data(self, default=None):
        result = super().copy_data(default=default)[0]
        not_time_windows = self.delivery_time_preference != "time_windows"
        not_copy_windows = not_time_windows or "delivery_time_window_ids" in result
        if not_copy_windows:
            return [result]
        values = [
            {
                "time_window_start": window_id.time_window_start,
                "time_window_end": window_id.time_window_end,
                "time_window_weekday_ids": [
                    Command.link(wd_id.id)
                    for wd_id in window_id.time_window_weekday_ids
                ],
                "company_id": window_id.company_id.id,
            }
            for window_id in self.delivery_time_window_ids
        ]
        result["delivery_time_window_ids"] = [Command.create(val) for val in values]
        return [result]
