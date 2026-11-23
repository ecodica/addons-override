# Copyright 2015 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    order_type = fields.Many2one(
        comodel_name="purchase.order.type",
        string="Type",
        ondelete="restrict",
        domain="[('company_id', 'in', [False, company_id])]",
        default=lambda self: self._default_order_type(self.env.company),
        compute="_compute_partner_order_type",
        store=True,
        readonly=False,
    )

    def _get_partner_purchase_type(self):
        self.ensure_one()
        partner = self.partner_id
        purchase_type = partner.purchase_type or partner.commercial_partner_id.purchase_type
        if not purchase_type:
            return purchase_type
        type_company = purchase_type.sudo().company_id
        if type_company and type_company != self.company_id:
            return self.env["purchase.order.type"]
        return purchase_type

    @api.onchange("partner_id")
    def onchange_partner_id(self):
        res = super().onchange_partner_id()
        purchase_type = self._get_partner_purchase_type()
        if purchase_type:
            self.order_type = purchase_type
        elif not self.order_type:
            self.order_type = self._default_order_type(self.company_id)
        return res

    @api.onchange("order_type")
    def onchange_order_type(self):
        for order in self:
            if order.order_type.payment_term_id:
                order.payment_term_id = order.order_type.payment_term_id.id
            if order.order_type.incoterm_id:
                order.incoterm_id = order.order_type.incoterm_id.id

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if not values.get("order_type"):
                company = (
                    self.env["res.company"].browse(values["company_id"])
                    if values.get("company_id")
                    else self.env.company
                )
                default_type = self._default_order_type(company)
                if default_type:
                    values["order_type"] = default_type.id
            if values.get("name", "/") == "/" and values.get("order_type"):
                purchase_type = self.env["purchase.order.type"].browse(
                    values["order_type"]
                )
                if purchase_type.sequence_id:
                    values["name"] = purchase_type.sequence_id.next_by_id(
                        sequence_date=values.get("date_order")
                    )
        return super().create(vals_list)

    @api.constrains("company_id")
    def _check_po_type_company(self):
        if self.filtered(
            lambda r: r.order_type.company_id
            and r.company_id
            and r.order_type.company_id != r.company_id
        ):
            raise ValidationError(
                self.env._("Document's company and type's company mismatch")
            )

    def _default_order_type(self, company=None):
        company = company or self.company_id or self.env.company
        regular = self.env.ref("purchase_order_type.po_type_regular", raise_if_not_found=False)
        if regular and regular.active and (
            not regular.company_id or not company or regular.company_id == company
        ):
            return regular
        return self.env["purchase.order.type"].search(
            [("company_id", "in", [False, company.id] if company else [False])],
            limit=1,
        )

    @api.onchange("company_id")
    def _onchange_company(self):
        if not self.order_type or (
            self.order_type
            and self.order_type.company_id not in [self.company_id, False]
        ):
            self.order_type = self._default_order_type(self.company_id)

    @api.depends("partner_id", "company_id")
    def _compute_partner_order_type(self):
        for record in self:
            partner_type = record._get_partner_purchase_type() if record.partner_id else False
            if partner_type:
                record.order_type = partner_type
            elif record.order_type and record.order_type.company_id in [record.company_id, False]:
                record.order_type = record.order_type
            else:
                record.order_type = record._default_order_type(record.company_id)
