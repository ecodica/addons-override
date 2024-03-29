# Copyright 2017-18 ForgeFlow S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


class TestMrpProductionRequest(TransactionCase):
    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)
        self.production_model = self.env["mrp.production"]
        self.request_model = self.env["mrp.production.request"]
        self.wiz_model = self.env["mrp.production.request.create.mo"]
        self.bom_model = self.env["mrp.bom"]
        self.group_model = self.env["procurement.group"]
        self.product_model = self.env["product.product"]
        self.bom_model = self.env["mrp.bom"]
        self.boml_model = self.env["mrp.bom.line"]

        self.warehouse = self.env.ref("stock.warehouse0")
        self.stock_loc = self.env.ref("stock.stock_location_stock")
        route_manuf = self.env.ref("mrp.route_warehouse0_manufacture")

        # Prepare Products:
        self.product = self.env.ref("product.product_product_3")
        self.product.mrp_production_request = True
        self.product.route_ids = [(4, route_manuf.id, 0)]

        self.product_no_bom = self.product_model.create(
            {
                "name": "Test Product without BoM",
                "mrp_production_request": True,
                "route_ids": [(6, 0, route_manuf.ids)],
            }
        )
        self.product_orderpoint = self.product_model.create(
            {
                "name": "Test Product for orderpoint",
                "mrp_production_request": True,
                "route_ids": [(6, 0, route_manuf.ids)],
            }
        )
        product_component = self.product_model.create(
            {
                "name": "Test component",
                "mrp_production_request": True,
                "route_ids": [(6, 0, route_manuf.ids)],
            }
        )

        # Create Bill of Materials:
        self.test_bom_1 = self.bom_model.create(
            {
                "product_id": self.product_orderpoint.id,
                "product_tmpl_id": self.product_orderpoint.product_tmpl_id.id,
                "product_uom_id": self.product_orderpoint.uom_id.id,
                "product_qty": 1.0,
                "type": "normal",
            }
        )
        self.boml_model.create(
            {
                "bom_id": self.test_bom_1.id,
                "product_id": product_component.id,
                "product_qty": 1.0,
            }
        )

        # Create Orderpoint:
        self.orderpoint = self.env["stock.warehouse.orderpoint"].create(
            {
                "warehouse_id": self.warehouse.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "product_id": self.product_orderpoint.id,
                "product_min_qty": 10.0,
                "product_max_qty": 50.0,
                "product_uom": self.product_orderpoint.uom_id.id,
            }
        )

        # Create Procurement Group:
        self.test_group = self.group_model.create({"name": "TEST"})

        # Create User:
        self.test_user = self.env["res.users"].create({"name": "John", "login": "test"})

        # Create Workcenter:
        self.workcenter_1 = self.env["mrp.workcenter"].create(
            {
                "name": "Workcenter #1",
                "capacity": 1,
                "time_start": 8,
                "time_stop": 16,
                "time_efficiency": 80,
            }
        )

    def procure(self, group, product, qty=4.0):
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.user.id)], limit=1
        )
        values = {
            "date_planned": fields.Datetime.now(),
            "group_id": group,
            "warehouse_id": warehouse,
        }
        self.group_model.run(
            [
                self.test_group.Procurement(
                    product,
                    qty,
                    product.uom_id,
                    self.stock_loc,
                    group.name,
                    group.name,
                    warehouse.company_id,
                    values,
                )
            ]
        )
        return True

    @mute_logger("odoo.addons.stock.models.stock_rule")
    def _run_scheduler(self):
        self.env["procurement.group"].run_scheduler()

    def test_01_validate_mo_states(self):
        """Tests that all hard-coded manufacturing order states match existing ones"""
        state_field = self.production_model._fields["state"]
        mo_states = [s[0] for s in state_field.selection]
        for state in self.request_model._get_mo_valid_states():
            self.assertIn(state, mo_states)

    def test_02_manufacture_request(self):
        """Tests manufacture request workflow."""
        self.procure(self.test_group, self.product)
        request = self.request_model.search(
            [
                ("product_id", "=", self.product.id),
                ("procurement_group_id", "=", self.test_group.id),
            ]
        )
        self.assertEqual(len(request), 1)
        request.button_to_approve()
        request.button_draft()
        request.button_to_approve()
        request.button_approved()
        self.assertEqual(request.assigned_to, self.env.user)
        self.assertEqual(request.pending_qty, 4.0)
        wiz = self.wiz_model.with_context(
            active_ids=request.ids, active_model="mrp.production.request"
        ).create({})
        wiz.compute_product_line_ids()
        wiz.mo_qty = 4.0
        wiz.create_mo()
        mo = self.production_model.search(
            [("mrp_production_request_id", "=", request.id)]
        )
        self.assertTrue(mo, "No MO created.")
        self.assertEqual(request.pending_qty, 0.0)
        self.assertEqual(self.product.mrp_production_request_count, 1.0)
        request.button_done()

    def test_03_wizard_access(self):
        self.procure(self.test_group, self.product)
        request = self.request_model.search(
            [
                ("product_id", "=", self.product.id),
                ("procurement_group_id", "=", self.test_group.id),
            ]
        )
        request.requested_by = self.test_user
        ctx = {
            "active_ids": [request.id],
            "active_model": request._name,
        }
        with self.assertRaises(AccessError):
            self.wiz_model.with_user(self.test_user).with_context(ctx).create({})
        # give request_user rights on our test user and retry
        self.test_user.groups_id = [
            (4, self.ref("mrp_production_request.group_mrp_production_request_user"))
        ]
        self.test_user.invalidate_cache()
        wizard_id = (
            self.wiz_model.with_user(self.test_user).with_context(ctx).create({})
        )
        self.assertTrue(wizard_id)

    def test_04_assignation(self):
        """Tests assignation of manufacturing requests."""
        random_bom_id = self.bom_model.search([], limit=1).id
        request = self.request_model.create(
            {
                "assigned_to": self.test_user.id,
                "product_id": self.product.id,
                "product_qty": 5.0,
                "bom_id": random_bom_id,
            }
        )
        request._onchange_product_id()
        self.assertEqual(
            request.bom_id.product_tmpl_id,
            self.product.product_tmpl_id,
            "Wrong Bill of Materials.",
        )
        request.write({"assigned_to": self.uid})
        self.assertTrue(request.message_follower_ids, "Followers not added correctly.")

    def test_05_substract_qty_from_orderpoint(self):
        """Quantity in Manufacturing Requests should be considered by
        orderpoints."""
        request = self.request_model.search(
            [("product_id", "=", self.product_orderpoint.id)]
        )
        self.assertFalse(request)
        self._run_scheduler()
        request = self.request_model.search(
            [("product_id", "=", self.product_orderpoint.id)]
        )
        self.assertEqual(len(request), 1)
        # Running again the scheduler should not generate a new MR.
        self._run_scheduler()
        request = self.request_model.search(
            [("product_id", "=", self.product_orderpoint.id)]
        )
        self.assertEqual(len(request), 1)

    def test_06_raise_errors(self):
        """Tests user errors raising properly."""
        with self.assertRaises(UserError):
            # No Bill of Materials:
            self.procure(self.test_group, self.product_no_bom)

    def test_07_manufacture_request_duplicate(self):
        """Ensure that the unique constraint « Reference must be unique per Company! »
        is not raised on duplicate."""
        self.procure(self.test_group, self.product)
        request = self.request_model.search(
            [
                ("product_id", "=", self.product.id),
                ("procurement_group_id", "=", self.test_group.id),
            ]
        )
        request_copy = request.copy()
        self.assertTrue(request_copy)

    def test_08_manufacture_request_workorders(self):
        """Check that if a BoM contains some workorders, they are correctly created in
        the manufacturing orders ."""
        # add two operations on the BoM of our product
        self.test_bom_1.write(
            {
                "operation_ids": [
                    (
                        0,
                        0,
                        {
                            "sequence": 1,
                            "name": "Step 1",
                            "workcenter_id": self.workcenter_1.id,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "sequence": 2,
                            "name": "Step 2",
                            "workcenter_id": self.workcenter_1.id,
                        },
                    ),
                ],
            }
        )
        # manually create a new request
        request = self.request_model.create(
            {
                "assigned_to": self.test_user.id,
                "product_id": self.product_orderpoint.id,
                "bom_id": self.test_bom_1.id,
                "product_uom_id": self.product_orderpoint.uom_id.id,
                "product_qty": 1.0,
            }
        )
        self.assertEqual(len(request), 1)
        # and use the wizard to create the manufacturing order
        ctx = {
            "active_ids": [request.id],
            "active_model": request._name,
        }
        wizard_id = self.wiz_model.with_context(ctx).create({})
        wizard_id.compute_product_line_ids()
        wizard_id.mo_qty = 1.0
        wizard_id.create_mo()
        # check that only one manufacturing order has been created
        self.assertEqual(len(request.mrp_production_ids), 1)
        # check that all steps of our BoM exists in the manufacturing order
        self.assertEqual(len(request.mrp_production_ids.workorder_ids), 2)
