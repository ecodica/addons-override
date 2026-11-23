# Copyright (C) 2019 - TODAY, Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


def pre_init_product_code(env):
    env.cr.execute(
        """
        UPDATE product_product
           SET default_code = NULL
         WHERE default_code = ''
        """
    )
    env.cr.execute(
        """
        WITH dup AS (
            SELECT pp.id,
                   ROW_NUMBER() OVER (
                       PARTITION BY pp.default_code, COALESCE(pt.company_id, 0)
                       ORDER BY pp.active DESC, pp.id ASC
                   ) AS rn
              FROM product_product pp
              JOIN product_template pt ON pt.id = pp.product_tmpl_id
             WHERE pp.default_code IS NOT NULL
        )
        UPDATE product_product pp
           SET default_code = 'DEFAULT' || nextval('ir_default_id_seq')
          FROM dup
         WHERE pp.id = dup.id
           AND dup.rn > 1
        """
    )
    return True
