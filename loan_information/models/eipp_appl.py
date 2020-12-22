from odoo import api, fields, models, _
from datetime import date, datetime,timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError


class eippApplication(models.Model):
    _inherit = 'eipp.application'

    eipp_purchase_term = fields.Selection([('install', 'Installment'), ('cash', 'Cash')], 'Purchase Term',
                                          default='install')
    date_of_application = fields.Date(default=fields.Date.today(), string='Date Applied')
    eipp_start_payment_date = fields.Date(string='Start Date', required=1)
    eipp_price_list = fields.Many2one('product.pricelist', string='Price List')
    eipp_product = fields.Many2one('product.product', string='Product',
                                   domain=[('type', '=', 'service'), ('sale_ok', '=', 'True')])
    eipp_selling_price = fields.Float(default=0.00, string='Price')
    eipp_payment_term = fields.Many2one('payment.config',
                                        domain=[('name','ilike','%EIPP ')],
                                        default=lambda self: self.env['payment.config'].search([('name','ilike','%EIPP ')])[0].id
                                        )

    total_amount = fields.Float(string="Total Amount", readonly=True, compute='_get_amount')
    total_paid_amount = fields.Float(string='Total Paid Amount', compute='_get_amount')
    balance_amount = fields.Float(string='Balance Amount', compute='_get_amount')

    @api.multi
    def _get_amount(self):
        total_paid_amount = 0.00
        compute_total_amount = 0.00
        for loan in self:
            for line in loan.eipp_loan_line:
                if line.is_paid == True:
                    total_paid_amount =+ line.paid_amount
                compute_total_amount += line.amount_to_pay
            bal_amount = (compute_total_amount) - (total_paid_amount)

            loan.total_amount = round(compute_total_amount, 2)
            loan.balance_amount = round(bal_amount, 2)
            loan.total_paid_amount = round(total_paid_amount, 2)




    eipp_monthly_payment = fields.Float(string='Monthly Payment', compute='onchange_for_monthly')
    eipp_loan_line = fields.One2many(comodel_name="eipp.loan.line", inverse_name="eipp_loan_id", string="Loan Line", required=False, )

    @api.onchange('eipp_price_list', 'eipp_product')
    def onchange_for_price(self):

        pricelist_item = self.env['product.pricelist.item'].search([('pricelist_id', '=', self.eipp_price_list.id),
                                                                    ('product_tmpl_id', '=', self.eipp_product.id)])
        # if self.eipp_payment_plan == 'week_e':
        #     paymen_con = self.env['payment.config']
        #     payment_week_e = paymen_con.search([('name', '=', 'weekend EIPP')])
        #     self.eipp_selling_price = pricelist_item.fixed_price * payment_week_e.less_perc
        # else:
        self.eipp_selling_price = pricelist_item.fixed_price

    @api.onchange('eipp_payment_term','eipp_payment_plan','eipp_price_list','eipp_product','eipp_selling_price')
    def onchange_for_monthly(self):
        eipp_12 = self.env['payment.config'].search([('name','like','%EIPP 12')])
        # print self.eipp_payment_term.id
        # print eipp_12.id
        if self.eipp_payment_term.id == eipp_12.id:
            self.eipp_monthly_payment = self.eipp_selling_price / self.eipp_payment_term.no_months
        else:
            self.eipp_monthly_payment = (self.eipp_selling_price * self.eipp_payment_term.less_perc) / self.eipp_payment_term.no_months

    @api.multi
    def compute_eipp_loan_line(self):
        eipp_loan_line = self.env['eipp.loan.line']
        eipp_loan_line.search([('eipp_loan_id','=', self.id)]).unlink()
        spotcash = self.env['payment.config'].search([('name', '=', 'spotcash')])

        for loan in self:
            loan.refresh()
            date_start_str = datetime.strptime(loan.eipp_start_payment_date, '%Y-%m-%d')
            # date_start_str = date_start_str + relativedelta(months=1)
            counter = 1
            if loan.eipp_purchase_term == 'cash':
                amount_per_time = loan.eipp_selling_price
                for i in range(1, 1 + 1):
                    line_id = eipp_loan_line.create({
                        'date_for_payment': date_start_str,
                        'amount_to_pay': amount_per_time,
                        'customer_id': loan.customer_id.id,
                        'eipp_loan_id': loan.id,
                        'payment_term': spotcash.id})
                    counter += 1
                    date_start_str = date_start_str + relativedelta(months=1)
            else:
                amount_per_time = loan.eipp_monthly_payment
                for i in range(1, loan.eipp_payment_term.no_months + 1):
                    line_id = eipp_loan_line.create({
                        'date_for_payment': date_start_str,
                        'amount_to_pay': amount_per_time,
                        'customer_id': loan.customer_id.id,
                        'eipp_loan_id': loan.id,
                        'payment_term': loan.eipp_payment_term.id})
                    counter += 1
                    date_start_str = date_start_str + relativedelta(months=1)
        return True

class EIPPLoanLine(models.Model):
    _name = 'eipp.loan.line'
    # _inherit = 'interment.loan.line'
    _order = 'date_for_payment'

    eipp_loan_id = fields.Many2one('eipp.application',string='Reference ID',ondelete='cascade', readonly=1)

    display_name = fields.Char(compute='get_name')
    date_for_payment = fields.Date(string='Date of Payment', required=True, readonly=1)
    customer_id = fields.Many2one('res.partner', string='Customer', ondelete='cascade', readonly=1)
    amount_to_pay = fields.Float(string='Amount to Pay', required=True, readonly=1)
    is_paid = fields.Boolean(string='Paid', default=False, readonly=1,
                             compute='_get_payment_id'
                             )
    notes = fields.Text()
    payment_term = fields.Many2one('payment.config', string='Payment Terms', domain=[('bpt', '=', True)], readonly=1)

    payment_id = fields.Many2one('account.payment',
                                 string='O.R. No',
                                 context={'default_payment_type': 'inbound', 'default_partner_type': 'customer'},
                                 domain=[('state', '=', 'draft'), ('partner_type', '=', 'customer')],
                                 # readonly=is_readonly
                                 )
    def get_name(self):
        self.display_name = '%s %s' % ((self.payment_id.name + ' ~') if self.payment_id.name else str(self.id) + ' ~',self.eipp_loan_id.name)

    partner_id = fields.Char(
        compute='_get_payment_id',
        string='Named To'
    )
    paid_amount = fields.Float(string='Paid Amount',
                               compute='_get_payment_id'
                               )
    balance = fields.Float(string="Customer's Advanced Payment",
                           compute='_get_payment_id'
                           )
    payable_balance = fields.Float(string="Customer's Balance")
    state = fields.Selection([('draft','Draft'),('confirm','Confirm Payment')], default='draft')

    @api.onchange('payment_id')
    def _get_payment_id(self):
        loan_line = self.env['eipp.loan.line']
        for rec in self:
            loan_line_id = loan_line.search([
                ('eipp_loan_id', '=', rec.eipp_loan_id.id)])
            for res in rec.payment_id:
                rec.partner_id = res.partner_id.name if res.partner_id.name else False
                rec.paid_amount = res.amount if res.amount else False
                rec.is_paid = (rec.payment_id != None)
                rec.update({'is_paid': rec.is_paid})
                print '%s yea1' % rec.date_for_payment
                print '%s' % loan_line_id[0].date_for_payment
            # for ll_id in loan_line_id:
                # print '%s yea1' % rec.date_for_payment
                # print '%s' % ll_id[0].date_for_payment
            if rec.date_for_payment == loan_line_id[0].date_for_payment:
                rec.balance = float(rec.paid_amount) - float(rec.amount_to_pay)
                if rec.balance < 0:
                    rec.balance = 0.00
                else:
                    rec.balance = float(rec.paid_amount) - float(rec.amount_to_pay)
            else:
                rec.balance = float(rec.paid_amount) - float(rec.payable_balance)
                if rec.balance < 0:
                    rec.balance = 0.00
                else:
                    rec.balance = float(rec.paid_amount) - float(rec.payable_balance)

    @api.multi
    def confirm_action(self):
        loan_line = self.env['eipp.loan.line']
        loan_line_id = loan_line.search([
            ('eipp_loan_id', '=', self.eipp_loan_id.id)])
        count_loan_line = self.env['eipp.loan.line'].search_count([('eipp_loan_id', '=', self.eipp_loan_id.id)])

        # print count_loan_line
        if (self.paid_amount < self.payable_balance) or (self.paid_amount < self.amount_to_pay):
            raise UserError(_('Amount paid is less Than the contract amount to pay.'))
        elif count_loan_line <= 1:
            if self.id == loan_line_id[-1].id and self.paid_amount > (self.amount_to_pay + 2):
                raise UserError(
                    _('Last Payment error, payment should be more than the exact amount of the last contract payment'))
            else:
                self.confirm()
        elif count_loan_line > 1:
            if self.id == loan_line_id[-1].id and self.paid_amount > (self.payable_balance + 2):
                raise UserError(
                    _('Last Payment error, payment should be more than the exact amount of the last contract payment'))
            else:
                self.confirm()

    def confirm(self):
        print 'yea'
        self.state = 'confirm'
        self.read_next_line()
        payment_ = self.env['account.payment']
        payment_id = payment_.search([('or_series.name', '=', self.payment_id.name)])
        payment_id.update({'state': 'posted'})

    @api.multi
    def read_next_line(self):
        loan_line = self.env['eipp.loan.line']
        date_start_str = datetime.strptime(self.date_for_payment, '%Y-%m-%d').date()
        date_start_str = date_start_str + relativedelta(months=1)
        loan_line_id = loan_line.search([
            ('eipp_loan_id', '=', self.eipp_loan_id.id)])

        if self.id == loan_line_id[-1].id:  # read the last record
            pass
        else:
            next_line_id = loan_line.search([
                ('date_for_payment', '=', date_start_str),
                ('eipp_loan_id', '=', self.eipp_loan_id.id)])
            for l in next_line_id:
                if self.balance:
                    amount_to_pay = l.amount_to_pay - self.balance
                    res = l.write({'payable_balance': round(amount_to_pay, 2),
                                   'notes': '[%s] %.2f is Deducted on the amount to pay for this month.' % (
                                       l.notes if l.notes else '', self.balance)
                                   })
                    return res


