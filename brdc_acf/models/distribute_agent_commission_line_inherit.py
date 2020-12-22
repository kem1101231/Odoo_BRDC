from odoo import api, fields, models, _
from datetime import date
from odoo.exceptions import UserError



class AgentCommissionFundMonitor(models.Model):
    _name = 'agent.commission.fund.monitor'
    _order = 'id desc'

    # @api.multi
    # def _get_acf(self):
    #     acf = self.env['brdc.config.settings'].search([])[0]
    #     for s in self:
    #         s.agent_commission_fund = acf.agent_commission_fund

    @api.multi
    def _get_name(self):
        for s in self:
            s.name = 'Fund of Date [%s]' % s.date

    @api.multi
    def _get_amount_line(self):
        for s in self:
            for line in s.DistributeAgentCommissionLine_ids:
                s.total_fund_request += line.total_commission
        self.acf_condition()

    @api.multi
    def _total_commission(self):
        amount = 0.00
        for s in self:
            for line in s.DistributeAgentCommissionLine_ids:
                amount += line.total_commission
            s.total_commission = amount
            s.remaining_fund = s.agent_commission_fund - s.total_commission
    name = fields.Char(string='Name', compute=_get_name)
    date = fields.Date(default=fields.Date.today())
    agent_commission_fund = fields.Float(default=0.00, string='Agent Commission Fund')
    total_fund_request = fields.Float(compute=_get_amount_line, string='Total Amount')

    DistributeAgentCommissionLine_ids = fields.One2many(comodel_name="distribute.commission_line", inverse_name="acfm_id", string="commission line", required=False, )
    has_request = fields.Boolean(default=False)

    @api.multi
    @api.depends('agent_commission_fund','remaining_fund')
    def _get_state(self):
        for s in self:
            if s.agent_commission_fund < 0:
                return 'draft'
            elif s.remaining_fund > 0:
                return 'open'
            elif s.remaining_fund <= 0:
                return 'close'
    state = fields.Selection([('draft','DRAFT'),('open','OPEN'),('close','CLOSE')], default='draft', compute=_get_state)
    total_commission = fields.Float(string='Total Commission', compute=_total_commission)
    remaining_fund = fields.Float(string='Remaining Fund', compute=_total_commission)

    @api.onchange('total_fund_request','agent_commission_fund')
    def _acf_condition(self):
        for s in self:
            if s.agent_commission_fund <= s.total_commission:
                raise UserError(_('Insufficient Fund, please request for replenishment!'))

    @api.multi
    def replenish_request(self):
        config_settings = self.env['brdc.config.settings'].search([])[0]
        print(config_settings.agent_commission_fund)
        request_expense = self.env['request.expense']

        if not request_expense.search([('acfm_id','=',self.id),('state','in',['draft','confirm'])]):
            request_expense.create({
                'name': '[EXP] Agent Commission Fund',
                'acfm_id': self.id,
                'agent_commission_fund': config_settings.agent_commission_fund,
                'produc_id': self._prepare_expense('Agent Commission Fund')
            })
        return {
            'name': 'Expense Request',
            'res_model': 'request.expense',
            'res_id': request_expense.search([('acfm_id','=',self.id),('state','in',['draft','confirm'])]).id,
            'type': 'ir.actions.act_window',
            'target': 'new',
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
        }
    @api.multi
    def _prepare_expense(self,name):
        product = self.env['product.product'].search([('name','=',name)])
        if product:
            return product.id
        else:
            return False
class DistributeAgentCommissionLine(models.Model):
    _inherit = 'distribute.commission_line'

    acfm_id = fields.Many2one('agent.commission.fund.monitor', 'Agent Commission Fund')

    @api.multi
    def request_through(self):
        dacl = self.env['distribute.commission_line'].search([('state', 'not in', ('requested', 'distributed'))])
        acf = self.env['brdc.config.settings'].search([])[0]
        print(acf.agent_commission_fund)

    @api.onchange('position','sa_temp_commission_line','um_temp_commission_line','am_temp_commission_line')
    @api.multi
    def _total_commission(self):
        amount = 0.00
        for s in self:
            if s.is_sa:
                for line in s.sa_temp_commission_line:
                    amount += line.sa_percentage
            elif s.is_um:
                for line in s.um_temp_commission_line:
                    amount += line.um_percentage
            elif s.is_am:
                for line in s.am_temp_commission_line:
                    amount += line.am_percentage
            s.total_commission = amount
            print(s.total_commission)

    total_commission = fields.Float(string='Total Commission', compute=_total_commission)