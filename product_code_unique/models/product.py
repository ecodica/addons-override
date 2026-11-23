# Copyright (C) 2018 - TODAY, Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductProduct(models.Model):
    _inherit = "product.product"

    # Stored technical mirror of product_tmpl_id.company_id so the SQL partial
    # unique index scopes default_code uniqueness per company without touching
    # the _inherits company_id delegation.
    code_company_id = fields.Many2one(
        comodel_name="res.company",
        string="Code Company",
        related="product_tmpl_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )

    # Override: replace global unique(default_code) with per-company partial unique index.
    def init(self):
        super().init()
        self.env.cr.execute(
            """
            UPDATE product_product pp
               SET code_company_id = pt.company_id
              FROM product_template pt
             WHERE pt.id = pp.product_tmpl_id
               AND pp.code_company_id IS DISTINCT FROM pt.company_id
            """
        )
        self.env.cr.execute(
            "ALTER TABLE product_product "
            "DROP CONSTRAINT IF EXISTS product_product_default_code_uniq"
        )
        self.env.cr.execute(
            "DROP INDEX IF EXISTS product_product_default_code_uniq"
        )
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS product_product_default_code_company_uniq
            ON product_product (default_code, COALESCE(code_company_id, 0))
            WHERE default_code IS NOT NULL AND default_code != ''
            """
        )

    # Override: populate code_company_id before INSERT so the SQL partial unique
    # index sees the real company_id immediately rather than NULL pre-recompute.
    @api.model_create_multi
    def create(self, vals_list):
        Template = self.env["product.template"].sudo()
        for vals in vals_list:
            if "code_company_id" not in vals:
                if "company_id" in vals:
                    vals["code_company_id"] = vals["company_id"]
                elif vals.get("product_tmpl_id"):
                    tmpl = Template.browse(vals["product_tmpl_id"])
                    vals["code_company_id"] = tmpl.company_id.id or False
        return super().create(vals_list)

    @api.constrains("default_code", "product_tmpl_id")
    def _check_default_code_unique_per_company(self):
        for product in self.sudo():
            code = product.default_code
            if not code:
                continue
            company = product.product_tmpl_id.company_id
            domain = [
                ("id", "!=", product.id),
                ("default_code", "=", code),
            ]
            if company:
                domain.append(("product_tmpl_id.company_id", "in", [False, company.id]))
            duplicate = self.sudo().with_context(active_test=False).search(domain, limit=1)
            if duplicate:
                raise ValidationError(
                    _(
                        "Internal Reference '%(code)s' must be unique per company!",
                        code=code,
                    )
                )


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.constrains("company_id")
    def _check_variant_default_code_company_unique(self):
        self.mapped("product_variant_ids")._check_default_code_unique_per_company()
