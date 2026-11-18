# Copyright 2023 Onestein (<https://www.onestein.eu>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import Form
from odoo.tests.common import new_test_user

from odoo.addons.base.tests.common import BaseCommon


class TestProductCostSecurity(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Prevent errors when the stock module is installed
        # and attempting to change standard_price
        # Without this flag in the context,
        # the system tries to access stock.move, which the user may not have permission.
        cls.env = cls.env(context=dict(cls.env.context, disable_auto_svl=True))
        cls.base_group_user_id = cls.env.ref("base.group_user").id
        cls.product_edit_cost_group_id = cls.env.ref(
            "product_cost_security.group_product_edit_cost"
        ).id
        cls.product_cost_group_id = cls.env.ref(
            "product_cost_security.group_product_cost"
        ).id
        cls.product_template_model = cls.env["product.template"]
        cls.env.user.write(
            {"group_ids": [Command.set(cls.env.ref("base.group_system").ids)]}
        )

    def test_without_access_to_product_costs_group(self):
        sheet_form = Form(self.product_template_model.with_user(self.env.user))
        sheet_form.name = "Test Product"
        sheet_form.save()
        with self.assertRaises(AssertionError):
            # It would raise an AssertionError as the field would not be found
            # in the view as the user does not have the group- Access to
            # product costs
            standard_price = sheet_form.standard_price
            self.assertEqual(standard_price, 0.0)

    def test_with_access_to_product_costs_group(self):
        self.env.user.group_ids = [
            Command.set([self.product_cost_group_id, self.base_group_user_id])
        ]
        sheet_form = Form(self.product_template_model.with_user(self.env.user))
        sheet_form.name = "Test Product"
        sheet_form.save()
        standard_price = (
            sheet_form.standard_price
        )  # It would not raise any error now as the user
        # has the required group to view the costs
        self.assertEqual(standard_price, 0.0)

    def test_without_access_to_modify_product_costs_group(self):
        sheet_form = Form(self.product_template_model.with_user(self.env.user))
        sheet_form.name = "Test Product"
        sheet_form.save()
        with self.assertRaises(AssertionError):
            # It would raise an AssertionError as the field is readonly in the view
            # as the user does not have the group- Modify product costs
            sheet_form.standard_price = 5.0

    def test_with_access_to_modify_product_costs_group(self):
        self.env.user.group_ids = [
            Command.set([self.product_edit_cost_group_id, self.base_group_user_id])
        ]
        sheet_form = Form(self.product_template_model.with_user(self.env.user))
        sheet_form.name = "Test Product"
        sheet_form.save()
        sheet_form.standard_price = 5.0  # It would not raise any error now as the user
        # has the required group to modify the costs
        self.assertEqual(sheet_form.standard_price, 5.0)

    def test_api_modification(self):
        """Test that a direct API call respects the security groups."""
        # Using base.group_system because it's the only group in this module's
        # dependency graph with CRUD access to products
        editor = new_test_user(
            self.env,
            "editor",
            groups="base.group_system,product_cost_security.group_product_edit_cost",
        )
        reader = new_test_user(
            self.env,
            "reader",
            groups="base.group_system,product_cost_security.group_product_cost",
        )
        user = new_test_user(self.env, "user", groups="base.group_system")
        # Editor can write and read
        product = (
            self.env["product.product"]
            .with_user(editor)
            .create(
                {
                    "name": "Test product",
                    "standard_price": 10.0,
                }
            )
        )
        self.assertEqual(
            product.read(["standard_price"]),
            [{"id": product.id, "standard_price": 10.0}],
        )
        product.standard_price = 20.0
        self.assertEqual(
            product.read(["standard_price"]),
            [{"id": product.id, "standard_price": 20.0}],
        )
        # Reader can read but not write
        product = product.with_user(reader)
        with self.assertRaises(AccessError):
            product.standard_price = 30.0
        self.assertEqual(
            product.read(["standard_price"]),
            [{"id": product.id, "standard_price": 20.0}],
        )
        # User can't read or write (standard Odoo when setting field groups)
        product = product.with_user(user)
        with self.assertRaises(AccessError):
            product.standard_price = 30.0
        with self.assertRaises(AccessError):
            product.read(["standard_price"])
        # Sudo still works
        product.sudo().standard_price = 30.0
        self.assertEqual(
            product.sudo().read(["standard_price"]),
            [{"id": product.id, "standard_price": 30.0}],
        )

    def test_view_patch_strips_standard_price_references_for_non_cost_users(self):
        """Non-cost users get clean seller_ids context and scoped expense span."""
        from lxml import etree

        View = self.env["ir.ui.view"]
        xml = etree.fromstring(
            """<form model_access_rights="product.template">
                <span class="d-flex w-50 ms-2" invisible="standard_price == 0"/>
                <field name="seller_ids" context="{'default_product_tmpl_id': id, 'default_price': standard_price, 'product_template_invisible_variant': True}"/>
                <field name="variant_seller_ids" context="{'model': 'product.product', 'active_id': id, 'default_price': standard_price}"/>
            </form>"""
        )
        View._pcs_patch_product_cost_nodes(xml, "product.template", strip_default_price=True)
        span = xml.find("span")
        self.assertEqual(span.get("groups"), "product_cost_security.group_product_cost")
        for fname in ("seller_ids", "variant_seller_ids"):
            ctx = xml.find(f"field[@name='{fname}']").get("context")
            self.assertNotIn("standard_price", ctx)
            # Must stay valid Python dict syntax
            eval(ctx, {"id": 1})

        purch_group = self.env.ref("purchase.group_purchase_user", raise_if_not_found=False)
        if purch_group:
            user = new_test_user(
                self.env,
                "purch_no_cost_user",
                groups=f"base.group_user,{purch_group.get_external_id()[purch_group.id]},product.group_product_manager",
            )
            partner = self.env["res.partner"].create({"name": "PCS Vendor"})
            form = Form(self.product_template_model.with_user(user))
            form.name = "Vendor Without Cost"
            with form.seller_ids.new() as s:
                s.partner_id = partner
                self.assertEqual(s.price, 0.0)
