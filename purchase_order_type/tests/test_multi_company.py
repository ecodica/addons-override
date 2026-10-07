# Ecodica override test: a partner carrying the purchase type of another
# company must not break orders of the current company.
from odoo.tests import Form, common, tagged


@tagged("post_install", "-at_install")
class TestPurchaseOrderTypeMultiCompany(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_1 = cls.env.company
        cls.company_2 = cls.env["res.company"].create({"name": "Other Co (po type)"})
        cls.type_1 = cls.env["purchase.order.type"].create(
            {"name": "Type of company 1", "company_id": cls.company_1.id}
        )
        cls.type_2 = cls.env["purchase.order.type"].create(
            {"name": "Type of company 2", "company_id": cls.company_2.id}
        )
        cls.type_shared = cls.env["purchase.order.type"].create(
            {"name": "Shared type", "company_id": False}
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Supplier with foreign type", "purchase_type": cls.type_2.id}
        )
        cls.env.user.write({"company_ids": [(4, cls.company_2.id)]})
        # The user works in company 1 only: company 2's type is out of reach.
        cls.env_1 = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company_1.id]))

    def test_foreign_type_not_copied_onto_order(self):
        """Picking the partner on a company 1 order neither raises nor sets
        company 2's type."""
        with Form(self.env_1["purchase.order"]) as form:
            form.partner_id = self.env_1["res.partner"].browse(self.partner.id)
            self.assertFalse(form.order_type)
            order = form.save()
        self.assertFalse(order.order_type)
        self.assertEqual(order.company_id, self.company_1)

    def test_compute_ignores_foreign_type(self):
        order = self.env_1["purchase.order"].create(
            {"partner_id": self.partner.id, "company_id": self.company_1.id}
        )
        self.assertFalse(order.order_type)

    def test_own_and_shared_types_still_copied(self):
        self.partner.purchase_type = self.type_1
        with Form(self.env_1["purchase.order"]) as form:
            form.partner_id = self.env_1["res.partner"].browse(self.partner.id)
            self.assertEqual(form.order_type, self.env_1["purchase.order.type"].browse(self.type_1.id))
        self.partner.purchase_type = self.type_shared
        with Form(self.env_1["purchase.order"]) as form:
            form.partner_id = self.env_1["res.partner"].browse(self.partner.id)
            self.assertEqual(form.order_type, self.env_1["purchase.order.type"].browse(self.type_shared.id))

    def test_same_partner_in_its_own_company(self):
        """In company 2 the partner's type applies as before."""
        env_2 = self.env(context=dict(self.env.context, allowed_company_ids=[self.company_2.id, self.company_1.id]))
        with Form(env_2["purchase.order"].with_company(self.company_2)) as form:
            form.partner_id = env_2["res.partner"].browse(self.partner.id)
            self.assertEqual(form.order_type.id, self.type_2.id)
