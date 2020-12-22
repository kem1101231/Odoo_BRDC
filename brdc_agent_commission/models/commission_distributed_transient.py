from odoo import api, fields, models

class commission_distributed_transient(models.TransientModel):
    _name = 'commission.distributed_transient'
    # _rec_name = 'date_paid'
    _description = 'Temporary List of all Commissions Distributed'
    name = fields.Char(string="Name")
    agent_percentage = fields.Float(default=0,string="Agent Commission")
    agent_commission_id = fields.Many2one('agent.commission','agent_commission_line')
    agent_id = fields.Many2one('res.partner', string="Sales Agent",)
    so_id = fields.Many2one('sale.order', string="Sale Order", related="agent_commission_id.so_id")
    pa_ref = fields.Char(string="Purchase Agreement", related="so_id.pa_ref")

    distribute_commission_line_id = fields.Many2one('distribute.commission_line')
    invoice_id = fields.Many2one('account.payment', string="Reference Payment")