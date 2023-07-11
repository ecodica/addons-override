# Copyright 2023 Ecodica d.o.o
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # This corrects issues with following code segment: /account/models/account_move.py:3443
    def write(self, vals):
        # CHECK ME: this change to commercial partner when find difference between main partner
        # https://github.com/odoo/odoo/blob/0f90852818a334d66ed8a6781f5abdc022f76ff7/addons/account/models/account_move.py#L2695 # noqa: B950
        if "partner_id" in vals and len(vals.keys()) == 1:
            lines_to_skip = self.filtered(lambda x: x.move_id.alternate_payer_id)
            return super(AccountMoveLine, self - lines_to_skip).write(vals)
        return super(AccountMoveLine, self).write(vals)

    def _compute_partner_id(self):
        # Even though drastically changing functionality, still call super
        super()._compute_partner_id()
        for line in self:
            if line.account_id.account_type in ('asset_receivable', 'liability_payable') \
                    and line.move_id.alternate_payer_id:
                line.partner_id = line.move_id.alternate_payer_id
