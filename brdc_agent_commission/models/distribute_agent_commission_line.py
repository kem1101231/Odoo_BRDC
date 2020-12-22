from odoo import api, fields, models, _
from odoo.exceptions import UserError
import time

class distribute_agent_commission_line(models.Model):
    _name = 'distribute.commission_line'
    # _rec_name = 'name'
    _description = 'Monitoring of Distribution of Commission'
    _inherit = ['mail.thread', 'ir.needaction_mixin']

    name = fields.Char()

    agent_id = fields.Many2one('res.partner',string="Agent", domain="[('is_agent', '=', True)]")
    position = fields.Many2one('agent.hierarchy', string="Position", related="agent_id.agency_id")
    date_distributed = fields.Date(string="Date Distributed", )

    sa_temp_commission_line = fields.Many2many('sa.commission.line',
                                               domain="[('is_paid', '=', True),('sales_agent_id', '=', agent_id)"
                                                      ",('is_distributed', '=', False)]")
    um_temp_commission_line = fields.Many2many('um.commission.line',
                                               domain="[('is_paid', '=', True),('unit_manager_id', '=', agent_id)"
                                                      ",('is_distributed', '=', False)]")
    am_temp_commission_line = fields.Many2many('am.commission.line',
                                               domain="[('is_paid', '=', True),('agency_manager_id', '=', agent_id)"
                                                      ",('is_distributed', '=', False)]")

    is_am = fields.Boolean(default=False, store=True,onchange='onchange_agent')
    is_um = fields.Boolean(default=False, store=True,onchange='onchange_agent')
    is_sa = fields.Boolean(default=False, store=True,onchange='onchange_agent')
    is_co = fields.Boolean(default=False, store=True,onchange='onchange_agent')

    @api.onchange('agent_id')
    def onchange_agent(self):
        self.sa_temp_commission_line =[]
        self.um_temp_commission_line =[]
        self.am_temp_commission_line =[]
        if self.agent_id.agency_id.name == "Agency Manager":
            self.is_am = True
        else:
            self.is_am = False
        if self.agent_id.agency_id.name == "Unit Manager":
            self.is_um = True
        else:
            self.is_um = False
        if self.agent_id.agency_id.name == "Sales Agent":
            self.is_sa = True
        else:
            self.is_sa = False
        if self.agent_id.agency_id.name == "Collector":
            self.is_co = True
        else:
            self.is_co = False
        print(self.is_sa,self.is_am,self.is_um,self.is_co)

    state = fields.Selection([
        ('draft', "Draft"),
        ('confirmed', "Confirmed"),
        # ('requested', "Requested"),
        ('distributed', "Distributed"),
    ], default='draft')

    @api.multi
    def action_draft(self):
        self.state = 'draft'
        return {
            "type": "ir.actions.do_nothing",
        }

    @api.multi
    def action_confirm(self):
        self.state = 'confirmed'
        # print self.agent_id.agency_id.name
        # i think in this state the attachments of checks or any proof of payments should happen
        return {
            "type": "ir.actions.do_nothing",
        }

    @api.multi
    def action_distributed(self):
        self.state = 'distributed'
        if self.is_sa:
            for x in range(0,len(self.sa_temp_commission_line)):
                # print self.sa_temp_commission_line[x]
                self.env['sa.commission.line'].search([('id','=',self.sa_temp_commission_line[x].id)]).write({
                            'date_distributed': fields.Date.today(),
                            'is_distributed': True,
                            'distribute_commission_line_id': self.id,
                        })
        elif self.is_um:
            for x in range(0,len(self.um_temp_commission_line)):
                # print self.um_temp_commission_line[x]
                self.env['um.commission.line'].search([('id','=',self.um_temp_commission_line[x].id)]).write({
                            'date_distributed': fields.Date.today(),
                            'is_distributed': True,
                            'distribute_commission_line_id': self.id,
                        })
        elif self.is_am:
            for x in range(0,len(self.am_temp_commission_line)):
                # print self.am_temp_commission_line[x]
                self.env['am.commission.line'].search([('id','=',self.am_temp_commission_line[x].id)]).write({
                            'date_distributed': fields.Date.today(),
                            'is_distributed': True,
                            'distribute_commission_line_id': self.id,
                        })
        com_name = "Distributed commission to " + self.agent_id.name + " as of " + fields.Date.today()
        self.write({
            'date_distributed': fields.Date.today(),
            'name': com_name,
        })
        return {
            "type": "ir.actions.do_nothing",
        }

    @api.multi
    def unlink(self):
        for quo in self:
            if quo.state != 'draft':
                raise UserError(_("Cannot delete confirmed application"))
            return super(distribute_agent_commission_line, self).unlink()
