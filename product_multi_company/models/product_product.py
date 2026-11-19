# Copyright 2026 ForgeFlow S.L. (https://www.forgeflow.com)
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, models
from odoo.tools import SQL


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _order_field_to_sql(self, alias, field_name, direction, nulls, query):
        # `company_id` comes from the template, where it is not stored, so skip it
        # in ORDER BY as `multi.company.abstract` does (core sorts on it in EDI import)
        fname = field_name.split(":", 1)[0].split(".", 1)[0]
        field = self._fields.get(fname)
        if fname == "company_id" and field is not None and not field.store:
            return SQL()
        return super()._order_field_to_sql(alias, field_name, direction, nulls, query)

    @api.model_create_multi
    def create(self, vals_list):
        # `company_id` and `company_ids` are related fields to
        # `product.template`, which discards `company_id` on write/create
        # when `company_ids` is also given, to prevent its `inverse` from
        # overwriting `company_ids` (see
        # `MultiCompanyAbstract._multicompany_patch_vals`). `product.product`
        # doesn't inherit that mixin, so replicate the same protection here.
        for vals in vals_list:
            self.env["product.template"]._multicompany_patch_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        self.env["product.template"]._multicompany_patch_vals(vals)
        return super().write(vals)
