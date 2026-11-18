def migrate(cr, version):
    """Clean stale pre-split metadata left under stock_package_sscc after the
    GS1/printing/weight extensions moved to stock_package_sscc_gs1 and this
    module reverted to upstream OCA stock_package_sscc."""
    cr.execute(
        """
        SELECT 1
          FROM ir_module_module
         WHERE name = 'stock_package_sscc_gs1'
           AND state IN ('installed', 'to upgrade')
        """
    )
    gs1_installed = bool(cr.fetchone())

    # 1. Stale views (the main failure: view_picking_form_sscc invokes
    #    action_print_sscc_labels which now lives in stock_package_sscc_gs1).
    stale_views = (
        'view_company_form_sscc',
        'view_package_type_form_sscc',
        'view_package_form_sscc',
        'view_picking_form_sscc',
        'report_sscc_label_template',
    )
    cr.execute(
        """
        SELECT id, name, res_id
          FROM ir_model_data
         WHERE module = 'stock_package_sscc'
           AND model = 'ir.ui.view'
           AND name IN %s
        """,
        (stale_views,),
    )
    for imd_id, xname, view_id in cr.fetchall():
        if gs1_installed:
            cr.execute(
                """
                SELECT 1 FROM ir_model_data
                 WHERE module = 'stock_package_sscc_gs1'
                   AND model = 'ir.ui.view'
                   AND name = %s
                """,
                (xname,),
            )
            if not cr.fetchone():
                cr.execute(
                    "UPDATE ir_model_data SET module = 'stock_package_sscc_gs1' WHERE id = %s",
                    (imd_id,),
                )
                continue
        cr.execute("DELETE FROM ir_model_data WHERE id = %s", (imd_id,))
        if view_id:
            cr.execute("DELETE FROM ir_ui_view_custom WHERE ref_id = %s", (view_id,))
            cr.execute("UPDATE ir_ui_view SET inherit_id = NULL WHERE inherit_id = %s", (view_id,))
            cr.execute("DELETE FROM ir_ui_view WHERE id = %s", (view_id,))

    # 2. Stale report action and sequence xmlid.
    cr.execute(
        """
        SELECT id, res_id
          FROM ir_model_data
         WHERE module = 'stock_package_sscc'
           AND model = 'ir.actions.report'
           AND name = 'action_report_sscc_label'
        """
    )
    row = cr.fetchone()
    if row:
        imd_id, rep_id = row
        cr.execute(
            """
            SELECT 1 FROM ir_model_data
             WHERE module = 'stock_package_sscc_gs1'
               AND model = 'ir.actions.report'
               AND name = 'action_report_sscc_label'
            """
        )
        if gs1_installed and not cr.fetchone():
            cr.execute(
                "UPDATE ir_model_data SET module = 'stock_package_sscc_gs1' WHERE id = %s",
                (imd_id,),
            )
        else:
            cr.execute("DELETE FROM ir_model_data WHERE id = %s", (imd_id,))
            if rep_id:
                cr.execute("DELETE FROM ir_act_report_xml WHERE id = %s", (rep_id,))

    cr.execute(
        """
        SELECT id
          FROM ir_model_data
         WHERE module = 'stock_package_sscc'
           AND model = 'ir.sequence'
           AND name = 'seq_stock_package_sscc'
        """
    )
    row = cr.fetchone()
    if row:
        imd_id = row[0]
        cr.execute(
            """
            SELECT 1 FROM ir_model_data
             WHERE module = 'stock_package_sscc_gs1'
               AND model = 'ir.sequence'
               AND name = 'seq_stock_package_sscc'
            """
        )
        if gs1_installed and not cr.fetchone():
            cr.execute(
                "UPDATE ir_model_data SET module = 'stock_package_sscc_gs1' WHERE id = %s",
                (imd_id,),
            )
        else:
            cr.execute("DELETE FROM ir_model_data WHERE id = %s", (imd_id,))

    # 3. Drop stale ir_model_data links for GS1 fields/selections/extra models
    #    (keep DB columns intact so stock_package_sscc_gs1 preserves data if installed later).
    keep_names = (
        'module_stock_package_sscc',
        'model_stock_package',
        'field_stock_package__id',
        'field_stock_package__display_name',
        'field_stock_package__sscc',
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'stock_package_sscc'
           AND name NOT IN %s
        """,
        (keep_names,),
    )
