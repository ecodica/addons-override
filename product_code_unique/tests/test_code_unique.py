import psycopg2

# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools.misc import mute_logger

from odoo.addons.base.tests.common import DISABLED_MAIL_CONTEXT


class TestCodeUnique(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, **DISABLED_MAIL_CONTEXT))
        cls.product_obj = cls.env["product.product"]
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "Code Unique Company B"})
        cls.product1 = cls.product_obj.create(
            {
                "name": "Test Product 1",
                "default_code": "TSTP1",
                "company_id": cls.company_a.id,
            }
        )

    def test_01_check_code_other(self):
        product2 = self.product_obj.create(
            {
                "name": "Test Product 2",
                "default_code": "TSTP2",
                "company_id": self.company_a.id,
            }
        )
        self.assertEqual(product2.default_code, "TSTP2")

    def test_02_check_code_unique_same_company(self):
        with self.assertRaises(psycopg2.IntegrityError):
            with mute_logger("odoo.sql_db"), self.cr.savepoint():
                self.product_obj.create(
                    {
                        "name": "Test Product Duplicate Same Co",
                        "default_code": "TSTP1",
                        "company_id": self.company_a.id,
                    }
                )

    def test_03_allow_same_code_different_companies(self):
        product_b = self.product_obj.create(
            {
                "name": "Test Product Company B",
                "default_code": "TSTP1",
                "company_id": self.company_b.id,
            }
        )
        self.assertEqual(product_b.default_code, "TSTP1")
        self.assertEqual(product_b.code_company_id, self.company_b)

    def test_04_forbid_shared_vs_company_collision(self):
        self.product_obj.create(
            {
                "name": "Shared Product",
                "default_code": "TSTPSHARED",
                "company_id": False,
            }
        )
        with self.assertRaises(ValidationError):
            with self.cr.savepoint():
                self.product_obj.create(
                    {
                        "name": "Company Colliding Product",
                        "default_code": "TSTPSHARED",
                        "company_id": self.company_a.id,
                    }
                )
