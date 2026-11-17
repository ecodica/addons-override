# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.base.tests.common import BaseCommon


@tagged("post_install", "-at_install")
class TestDeliveryWindowCompany(BaseCommon):
    """A shared partner keeps a delivery preference and delivery time
    windows per company."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_b = cls.env["res.company"].create({"name": "Delivery Window B"})
        cls.env.user.company_ids |= cls.company_b
        cls.env_b = cls.env(
            context=dict(cls.env.context, allowed_company_ids=cls.company_b.ids)
        )
        cls.monday = cls.env.ref("base_time_window.time_weekday_monday")
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Shared Customer",
                "delivery_time_preference": "time_windows",
                "delivery_time_window_ids": [cls._window_vals(8.0, 12.0)],
            }
        )

    @classmethod
    def _window_vals(cls, start, end):
        return Command.create(
            {
                "time_window_start": start,
                "time_window_end": end,
                "time_window_weekday_ids": [Command.set(cls.monday.ids)],
            }
        )

    def test_preference_and_windows_per_company(self):
        partner_b = self.partner.with_env(self.env_b)
        self.assertEqual(partner_b.delivery_time_preference, "anytime")
        self.assertFalse(partner_b._get_company_delivery_windows())

        # the other company may take the same day and time
        partner_b.write(
            {
                "delivery_time_preference": "time_windows",
                "delivery_time_window_ids": [self._window_vals(8.0, 12.0)],
            }
        )
        self.assertEqual(self.partner.delivery_time_preference, "time_windows")
        self.assertEqual(len(self.partner._get_company_delivery_windows()), 1)
        self.assertEqual(
            partner_b._get_company_delivery_windows().company_id, self.company_b
        )

        # within a company the windows still may not overlap
        with self.assertRaises(ValidationError):
            self.partner.write(
                {"delivery_time_window_ids": [self._window_vals(10.0, 14.0)]}
            )
