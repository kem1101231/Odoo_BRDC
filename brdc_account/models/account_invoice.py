from odoo import api, fields, models, _
from datetime import date, datetime,timedelta
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_compare
from odoo.tools.misc import formatLang
import json
import calendar
import time
import math


class color:
   PURPLE = '\033[95m'
   CYAN = '\033[96m'
   DARKCYAN = '\033[36m'
   BLUE = '\033[94m'
   GREEN = '\033[92m'
   YELLOW = '\033[93m'
   RED = '\033[91m'
   BOLD = '\033[1m'
   UNDERLINE = '\033[4m'
   END = '\033[0m'


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'
    _order = 'state'

    # def name_get(self,cr,uid,ids,context=None):
    #     res = []
    #     if not ids:
    #         return res
    #     if isinstance(ids, list):
    #         references = self.read(cr, uid, ids, ['pa_ref', 'number'], context=context)
    #
    #         for ref in references:
    #             pa = ref['pa_ref']
    #             num = ref['number']
    #
    #             if pa and not num:
    #                 cid = pa + " " + num
    #             elif pa and num:
    #                 cid = pa + " " + num
    #             else:
    #                 cid = ""
    #             res.append((ref['id'], cid))
    #         return res
    #     else:
    #         return res or ids

    @api.multi
    def name_get(self):
        res = super(AccountInvoice, self).name_get()
        data = []
        for s in self:
            display_val = ''
            display_val += (s.pa_ref if s.pa_ref else s.number) or ""
            display_val += (" [Php %s]" % str(s.monthly_payment)) if s.purchase_term == 'install' else ""

            data.append((s.id, display_val))
        return data

    @api.depends('purchase_term','new_payment_term_id')
    def has_down(self):
        for s in self:
            dp = self.env['invoice.installment.line.dp'].search([('account_invoice_id', '=', s.id)])
            if dp:
                s.has_down_ = True
            else:
                s.has_down_ = False
            # if s.purchase_term == 'cash':
            #     s.has_down_ = False
            # elif s.purchase_term == 'install':
            #     for term in s.new_payment_term_id:
            #         if term.bpt_wod:
            #             s.has_down_ = False
            #         if not term.bpt_wod:
            #             s.has_down_ = True
    has_down_ = fields.Boolean(default=False, compute=has_down)

    @api.one
    @api.depends(
        'state', 'currency_id', 'invoice_line_ids.price_subtotal',
        'move_id.line_ids.amount_residual',
        'move_id.line_ids.currency_id')
    def _compute_residual(self):
        residual = 0.0
        residual_company_signed = 0.0
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        install_line = self.env['invoice.installment.line'].search([('account_invoice_id','=',self.id)])
        install_line_dp = self.env['invoice.installment.line.dp'].search([('account_invoice_id','=',self.id)])
        for line in self.sudo().move_id.line_ids:
            if line.account_id.internal_type in ('receivable', 'payable'):
                residual_company_signed += (line.amount_residual - self.pcf)
                # residual_company_signed = residual_company_signed - self.amount_tax
                if line.currency_id == self.currency_id:
                    residual += line.amount_residual_currency if line.currency_id else line.amount_residual
                    # residual += self.amount_tax
                else:
                    from_currency = (line.currency_id and line.currency_id.with_context(
                        date=line.date)) or line.company_id.currency_id.with_context(date=line.date)
                    residual += from_currency.compute(line.amount_residual, self.currency_id)
                    # residual += self.amount_tax
        self.residual_company_signed = abs(residual_company_signed) * sign
        self.residual_signed = abs(residual) * sign
        self.residual = abs(residual)
        digits_rounding_precision = self.currency_id.rounding
        if float_is_zero(self.residual, precision_rounding=digits_rounding_precision):
            self.reconciled = True
            install_line.write({
                'is_paid': True
            })
            install_line_dp.write({
                'is_paid': True
            })
        else:
            self.reconciled = False

    def compute_residual(self):
        self._compute_residual()

    InvoiceInstallmentLine_ids = fields.One2many(comodel_name="invoice.installment.line", inverse_name="account_invoice_id", string="", required=False, )
    InvoiceInstallmentLineDP_ids = fields.One2many(comodel_name="invoice.installment.line.dp", inverse_name="account_invoice_id", string="", required=False, )
    date_for_payment = fields.Date(string='Date for Payment', default=fields.Date.today())
    purchase_term = fields.Selection([('cash', 'Cash'), ('install', 'Installment')], string='Payment Type',
                                     default='install')
    is_10y = fields.Boolean(compute='get_term')
    @api.model
    def get_term(self):
        for loan in self:
            DPloan = loan.env['invoice.installment.line.dp'].search([('account_invoice_id','=',loan.id)])
            loan.is_10y = (len(DPloan) > 0)
            # print loan.is_10y

    new_payment_term_id = fields.Many2one('payment.config', string='Payment Terms',
                                          domain="[('parent_id', '=', product_type)]",
                                          )
    amortization = fields.Integer(related="new_payment_term_id.no_months", string="Amortization")

    product_type = fields.Many2one('payment.config', string='Product Type',domain="[('is_parent', '=', 1)]", default= lambda self: self.env['payment.config'].search([('is_parent', '=', 1)])[0].id)
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms', oldname='payment_term',
                                      default=lambda self: self.search([('name', '=', 'Immediate Payment')]))
    invoice_line_ids = fields.One2many('account.invoice.line', 'invoice_id', string='Invoice Lines',
                                       oldname='invoice_line',
                                       readonly=True, states={'draft': [('readonly', False)]}, copy=True, required=False
                                       )

    is_split = fields.Boolean(default=False, string='Split Downpayment/Cash')
    is_paidup = fields.Boolean(default=False, string='Paid-up')

    o_selling_price = fields.Float(string='Original Selling Price', default=0.00,
                                   # compute='get_value_from_line',
                                   )
    contract_price = fields.Float(string='Contract Price')
    o_dp = fields.Float(string='Downpayment', default=0.00,
                        # compute='get_value_from_line',
                        )
    s_dp = fields.Float(string='Paid-up DP', default=0.00,
                        # compute='get_value_from_line',
                        )
    st4_dp = fields.Float(string='Split DP', default=0.00,
                          # compute='get_value_from_line',
                          )
    spot_cash = fields.Float(string='Spot Cash', default=0.00,
                             # compute='get_value_from_line',
                             )
    split_cash = fields.Float(string='Split Cash', default=0.00,
                              # compute='get_value_from_line',
                              )
    balance_payment = fields.Float(string='Balance', default=0.00,
                                   # compute='get_value_from_line',
                                   )
    balance_payment_wi = fields.Float(string='Balance with Interest', default=0.00,
                                      # compute='get_value_from_line',
                                      )
    monthly_payment = fields.Float(string='Monthly Payment', default=0.00,
                                   )
    is_plan_mod = fields.Boolean(default=False)
    no_months_mode = fields.Integer(default=0)

    account_payment_id = fields.One2many(comodel_name="account.payment", inverse_name="account_invoice_id", string="", required=False, )

    total_principal_payment = fields.Monetary(default=0)

    general_aging_id = fields.Many2one('general.aging', string="Aging")
    general_aging_cd_id = fields.Many2one('general.aging_cd', string="Aging (CD)")
    user_id = fields.Many2one('res.users', string='Salesperson', track_visibility='onchange',
                              readonly=True,
                              default=lambda self: self.env.user)

    lpd = fields.Date()
    sale_order_id = fields.Many2one('sale.order')
    lot_price = fields.Monetary(store=True, readonly=True,
                                     compute='_get_amounts',
                                     track_visibility='always')

    unit_price = fields.Monetary(store=True, readonly=True,
                                 compute='_get_amounts',
                                 track_visibility='always')
    pcf = fields.Monetary(string='PCF', store=True, readonly=True, compute='_get_amounts',
                          track_visibility='always')
    vat = fields.Monetary(string='VAT', store=True, readonly=True, compute='_compute_amount',
                                  track_visibility='always')
    
    amount_total_wo_pcf = fields.Monetary(string='Total without PCF', store=True, readonly=True, compute='_get_amounts',
                                track_visibility='always')
    amot_total_wo_pcf_n_disc = fields.Monetary(string='Total without PCF and Discount', store=True, readonly=True, compute='_get_amounts',
                                track_visibility='always')
    lot_price_wo_disc = fields.Monetary(string='Lot Price with Discount', store=True, readonly=True, compute='_get_amounts',
                                track_visibility='always')
    inv_total_discount_amount = fields.Monetary(string='Total Discount', store=True, readonly=True, compute='_compute_amount',
                                  track_visibility='always')
    
    cost_of_sales = fields.Float(string="Cost of Sales", default=518.63,store=True, readonly=True, compute='_get_amounts',
                                track_visibility='always')
    net_profit = fields.Float(string="Net Profit", store=True, readonly=True, compute='_get_amounts',
                                track_visibility='always')
    gross_profit_rate = fields.Float(string="Gross Profit Rate", store=True, readonly=True, compute='_get_amounts',
                                track_visibility='always')

    # pa_ref = fields.Char(string='Purchase Agreement')
    # ranzu

    custom_trans_created = fields.Boolean(string="Transaction Created")

    pa_ref = fields.Char(string='Purchase Agreement')

    @api.depends('pa_ref')
    def _get_collector(self):
        for inv in self:
            so = self.env['sale.order'].search([('pa_ref','=',inv.pa_ref)], limit=1)

            inv.pa_ref_collector = so.collector.id if so.collector else False
            inv.update({
                            'pa_ref_collector':so.collector.id if so.collector else False,
                })

    pa_ref_collector = fields.Many2one(comodel_name="res.users", string="Assigned Collector", compute="_get_collector", default=False, store=True)
    collector_history = fields.One2many(comodel_name="brdc.invoice.collector.history", inverse_name="invoice_id", string="Collector History")
    
    total_paid = fields.Monetary(compute='total_paid_')
    monthly_due = fields.Monetary(string='Monthly Due', compute='get_total_payment')

    # @api.multi
    # def write(self, vals):

    #     result = super(AccountInvoice, self).write(vals)

    #     if self.state == 'open' and self.custom_trans_created == False:
    #         #  
    #         transaction = self.env['brdc.transactions']

    #         transactions_list = transaction.search([('invoice_id','=', self.id),])
    #         if len(transactions_list) == 0:

    #             transaction.create({
    #                                     'name': self.number + "/A_T",
    #                                     'invoice_id': self.id,
    #                                     'journal_entry':self.move_id.id,
    #                                     'ref_type': 'sale',
    #                                 })

    #         #self.journal_update('post', new_journal_entry.id)

    #     return result
    
  
    # @api.onchange('residual', 'monthly_due', 'monthly_payment')
    
    def total_paid_(self):

        for s in self:
            ids = []
            amount = 0.0
            for am in s.move_id:
                for aml in am.line_ids:
                    if aml.account_id.reconcile:
                        ids.extend(
                            [r.debit_move_id.id for r in aml.matched_debit_ids] if aml.credit > 0 else [r.credit_move_id.id
                                                                                                        for r in
                                                                                                        aml.matched_credit_ids])
                        ids.append(aml.id)


            move_line = self.env['account.move.line'].search([('id', 'in', ids)])

            
            for ml in move_line:
                amount += ml.payment_id.amount

            s.total_paid = amount

    @api.depends('residual', 'monthly_due', 'monthly_payment')
    def get_due_length(self):
        for s in self:
            total_due = 0.0 if s.monthly_payment == 0.0 else (s.monthly_due / s.monthly_payment)
            if s.state == 'open':
                s.month_due = round(total_due)
                s.write_due(round(total_due), s.monthly_due, s.id)

    month_due = fields.Float(string='Month Due', compute=get_due_length)

    def write_due(self, due, total, id):
        self._cr.execute("""update account_invoice set month_due = %s, monthly_due = %s where id = %s""" % (due, total, id))
        self._cr.commit()

        print self.month_due, 'month due'

    advances = fields.Monetary(compute='get_total_payment')
    amount_to_pay = fields.Monetary(compute='get_total_payment')
    payment_count = fields.Integer(string='No. of Payments', compute='get_total_payment')
    month_to_pay = fields.Date(string='Schedule', compute='get_total_payment')

    state = fields.Selection(selection_add=[('terminate', 'Terminated'), ('pre_active','Pre-Reactivatation'),('pre_terminate','Pre-Terminate'),('for_reactive','For Reactivation')])
    date_due = fields.Date(string='Due Date')

    def restructure_account(self):
        # get Covered payments and Identify uncovered lines then restructure payment schedule
        for s in self:
            installment_line = self.env['invoice.installment.line'].search([('account_invoice_id', '=', s.id)])
            if installment_line and s.purchase_term == 'install' and s.custom_account_id:
                total_paid = s.total_paid
                amounts = []
                ids = []
                due_length = 0
                for line in installment_line:
                    amounts.append(line.amount_to_pay)
                    if sum(amounts) <= total_paid:
                        ids.append(line.id)
                not_included_lines = installment_line.filtered(lambda rec: rec.id not in ids)
                due_length = len(installment_line.filtered(lambda rec: (rec.id not in ids) and (rec.date_for_payment < fields.Date.today())))
                for line in not_included_lines:
                    current_schedule = line.date_for_payment
                    new_schedule = datetime.strptime(current_schedule, '%Y-%m-%d') + relativedelta(months=due_length)
                    line.write({
                        'date_for_payment': new_schedule,
                        # 'series_no': line.series_no + 1
                    })
                s.state = 'open'
                s.has_terminated = False
                s.restructured = True
                # add 1 month
                last_line = installment_line[-1]
                series = last_line.series_no + 1
                installment_line.create({
                    'name': "(%s/%s)" % (str(series), str(series)),
                    'account_invoice_id': s.id,
                    'date_for_payment': datetime.strptime(last_line.date_for_payment, '%Y-%m-%d') + relativedelta(months=1),
                    'customer_id': s.partner_id.id,
                    'amount_to_pay': s.monthly_payment,
                    'type': 'install',
                    'payable_balance': s.monthly_payment,
                    'series_no': series,
                })
                new_amount_total = 0.0
                for line in self.env['invoice.installment.line'].search([('account_invoice_id', '=', s.id)]):
                    new_amount_total += line.amount_to_pay
                # modify contract price
                s.restructure_contract(new_amount_total)
            pass

    def restructure_contract(self, amount_total):
        print amount_total, 'restructure_contract'
        vat_taxes = []
        held_taxes = []
        other_taxes = []
        contract_price = amount_total
        pcf = contract_price * 0.1

        # for s in self:
        for line in self.invoice_line_ids:
                for taxes in line.invoice_line_tax_ids:
                    if taxes.amount_type == 'vat':
                        vat_taxes.append(taxes.amount)
                    elif taxes.amount_type == 'held':
                        held_taxes.append(taxes.amount)
                    else:
                        other_taxes.append(taxes.amount)
        less_pcf = contract_price * 0.9
        untaxed = less_pcf / (1 + (sum(vat_taxes) / 100))
        vat = untaxed * (sum(vat_taxes) or 0.0) / 100.0
        held = contract_price * (sum(held_taxes) or 0.0) / 100.0
        self.write({
            'unit_price': contract_price - pcf - vat,
            'pcf': pcf,
            'vat': vat,
            'amount_total': contract_price
        })

        # modify journal entry.
        self.restructure_entry(amount_total, pcf, vat, (contract_price - pcf - vat))
        self.restructure_move(amount_total, amount_total - vat, vat)

    def restructure_entry(self, contract, pcf, vat, untaxed):
        move = self.custom_account_id
        move.button_cancel()
        move_line = self.env['account.move.line']
        debit = move_line.search(
            [('move_id', '=', move.id), ('balance', '>', 0), ('is_tax', '=', False), ('is_pcf', '=', False)])
        credit = move_line.search(
            [('move_id', '=', move.id), ('balance', '<', 0), ('is_tax', '=', False), ('is_pcf', '=', False)])
        tax = move_line.search([('move_id', '=', move.id), ('is_tax', '=', True)])
        pcf_ = move_line.search([('move_id', '=', move.id), ('is_pcf', '=', True)])
        if debit:
            self._cr.execute(
                """update account_move_line set amount_residual = %s, debit = %s, balance = %s where id = %s""" % (
                    contract, contract, contract, debit.id
                ))
            self._cr.commit()
        else:
            print 'no debit found'

        if credit:
            self._cr.execute(
                """update account_move_line set credit = %s, balance = %s where id = %s""" % (
                    untaxed, 0 - untaxed, credit.id
                ))
            self._cr.commit()
        else:
            print 'no credit found'

        if tax:
            self._cr.execute(
                """update account_move_line set credit = %s, balance = %s where id = %s""" % (
                    vat, 0 - vat, tax.id
                ))
            self._cr.commit()
        else:
            print 'no tax found'

        if pcf_:
            self._cr.execute(
                """update account_move_line set credit = %s, balance = %s where id = %s""" % (
                    pcf, 0 - pcf, pcf_.id
                ))
            self._cr.commit()
        else:
            print 'no pcf found'

        move.post()
        pass

    def restructure_move(self, total, untaxed, vat):
        move = self.move_id
        move.button_cancel()
        move_line = self.env['account.move.line']
        debit = move_line.search(
            [('move_id', '=', move.id), ('balance', '>', 0), ('is_tax', '=', False), ('is_pcf', '=', False)])
        credit = move_line.search(
            [('move_id', '=', move.id), ('balance', '<', 0), ('is_tax', '=', False), ('is_pcf', '=', False)])
        tax = move_line.search([('move_id', '=', move.id), ('is_tax', '=', True)])
        if debit:
            self._cr.execute(
                """update account_move_line set amount_residual = %s, debit = %s, balance = %s where id = %s""" % (
                    total, total, total, debit.id
                ))
            self._cr.commit()
        else:
            print 'no debit found'

        if credit:
            self._cr.execute(
                """update account_move_line set credit = %s, balance = %s where id = %s""" % (
                    untaxed, 0 - untaxed, credit.id
                ))
            self._cr.commit()
        else:
            print 'no credit found'

        if tax:
            self._cr.execute(
                """update account_move_line set credit = %s, balance = %s where id = %s""" % (
                    vat, 0 - vat, tax.id
                ))
            self._cr.commit()
        else:
            print 'no tax found'
        move.post()


    # @api.onchange('residual', 'total_paid', 'monthly_due')
    @api.depends('residual', 'total_paid', 'purchase_term', 'amount_total')
    def get_total_payment(self):
        for s in self:
            installment_line = s.env['invoice.installment.line'].search([('account_invoice_id', '=', s.id)])
            if installment_line: #and s.purchase_term == 'install'
                # total_paid = s.total_paid
                # # s.total_paid = total_paid
                # line_array_id = []
                # last_id = []
                # result_amount = []
                # advance_payment_amount = 0

                # a = 0
                # amount = s.total_paid
                
                # for insLine in installment_line:
                #     a += (insLine.amount_to_pay if insLine.amount_to_pay != 0 else insLine.payable_balance)
                    
                #     mypayment = (insLine.amount_to_pay if insLine.amount_to_pay != 0 else insLine.payable_balance)
                #     if a <= amount:
                #         # print a, 'a'
                #         result_amount.append(mypayment)
                #         line_array_id.append(insLine.id)
                    
                #     advance_payment_amount += insLine.balance 

                # for i in line_array_id:
                #     last_id.append(i)
                #     # advance_payment_count = advance_payment_count + 1
                # current_date = str(datetime.now().date())
                # date_today = datetime.today().strftime('%Y-%m-%d')
                # get_due = s.env['invoice.installment.line'].search([('account_invoice_id', '=', s.id),
                #                                                        ('id', 'not in', line_array_id),
                #                                                        ('date_for_payment', '<', fields.date.today())
                #                                                        ])
                # payment_date = None
                # last_line_id = s.env['invoice.installment.line'].search([
                #     ('id', '=', None if not line_array_id else (line_array_id[-1] + 1))
                # ])
                # total_due = 0
                # amount_to_pay = 0
                # month_to_pay = None
                # print("()()()()()()( ===================================")
                # print amount, sum(result_amount)
                # advances = advance_payment_amount #amount - sum(result_amount)
                # for due in get_due:
                #     total_due += due.amount_to_pay
                #     payment_date = due.date_for_payment
                
                # if not total_due:
                #     amount_to_pay = last_line_id.amount_to_pay - (0 if advances <= 0 else advances)
                #     month_to_pay = last_line_id.date_for_payment
                
                # else:
                #     total_due = total_due - advances
                #     month_to_pay = payment_date
                
                # due_len = 0.0 if s.monthly_payment == 0.0 else (total_due / s.monthly_payment)
                # print due_len

                advances = 0
                monthly_due = 0
                amount_to_pay = 0
                payment_count = 0
                month_due = 0
                month_to_pay = 0

                for insLine in installment_line:
                    advances += insLine.balance
                    payment_count += 1 if insLine.is_paid else 0
                    date_for_payment = datetime.strptime(insLine.date_for_payment, '%Y-%m-%d')

                    if datetime.now() >= date_for_payment + timedelta(days=30):
                        monthly_due += insLine.amount_due
                        month_due += 1 if insLine.amount_due != 0 else 0

                s.update({
                    'advances': advances,
                    'monthly_due': monthly_due,
                    'amount_to_pay': monthly_due if monthly_due != 0 else s.current_due,
                    'payment_count': payment_count,
                    'month_due': month_due,
                    'month_to_pay': s.current_due_date
                })

                s.write({
                    'date_due': month_to_pay,
                })
            else:
                pass

    @api.multi
    def compute_surcharge(self):
        #maliiiiiiiiii
        # for s in self:
        # for s in self.env['account.invoice'].search([('state', 'in', ('open', 'terminate'))]):
        #     # print s.month_due, 'month due'
        #     sur_perc = None
        #     surcharge = 0
        #     if s.state == 'open':
        #         sur_perc = 1.17
        #
        #     elif s.state == 'terminate':
        #         sur_perc = 3
        #     if s.monthly_due != 0:
        #         surcharge = s.monthly_due * (sur_perc or 0.0) / 100.0
        #
        #     s.surcharge = round(surcharge)
        #     self._cr.execute(
        #         """update account_invoice set surcharge = %s where id = %s""" % (round(surcharge), s.id))
        #     self._cr.commit()
        pass

        # print self.surcharge, 'surcharge'

    @api.depends('residual', 'total_paid', 'monthly_due', 'has_terminated')
    def update_surcharge(self):
        print("++++++++++++++++")
        print("upadte surcharge")
        
        for s in self:
            if s.state in ['terminate', 'pre_active', 'pre_terminate'] and not s.curr_termination_id.surcharge_paid:
                sur_perc = None
                surcharge = 0
                if not s.has_terminated:
                    sur_perc = 1.17
                elif s.has_terminated:
                    sur_perc = 3

                if s.purchase_term == 'install':
                    surcharge = s.monthly_due * (sur_perc or 0.0) / 100.0
                
                else:
                    surcharge = 0.0
                
                s.surcharge = round(surcharge)
                s.update({
                    'surcharge': round(surcharge)
                })

                print s.surcharge, 'surcharge'

    surcharge = fields.Monetary(string='Surcharge', compute="update_surcharge")
    surcharge_journal = fields.Many2one('account.journal',
                                        string='Surcharge Journal',
                                        required=True,
                                        default=lambda self: self._get_surcharge_journal()
                                        )


    brdc_account_move = fields.Many2one(string="BRDC Acct Entry", comodel_name="account.brdc.move")


    @api.depends('total_paid')
    def _get_current_due(self):
        for invoice in self:

            schec_instance = self.env['invoice.installment.line']
            due_amount = 0
            due_date = None

            if invoice.purchase_term == 'install' and invoice.is_split:
                sched_instance = self.env['invoice.installment.line']
                monthly = sched_instance.get_monthly_amort_sched('due', invoice.id)
                downs = sched_instance.get_downpayment_sched('due', invoice.id)

                due_amount = monthly[0].amount_to_pay if len(monthly) != 0 else 0
                due_amount += downs[0].amount_to_pay if len(downs) != 0 else 0
                due_date = monthly[0].date_for_payment if len(monthly) != 0 else False


            else:

                next_payment = schec_instance.get_all_sched('due', invoice.id)
                due_amount = next_payment[0].amount_to_pay if len(next_payment) > 0 else 0
                due_date = next_payment[0].date_for_payment if len(next_payment) > 0 else False
            
            invoice.current_due = due_amount
            invoice.current_due_date = due_date

    current_due= fields.Monetary(string="Current Due", compute="_get_current_due")
    current_due_date = fields.Date(string="Due on Date", compute="_get_current_due")

    @api.multi
    def _get_surcharge_journal(self):
        id_ = None
        values = []
        rec = None
        ir_property = self.env['ir.property'].search([('name', '=', 'brdc_surcharge_property_id')])
        if ir_property:
            values = ir_property.value_reference.split(",")
            print values[1]
            id_ = int(values[1])
        elif ir_property and not self.surcharge_journal:
            values = ir_property.value_reference.split(",")
            print values[1]
            id_ = int(values[1])
        return id_

        # return rec

    # def _get_default_journal(self):
    #     journal = self.env['account.journal'].search([('code', '=ilike', 'SUR')])
    #     print journal.code, 'asdassssjournal'
    #     return journal.id

    @api.depends('sale_order_id','transaction_inv_id','service_order_id','state')
    def _get_amounts(self):
        for s in self:
            if s.sale_order_id:
                for so in s.sale_order_id:
                    s.unit_price = so.amount_untaxed
                    s.pcf = so.pcf
                    s.lot_price = so.unit_price
                    s.amount_total_wo_pcf = so.amount_total_wo_pcf
                    s.amot_total_wo_pcf_n_disc = so.amot_total_wo_pcf_n_disc
                    s.lot_price_wo_disc = so.lot_price_wo_disc
                    s.net_profit = so.net_profit
                    s.gross_profit_rate = so.gross_profit_rate
                    s.cost_of_sales = so.cost_of_sales
                    
            elif s.service_order_id:
                for seo in s.service_order_id:
                    s.unit_price = seo.amount_untaxed
                    s.pcf = seo.pcf
                    s.vat = seo.amount_tax
                    s.lot_price = seo.amount_total
            else:
                for tr in s.transaction_inv_id:
                    s.unit_price = tr.amount_untaxed
                    s.pcf = tr.pcf
                    s.lot_price = tr.contract

    # needs to update the code
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'currency_id', 'company_id', 'date_invoice',
                 'type','InvoiceInstallmentLine_ids.amount_to_pay','InvoiceInstallmentLineDP_ids.amount_to_pay')
    def _compute_amount(self):
        
        for invoice in self:
            amount_tax = 0.0
            _vat = []
            _held = []
            vat = 0.0
            held = 0.0
            


            # amount_untaxed_f = (order.pricelist_id.currency_id.round(amount_untaxed) - pcf) - order.pricelist_id.currency_id.round(amount_tax)
            round_curr = invoice.currency_id.round
            # amount_untaxed_InvoiceInstallmentLine = sum(line.amount_to_pay for line in invoice.InvoiceInstallmentLine_ids)
            # amount_untaxed_InvoiceInstallmentLineDP = sum(line.amount_to_pay for line in invoice.InvoiceInstallmentLineDP_ids)
            # invoice.amount_untaxed = amount_untaxed_InvoiceInstallmentLine + amount_untaxed_InvoiceInstallmentLineDP
            invoice.amount_untaxed = invoice.contract_price
            pcf = invoice.lot_price * 0.10
            unit_price = invoice.lot_price - pcf
            # invoice.pcf = pcf
            total_tax = 0
            total_discount = 0

            for orderline in invoice.invoice_line_ids:
                price = invoice.amount_untaxed * (1 - (orderline.discount or 0.0) / 100.0)
                total_tax += orderline.line_vat_value
                total_discount += orderline.line_discount_value
                
                if orderline.invoice_line_tax_ids:
                    for tax_ids in orderline.invoice_line_tax_ids:
                        if tax_ids.amount_type == 'vat':
                            _vat.append(tax_ids.amount)
                        elif tax_ids.amount_type == 'held':
                            _held.append(tax_ids.amount)
                        else:
                            pass

            
            vat = sum(_vat)
            held = sum(_held)
            amount_tax = invoice.unit_price * (vat or 0.0) / 100.0
            # invoice.amount_tax = amount_tax if len(invoice.invoice_line_ids.product_id.taxes_id) != 0 else 0 #sum(round_curr(line.amount) for line in invoice.tax_line_ids)
            # without_vat = invoice.unit_price / (
            #                     1 + (vat or 0.0) / 100.0)
            on_held = invoice.unit_price * (held or 0.0) / 100.0
            invoice.amount_tax = 0 - on_held
            
            tax_len = []
            for line in invoice.invoice_line_ids:
                for tax in line.product_id.taxes_id:
                    tax_len.append(tax)
            

            invoice.vat = total_tax #amount_tax if len(tax_len) != 0 else 0
            invoice.inv_total_discount_amount = total_discount
            # invoice.unit_price = unit_price - amount_tax
            invoice.amount_total = invoice.amount_untaxed
            amount_total_company_signed = invoice.amount_total
            amount_untaxed_signed = invoice.amount_untaxed
            if invoice.currency_id and invoice.company_id and invoice.currency_id != invoice.company_id.currency_id:
                currency_id = invoice.currency_id.with_context(date=invoice.date_invoice)
                amount_total_company_signed = currency_id.compute(invoice.amount_total, invoice.company_id.currency_id)
                amount_untaxed_signed = currency_id.compute(invoice.amount_untaxed, invoice.company_id.currency_id)
            sign = invoice.type in ['in_refund', 'out_refund'] and -1 or 1
            invoice.amount_total_company_signed = amount_total_company_signed * sign
            invoice.amount_total_signed = invoice.amount_total * sign
            invoice.amount_untaxed_signed = amount_untaxed_signed * sign


    @api.onchange('invoice_line_ids', 'new_payment_term_id','product_type','purchase_term')
    def get_value_from_line(self):

        payment = self.env['payment.config']
        try:

            for s in self:
                for orderline in s.order_line:
                    total_price = sum(orderline.price_subtotal)
                    installable = orderline[0].product_id.installable_product
                    
                    if s.product_type.category == 'product' and installable:
                        if s.purchase_term == 'install':

                            if s.new_payment_term_id.bpt_wod:
                                # print "kirto"
                                balance_payment_wi = total_price * s.new_payment_term_id.less_perc
                                s.balance_payment_wi = 0.00
                                s.o_dp = 0.00
                                s.s_dp = 0.00
                                s.st4_dp = 0.00
                                s.spot_cash = 0.00
                                s.split_cash = 0.00
                                s.balance_payment = 0.00
                            
                            else:
                                dp = payment.search([('parent_id','=',s.product_type.id), ('name', '=', 'downpayment')])
                                s.o_dp = total_price * dp.less_perc
                                s_dp = payment.search([('parent_id','=',s.product_type.id), ('name', '=', 'paid up DP')])
                                s.s_dp = s.o_dp * s_dp.less_perc
                                st4_dp = payment.search([('parent_id','=',s.product_type.id), ('name', '=', '4 mos split dp')])
                                s.st4_dp = (s.o_dp * st4_dp.less_perc) / 4

                                balance_payment = payment.search([('parent_id','=',s.product_type.id), ('name', '=', 'Balance')])
                                s.balance_payment = total_price * balance_payment.less_perc
                                s.balance_payment_wi = s.balance_payment * s.new_payment_term_id.less_perc
                                balance_payment_wi = s.balance_payment_wi
                        else:
                            spot_cash = payment.search([('parent_id','=',s.product_type.id), ('name', '=', 'spotcash')])
                            s.spot_cash = total_price * spot_cash.less_perc
                            cash = payment.search([('parent_id','=',s.product_type.id), ('name', '=', '3-months deferred')])
                            split_cash = total_price * cash.less_perc
                            s.split_cash = split_cash / 3



                        s.monthly_payment = balance_payment_wi / s.new_payment_term_id.no_months
                    
                    elif s.product_type.category == 'service' and installable:
                        payment_wi = 0.00
                        # term_id = payment.search([('parent_id','=','service'),('name','=','120 mos')]).id
                        # if s.eipp_payment_term_id.name == name:
                        #     raise UserError(_('This payment term is intended only for special packages!'))
                        dp = payment.search([('parent_id', '=', s.product_type.id), ('name', '=', 'downpayment')])
                        s.o_dp = total_price * dp.less_perc if dp else 0.00
                        s_dp = payment.search([('parent_id', '=', s.product_type.id), ('name', '=', 'paid up DP')])
                        s.s_dp = s.o_dp * s_dp.less_perc if s_dp else 0.00
                        st4_dp = payment.search([('parent_id', '=', s.product_type.id), ('name', '=', '4 mos split dp')])
                        s.st4_dp = (s.o_dp * st4_dp.less_perc) / 4 if st4_dp else 0.00
                        spot_cash = payment.search([('parent_id', '=', s.product_type.id), ('name', '=', 'spotcash')])
                        s.spot_cash = total_price * spot_cash.less_perc if spot_cash else 0.00
                        cash = payment.search([('parent_id', '=', s.product_type.id), ('name', '=', '3-months deferred')])
                        split_cash = total_price * cash.less_perc if spot_cash else 0.00
                        s.split_cash = split_cash / 3 if cash else 0.00
                        balance_payment = payment.search([('parent_id', '=', s.product_type.id), ('name', '=', 'Balance')])
                        s.balance_payment = total_price * balance_payment.less_perc if balance_payment else 0.00
                        s.balance_payment_wi = s.balance_payment * s.new_payment_term_id.less_perc if s.balance_payment != 0 else 0.00
                        if s.purchase_term == 'install' and s.new_payment_term_id.bpt_wod:
                            s.balance_payment_wi = 0.00
                            payment_wi = (s.balance_payment_wi if s.balance_payment_wi != 0 else total_price) * s.new_payment_term_id.less_perc
                            s.monthly_payment = payment_wi / s.new_payment_term_id.no_months
                            s.o_dp = 0.00
                            s.s_dp = 0.00
                            s.st4_dp = 0.00
                            s.spot_cash = 0.00
                            s.split_cash = 0.00
                            s.balance_payment = 0.00
                                    # s.new_payment_term_id = term_id
                        else:
                            payment_wi = (s.balance_payment_wi if s.balance_payment_wi != 0 else total_price) * s.new_payment_term_id.less_perc
                            s.monthly_payment = payment_wi / s.new_payment_term_id.no_months
                    else:
                        s.monthly_payment = total_price
                        # s.split_cash = 0.00
        except:
            pass

    @api.multi
    def action_cancel(self):
        moves = self.env['account.move']
        for inv in self:
            if inv.move_id:
                moves += inv.move_id
            if inv.payment_move_line_ids:
                raise UserError(_('You cannot cancel an invoice which is partially paid. You need to unreconcile related payment entries first.'))

        # First, set the invoices as cancelled and detach the move ids
        self.write({'state': 'cancel', 'move_id': False})
        if moves:
            # second, invalidate the move(s)
            moves.button_cancel()
            # delete the move this invoice was pointing to
            # Note that the corresponding move_lines and move_reconciles
            # will be automatically deleted too
            moves.unlink()

        if self.brdc_account_move:
            self.brdc_account_move.unreconcile_entries()

        return True

    ###################
    @api.multi
    def action_invoice_open(self):
        # <-- Ranz
        # if len(self.env['account.invoice.line'].search([('invoice_id', '=', self.id)])) <= 1:
        order_line = self.env['sale.order.line'].search(
            [('order_id', '=', self.env['sale.order'].search([('name', '=', self.origin)]).id)])
        invoice_line = self.env['account.invoice.line'].search([('invoice_id', '=', self.id)])
        for line in order_line:
            invoice_line.filtered(lambda res: res.product_id == line.product_id).lot_id = line.lot_id.id
            # self.env['account.invoice.line'].search([('invoice_id', '=', self.id)]).lot_id = self.env['sale.order'].search([('name', '=', self.origin)]).lot_id.id
        self.lpd = datetime.today().strftime('%Y-%m-%d')
        gen_aging = self.env['general.aging']
        line_id = gen_aging.create({
            'invoice_id': self.id,
        })
        gen_aging_cd = self.env['general.aging_cd']
        line_id2 = gen_aging_cd.create({
            'invoice_id': self.id,
        })

        self.general_aging_id = line_id.id
        collector = self.env['brdc.collection.collector'].search([('collector_id','=',self.pa_ref_collector.id),])
        self.env['brdc.invoice.collector.history'].create({
                                                                        'invoice_id':self.id,
                                                                        'collector_id':collector.id,
                                                                        'status':'current',
                                                                        'date_assigned':date.today(),
                                                    })

        # this is too taxing to the unit when there are millions(or probably thousands of transactions) basically it updates all aging of recievables
        # generate_general_aging = self.env['general.aging'].search([])
        # dt = str(datetime.now().date())
        # pl = 30
        # # print dt, pl
        # for c in range(0, len(generate_general_aging)):
        #     generate_general_aging[c].get_days_passed(dt, pl)
        #
        # self.general_aging_cd_id = line_id2.id
        # # this is too taxing to the unit when there are millions(or probably thousands of transactions) basically it updates all aging of recievabl
        # generate_general_aging_cd = self.env['general.aging_cd'].search([])
        # # print dt, pl
        # for c in range(0, len(generate_general_aging_cd)):
        #     generate_general_aging_cd[c].get_days_passed(dt, pl)
        # Ranz-->

        # lots of duplicate calls to action_invoice_open, so we remove those already open
        to_open_invoices = self.filtered(lambda inv: inv.state != 'open')
        if to_open_invoices.filtered(lambda inv: inv.state not in ['proforma2', 'draft']):
            raise UserError(_("Invoice must be in draft or Pro-forma state in order to validate it."))
        to_open_invoices.action_date_assign()
        to_open_invoices.action_move_create()
        tax_id = []
        account_id = 0
        icr_id = 0
        ugp_id = 0
        has_pcf = False
        for invoiceline in self.invoice_line_ids:
            for taxes in invoiceline[0].invoice_line_tax_ids:
                tax_id.append(taxes.id)
            for acc in invoiceline[0].product_id:
                account_id = acc.pcf_account_id.id
                icr_id = acc.installment_contract_rec_id.id if acc.installment_contract_rec_id.id else False
                ugp_id = acc.gross_profit_id.id if acc.gross_profit_id.id else False
        installment_ = None
        advances_ = None

        if account_id:
            has_pcf = True
        
        self.update_move_line(tax_id)
        self.update_tax_0(self.move_id.id, tax_id, self.contract_price, self.vat, self.pcf, account_id, has_pcf, self.amount_tax)
        self._payment_schedule()

        config_ref = ''

        if self.purchase_term == 'cash':
            config_ref = 'acct_lot_inv_cash'
        else:
            config_ref = 'acct_lot_inv_inst'

        acct_conf = self.env['brdc.transaction.acct.conf'].search([('conf_code','=', config_ref)])

        if self.brdc_account_move:
            self.brdc_account_move.reconcile_entries()
            
        
        else:
            brdc_account_move_id = acct_conf.create_entries(self.id, self.number, self.date_invoice)
            
            # brdc_account_move_id.reconcile_entries()
            self.brdc_account_move = brdc_account_move_id.id
            self.brdc_account_move.reconcile_entries()

        return True, to_open_invoices.invoice_validate(), self._compute_amount(), self.generate_commission(self),  #, self.create_CostOfSale(), self.create_journal_entry()
   
    @api.multi
    def _payment_schedule(self):
        #generate payment schedule
        number = 1
        for s in self:
            date_start_str = datetime.strptime(s.date_invoice, '%Y-%m-%d')
            installment_line = s.env['invoice.installment.line']
            installment_line.search([('account_invoice_id', '=', s.id)]).unlink()
            #cash
            dp = None
            dp_amount = None
            split = None
            type_ = None
            if s.purchase_term == 'cash':
                if s.is_split:
                    split = 3
                    type_ = 'split'
                else:
                    split = 1
                    type_ = 'spot'
                for i in range(1, split + 1):
                    installment_line.create({
                        'name': "(%s/%s)" % (str(i), split),
                        'account_invoice_id': s.id,
                        'date_for_payment': date_start_str,
                        'customer_id': s.partner_id.id,
                        'amount_to_pay': s.amount_total / split,
                        'type': type_,
                        'payable_balance': s.amount_total / split,
                        'series_no': i,
                    })
                    number += 1
                    date_start_str = date_start_str + relativedelta(months=1)
            
            elif s.purchase_term == 'install':
                if s.new_payment_term_id.bpt_wod:
                    split = s.new_payment_term_id.no_months
                    dp = 0
                    dp_amount = 0
                else:
                    if s.is_split:
                        dp = 4
                        split = s.new_payment_term_id.no_months
                        dp_amount = s.st4_dp
                    else:
                        dp = 1
                        split = s.new_payment_term_id.no_months
                        if s.is_paidup:
                            dp_amount = s.s_dp
                        else:
                            dp_amount = s.o_dp
                ins_amount = s.balance_payment_wi
                
                for d in range(1, dp + 1):
                    installment_line.create({
                        'name': "(%s/%s)" % (str(d), split + dp),
                        'account_invoice_id': s.id,
                        'date_for_payment': date_start_str,
                        'customer_id': s.partner_id.id,
                        'amount_to_pay': dp_amount,
                        'type': 'down',
                        'payable_balance': dp_amount,
                        'series_no': d,
                    })
                    number += 1
                    date_start_str = date_start_str + relativedelta(months=1)
                print dp
                # date_start_str = date_start_str + relativedelta(months=int(dp))
                print date_start_str
                
                if s.purchase_term == 'install' and s.is_split:
                    date_start_str = datetime.strptime(s.date_invoice, '%Y-%m-%d')
                
                for i in range(1, split + 1):
                    print("+++++++++++++++++++++++++ &*&*&*&*&*&*&*&*&*&*&*&*&*&")
                    print(number)

                    installment_line.create({
                        'name': "(%s/%s)" % (str(i + dp), split + dp),
                        'account_invoice_id': s.id,
                        'date_for_payment': date_start_str,
                        'customer_id': s.partner_id.id,
                        'amount_to_pay': s.monthly_payment,
                        'type': 'install',
                        'payable_balance': s.monthly_payment,
                        'series_no': i + dp,
                    })
                    
                    number += 1
                    print("-----------------")
                    print(number)
                    date_start_str = date_start_str + relativedelta(months=1)
                    print(date_start_str)
                    print(":::::::::::::::::::::::::::::::\n\n\n")
        return True

    # @api.multi
    # def add_beginning_balance(self):
    #     for loan in self:
    #         installment_line = loan.env['invoice.installment.line'].search([('account_invoice_id','=',loan.id)])
    #         installment_line_dp = loan.env['invoice.installment.line.dp'].search([('account_invoice_id','=',loan.id)])
    #         if len(installment_line_dp) != 0:
    #             line_id = installment_line_dp[0].write({
    #                 'beginning_balance': loan.residual,
    #                 'payable_balance': installment_line_dp[0].amount_to_pay
    #             })
    #         else:
    #             line_id = installment_line[0].write({
    #                 'beginning_balance': loan.residual,
    #                 'payable_balance': installment_line[0].amount_to_pay
    #             })
    #         return True


    @api.multi
    def sep_down(self):
        installment_line_dp = self.env['invoice.installment.line.dp']
        installment_line = self.env['invoice.installment.line']

        number = 1
        dp_ = installment_line_dp.search([('account_invoice_id', '=', self.id)])
        for dp in dp_:
            ip_ = installment_line.search([('account_invoice_id','=',self.id),('date_for_payment','=',dp.date_for_payment)])
        for ip in ip_:
            installment_line_dp_ = installment_line_dp.search([('account_invoice_id', '=', self.id), ('date_for_payment', '=', ip.date_for_payment)])
            amount_to_pay = round((ip.amount_to_pay + installment_line_dp_.amount_to_pay), 2)
            # print amount_to_pay
            res = ip.write({
                'amount_to_pay': amount_to_pay,
                'notes': 'Splitted Downpayment + Monthly Payment'
            })
            number += 1
            installment_line_dp_.unlink()
            return res



    # def _compute_total_invoices_amount(self):
    #     """ Compute the sum of the residual of invoices, expressed in the payment currency """
    #     payment_currency = self.currency_id or self.journal_id.currency_id or self.journal_id.company_id.currency_id or self.env.user.company_id.currency_id
    #     invoices = self._get_invoices()
    #
    #     if all(inv.currency_id == payment_currency for inv in invoices):
    #         total = sum(invoices.mapped('residual_signed'))
    #     else:
    #         total = 0
    #         for inv in invoices:
    #             if inv.company_currency_id != payment_currency:
    #                 total += inv.company_currency_id.with_context(date=self.payment_date).compute(
    #                     inv.residual_company_signed, payment_currency)
    #             else:
    #                 total += inv.residual_company_signed
    #     return abs(total)



    @api.multi
    def print_receipt(self):
        for s in self:
            ins_line = s.env['invoice.installment.line'].search(
                [('account_invoice_id', '=', s.id), ('payment_parent', '=', True)])
            down_line = s.env['invoice.installment.line.dp'].search(
                [('account_invoice_id', '=', s.id), ('payment_parent', '=', True)])
            down_line1 = s.env['invoice.installment.line.dp'].search(
                [('account_invoice_id', '=', s.id), ('is_paid', '=', True)])

            ins_ids = []
            ins_pay_ids = []
            dwn_ids = []
            dwn_pay_ids = []
            dwn1_ids = []
            dwn1_pay_ids = []
            for ins in ins_line:
                ins_pay_ids.append(ins.payment_transaction.id)
                ins_ids.append(ins.id)
            for dwn in down_line:
                dwn_pay_ids.append(dwn.payment_transaction.id)
                dwn_ids.append(dwn.id)
            for dwn1 in down_line1:
                dwn1_pay_ids.append(dwn1.payment_transaction.id)
                dwn1_ids.append(dwn1.id)
            payment_id = None
            if dwn_ids or dwn1_ids:
                payment_id = dwn1_pay_ids[-1] if len(dwn_pay_ids) < 1 else dwn_pay_ids[-1]
            elif ins_ids:
                payment_id = ins_pay_ids[0] if len(ins_pay_ids) < 1 else ins_pay_ids[-1]
            else:
                payment_id = None
            print payment_id
            account_payment = s.env['account.payment'].search([('id', '=', payment_id)])
            # print account_payment.or_series
            if account_payment:
                account_payment.write({
                    'printed': account_payment.printed + 1
                })
                model = None
                report = None
                if ins_ids:
                    model = s.env['invoice.installment.line'].search(
                        [('id', '=', ins_ids[-1] if len(ins_ids) < 1 else ins_ids[-1])])
                    report = 'brdc_account.official_receipt_view_line'
                elif not ins_ids:
                    model = s.env['invoice.installment.line.dp'].search([('id', '=', dwn1_ids[-1] if len(dwn_ids) < 1 else dwn_ids[-1])])
                    report = 'brdc_account.official_receipt_view_dp'
                else:
                    model = None
                    report = None

                return model.env['report'].get_action(model, report)
            else:
                raise UserError(_("No payment record!"))

    # @api.multi
    # def open_reconcile_view(self):
    #     return self.line_ids.open_reconcile_view()

    @api.multi
    def view_payment(self):
        for s in self:
            ids = []
            payment_ids = []
            for am in s.move_id:
                for aml in am.line_ids:
                    if aml.account_id.reconcile:
                        ids.extend(
                            [r.debit_move_id.id for r in aml.matched_debit_ids] if aml.credit > 0 else [r.credit_move_id.id
                                                                                                        for r in
                                                                                                        aml.matched_credit_ids])
                        ids.append(aml.id)
            move_line = self.env['account.move.line'].search([('id', 'in', ids)])
            for ml in move_line:
                payment_ids.append(ml.payment_id.id)
                # print ml.payment_id.amount
            # action['domain'] = [('id', 'in', ids)]
            # return action
            # invoice = s.env['account.invoice'].search([('name', '=', s.communication)])
            return {
                'name': "Payment",
                'res_model': 'account.payment',
                'type': 'ir.actions.act_window',
                'view_mode': 'tree,form',
                'view_id': False,
                'view_type': 'form',
                'domain': [('id', 'in', payment_ids)]
            }

    @api.one
    def _get_outstanding_info_JSON(self):
        print self.id
        self.outstanding_credits_debits_widget = json.dumps(False)
        if self.state == 'open':
            domain = [('account_id', '=', self.account_id.id),
                      ('partner_id', '=', self.env['res.partner']._find_accounting_partner(self.partner_id).id),
                      ('reconciled', '=', False), ('amount_residual', '!=', 0.0),
                      ('move_id.state', '=', 'posted'),
                      ] #bugggggggggg
            if self.type in ('out_invoice', 'in_refund'):
                domain.extend([('credit', '>', 0), ('debit', '=', 0)])
                type_payment = _('Outstanding credits')
            else:
                domain.extend([('credit', '=', 0), ('debit', '>', 0)])
                type_payment = _('Outstanding debits')
            info = {'title': '', 'outstanding': True, 'content': [], 'invoice_id': self.id}
            # domain.extend([('account_invoice_id', '=', self.id)])
            lines = self.env['account.move.line'].search(domain)
            currency_id = self.currency_id
            if len(lines) != 0:
                for line in lines:
                    # get the outstanding residual value in invoice currency
                    if line.currency_id and line.currency_id == self.currency_id:
                        amount_to_show = abs(line.amount_residual_currency)
                    else:
                        amount_to_show = line.company_id.currency_id.with_context(date=line.date).compute(
                            abs(line.amount_residual), self.currency_id)
                    if float_is_zero(amount_to_show, precision_rounding=self.currency_id.rounding):
                        continue
                    info['content'].append({
                        'journal_name': line.ref or line.move_id.name,
                        'amount': amount_to_show,
                        'currency': currency_id.symbol,
                        'id': line.id,
                        'position': currency_id.position,
                        'digits': [69, self.currency_id.decimal_places],
                    })
                info['title'] = type_payment
                self.outstanding_credits_debits_widget = json.dumps(info)
                self.has_outstanding = True

    is_fp = fields.Boolean(default=False, string='Fully Paid', compute='_onchange_state', track_visibility="always")
    lot_is_paid = fields.Boolean(string="Lot is Paid")

    # @api.onchange('total_paid')
    @api.depends('state', 'total_paid')
    def _onchange_state(self):
        for rec in self.filtered(lambda res: res.state in ['open', 'paid']):
            # origin
            lot_ids = []
            lot_description = []
            sale_order = self.env['sale.order'].search([('name', '=', rec.origin)])
            print sale_order.pa_ref, 'sale_order'
            pickings = sale_order.mapped('picking_ids')
            stock_picking = self.env['stock.picking'].search([('id', '=', pickings.id), ('state', '!=', 'cancel')])
            stock_pack_operation = self.env['stock.pack.operation'].search([('picking_id', '=', stock_picking.id)])
            pack_lots = self.env['stock.pack.operation.lot'].search([('operation_id', 'in', stock_pack_operation.ids)])
            for pack_lot in pack_lots:
                print pack_lot.lot_id.name
                lot_ids.append(pack_lot.lot_id.id)
                lot_description.append(pack_lot.lot_id.name)
            if rec.invoice_line_ids:
                if lot_ids:
                    lot = self.env['stock.production.lot'].search([('id', 'in', lot_ids)])
                    print lot, '_onchange_state'
                    for res_lot in lot:
                        print res_lot, 'res_lot'
                        if res_lot.filtered(lambda res: res.status in ['wit', 'fi']):
                            print 'lot'
                            pass
                        else:
                            if rec.state == 'paid':
                                print 'fp', res_lot.name

                                res_lot.write({
                                    'status': 'fp',
                                    'invoice_id': rec.id
                                })
                                if not res_lot.sale_order_id:
                                    self._cr.execute("""
                                        update stock_production_lot 
                                        set sale_order_id = %s, invoice_id = %s, note = '***FREE LOT***',
                                        is_free = true 
                                        where id = %s
                                    """ % (sale_order.id, rec.id, res_lot.id))
                                    self._cr.commit()
                                rec.update({
                                    'is_fp': True
                                })
                                print res_lot.name
                            elif rec.state == 'open':

                                res_lot.write({
                                    'status': 'amo',
                                    'invoice_id': rec.id
                                })
                                if not res_lot.sale_order_id:
                                    self._cr.execute("""
                                        update stock_production_lot 
                                        set sale_order_id = %s, invoice_id = %s, note = '***FREE LOT***',
                                        is_free = true  
                                        where id = %s
                                    """ % (sale_order.id, rec.id, res_lot.id))
                                    self._cr.commit()
                                rec.update({
                                    'is_fp': False
                                })
                                print 'amo', res_lot.name
                            else:
                                pass
                        for line in rec.invoice_line_ids:
                            if line.is_free:
                                res_lot.filtered(lambda res: res.id == line.lot_id.id).write({
                                    'is_free': line.is_free
                                })
                                print res_lot.is_free, 'res_lot.is_free'
                            else:
                                pass


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    printed = fields.Integer(default=0)


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    is_free = fields.Boolean(default=False, string='Free')
    line_vat_value = fields.Float(string="Tax")
    line_discount_value = fields.Float(string="Discount Value")
    invoice_type = fields.Selection(slelction=[
            ('out_invoice','Customer Invoice'),
            ('in_invoice','Vendor Bill'),
            ('out_refund','Customer Refund'),
            ('in_refund','Vendor Refund'),
        ], string="Invoice Type", related="invoice_id.type")
    so_based_sub_total = fields.Float(string="Sub Amount", compute="_get_subtotal", store=True)

    @api.one
    @api.depends('price_subtotal')
    def _get_subtotal(self):
        for line in self:
            new_subtotal = line.price_unit - line.line_discount_value

            if line.invoice_type == 'out_invoice':

                line.price_subtotal = new_subtotal
                line.so_based_sub_total = new_subtotal
                #line.invoice_type = line.invoice_id.type

                print("***********************************************")
                print(line.invoice_type)

                line.update({
                    'price_subtotal':new_subtotal,
                    'so_based_sub_total':new_subtotal,
                    #'invoice_type':line.invoice_id.type,
                    })
    
    # @api.onchange('price_subtotal')
    # def price_subtotal_change(self):
    #     if self.price_subtotal:
    #         self.price_subtotal = self.so_based_sub_total



class InvoiceInstallmentLine(models.Model):
    _name = 'invoice.installment.line'
    _order = 'date_for_payment'

    name = fields.Char(string="No")
    account_invoice_id = fields.Many2one('account.invoice',string="Reference ID", ondelete='cascade',readonly=1)

    date_for_payment = fields.Date(string='Scheduled Date', required=True, readonly=1)
    customer_id = fields.Many2one('res.partner', string='Customer', ondelete='cascade', readonly=1)
    amount_to_pay = fields.Float(string='Amount to Pay', required=True, readonly=1)
    type = fields.Selection(string="", selection=[('down', 'Down Payment'),
                                                  ('install', 'Monthly Amort.'),
                                                  ('spot', 'Spot Cash'),
                                                  ('split', 'Split Cash')], required=False, default='install')
    is_paid = fields.Boolean(string='Paid', default=False, readonly=1,
                             # compute='_get_payment_id'
                             )
    
    series_no = fields.Integer()

    @api.model
    def _get_amount_due(self):
        for line in self:

            amount_due_value = 0
            today = datetime.now()

            # print("????????????????????????????????????????????")
            # print(type(today))
            # print(line.date_for_payment)
            date_for_p = datetime.strptime(line.date_for_payment, '%Y-%m-%d')
            # print(date_for_p)

            if line.is_paid == False and date_for_p <= today:
                amount_due_value = line.amount_to_pay - line.balance

            line.amount_due = amount_due_value
            line.update({'amount_due': amount_due_value,})


    amount_due = fields.Float(string="Amount Due", compute="_get_amount_due")
    # notes = fields.Text()
    # payment_term = fields.Many2one('payment.config', string='Payment Terms', readonly=1)
    #
    paid_amount = fields.Float(string='Paid Amount')
    balance = fields.Float(string="Customer's Advanced Payment")
    payable_balance = fields.Float(string="Total Payment")
    state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirm Payment')], default='draft')
    payment_transaction = fields.Many2many('account.payment',
                                string='O.R. Number')
    beginning_balance = fields.Float(string='Beginning Balance')
    ending_balance = fields.Float(string='Ending Balance', default=0.00)
    advance_payment = fields.Float(string='Advance Payment', defualt=0.00)
    date_paid = fields.Date(string="Payment Date")
    cover_by = fields.Many2one('invoice.installment.line')
    payment_parent = fields.Boolean(default=False)

    def register_payment(self, amount, payment_id, date_of_payment, sched_id):
            instance = self.env['invoice.installment.line'].search([('id','=',sched_id)], limit=1)
            advance_payment = 0
            paid_amount = 0
            is_paid = False

            if round((amount + instance.balance),2) < round(instance.amount_to_pay, 2):
                advance_payment = instance.balance + amount
            else:
                self.set_line_paid(instance)
                is_paid = True

            instance.update({
                            'payment_transaction':[(4, payment_id)],
                            'balance': advance_payment,
                            'date_paid':date_of_payment, 
                        })
   
    def unregister_payment(self, amount, sched_id):
            instance = self.env['invoice.installment.line'].search([('id','=', sched_id)], limit=1)
            advance_payment = 0
            paid_amount = 0

            is_paid = False

            update_list = {}

            if instance.balance == 0:
                if amount < round(instance.amount_to_pay, 2):
                    balance = round(instance.amount_to_pay, 2) - amount 
                    update_list['balance'] = balance                 

                else:
                    update_list['payment_transaction'] = False
                    update_list['date_paid'] = False
                    update_list['state'] = 'draft'
                    self.set_line_unpaid(instance)
            else:
                if amount < round(instance.balance, 2):
                    balance = round(instance.balance, 2) - amount 
                    update_list['balance'] = balance
                
                else:
                    update_list['payment_transaction'] = False
                    update_list['date_paid'] = False
                    update_list['balance'] = 0
                    update_list['state'] = 'draft'  
                    self.set_line_unpaid(instance)

            instance.update(update_list)

    def set_line_paid(self, instance):   
        instance.update({
                            'is_paid': True, 
                        })
    
    def set_line_unpaid(self, instance):   
        instance.update({
                            'is_paid': False, 
                        })


    def set_sched_to_draft(self, sched_id):
        instance = self.env['invoice.installment.line'].search([('id','=', sched_id)], limit=1)
        print("##################")
        print("setting to draft")

        instance.update({
                            'payment_transaction': False,
                            'state':'draft',
                            'is_paid': False,
                            'balance': 0,
                            'date_paid': False,
                            'paid_amount': 0,
                        })
    
    def set_sched_to_draft_all(self):
        all_sched = self.env['invoice.installment.line'].search([('id','!=', 0)])

        for sched_line in all_sched:
            self.set_sched_to_draft(sched_line.id)
    
    def set_sched_to_draft_by_invoice(self, invoice_id):
        all_sched = self.env['invoice.installment.line'].search([('account_invoice_id','=', invoice_id)])

        for sched_line in all_sched:
            self.set_sched_to_draft(sched_line.id)

    def register_payment_amount(self, payment, invoice):
        print("================================================")
        print("registering payment")
        pay_sched_line_id = None
        # sched_instance = self.env['invoice.installment.line']
                    
        if invoice.purchase_term == 'install' and invoice.is_split:

            to_out = []
                        
            monthly = self.get_monthly_amort_sched('unpaid', invoice.id)
            downs = self.get_downpayment_sched('unpaid', invoice.id)


            for index, line in enumerate(monthly):
                if index < len(downs):
                    to_out.append(downs[index])

                to_out.append(line)

            pay_sched_line_id = to_out

        else:
            if invoice.purchase_term == 'cash' and invoice.is_split == False:
                pay_sched_line_id = self.env['invoice.installment.line'].search([('account_invoice_id','=', invoice.id)])
            else:
                pay_sched_line_id = self.env['invoice.installment.line'].search([('account_invoice_id','=', invoice.id),('is_paid','=', False)], order="id asc")

        amount_in = payment.amount


        if payment.invoice_is_terminated and payment.reactivation_fee_paid == False:
            amount_in -= payment.reactivation_fee

        if payment.surcharge_included:
            amount_in -= payment.surcharge

        amount_catered = 0
        current_index = 0

        down_payment_catered = 0
        monthly_payment_catered = 0



        while round(amount_catered, 2) < round(amount_in, 2):
            print("+++++++")
            print("paying")
            current_line = pay_sched_line_id[current_index]
            amount_to_pay = current_line.amount_to_pay - current_line.balance
            amount_to_dispose = amount_in - amount_catered
            amount_to_register = 0
                    
            amount_to_register = amount_to_dispose if amount_to_pay > amount_to_dispose else amount_to_pay

            if current_line.type == 'down':
                down_payment_catered = amount_to_register

            if current_line.type == 'install':
                monthly_payment_catered = amount_to_register

            # sched_instance = self.env['invoice.installment.line']
            self.register_payment(amount_to_register, payment.id, payment.payment_date, current_line.id)
            current_index += 1
            amount_catered += amount_to_register


    def get_monthly_amort_sched(self, search_type, reference_id):
        
        search_reference = {
                            
                            'all': [('account_invoice_id', '=', reference_id),('type','=','install')],
                            'paid':[('account_invoice_id', '=', reference_id), ('type','=','install'), ('is_paid','=',True)],
                            'unpaid':[('account_invoice_id', '=', reference_id), ('type','=','install'), ('is_paid','=',False)],
                            'due':[('account_invoice_id', '=', reference_id),('date_for_payment','>=', date.today()),('type','=','install'), ('is_paid','=',False)],
        }

        search_result = self.env['invoice.installment.line'].search(search_reference[search_type], order="id asc")

        return search_result

    def get_downpayment_sched(self, search_type, reference_id):
        
        search_reference = {
                            
                            'all': [('account_invoice_id', '=', reference_id),('type','=','down')],
                            'paid':[('account_invoice_id', '=', reference_id), ('type','=','down'), ('is_paid','=',True)],
                            'unpaid':[('account_invoice_id', '=', reference_id), ('type','=','down'), ('is_paid','=',False)],
                            'due':[('account_invoice_id', '=', reference_id),('date_for_payment','>=', date.today()),('type','=','down'), ('is_paid','=',False)],
        }

        search_result = self.env['invoice.installment.line'].search(search_reference[search_type], order="id asc")

        return search_result
        
    def get_all_sched(self, search_type, reference_id):
        
        search_reference = {
                            
                            'all': [('account_invoice_id', '=', reference_id)],
                            'paid':[('account_invoice_id', '=', reference_id), ('is_paid','=',True)],
                            'unpaid':[('account_invoice_id', '=', reference_id), ('is_paid','=',False)],
                            'due':[('account_invoice_id', '=', reference_id),('date_for_payment','>=', date.today()), ('is_paid','=',False)],
        }

        search_result = self.env['invoice.installment.line'].search(search_reference[search_type], order="id asc")

        return search_result

    def get_payment_date_status(self):
        for line in self:
            output_data = ''

            payment_date = datetime.strptime(line.date_paid,'%Y-%m-%d')
            due_payment_date = datetime.strptime(line.date_for_payment,'%Y-%m-%d')

            if payment_date >= due_payment_date - timedelta(days=30) and payment_date <= due_payment_date:
                output_data = 'current'
            if payment_date < due_payment_date - timedelta(days=30):
                output_data = 'advance'
            if payment_date > due_payment_date:
                output_data = 'past'

            return output_data
    
    # def get_latest_update(self, invoice_reference):


    # @api.multi
    # def print_receipt(self):
    #     for s in self:
    #         # sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))
    #         account_payment = s.env['account.payment'].search([('id', '=', s.payment_transaction.id)])
    #         # print s.payment_transaction
    #         # print account_payment.or_series
    #         if account_payment:
    #             return s.env['report'].get_action(s, 'brdc_account.official_receipt_view_line')
    #         else:
    #             # print 1
    #             raise UserError(_("No payment record!"))
    #
    # def cancel_payment(self):
    #     for s in self:
    #         am_in = s.env['account.move'].search([('installment_line_id','=',s.id)])
    #         aml_in = s.env['account.move.line'].search([('move_id','=',am_in.id)])
    #         for move_line in aml_in:
    #             print(move_line.name)
    #         for c in s.cover_by:
    #             print(c.paid_amount)
    #
    # def get_pa(self):
    #     pa = None
    #     for s in self:
    #         pa = s.account_invoice_id.pa_ref
    #     return 'P.A.: %s' % pa
    #
    # def get_journal(self):
    #     journal = None
    #     for s in self:
    #         journal = s.payment_transaction.journal_id
    #     j_name = None
    #     for j in journal:
    #         j_name = j.name
    #     return j_name
    #
    # def get_covered_months(self):
    #     for s in self:
    #         payment_ = []
    #         children = self.env['invoice.installment.line'].search([('cover_by', '=', s.id)])
    #         payment_.append(s.date_for_payment)
    #         adv = []
    #         cov = ""
    #         if children:
    #             for child in children:
    #                 payment_.append(child.date_for_payment)
    #                 adv.append(child.amount_to_pay if child.paid_amount > child.amount_to_pay else child.advance_payment)
    #             start = parser.parse(payment_[0])
    #             end = parser.parse(payment_[-1])
    #             adv_ = '{:0,.2f}'.format(adv[-1])
    #             cov = "%s - %s" % (datetime.strftime(start, "%b"), datetime.strftime(end, "%b") + ' adv: ' + adv_)
    #         else:
    #             cov = s.date_for_payment
    #         return cov

class InvoiceInstallmentLineDP(models.Model):
    _name = 'invoice.installment.line.dp'
    _inherit = 'invoice.installment.line'
# #     _order = 'date_for_payment, date_paid'
#
#     def print_receipt(self):
#         for s in self:
#             # sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))
#             account_payment = s.env['account.payment'].search([('id', '=', s.payment_transaction.id)])
#             # print s.payment_transaction.name
#             # print account_payment.or_series.name
#             if account_payment:
#                 return s.env['report'].get_action(s, 'brdc_account.official_receipt_view_dp')
#             else:
#                 raise UserError(_("No payment record!"))
#
#     def cancel_payment(self):
#         for s in self:
#             am_in = s.env['account.move'].search([('downpayment_line_id','=',s.id)])
#             aml_in = s.env['account.move.line'].search([('move_id','=',am_in.id)])
#             for move_line in aml_in:
#                 print(move_line.name)
#             for c in s.cover_by:
#                 print(c.paid_amount)
#
#     def get_pa(self):
#         pa = None
#         for s in self:
#             pa = s.account_invoice_id.pa_ref
#         return 'P.A.: %s' % pa
#
#     def get_journal(self):
#         journal = None
#         for s in self:
#             journal = s.payment_transaction.journal_id
#         j_name = None
#         for j in journal:
#             j_name = j.name
#         return j_name
#
#     def get_covered_months(self):
#         for s in self:
#             payment_ = []
#             children = self.env['invoice.installment.line'].search([('cover_by', '=', s.id)])
#             payment_.append(s.date_for_payment)
#             adv = []
#             cov = ""
#             if children:
#                 for child in children:
#                     payment_.append(child.date_for_payment)
#                     adv.append(child.amount_to_pay if child.paid_amount > child.amount_to_pay else child.advance_payment)
#                 start = parser.parse(payment_[0])
#                 end = parser.parse(payment_[-1])
#                 adv_ = '{:0,.2f}'.format(adv[-1])
#                 cov = "%s - %s" % (datetime.strftime(start, "%b"), datetime.strftime(end, "%b") + ' adv: ' + adv_)
#             else:
#                 cov = s.date_for_payment
#             return cov


