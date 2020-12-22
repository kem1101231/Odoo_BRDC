from odoo import api, fields, models, _
from datetime import date, datetime,timedelta
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse
# import arrow
from odoo.exceptions import UserError

class IntermentLoanLine(models.Model):
    _name = 'interment.loan.line'
    _order = 'date_for_payment'

    loan_id = fields.Many2one('interment.quotation.request', string='Reference ID', ondelete='cascade', readonly=1)
    # installment_invoice = fields.Many2one('account.invoice',string='Reference ID', ondelete='cascade', readonly=1)

    # @api.multi
    # @api.multi
    # def _compute_payment(self):
    #     for rec in self:
    #         loan_line = rec.env['interment.loan.line']
    #         loan_line_id = loan_line.search([
    #             ('loan_id', '=', rec.loan_id.id)])
    
    display_name = fields.Char(compute='get_name')
    date_for_payment = fields.Date(string='Date of Payment', required=True, readonly=1)
    customer_id = fields.Many2one('res.partner', string='Customer', ondelete='cascade',readonly=1)
    amount_to_pay = fields.Float(string='Amount to Pay', required=True,readonly=1)
    is_paid = fields.Boolean(string='Paid', default=False,readonly=1,compute='_get_payment_id')
    notes = fields.Text()
    payment_term = fields.Many2one('payment.config', string='Payment Terms', domain=[('bpt','=',True)],readonly=1)


    payment_id = fields.Many2one('account.payment',
                                 string='O.R. No',
                                 context={'default_payment_type': 'inbound', 'default_partner_type': 'customer'},
                                 domain=[('state','=','draft'),('partner_type', '=', 'customer')],
                                 # readonly=is_readonly
                                )

    def get_name(self):
        self.display_name = '%s %s' % ((self.payment_id.name + ' ~') if self.payment_id.name else str(self.id) + ' ~',self.loan_id.name)

    partner_id = fields.Char(compute='_get_payment_id', string='Named To')
    paid_amount = fields.Float(string='Paid Amount',compute='_get_payment_id')
    balance = fields.Float(string="Customer's Advanced Payment",compute='_get_payment_id')
    payable_balance = fields.Float(string="Customer's Balance")
    state = fields.Selection([('draft','Draft'),('confirm','Confirm Payment')], default='draft')



    @api.multi
    def read_next_line(self):
        loan_line = self.env['interment.loan.line']
        date_start_str = datetime.strptime(self.date_for_payment, '%Y-%m-%d').date()
        date_start_str = date_start_str + relativedelta(months=1)
        loan_line_id = loan_line.search([
            ('loan_id','=',self.loan_id.id)])
        # print loan_line_id[-1].id
        # print loan_line_id[-1].date_for_payment

        if self.id == loan_line_id[-1].id: # read the last record
            pass
        # elif self.id == loan_line_id[0].id:
        #     next_line_id = loan_line.search([
        #         ('date_for_payment', '=', date_start_str),
        #         ('loan_id', '=', self.loan_id.id)])
        #     for l in next_line_id:
        #         if self.balance:
        #             amount_to_pay = l.amount_to_pay - self.balance
        #             res = l.write({'payable_balance': round(amount_to_pay, 2),
        #                            'notes': '[%s] %.2f is Deducted on the amount to pay for this month.' % (
        #                            l.notes, self.balance)
        #                            })
        #             return res
        else:
            next_line_id = loan_line.search([
                ('date_for_payment', '=', date_start_str),
                ('loan_id', '=', self.loan_id.id)])
            for l in next_line_id:
                if self.balance:
                    amount_to_pay = l.amount_to_pay - self.balance
                    res = l.write({'payable_balance': round(amount_to_pay, 2),
                                   'notes': '[%s] %.2f is Deducted on the amount to pay for this month.' % (
                                       l.notes if l.notes else '', self.balance)
                                   })
                    return res

    @api.multi
    def draft_action(self):
        self.state = 'draft'

    @api.multi
    def confirm_action(self):
        loan_line = self.env['interment.loan.line']
        loan_line_id = loan_line.search([
            ('loan_id', '=', self.loan_id.id)])
        if (self.paid_amount < self.payable_balance) or (self.paid_amount < self.amount_to_pay):
            raise UserError(_('Amount paid is less Than the contract amount to pay.'))
        elif self.id == loan_line_id[-1].id and self.paid_amount > (self.payable_balance + 2):
            raise UserError(_('Last Payment error, payment should be more than the exact amount of the last contract payment'))
        else:
            self.state = 'confirm'
            self.read_next_line()
            payment_ = self.env['account.payment']
            payment_id = payment_.search([('or_series.name','=',self.payment_id.name)])
            payment_id.update({'state':'posted'})


    @api.onchange('payment_id')
    def _get_payment_id(self):
        loan_line = self.env['interment.loan.line']
        for rec in self:
            loan_line_id = loan_line.search([
                ('loan_id', '=', rec.loan_id.id)])
            for res in rec.payment_id:
                rec.partner_id = res.partner_id.name if res.partner_id.name else False
                rec.paid_amount = res.amount if res.amount else False
                rec.is_paid = (rec.payment_id != None)
                rec.update({'is_paid': rec.is_paid})
            for ll_id in loan_line_id:
                if rec.date_for_payment == ll_id[0].date_for_payment:
                    rec.balance = float(rec.paid_amount) - float(rec.amount_to_pay)
                    if rec.balance < 0:
                        rec.balance = 0.00
                    else:
                        rec.balance = float(rec.paid_amount) - float(rec.amount_to_pay)
                # elif rec.date_for_payment == loan_line_dp_id[0].date_for_payment:
                #     rec.balance = float(rec.paid_amount) - float(rec.amount_to_pay)
                #     if rec.balance < 0:
                #         rec.balance = 0.00
                #     else:
                #         rec.balance = float(rec.paid_amount) - float(rec.amount_to_pay)
                else:
                    rec.balance = float(rec.paid_amount) - float(rec.   payable_balance)
                    if rec.balance < 0:
                        rec.balance = 0.00
                    else:
                        rec.balance = float(rec.paid_amount) - float(rec.payable_balance)

                            # rec.payable_balance = round((rec.paid_amount - rec.amount_to_pay), 2)
    @api.one
    def action_paid_amount(self):
        pass
    
class IntermentLoanLineDP(models.Model):
    _name = 'interment.loan.line.dp'
    _inherit = 'interment.loan.line'

    @api.multi
    def read_next_line(self):
        loan_line = self.env['interment.loan.line.dp']
        date_start_str = datetime.strptime(self.date_for_payment, '%Y-%m-%d').date()
        date_start_str = date_start_str + relativedelta(months=1)
        loan_line_id = loan_line.search([
            ('loan_id', '=', self.loan_id.id)])
        print loan_line_id[-1].id
        print loan_line_id[-1].date_for_payment

        if self.id == loan_line_id[-1].id:  # read the last record
            pass
        else:  # if not the last record falls here.
            next_line_id = loan_line.search([
                ('date_for_payment', '=', date_start_str),
                ('loan_id', '=', self.loan_id.id)])
            for l in next_line_id:
                if self.balance:
                    amount_to_pay = l.amount_to_pay - self.balance
                    res = l.write({'amount_to_pay': round(amount_to_pay, 2),
                                   'notes': '[%s] %.2f is Deducted on the amount to pay for this month.' % (
                                   l.notes, self.balance)
                                   })
            return res

    @api.multi
    def draft_action(self):
        self.state = 'draft'

    @api.multi
    def confirm_action_dp(self):
        loan_line = self.env['interment.loan.line.dp']
        loan_line_id = loan_line.search([
            ('loan_id', '=', self.loan_id.id)])
        print loan_line_id[-1].date_for_payment
        if (self.paid_amount < self.payable_balance) or (self.paid_amount < self.amount_to_pay):
            raise UserError(_('Amount paid is less Than the contract amount to pay.'))
        elif self.id == loan_line_id[-1].id and self.paid_amount > (self.amount_to_pay + 2.00):
            raise UserError(_('Last Payment error, payment should be more than the exact amount of the last contract payment'))
        else:
            self.state = 'confirm'
            self.read_next_line()
            payment_ = self.env['account.payment']
            payment_id = payment_.search([('or_series.name', '=', self.payment_id.name)])
            payment_id.update({'state': 'posted'})

