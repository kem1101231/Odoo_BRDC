# -*- coding: utf-8 -*-
{
    'name': "Agent Commissions",

    'summary': """
        Commission """,

    'description': """
        ya-da-ya-da
    """,

    'author': "MGC",
    'website': "http://www.mutigroup.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'brdc_account', 'brdc_inventory'],

    # always loaded
    'data': [
        'views/agent_hierarchy.xml',
        'views/agent_commission.xml',
        'views/agent_commission_line.xml',
        'views/init_config.xml',
        # 'views/inherited_account_invoice_form.xml',
        'views/inherited_res_partner.xml',
        'views/inherited_sale_order_form.xml',
        'views/distribute_agent_commission_line.xml',
        'views/commission_distributed_handler.xml',
        'reports/commission_distributed_report.xml',
        'reports/distribute_commission_line_report.xml',
        # 'reports/commission_voucher_report.xml',

        'views/register_commission_payment.xml',
        'views/menuitems.xml',
        'security/ir.model.access.csv',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}