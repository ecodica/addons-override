# Copyright 2018 Sergio Teruel - Tecnativa <sergio.teruel@tecnativa.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import Command, fields, models


class ProductProduct(models.Model):
    _name = "product.product"
    _inherit = ["product.product", "product.cost.security.mixin"]

    # Inherited fields
    standard_price = fields.Float(groups="product_cost_security.group_product_cost")

    # Ensure base.user_admin always has product cost read/edit groups on existing databases.
    def _register_hook(self):
        super()._register_hook()
        admin = self.env.ref("base.user_admin", raise_if_not_found=False)
        edit_grp = self.env.ref("product_cost_security.group_product_edit_cost", raise_if_not_found=False)
        read_grp = self.env.ref("product_cost_security.group_product_cost", raise_if_not_found=False)
        if admin and edit_grp and read_grp and edit_grp not in admin.sudo().group_ids:
            admin.sudo().write({
                "group_ids": [Command.link(read_grp.id), Command.link(edit_grp.id)],
            })
