# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    "name": "Croatia - OCA version (RRIF 2021 CoA)",
    "description": """
Croatian localisation.
======================

This is the base module to manage the accounting chart for Croatia in Odoo

Description:
Croatian Chart of Accounts (RRIF ver.2021) OCA version
Set of taxes and fiscal positions

File used for this localisation:
https://www.rrif.hr/dok/preuzimanje/Bilanca-2016.pdf
https://www.rrif.hr/dok/preuzimanje/RRIF-RP2021.PDF
https://www.rrif.hr/dok/preuzimanje/RRIF-RP2021-ENG.PDF

""",
    "version": "16.0",
    "author": "Odoo SA, DAJ MI 5, Ecodica",
    'category': 'Accounting/Localizations/Account Charts',

    'depends': [
        'account',
        'base_vat',
        'l10n_multilang',
    ],
    'data': [
        'data/l10n_hr_chart_data.xml',
        'data/account.account.template.csv',
        'data/account.group.template.csv',  # Account groups full structure for analytic
        'data/account.tax.group.csv',
        'data/account_chart_tag_data.xml',
        'data/account_tax_report_data.xml',
        'data/account_tax_template_data.xml',
        'data/account_tax_fiscal_position_data.xml',
        'data/account_chart_template_data.xml',
        'views/res_company_view.xml',
    ],
    'demo': [
        'demo/demo_company.xml',
    ],
    'license': 'LGPL-3',
}
