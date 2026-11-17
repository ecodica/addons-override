from odoo.tools import SQL, sql


def migrate(cr, version):
    """The delivery time windows belong to a company now and the delivery
    preference of a partner is per company (company-dependent: jsonb by
    company id). What exists so far goes to the main company.

    The ORM cannot turn a varchar column into a jsonb one, so the partner
    column is converted here, before the module loads."""
    cr.execute(
        "SELECT res_id FROM ir_model_data"
        " WHERE module = 'base' AND name = 'main_company'"
    )
    company_id = cr.fetchone()[0]

    if not sql.column_exists(cr, "partner_delivery_time_window", "company_id"):
        sql.create_column(cr, "partner_delivery_time_window", "company_id", "int4")
    cr.execute(
        SQL(
            "UPDATE partner_delivery_time_window SET company_id = %s"
            " WHERE company_id IS NULL",
            company_id,
        )
    )

    column = sql.table_columns(cr, "res_partner").get("delivery_time_preference")
    if column and column["udt_name"] != "jsonb":
        sql.drop_not_null(cr, "res_partner", "delivery_time_preference")
        cr.execute(
            SQL(
                """ALTER TABLE res_partner
                   ALTER COLUMN delivery_time_preference TYPE jsonb USING
                   CASE WHEN delivery_time_preference IS NOT NULL
                        THEN jsonb_build_object(%s, delivery_time_preference)
                   END""",
                str(company_id),
            )
        )
