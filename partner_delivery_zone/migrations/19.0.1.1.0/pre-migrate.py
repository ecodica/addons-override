from odoo.tools import SQL, sql


def migrate(cr, version):
    """The delivery zone of a partner is per company now (company-dependent:
    jsonb by company id). What exists so far goes to the main company.

    The ORM cannot turn an integer column into a jsonb one, so the column is
    converted here, before the module loads."""
    column = sql.table_columns(cr, "res_partner").get("delivery_zone_id")
    if not column or column["udt_name"] == "jsonb":
        return
    cr.execute(
        "SELECT res_id FROM ir_model_data"
        " WHERE module = 'base' AND name = 'main_company'"
    )
    company_id = cr.fetchone()[0]
    # a company-dependent many2one has no foreign key
    cr.execute(
        """SELECT conname FROM pg_constraint
            WHERE conrelid = 'res_partner'::regclass AND contype = 'f'
              AND conkey = ARRAY[(SELECT attnum FROM pg_attribute
                                  WHERE attrelid = 'res_partner'::regclass
                                    AND attname = 'delivery_zone_id')]"""
    )
    for (constraint,) in cr.fetchall():
        sql.drop_constraint(cr, "res_partner", constraint)
    cr.execute(
        SQL(
            """ALTER TABLE res_partner
               ALTER COLUMN delivery_zone_id TYPE jsonb USING
               CASE WHEN delivery_zone_id IS NOT NULL
                    THEN jsonb_build_object(%s, delivery_zone_id)
               END""",
            str(company_id),
        )
    )
