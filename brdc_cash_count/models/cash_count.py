from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, date


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    account_payment_id = fields.Many2one(comodel_name="account.payment.summary", string="", required=False, )
    check_number = fields.Char(string='Cheque No.')
    bank_id = fields.Many2one('res.bank','Bank')
    check_date = fields.Date(string='Cheque Date')
    is_invisible = fields.Boolean(default=False, compute='if_not_cash')

    cash_cheque_selection = fields.Selection(string="", selection=[('cash', 'Through Cash'), ('cheque', 'Through Cheque'),('bank','Through Bank'), ('gcash','Through GCash')], required=False, default='cash')

    @api.onchange('cash_cheque_selection')
    def if_not_cash(self):
        for s in self:
            s.check_number = None
            s.bank_id = None
            s.check_date = None


class AccountPaymentSummary(models.Model):
    _name = 'account.payment.summary'
    # _inherit = 'account.payment'
    _order = 'date desc, id desc'

    @api.model
    def get_name(self):
        for s in self:
            type_ = None
            if s.journal_type == 'cash':
                type_ = 'CASH'
            else:
                type_ = 'BANK'
            s.name = "%s [%s]" % (s.date, type_) #if (self.date, self.journal_id.name) else False

    name = fields.Char(compute='get_name')
    responsible_id = fields.Many2one(comodel_name="res.users", string="Responsible", default=lambda self: self.env.user)
    date = fields.Date(string="Date", default=fields.Date.today())
    journal_id = fields.Many2one(comodel_name='account.journal', string='Payment Journal',
                                 default=lambda self: self.env['account.journal'].search([('name', '=', 'Cash')])[0].id)
    payment_ids = fields.One2many(comodel_name="account.payment", inverse_name="account_payment_id", string="Payments",
                                  required=False, )
    # compute = "get_payments"
    # cash_count_ids = fields.Many2many(comodel_name="cash.count.config" )
    state = fields.Selection(string="", selection=[('draft', 'Draft'), ('create', 'Cash Count Created'), ], required=False, default='draft')

    # _sql_constraints = [('date_uniq', 'UNIQUE(date,journal_id)', 'Payment Summary Already Exist')]
    journal_type = fields.Selection(string="Type", selection=[('cash', 'Cash'), ('cheque', 'Bank'), ], required=False, default='cash')

    # is_bank = fields.Boolean(default=False, compute='read_journal')
    #
    # @api.onchange('state')
    # @api.depends('journal_id')
    # def read_journal(self):
    #     for s in self:
    #         journal = s.env['account.journal'].search([('type', '=', 'bank')])
    #         for j in journal:
    #             s.is_bank = (s.journal_id == j.id)

    @api.multi
    def unlink(self):
        for s in self:
            if s.state != 'draft':
                raise UserError(_("Cannot delete evaluated application"))
            return super(AccountPaymentSummary, self).unlink()

    @api.multi
    def create_cash_count_form(self):
        self.state = 'create'
        cash_count_obj = self.env['cash.count.config']
        # cash_count_obj = self.pool.get('cash.count.config')
        for s in self:
            print s.journal_type
            docs = s.env['account.payment'].search(
                [('cash_cheque_selection', '=', s.journal_type), ('user_id', '=', s.responsible_id.id), ('state', '!=', s.state)]).filtered(
                lambda rec: rec.payment_date == s.date)
            # print res[0]
            docs.write({
                'account_payment_id': s.id
            })

            cash_count = s.env['cash.count.config']
            cash_count.create({
                'id': s.id,
                'name': s.name,
                'payment_summary_id': s.id,
                'date_of_transaction': s.date,
                'payment_quantity': s.amount_total,
            })
        return True, self.get_denomination(cash_count_obj.search([])[-1].id)

    def get_denomination(self, id):
        for s in self:
            denomination = s.env['cash.count.config.line'].search([('active', '=', True)])
            s.env['cash.count.temp'].search([('cash_config_id', '=', id)]).unlink()
            cash_count_line = s.env['cash.count.temp']

            array = []
            number = 1
            for d_ in denomination:
                array.append(d_.id)
                # print array
                cash_count_line.create({
                    'cash_config_id': id,
                    'cash_config_line_id': array[-1]
                })
                number += 1

    @api.multi
    def action_draft(self):
        for s in self:
            s.state = 'draft'
            cash_count = s.env['cash.count.config'].search([('payment_summary_id', '=', s.id)])
            cash_count.unlink()
            docs = s.env['account.payment'].search([('account_payment_id', '=', s.id)])
            self._cr.execute("""update account_payment as ab
                                set account_payment_id = NULL
                                FROM account_journal as ba
                                           where 
                                           ab.journal_id = ba.id and
                                           ab.cash_cheque_selection = '%s' and
                                           ab.payment_date = '%s' and
                                           ab.user_id = %s and
                                           ab.state = 'posted' and 
                                           ab.payment_type = 'inbound' and
                                           ab.account_payment_id = %s;""" %
                             (s.journal_type, s.date, s.responsible_id.id, s.id))
            self._cr.commit()
            return s.update(
                {
                    'payment_ids': None
                }
            )
            # return {
            #     'type': 'ir.actions.client',
            #     'tag': 'reload',
            # }

    @api.multi
    def action_view_cash_count(self):
        cash_count = self.env['cash.count.config'].search([('payment_summary_id', '=', self.id)])
        return {
            'name': 'Cash Count',
            'res_model': 'cash.count.config',
            'type': 'ir.actions.act_window',
            "res_id": cash_count.id,
            # 'context': {
            #     'default_payment_summary_id': self.id,
            # },
            'target': 'self',
            'domain': [('date_of_transaction', '=', self.date), ('payment_summary_id', '=', self.id)],
            'view_mode': 'form',
            'view_id': False,
            # 'views': [(False, 'tree')],
            'view_type': 'form',
            'nodestroy': True,
            'flags': {'initial_mode': 'edit'},
        }

    @api.onchange('payment_ids')
    def get_total_amount(self):
        # for p_ids in self.payment_ids:
        for s in self:
            s.amount_total = sum(line.amount for line in s.payment_ids)

    amount_total = fields.Float(string='Total', compute=get_total_amount,
                                   track_visibility='always')

    # @api.onchange('responsible_id', 'date', 'journal_id')
    # def get_payments(self):
    #     for p in self:
    #         # p.payment_ids.unlink()
    #         if p.state == 'draft':
    #             docs = p.env['account.payment'].search(['&', ('payment_date', '=', p.date),
    #                                                     ('user_id', '=', p.responsible_id.id),
    #                                                     # ('journal_id', '=', p.journal_id.id),
    #                                                     ('state', '=', 'posted'),
    #                                                     ('payment_type', '=', 'inbound'),
    #                                                     ('account_payment_id', '=', None)])
    #         else:
    #             docs = p.env['account.payment'].search(['&', ('payment_date', '=', p.date),
    #                                                     ('user_id', '=', p.responsible_id.id),
    #                                                     # ('journal_id', '=', p.journal_id.id),
    #                                                     ('state', '=', 'posted'),
    #                                                     ('payment_type', '=', 'inbound'),
    #                                                     ('account_payment_id', '=', p.id)])
    #         array = []
    #         number = 1
    #         if len(docs) < 1:
    #             p.payment_ids = array
    #         else:
    #             for d in range(1, int(len(docs)) + 1):
    #                 for d_ in docs:
    #                     # print number
    #                     array.append(d_.id)
    #                     p.payment_ids = array
    #                     number += 1
    #
    #         # p.payment_ids = array
    #         # return array

    @api.multi
    def preview_report(self):
        for s in self:
                    return s.env['report'].get_action(self, 'brdc_cash_count.daily_payment_summary_report_template')


class CashConfig(models.Model):
    _name = 'cash.count.config'

    name = fields.Char(string='name')
    payment_summary_id = fields.Many2one('account.payment.summary')
    date_of_transaction = fields.Date()
    # is_parent = fields.Boolean(string='Set as Parent', default=0)
    config_line_ids = fields.One2many(comodel_name="cash.count.temp",
                                      inverse_name="cash_config_id",
                                      string="Denominations",
                                      required=False,
                                      )
    payment_quantity = fields.Float(default=0.00, string='Total Payments')
    total_amount = fields.Float(default=0.00, compute='get_total_amount', string='Total Count')
    remaining_balance = fields.Float(default=0.00, string='Balance', compute='compute_remaining_balance')
    state = fields.Selection(string="", selection=[('draft', 'DRAFT'), ('confirm', 'CONFIRMED'), ], default='draft')

    @api.onchange('total_amount')
    def compute_remaining_balance(self):
        for s in self:
            s.remaining_balance = s.total_amount - s.payment_quantity

    @api.multi
    def action_draft(self):
        self.state = 'draft'

    @api.multi
    def action_confirm(self):
        for s in self:
            if s.remaining_balance != 0:
                raise UserError(_('Balance should be 0'))
            else:
                self.state = 'confirm'

    @api.multi
    def print_cash_count(self):
        for s in self:
            return s.env['report'].get_action(self, 'brdc_cash_count.cash_count_report_template')

    @api.onchange('config_line_ids')
    def get_total_amount(self):
        for s in self:
            s.total_amount = sum(line.total_amount for line in s.config_line_ids)


class CashCountLine(models.Model):
    _name = 'cash.count.temp'

    cash_config_id = fields.Many2one('cash.count.config')
    cash_config_line_id = fields.Many2one(comodel_name="cash.count.config.line", string="Coins/Bills", required=False, )
    bill_number = fields.Integer(string='Number of coins/bill', default=0)
    description = fields.Float(compute='get_descrip', string='Value')
    total_amount = fields.Float(string='Total', default=0.00, compute='get_descrip')




    @api.onchange('bill_number')
    @api.depends('cash_config_line_id')
    def get_descrip(self):
        for s in self:
            for ccli in s.cash_config_line_id:
                s.description = ccli.description if ccli.description else 0.00
                s.total_amount = (s.description * s.bill_number) if (s.description * s.bill_number) else 0.00








class CashConfigLine(models.Model):
    _name = 'cash.count.config.line'

    name = fields.Char(string='Denomination')
    description = fields.Float()
    active = fields.Boolean(default=True)
    # cash_config_id = fields.Many2one(comodel_name="cash.count.config", string="", required=False, )


