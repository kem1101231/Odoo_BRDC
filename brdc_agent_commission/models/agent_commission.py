
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class agent_commission(models.Model):
    _name = 'agent.commission'
    _rec_name = 'pa_ref'
    _description = 'List of agent Commission'
    _inherit = ['mail.thread', 'ir.needaction_mixin']

    # name = fields.Char()
    so_id = fields.Many2one('sale.order', string="Sale No", readonly=True)
    pa_ref = fields.Char(string="Purchase Agreement", related='so_id.pa_ref')
    # currency_id = fields.Many2one('res.currency', related='so_id.currency_id')
    currency_id = fields.Many2one('res.currency', default = lambda self: self.env.user.company_id.currency_id)

    sales_agent_id = fields.Many2one('res.partner', string="Sales Agent", readonly=True, related="so_id.agent_id", required=True)
    unit_manager_id = fields.Many2one('res.partner', string="Unit Manager", readonly=True, related="so_id.um_id")
    agency_manager_id = fields.Many2one('res.partner', string="Agency Manager", readonly=True, related="so_id.am_id")

    # ref_name = fields.Char(string="Ref No", related='so_id.name', store=False)
    # sales_agent_name = fields.Char(string="Sales Agent", related='sales_agent_id.name', store=False)
    # unit_manager_name = fields.Char(string="Unit Manager", related='unit_manager_id.name', store=False)
    # agent_manager_name = fields.Char(string="Agent Manager", related='agency_manager_id.name', store=False)
    confirmation_date = fields.Datetime(string="Confirmation Date", related='so_id.confirmation_date')
    partner_id = fields.Many2one(string="Customer", related='so_id.partner_id')
    contract_price = fields.Monetary(string="Contract Price", related='so_id.amount_total', store=False)
    selling_price = fields.Float(string="Selling Price", related='so_id.order_line.price_unit', store=False)

    sa_comm = fields.Monetary(string="Sales Agent Commission", readonly=True)
    um_comm = fields.Monetary(string="Unit Manager Commission", readonly=True)
    am_comm = fields.Monetary(string="Agency Manager Commission", readonly=True)

    sa_ded = fields.Monetary(string="Sales Agent Deduction")
    um_ded = fields.Monetary(string="Unit Manager Deduction")
    am_ded = fields.Monetary(string="Agency Manager Deduction")

    f_sa_comm = fields.Monetary(compute='deduct_comm')
    f_um_comm = fields.Monetary(compute='deduct_comm')
    f_am_comm = fields.Monetary(compute='deduct_comm')

    # w_sa_comm = fields.Monetary(string="Sales Agent Commission", )
    # w_um_comm = fields.Monetary(string="Unit Manager Commission", )
    # w_am_comm = fields.Monetary(string="Agency Manager Commission", )

    w_sa_comm = fields.Monetary(string="Sales Agent Commission", related='f_sa_comm')
    w_um_comm = fields.Monetary(string="Unit Manager Commission", related='f_um_comm')
    w_am_comm = fields.Monetary(string="Agency Manager Commission", related='f_am_comm')
    # @api.model
    # def create(self, values):
    sa_commission_line = fields.One2many('sa.commission.line','agent_commission_id')
    um_commission_line = fields.One2many('um.commission.line','agent_commission_id')
    am_commission_line = fields.One2many('am.commission.line','agent_commission_id')


    @api.constrains('sa_ded', 'um_ded', 'am_comm')
    def _check_deductions(self):
        for record in self:
            print(record.sa_ded)
            if record.sa_ded > self.sa_comm:
                raise ValidationError("Deduction is Greater than Commission Payable")
            elif record.um_ded > self.um_comm:
                raise ValidationError("Deduction is Greater than Commission Payable")
            elif record.am_ded > self.am_comm:
                raise ValidationError("Deduction is Greater than Commission Payable")

    @api.onchange('sa_ded', 'um_ded', 'am_comm')
    def deduct_comm(self):
        self.f_sa_comm = self.sa_comm
        self.f_um_comm = self.um_comm
        self.f_am_comm = self.am_comm
        # if self.sa_ded < self.sa_comm:
        self.f_sa_comm = self.f_sa_comm - self.sa_ded
        self.f_um_comm = self.f_um_comm - self.um_ded
        self.f_am_comm = self.f_am_comm - self.am_ded
        # else:
        #     return {
        #         'warning': {
        #             'title': "Error",
        #             'message': "Deduction is Greater than Commission Payable",
        #         }
        #     }
        # if self.um_ded > self.f_um_comm:
        #     raise ValidationError("Deduction is Greater than Commission Payable")
        # else:
        # if self.am_ded > self.f_am_comm:
        #     raise ValidationError("Deduction is Greater than Commission Payable")
        # else:

        # self.w_sa_comm = self.f_sa_comm
        # self.w_um_comm = self.f_um_comm
        # self.w_am_comm = self.f_am_comm
    def compute_commission_manually(self):
        if self.contract_price < self.selling_price:
            self.sa_comm = (self.contract_price * (self.sales_agent_id.agency_id.comm_percent / 100)) * ((100-self.sales_agent_id.agency_id.withholding_tax) / 100)
            self.um_comm = (self.contract_price * (self.unit_manager_id.agency_id.comm_percent / 100)) * ((100-self.sales_agent_id.agency_id.withholding_tax) / 100)
            self.am_comm = (self.contract_price * (self.agency_manager_id.agency_id.comm_percent / 100)) * ((100-self.sales_agent_id.agency_id.withholding_tax) / 100)
        elif self.selling_price < self.contract_price:
            self.sa_comm = (self.selling_price * (self.sales_agent_id.agency_id.comm_percent / 100)) * ((100-self.sales_agent_id.agency_id.withholding_tax) / 100)
            self.um_comm = (self.selling_price * (self.unit_manager_id.agency_id.comm_percent / 100)) * ((100-self.sales_agent_id.agency_id.withholding_tax) / 100)
            self.am_comm = (self.selling_price * (self.agency_manager_id.agency_id.comm_percent / 100)) * ((100-self.sales_agent_id.agency_id.withholding_tax) / 100)
        else:
            self.sa_comm = (self.selling_price * (self.sales_agent_id.agency_id.comm_percent / 100)) * ((100-self.sales_agent_id.agency_id.withholding_tax) / 100)
            self.um_comm = (self.selling_price * (self.unit_manager_id.agency_id.comm_percent / 100)) * ((100-self.sales_agent_id.agency_id.withholding_tax) / 100)
            self.am_comm = (self.selling_price * (self.agency_manager_id.agency_id.comm_percent / 100)) * ((100-self.sales_agent_id.agency_id.withholding_tax) / 100)
        # print self.env['sa.commission.line'].search_count([('agent_commission_id', '=', self.id)])
        print self.sa_comm, self.um_comm, self.am_comm
        commission_divider = self.env['sa.commission.line'].search_count([('agent_commission_id', '=', self.id)])
        for x in range(1, commission_divider + 1):
            self.env['sa.commission.line'].search([('agent_commission_id', '=', self.id)])[x-1].write({
                'sa_percentage': self.sa_comm / commission_divider,
            })
        for x in range(1, commission_divider + 1):
            self.env['um.commission.line'].search([('agent_commission_id', '=', self.id)])[x-1].write({
                'um_percentage': self.um_comm / commission_divider,
            })
        for x in range(1, commission_divider + 1):
            self.env['am.commission.line'].search([('agent_commission_id', '=', self.id)])[x-1].write({
                'am_percentage': self.am_comm / commission_divider,
            })


    @api.depends('sales_agent_id')
    @api.onchange('sales_agent_id')
    def compute_commission(self):
        # print self.sales_agent_id,self.unit_manager_id,self.agency_manager_id
        # print self.unit_manager_id, self.agency_manager_id, self.contract_price
        # if self.contract_price < self.selling_price:
        #     self.sa_comm = self.contract_price * (self.sales_agent_id.agency_id.comm_percent / 100)
        #     self.um_comm = self.contract_price * (self.unit_manager_id.agency_id.comm_percent / 100)
        #     self.am_comm = self.contract_price * (self.agency_manager_id.agency_id.comm_percent / 100)
        # elif self.selling_price < self.contract_price:
        #     self.sa_comm = self.selling_price * (self.sales_agent_id.agency_id.comm_percent / 100)
        #     self.um_comm = self.selling_price * (self.unit_manager_id.agency_id.comm_percent / 100)
        #     self.am_comm = self.selling_price * (self.agency_manager_id.agency_id.comm_percent / 100)
        # else:
        #     self.sa_comm = self.selling_price * (self.sales_agent_id.agency_id.comm_percent / 100)
        #     self.um_comm = self.selling_price * (self.unit_manager_id.agency_id.comm_percent / 100)
        #     self.am_comm = self.selling_price * (self.agency_manager_id.agency_id.comm_percent / 100)
        if self.contract_price < self.selling_price:
            self.sa_comm = (self.contract_price * (self.sales_agent_id.agency_id.comm_percent / 100)) * (
            (100 - self.sales_agent_id.agency_id.withholding_tax) / 100)
            self.um_comm = (self.contract_price * (self.unit_manager_id.agency_id.comm_percent / 100)) * (
            (100 - self.sales_agent_id.agency_id.withholding_tax) / 100)
            self.am_comm = (self.contract_price * (self.agency_manager_id.agency_id.comm_percent / 100)) * (
            (100 - self.sales_agent_id.agency_id.withholding_tax) / 100)
        elif self.selling_price < self.contract_price:
            self.sa_comm = (self.selling_price * (self.sales_agent_id.agency_id.comm_percent / 100)) * (
            (100 - self.sales_agent_id.agency_id.withholding_tax) / 100)
            self.um_comm = (self.selling_price * (self.unit_manager_id.agency_id.comm_percent / 100)) * (
            (100 - self.sales_agent_id.agency_id.withholding_tax) / 100)
            self.am_comm = (self.selling_price * (self.agency_manager_id.agency_id.comm_percent / 100)) * (
            (100 - self.sales_agent_id.agency_id.withholding_tax) / 100)
        else:
            self.sa_comm = (self.selling_price * (self.sales_agent_id.agency_id.comm_percent / 100)) * (
            (100 - self.sales_agent_id.agency_id.withholding_tax) / 100)
            self.um_comm = (self.selling_price * (self.unit_manager_id.agency_id.comm_percent / 100)) * (
            (100 - self.sales_agent_id.agency_id.withholding_tax) / 100)
            self.am_comm = (self.selling_price * (self.agency_manager_id.agency_id.comm_percent / 100)) * (
            (100 - self.sales_agent_id.agency_id.withholding_tax) / 100)

        self.divide_commissions()
        # self.f_sa_comm = self.sa_comm
        # self.f_um_comm = self.um_comm
        # self.f_am_comm = self.am_comm
        # print self.sa_comm, self.um_comm, self.am_comm
        # return super(agent_commission, self).create(values)
    @api.depends('agent_commission_line')
    def divide_commissions(self):
        # print self.env['sale.order'].search([('id', '=', self.so_id.id)]).purchase_term
        if self.so_id:
            if self.env['sale.order'].search([('id', '=', self.so_id.id)]).purchase_term == 'cash':
                div_range = 1
            elif self.env['sale.order'].search([('id', '=', self.so_id.id)]).purchase_term == 'install':
                if self.env['sale.order'].search([('id', '=', self.so_id.id)]).new_payment_term_id.no_months >= 60:
                    div_range = 18
                else:
                    if self.env['sale.order'].search([('id', '=', self.so_id.id)]).is_split:
                        div_range = 4
                    else:
                        div_range = 1

            for x in range(0,div_range):
                # print self.sa_comm / 18
                name = "(" + str(x+1) + "/" + str(div_range) + ")"
                sa_line_id = self.env['sa.commission.line'].create({
                    'agent_commission_id': self.id,
                    'sa_percentage': self.sa_comm / div_range,
                    'is_distributed': False,
                    'name': name,
                })
                um_line_id = self.env['um.commission.line'].create({
                    'agent_commission_id': self.id,
                    'um_percentage': self.um_comm / div_range,
                    'is_distributed': False,
                    'name': name,
                })
                am_line_id = self.env['am.commission.line'].create({
                    'agent_commission_id': self.id,
                    'am_percentage': self.am_comm / div_range,
                    'is_distributed': False,
                    'name': name,
                })
        else:
            pass


        # if self.so_id:
        #     if self.env['sale.order'].search([('id', '=', self.so_id.id)]).purchase_term == 'cash':
        #         div_range = 1
        #     elif self.env['sale.order'].search([('id', '=', self.so_id.id)]).purchase_term == 'install':
        #         if self.env['sale.order'].search([('id', '=', self.so_id.id)]).new_payment_term_id.no_months < 18:
        #             if self.env['sale.order'].search([('id', '=', self.so_id.id)]).is_split:
        #                 div_range = 4
        #             else:
        #                 div_range = 1
        #         else:
        #             div_range = 18


class AccountAgentCommission(models.Model):
    _inherit = 'account.agent.commission'

    position_id = fields.Many2one('agent.hierarchy', 'position', related='agent_id.agency_id')