from odoo import api, fields, models

class sa_commission_line(models.Model):
    _name = 'sa.commission.line'
    _rec_name = 'date_paid'
    _description = 'List of all SA Commissions'

    name = fields.Char(string="No", )
    sa_percentage = fields.Float(default=0,string="Sales Agent Commission")
    agent_commission_id = fields.Many2one('agent.commission','agent_commission_line')
    sales_agent_id = fields.Many2one('res.partner', string="Sales Agent", related="agent_commission_id.sales_agent_id", readonly=True)
    so_id = fields.Many2one('sale.order', string="Sale Order", related="agent_commission_id.so_id")
    pa_ref = fields.Char(string="Purchase Agreement", related='so_id.pa_ref')
    partner_id = fields.Many2one('res.partner', related="so_id.partner_id")

    distribute_commission_line_id = fields.Many2one('distribute.commission_line',string="Reference Distribution")
    is_distributed = fields.Boolean(default=False,string="Is Distributed")
    date_distributed = fields.Date(string="Date distributed")

    invoice_id = fields.Many2one('account.payment', string="Reference Payment")
    is_paid = fields.Boolean(string="Is Paid", default=False)
    date_paid = fields.Date(string="Date Paid")

class um_commission_line(models.Model):
    _name = 'um.commission.line'
    _rec_name = 'date_paid'
    _description = 'List of all UM Commissions'

    name = fields.Char(string="No", )
    um_percentage = fields.Float(default=0,string="Unit Manager Commission")
    agent_commission_id = fields.Many2one('agent.commission','agent_commission_line')
    unit_manager_id = fields.Many2one('res.partner', string="Unit Manager", related="agent_commission_id.unit_manager_id", readonly=True)
    so_id = fields.Many2one('sale.order', string="Sale Order", related="agent_commission_id.so_id")
    pa_ref = fields.Char(string="Purchase Agreement", related='so_id.pa_ref')
    partner_id = fields.Many2one('res.partner', related="so_id.partner_id")

    distribute_commission_line_id = fields.Many2one('distribute.commission_line',string="Reference Distribution")
    is_distributed = fields.Boolean(default=False,string="Is Distributed")
    date_distributed = fields.Date(string="Date distributed")

    invoice_id = fields.Many2one('account.payment', string="Reference Payment")
    is_paid = fields.Boolean(string="Is Paid", default=False)
    date_paid = fields.Date(string="Date Paid")

class am_commission_line(models.Model):
    _name = 'am.commission.line'
    _rec_name = 'date_paid'
    _description = 'List of all AM Commissions'

    name = fields.Char(string="No", )
    am_percentage = fields.Float(default=0,string="Agency Manager Commission")
    agent_commission_id = fields.Many2one('agent.commission','agent_commission_line')
    agency_manager_id = fields.Many2one('res.partner', string="Agency Manager", related="agent_commission_id.agency_manager_id", readonly=True)
    so_id = fields.Many2one('sale.order', string="Sale Order", related="agent_commission_id.so_id")
    pa_ref = fields.Char(string="Purchase Agreement", related='so_id.pa_ref')
    partner_id = fields.Many2one('res.partner', related="so_id.partner_id")

    distribute_commission_line_id = fields.Many2one('distribute.commission_line',string="Reference Distribution")
    is_distributed = fields.Boolean(default=False,string="Is Distributed")
    date_distributed = fields.Date(string="Date distributed")

    invoice_id = fields.Many2one('account.payment', string="Reference Payment")
    is_paid = fields.Boolean(string="Is Paid", default=False)
    date_paid = fields.Date(string="Date Paid")