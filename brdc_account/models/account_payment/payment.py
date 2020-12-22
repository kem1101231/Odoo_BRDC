from odoo import api, fields, models,_
from odoo.exceptions import UserError, ValidationError
import num2words
from dateutil.relativedelta import relativedelta
from datetime import datetime
import math
from re import sub
from decimal import Decimal
import locale

MAP_INVOICE_TYPE_PARTNER_TYPE = {
    'out_invoice': 'customer',
    'out_refund': 'customer',
    'in_invoice': 'supplier',
    'in_refund': 'supplier',
}

MAP_INVOICE_TYPE_PAYMENT_SIGN = {
    'out_invoice': 1,
    'in_refund': 1,
    'in_invoice': -1,
    'out_refund': -1,
}


class AccountPayment(models.Model):
    # _name = 'loan.account.payment'
    _inherit = 'account.payment'
    _rec_name = 'or_reference'

    #amount = fields.Monetary('Payment Amount',readonly=True, required=True)

    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Additional Fields 
    # @api.depends('amount_received')
    # def get_amount_value_from_received(self):

    amount = fields.Monetary('Amount to Cater', required=True)
    amount_tender = fields.Monetary('Amount Due',readonly=True, required=True)
    is_exact = fields.Selection([('exact','Cater amount due'),
                                 ('inexact','Cater more/less than amount due')],
                                string=' ', default="exact",
                                required=True)
    
    change_release = fields.Selection([('keep','Keep change as advance'),
                                 ('return','Return change to customer')],
                                string=' ', default="return",
                                required=True)

    user_id = fields.Many2one(comodel_name="res.users", string="Responsible", required=True,
                              default=lambda self: self.env.user, readonly=1)
    payment_type = fields.Selection([('outbound', 'Send Money'), ('inbound', 'Receive Money')], string='Payment Type',
                                    required=True, default='inbound')
    scheduled_payment_id = fields.Integer()

    invoice_past_due_amount = fields.Monetary(string="Previous Due")
    invoice_advances_amount = fields.Monetary(string="Advances")
    invoice_advances_amount_whole = fields.Monetary(string="Advances")

    pa_reference = fields.Char(string='PA Ref.', compute='get_pareference', store=True)
    prev_due = fields.Monetary(string="Previous Due")
    current_due = fields.Monetary(string="Current Due")
    current_due_date = fields.Date(string="Due on")
    total_to_pay = fields.Monetary(string="Total Due")

    amount_received = fields.Monetary(string="Amount Tender", required=True)
    value_change = fields.Monetary(string="Change", compute="get_change", store=True)

    invoice_is_terminated = fields.Boolean(string="Terminated Account")
    display_advance = fields.Boolean(string="Display Advances")
    display_advance_whole = fields.Boolean(string="Display Advances")

    terminate_due = fields.Monetary(string="Balance to Pay")
    reactivation_fee = fields.Monetary(string="Reactivation Fee")
    reactivation_fee_paid = fields.Boolean(string="Reactivation Fee Paid")

    brdc_account_move = fields.Many2many(comodel_name="account.brdc.move", string="BRDC Account Entry")
    payment_record_type = fields.Selection(selection=[('cashier','BRDC Cashier'),('collect','BRDC Collector')], string="Collected Throughs", default='cashier')

    collection_recorded = fields.Boolean(string="Payment added to Collection")
    # brdc_move_created = 
    
    @api.onchange('amount_received')
    def _change_amount_received(self):
        if self.amount_received:
            if self.amount_received < self.amount_tender and self.invoice_is_terminated:
                raise ValidationError(_('Amount Tender should be higher or equal to the "Amount Due"'))
            else:
                if self.change_release == 'keep':
                    self.amount = self.amount_received
                else:
                    self.amount = self.amount_tender if self.amount_received > self.amount_tender else self.amount_received


    @api.depends('amount', 'amount_received')
    def get_change(self):
        for payment in self:
            change = payment.amount_received - payment.amount
            if change > 0:
                payment.value_change = change
                payment.update({'value_change':change})
        

    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Background Function 

    @api.onchange('is_exact')
    def tender_amount(self):
        if self.is_exact == 'exact':
            #print("_________________________________")
            #print(type(self.amount_tender))
            #print(self.amount_tender) 
            self.amount = self.amount_tender

        if self.is_exact == 'inexact':
            self.amount = 0
    
    @api.onchange('change_release')
    def change_release_check(self):
        if self.change_release == 'return':
            self.amount = self.amount_tender

        if self.change_release == 'keep':
            self.amount = self.amount_received
    
    @api.model
    def default_get(self, fields):

        rec = super(AccountPayment, self).default_get(fields)
        
        invoice_defaults = self.resolve_2many_commands('invoice_ids', rec.get('invoice_ids'))
        ##print("&*&*&*&*&*&*&*&*&*&*&*&*&s")
        ##print(rec['payment_method_id'])

        if invoice_defaults and len(invoice_defaults) == 1:
            invoice = invoice_defaults[0]
            amount_value_list = self.get_default_amount()
            amount_value = amount_value_list['amount_total']

            product_type = self.env['payment.config'].search([('id','=',invoice['product_type'][0])])
            trans_type = invoice['purchase_term']
            is_full = invoice['is_paidup']
            is_split = invoice['is_split']
            full_dp = invoice['s_dp']
            split_dp = invoice['st4_dp']
            total_paid = invoice['total_paid']
            journal_id_use = 0


            if trans_type == 'cash':

                if  is_full == True:
                    journal_id_use = product_type['full_cash']['id']

                if is_split == True:
                    journal_id_use = product_type['split_cash']['id']
            else:

                no_month_str = (invoice['new_payment_term_id'][1]).split(' ')
                no_months = int(no_month_str[0])

                if no_months <= 48:

                    if (total_paid < full_dp and is_full) or (total_paid < (split_dp * 3) and is_split):
                        if is_full:
                            journal_id_use = product_type['downpayment']['id']
                        if is_split: 
                            journal_id_use = product_type['split_downpayment']['id']
                    
                    else:
                        journal_id_use = product_type['amortization']['id']
                
                else:
                    journal_id_use = product_type['amortization']['id']

            rec['communication'] = invoice['reference'] or invoice['name'] or invoice['number']
            rec['currency_id'] = invoice['currency_id'][0]
            rec['payment_type'] = invoice['type'] in ('out_invoice', 'in_refund') and 'inbound' or 'outbound'
            rec['partner_type'] = MAP_INVOICE_TYPE_PARTNER_TYPE[invoice['type']]
            rec['partner_id'] = invoice['partner_id'][0]
            rec['amount'] = 0
            rec['amount_tender'] = amount_value

            rec['payment_with_surcharge'] = invoice['surcharge'] + amount_value
            rec['pa_reference'] = invoice['pa_ref']
            rec['journal_id'] = journal_id_use,
            rec['pa_reference'] = invoice['pa_ref']
            rec['invoice_past_due_amount'] = invoice['monthly_due']
            rec['invoice_advances_amount'] = invoice['advances']
            rec['invoice_advances_amount_whole'] = int(invoice['advances'])
            rec['prev_due'] = invoice['monthly_due']
            rec['current_due'] = invoice['current_due']
            rec['total_to_pay'] = amount_value

            rec['display_advance'] = amount_value_list['display_advance']
            rec['display_advance_whole'] = amount_value_list['display_advance_whole']
            rec['current_due_date'] = invoice['current_due_date']
            
            if invoice['state'] == 'pre_active':
                
                termination_data = self.env['account.invoice.terminate.info'].search([('id','=',invoice['curr_termination_id'][0])], limit=1)
                
                rec['invoice_is_terminated'] = True
                rec['terminate_due'] = termination_data[0].amount_due
                rec['reactivation_fee'] = 200
                
                rec['surcharge'] = invoice['surcharge']
                #rec['payment_with_surcharge'] = invoice['surcharge'] + amount_value
                rec['reactivation_fee_paid'] = termination_data.reactivation_paid
                # rec['surcharge_included'] = Tr

                #print("++++++++++++++++++++++++++++++++ ===== +")
                #print(termination_data.reactivation_paid)
  
            # rec['pa_ref'] = invoice['pa_ref']
            # #print rec['surcharge'], 'surbok'
            # #print rec['pa_reference'], 'test'

            # #print rec['pa_ref'], 'test'
            # rec['scheduled_payment_id'] = self.get_default_id()
            # #print 'hhgaw'
        
        return rec



    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Unused Functions 

    @api.multi
    def post_payments_(self):

        payments = self.env['account.payment'].search([('state', '=', 'draft'), ('user_id', '=', self._uid)]).filtered(
            lambda rec: rec.journal_id.id == 43
        )
        #print(self.env['res.users'].search([('id', '=', self._uid)]).name)
        for payment in payments:
            #print(payment.move_name)

            # payment.cancel()
            payment.post()

    @api.multi
    def name_get(self):
        res = super(AccountPayment, self).name_get()
        data = []
        for s in self:
            display_val = ''
            display_val += (str(s.or_reference) if s.or_reference else "O.R. is Blank") or ""

            data.append((s.id, display_val))
        return data

    #++++++++++++++++++++++++++++++++++++++++++++++++
    # Commented Functions

    
    # journal_id = fields.Many2one('account.journal', string='Payment Journal', required=True,
    #                              domain=[('type', 'in', ('bank', 'cash')), ('company_id','=', 'user.company_id')])
    # < field
    # name = "domain" > [('type', 'in', ('out_invoice', 'out_refund'))] < / field >
    # < field
    # name = "context" > {'type': 'out_invoice', 'journal_type': 'sale'} < / field >
    # @api.multi
    # def button_invoices(self):
    #     return "%(account.)d"
    #     # return {
    #     #     'name': _('Invoice'),
    #     #     'view_type': 'tree',
    #     #     'view_mode': 'tree,form',
    #     #     'res_model': 'account.invoice',
    #     #     'view_id': False,
    #     #     'type': 'ir.actions.act_window',
    #     #     'domain': [('type', 'in', ('out_invoice', 'out_refund')),('id', '=', self.account_invoice_id.id)],
    #     #     'context': {'type': 'out_invoice', 'journal_type': 'sale'}
    #     # }



    @api.onchange('account_invoice_id')
    def get_pareference(self):
        # account_invoice = self.env['account.invoice'].browse(self._context.get('active_ids', []))
        for s in self:
            s.pa_reference = s.account_invoice_id.pa_ref

    surcharge_included = fields.Boolean(string='Surcharge Included', default=False)
    surcharge_included_select = fields.Selection(string="Include Surcharge", selection=[('1','Yes'),('0','No')])
    surcharge = fields.Monetary(string='Surcharge', track_visibility='always', compute='get_surcharge', store=True)
    payment_with_surcharge = fields.Monetary(string='Total Payment', compute='with_surcharge_payment')

    @api.onchange('surcharge_included')
    def _onchange_surcharge_included(self):
        if self.surcharge_included:
            self.amount_tender += self.surcharge
            self.amount += self.surcharge
            
        else:
            self.amount_tender = self.total_to_pay
            self.amount = self.total_to_pay
    
    @api.onchange('surcharge_included_select')
    def _change_surcharge_select(self):
        if self.surcharge_included_select:
            if self.surcharge_included_select == '1':
                self.surcharge_included = True
            else:
                self.surcharge_included = False


    @api.multi
    def get_surcharge(self):
        account_invoice = self.env['account.invoice'].browse(self._context.get('active_ids', []))
        #print("_______________________")
        #print(account_invoice.surcharge)
        for s in self:
            s.surcharge = account_invoice.surcharge

    @api.multi
    def with_surcharge_payment(self):
        account_invoice = self.env['account.invoice'].browse(self._context.get('active_ids', []))
        for s in self:
            s.payment_with_surcharge = self.get_default_amount() + account_invoice.surcharge

    @api.multi
    def get_property_surcharge(self):
        property_surcharge = self.env.ref('ir_property.brdc_surcharge_property_id')
        #print property_surcharge.name

    @api.multi
    # @api.depends('surcharge_included')
    def with_surcharge(self):
        #print("+++++++++++++++++++++++++++++++++++++++++++++++++++")
        #print("executing 'with_surcharge'")


        account_invoice = self.env['account.invoice'].browse(self._context.get('active_ids', []))
        surcharge = account_invoice.surcharge + self.reactivation_fee

        payment_ = None
        for s in self:
            amount = s.get_default_amount()
            payment = s.env['account.payment'].search([])
            total = None
            if s.surcharge_included:
                payment_ = payment.create({
                    'paymentType': 'manual',
                    'or_reference': self.or_reference,
                    'journal_id': account_invoice.surcharge_journal.id,
                    'amount': surcharge,
                    'amount_tender': surcharge,
                    'amount_received': surcharge,
                    'payment_difference_handling': 'open',
                    'payment_date': self.payment_date,
                    'partner_type': 'customer',
                    'payment_type': 'inbound',
                    'account_invoice_id': account_invoice.id,
                    'communication': '%s - %s' % (account_invoice.number,self.or_reference),
                    'partner_id': account_invoice.partner_id.id,
                    'user_id': s.env.user.id,
                    'payment_method_id': 1,
                    'has_invoices': False,
                    'invoice_ids': [(4, account_invoice.id)],
                    'pa_reference': account_invoice.pa_ref,
                    # 'pa_ref': account_invoice.pa_ref
                })
                # total = amount + s.surcharge
                payment_to_post = payment.search([('id', '=', payment_.id)])
                #print post, 'posssssssssssssst'
                payment_to_post.post()
                self.surcharge_entry(payment_to_post, account_invoice.surcharge_journal)
                # account_invoice.update_surcharge()
            else:
                pass

    @api.multi
    def surcharge_entry(self, rec, journal):
        move_line_ids = rec.mapped('move_line_ids')
        for line in move_line_ids:
            # amount = line.debit - line.credit
            if line.balance < 0:
                # credit
                self._cr.execute("""
                                update account_move_line set account_id = %s where id = %s
                                """ % (journal.default_debit_account_id.id, line.id))
                self._cr.commit()
                pass
            else:
                # debit
                self._cr.execute("""
                                update account_move_line set account_id = %s where id = %s
                                """ % (journal.default_credit_account_id.id, line.id))
                self._cr.commit()
                pass

        # return payment_, account_invoice.update_surcharge()
        # s.amount = total

    # @api.multi
    # def surcharge_journal(self):
    #     if self.surcharge_included and self.surcharge:
    #         account_invoice = self.env['account.invoice'].browse(self._context.get('active_ids', []))
    #         surcharge = account_invoice.surcharge_journal
    #         surcharge_amount = account_invoice.surcharge
    #         line_count = sum(account_invoice.move_id.line_ids)
    #
    #         account_invoice.update_surcharge()
    #
    #         pass
    #     else:
    #         pass

    @api.multi
    def write_payment_schedule(self):
        # account_invoice = self.env['account.invoice'].browse(self._context.get('active_ids', []))
        # self._cr.execute("""
        # select amount_to_pay from invoice_installment_line where account_invoice_id = %s and date_for_payment = '%s'
        # """ % (account_invoice.id, account_invoice.month_to_pay))
        # res = self._cr.fetchall()
        # #print res[0], 'res'
        # for r in res:
        #     self._cr.execute("""
        #     update invoice_installment_line set payable_balance = %s, amount_to_pay = %s
        #     where account_invoice_id = %s and date_for_Payment = '%s'
        #     """ % (r[0] + self.surcharge, r[0] + self.surcharge, account_invoice.id, account_invoice.month_to_pay))
        # account_invoice.get_total_payment()
        pass

    def get_default_amount(self):
        
        account_invoice = self.env['account.invoice'].browse(self._context.get('active_ids', []))
        amount = 0.00
        surcharge = account_invoice.surcharge

        def roundup(a, digits=0):
            n = 10 ** - digits
            #return round(math.ceil(a / n) * n, digits)
            return round(a)

        # if account_invoice.purchase_term == 'cash':
        #     if account_invoice.is_split == True:
        #         amount = account_invoice.split_cash
        #     else:
        #         amount = account_invoice.spot_cash

        # else:
        #     if account_invoice.new_payment_term_id.no_months < 48:
        #         if (account_invoice.total_paid < account_invoice.s_dp and account_invoice.is_paidup) or (account_invoice.total_paid < (account_invoice.st4_dp * 4) and account_invoice.is_split):
        #             if account_invoice.is_paidup:
        #                 amount = account_invoice.s_dp
        #             else:
        #                 amount = account_invoice.st4_dp
        #         else:
        #             amount = account_invoice.monthly_payment 

        #     else:
        #         amount = account_invoice.monthly_payment

        # amount = account_invoice.current_due

        # if account_invoice.purchase_term == 'install' and account_invoice.is_split:
        #     sched_instance = self.env['invoice.installment.line']
        #     monthly = sched_instance.get_monthly_amort_sched('unpaid', account_invoice.id)
        #     downs = sched_instance.get_downpayment_sched('unpaid', account_invoice.id)

        #     amount = monthly[0].amount_to_pay
        #     amount += downs[0].amount_to_pay if len(downs) != 0 else 0

        # else:
        amount = account_invoice.current_due  

        wo_amount = amount

        display_advance = False
        display_advance_whole = False

        if account_invoice.state == 'pre_active':
            terminate_data = account_invoice.curr_termination_id
            # amount_to_pay = terminate_data.amount_per_collection
            # advances = terminate_data.advance
            reactivation_fee = 200 if terminate_data.reactivation_paid == False else 0

            amount += terminate_data.amount_due + reactivation_fee


        else:

            if account_invoice.monthly_due != 0:
                amount += account_invoice.monthly_due

            else:
                if account_invoice.advances != 0:
                    amount_wo_advance = amount - account_invoice.advances

                    if amount_wo_advance == int(amount_wo_advance):
                        amount = amount_wo_advance
                        display_advance = True
                        

                    else:
                        if int(account_invoice.advances) != 0:
                            
                            if roundup(amount) < wo_amount:
                                amount += 1

                            amount -= int(account_invoice.advances)
                            display_advance_whole = True

                else:           

                    if roundup(amount) < wo_amount:
                        amount += 1

        # if account_invoice.purchase_term == 'install':
        #     paid_amount = account_invoice.total_paid
        #     dp_ref = 0

        #     if account_invoice.is_split == True:
        #         dp_ref = account_invoice.st4_dp
        #     else:
        #         dp_ref = account_invoice.s_dp

        #     if paid_amount >= account_invoice.s_dp:
        #         amount = account_invoice.monthly_payment
        #     else:
        #         amount = account_invoice.s_dp - paid_amount

        # elif account_invoice.purchase_term == 'cash' and not account_invoice.is_split:
        #     amount = account_invoice.spot_cash
        # elif account_invoice.purchase_term == 'cash' and account_invoice.is_split:
        #     amount = account_invoice.split_cash
        
        # elif not account_invoice.payment_count and not account_invoice.monthly_due:
        #     paid_amount = account_invoice.total_paid
        #     if paid_amount >= account_invoice.s_dp:
        #         amount = account_invoice.monthly_payment
        #     else:
        #         amount = account_invoice.s_dp - paid_amount
        # elif not account_invoice.amount_to_pay:
        #     paid_amount = account_invoice.total_paid
        #     if paid_amount >= account_invoice.s_dp:
        #         amount = account_invoice.monthly_payment
        #     else:
        #         amount = account_invoice.s_dp - paid_amount
        # else:
        #     amount = account_invoice.amount_to_pay
            


        if self.surcharge_included:
            total = amount + surcharge
        else:
            total = amount

        return {'amount_total':roundup(total),'wo_additions':wo_amount,'display_advance': display_advance,'display_advance_whole': display_advance_whole}

    def get_default_id(self):
        account_invoice = self.env['account.invoice'].browse(self._context.get('active_ids', []))
        dp_id = self.env['invoice.installment.line.dp'].search(
            [('account_invoice_id', '=', account_invoice.id), ('is_paid', '=', False)])
        line_id = self.env['invoice.installment.line'].search(
            [('account_invoice_id', '=', account_invoice.id), ('is_paid', '=', False)])
        if len(dp_id) > 0:
            id = dp_id[0].id
        else:
            id = line_id[0].id

        return id

# #here i am
#     @api.model
#     def create(self, vals):
#         or_number_line = self.env['or.series.line']
#         # vals['or_series'] = self.or_series.id
#         vals['or_series_text'] = or_number_line.search([('id', '=', vals['or_series'])]).name or _('New')
#         vals['name'] = or_number_line.search([('id', '=', vals['or_series'])]).name
#         #print(self.or_series.state)
#         res = super(AccountPayment, self).create(vals)
#         write_status = self.or_series_write
#         #print(self.or_series_write(vals['or_series_text'],'used'))
#         #print(self.payment_sequence_or_series(vals['or_series'],vals['or_series_text']))
#         return res

    # @api.multi
    # def post(self):
    #     for rec in self:
    #         or_number_line = self.env['or.series.line']
    #         or_series = or_number_line.search([('or_series_id.responsible', '=', self.env.user.name), ('state', '=', 'unused')])[0].id
    #         rec.name = or_number_line.search([('id', '=', or_series)]).name
    #         rec.create({'name':rec.name})

    def get_default(self):
        or_number_line = self.env['or.series.line']
        return or_number_line.search([('or_series_id.responsible', '=', self.env.user.name), ('state', '=', 'unused')])[0].id

    def or_series_write(self,x,y):
        or_number_line = self.env['or.series.line']
        or_number = or_number_line.search([('name', '=', x)])
        rec = or_number.write({'state':y})
        return rec

    def payment_sequence_or_series(self,x,y):
        payment_line = self.env['account.payment']
        payments = payment_line.search([('or_series','=',x)])
        return payments.write({'name':y})

    def return_write(self,dp_line_id_1,dp_line_id_2,paid_amount,balance,payable_balance,beginning_b,ending_b):
        line_dp_id = dp_line_id_1.write({
            'is_paid': True,
            'paid_amount': paid_amount,
            'balance': balance,
            'state': 'confirm',
            'payment_transaction': self.id,
            'ending_balance': ending_b,
            'date_paid': self.payment_date
        })
        dp_line_id_2.write({
            'beginning_balance': beginning_b,
            'advance_payment': balance,
            'payable_balance': payable_balance
        })

    # @api.multi
    # def #print_report(self):
    #     return {
    #         'type': 'ir.actions.report.xml',
    #         'report_name': 'brdc_account.official_receipt_view'
    #     }
    # is_first = fields.Boolean(default=False)

    def on_post(self):

        #print("+++++++++++++++++++++++++++++++++++++++++++++++++++")
        #print("executing 'on_post'")

        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only a draft payment can be posted. Trying to post a payment in state %s.") % rec.state)
            if any(inv.state not in ['open','pre_active'] for inv in rec.invoice_ids):
                raise ValidationError(_("The payment cannot be processed because the invoice is not open!"))

            if rec.amount_received < rec.amount_tender and rec.invoice_is_terminated:
                raise ValidationError(_('Amount Tender should be higher or equal to the "Amount Due"'))
            
            # Use the right sequence to set the name
            if rec.payment_type == 'transfer':
                sequence_code = 'account.payment.transfer'
            else:
                if rec.partner_type == 'customer':
                    if rec.payment_type == 'inbound':
                        sequence_code = 'account.payment.customer.invoice'
                    if rec.payment_type == 'outbound':
                        sequence_code = 'account.payment.customer.refund'
                if rec.partner_type == 'supplier':
                    if rec.payment_type == 'inbound':
                        sequence_code = 'account.payment.supplier.refund'
                    if rec.payment_type == 'outbound':
                        sequence_code = 'account.payment.supplier.invoice'
            
            or_number_line = self.env['or.series.line']

            # rec.name = self.env['ir.sequence'].with_context(ir_sequence_date=rec.payment_date).next_by_code(sequence_code)
            rec.name = '%s' % or_number_line.search([('id', '=', rec.or_series.id)]).name
            if not rec.name and rec.payment_type != 'transfer':
                raise UserError(_("You have to define a sequence for %s in your company.") % (sequence_code,))

            # Create the journal entry
            amount = rec.amount * (rec.payment_type in ('outbound', 'transfer') and 1 or -1)
            move = rec._create_payment_entry(amount, rec.scheduled_payment_id)

            # In case of a transfer, the first journal entry created debited the source liquidity account and credited
            # the transfer account. Now we debit the transfer account and credit the destination liquidity account.
            if rec.payment_type == 'transfer':
                transfer_credit_aml = move.line_ids.filtered(lambda r: r.account_id == rec.company_id.transfer_account_id)
                transfer_debit_aml = rec._create_transfer_entry(amount)
                (transfer_credit_aml + transfer_debit_aml).reconcile()

            rec.write({'state': 'posted', 'move_name': move.name})

    def _create_payment_entry(self, amount, id):

        aml_obj = self.env['account.move.line'].with_context(check_move_validity=False)
        
        invoice_currency = False
        
        if self.invoice_ids and all([x.currency_id == self.invoice_ids[0].currency_id for x in self.invoice_ids]):
            invoice_currency = self.invoice_ids[0].currency_id
        
        debit, credit, amount_currency, currency_id = aml_obj.with_context(date=self.payment_date).compute_amount_fields(amount, self.currency_id, self.company_id.currency_id, invoice_currency)
        move = self.env['account.move'].create(self._get_move_vals(id))

        counterpart_aml_dict = self._get_shared_move_line_vals(debit, credit, amount_currency, move.id, False)
        counterpart_aml_dict.update(self._get_counterpart_move_line_vals(self.invoice_ids))
        counterpart_aml_dict.update({'currency_id': currency_id})
        counterpart_aml = aml_obj.create(counterpart_aml_dict)

        if self.payment_difference_handling == 'reconcile' and self.payment_difference:
            
            writeoff_line = self._get_shared_move_line_vals(0, 0, 0, move.id, False)
            
            amount_currency_wo, currency_id = aml_obj.with_context(date=self.payment_date).compute_amount_fields(self.payment_difference, self.currency_id, self.company_id.currency_id, invoice_currency)[2:]
            total_residual_company_signed = sum(invoice.residual_company_signed for invoice in self.invoice_ids)
            total_payment_company_signed = self.currency_id.with_context(date=self.payment_date).compute(self.amount, self.company_id.currency_id)
            
            if self.invoice_ids[0].type in ['in_invoice', 'out_refund']:
                amount_wo = total_payment_company_signed - total_residual_company_signed
            else:
                amount_wo = total_residual_company_signed - total_payment_company_signed
            
            if amount_wo > 0:
                debit_wo = amount_wo
                credit_wo = 0.0
                amount_currency_wo = abs(amount_currency_wo)
            else:
                debit_wo = 0.0
                credit_wo = -amount_wo
                amount_currency_wo = -abs(amount_currency_wo)
            
            writeoff_line['name'] = self.or_reference #if 'False' else _('Counterpart')
            writeoff_line['account_id'] = self.writeoff_account_id.id
            writeoff_line['debit'] = debit_wo
            writeoff_line['credit'] = credit_wo
            writeoff_line['amount_currency'] = amount_currency_wo
            writeoff_line['currency_id'] = '%s %s' % (currency_id, 'bok')
            writeoff_line['account_invoice_id'] = self.account_invoice_id.id
            
            writeoff_line = aml_obj.create(writeoff_line)
            
            if counterpart_aml['debit']:
                counterpart_aml['debit'] += credit_wo - debit_wo
            if counterpart_aml['credit']:
                counterpart_aml['credit'] += debit_wo - credit_wo
            
            counterpart_aml['amount_currency'] -= amount_currency_wo
        
        self.invoice_ids.register_payment(counterpart_aml)

        if not self.currency_id != self.company_id.currency_id:
            amount_currency = 0
        liquidity_aml_dict = self._get_shared_move_line_vals(credit, debit, -amount_currency, move.id, False)
        liquidity_aml_dict.update(self._get_liquidity_move_line_vals(-amount))
        
        aml_obj.create(liquidity_aml_dict)

        move.post()
        return move

    @api.one
    @api.depends('invoice_ids', 'payment_type', 'partner_type', 'partner_id')
    def _compute_destination_account_id(self):
        if self.invoice_ids:
            self.destination_account_id = self.invoice_ids[0].account_id.id
        elif self.journal_id.is_customers_deposit:
            self.destination_account_id = self.journal_id.default_debit_account_id.id
        elif self.payment_type == 'transfer':
            if not self.company_id.transfer_account_id.id:
                raise UserError(_('Transfer account not defined on the company.'))
            self.destination_account_id = self.company_id.transfer_account_id.id
        elif self.partner_id:
            if self.partner_type == 'customer':
                self.destination_account_id = self.partner_id.property_account_receivable_id.id
            else:
                self.destination_account_id = self.partner_id.property_account_payable_id.id
    
    def _get_move_vals(self, id, journal=None):
        account_invoice = self.env['account.invoice'].browse(self._context.get('active_ids', []))
        dp_id = self.env['invoice.installment.line.dp'].search(
            [('account_invoice_id', '=', account_invoice.id), ('is_paid', '=', False)])
        # line_id = self.env['invoice.installment.line'].search(
        #     [('account_invoice_id', '=', account_invoice.id), ('is_paid', '=', False)])
        if len(dp_id) > 0:
            dp_val = id
            in_val = False
        else:
            dp_val = False
            in_val = id
        journal = journal or self.journal_id
        if not journal.sequence_id:
            raise UserError(_('Configuration Error !'), _('The journal %s does not have a sequence, please specify one.') % journal.name)
        if not journal.sequence_id.active:
            raise UserError(_('Configuration Error !'), _('The sequence of journal %s is deactivated.') % journal.name)
        name = self.move_name or journal.with_context(ir_sequence_date=self.payment_date).sequence_id.next_by_id()
        return {
            'name': name,
            'date': self.payment_date,
            'ref': self.communication or '',
            'company_id': self.company_id.id,
            'journal_id': journal.id,
            'installment_line_id': in_val,
            'downpayment_line_id': dp_val,
        }

    @api.multi
    def post(self):
        
        #bug here! need to finddddddd T_T
        
        for rec in self:

            if rec.state == 'draft' :

                # get the invoice tagged to the payment
                #==============================================================================

                rec.refresh()
                ai = None
                if rec.communication:
                    ai = rec.env['account.invoice'].search([('number','=',rec.communication)]) or \
                         rec.env['account.invoice'].browse(rec._context.get('active_ids', [])) or \
                         rec.env['service.order'].browse(rec._context.get('active_ids', []))
                



                # line_id = rec.env['invoice.installment.line'].search([('account_invoice_id', '=', ai.id),
                #                                                       ('is_paid', '=', False)])





                # get the payment sched to cater.
                #==============================================================================

                paid_amount = rec.amount
                advance_payment_count = 0
                
                pay_sched_line_id = None
                sched_instance = self.env['invoice.installment.line']
                
                if ai.purchase_term == 'install' and ai.is_split:

                    to_out = []
                    
                    monthly = sched_instance.get_monthly_amort_sched('unpaid', ai.id)
                    downs = sched_instance.get_downpayment_sched('unpaid', ai.id)


                    for index, line in enumerate(monthly):
                        if index < len(downs):
                            to_out.append(downs[index])

                        to_out.append(line)

                    pay_sched_line_id = to_out

                else:
                    if ai.purchase_term == 'cash' and ai.is_split == False:
                        pay_sched_line_id = rec.env['invoice.installment.line'].search([('account_invoice_id','=', ai.id)])
                    else:
                        pay_sched_line_id = rec.env['invoice.installment.line'].search([('account_invoice_id','=', ai.id),('is_paid','=', False)], order="id asc")
                    
                #print("++++++++++++===============+++++++++++++")
                #print(pay_sched_line_id)
                #for line in pay_sched_line_id:
                    #print(line.account_invoice_id.number)
                    #print(line.is_paid)
                    # #print(line.customers_id)


                # if len(line_id) > 1:
                #     if paid_amount <= line_id[0].payable_balance:
                #         NextLine_id = rec.env['invoice.installment.line'].search(['id', '=', (line_id[0].id + 1)])
                #         amount_to_pay = line_id[0].payable_balance
                #         balance = amount_to_pay - paid_amount
                #         ending_b = line_id[0].beginning_balance - paid_amount
                #         line_id[0].write({
                #             'is_paid': True,
                #             'payment_parent': True,
                #             'paid_amount': paid_amount,e
                #             'balance': balance,
                #             'state': 'confirm',
                #             'payment_transaction':
                #         })
                # rec.write_payment_schedule() TODOOOOO

                rec.with_surcharge()
                rec.on_post()

                # rec.realized_entry()
                #     # #print "single"
                # # #print "hello stupid",advance_payment_count
                # payment_line = self.env['account.payment']
                # payments = payment_line.search([('or_series', '=', self.or_series.id)])
                # # account_payment.#print_report()

                # # Ranzy
                # # self.account_invoice_id.invoice_line_ids[0].lot_id.status = 'amo' # here doggy
                #
                # # #print self.account_invoice_id.state
                #
                # giusab temporarily
                # #print "hello, baby", self.account_invoice_id.purchase_term, self.env['sale.order'].search([('id','=',self.account_invoice_id.sale_order_id.id)]).is_split
                # if advance_payment_count <= 1:
                #     line_count = self.env['sa.commission.line'].search_count([('agent_commission_id', '=',
                #                                                           self.env['agent.commission'].search([('so_id', '=',
                #                                                                                                 self.account_invoice_id.sale_order_id.id)]).id)])
                #     paid_count = self.env['invoice.installment.line'].search_count([('account_invoice_id', '=',self.account_invoice_id.id), ('is_paid', '=', True)])
                #     if line_count >= 18 and paid_count <= 1:
                #         #print line_count, paid_count
                #         return
                #
                #     if self.account_invoice_id.purchase_term == 'cash' and self.env['sale.order'].search([('id','=',self.account_invoice_id.sale_order_id.id)]).is_split == True:
                #         if self.account_invoice_id.state == 'paid':
                #             if self.env['sa.commission.line'].search([('agent_commission_id', '=',
                #                                                           self.env['agent.commission'].search([('so_id', '=',
                #                                                                                                 self.account_invoice_id.sale_order_id.id)]).id
                #                                                           ), ('is_paid', '=', False)]):
                #
                #                 self.env['sa.commission.line'].search([('agent_commission_id', '=',
                #                                                            self.env['agent.commission'].search([('so_id', '=',
                #                                                                                                  self.account_invoice_id.sale_order_id.id)]).id
                #                                                            ), ('is_paid', '=', False)])[0].write({
                #                     'date_paid': self.payment_date,
                #                     'is_paid': True,
                #                     'invoice_id': self.id,
                #                 })
                #             else:
                #                 pass
                #             if self.env['um.commission.line'].search([('agent_commission_id', '=',
                #                                                           self.env['agent.commission'].search([('so_id', '=',
                #                                                                                                 self.account_invoice_id.sale_order_id.id)]).id
                #                                                           ), ('is_paid', '=', False)]):
                #
                #                 self.env['um.commission.line'].search([('agent_commission_id', '=',
                #                                                            self.env['agent.commission'].search([('so_id', '=',
                #                                                                                                  self.account_invoice_id.sale_order_id.id)]).id
                #                                                            ), ('is_paid', '=', False)])[0].write({
                #                     'date_paid': self.payment_date,
                #                     'is_paid': True,
                #                     'invoice_id': self.id,
                #                 })
                #             else:
                #                 pass
                #             if self.env['am.commission.line'].search([('agent_commission_id', '=',
                #                                                           self.env['agent.commission'].search([('so_id', '=',
                #                                                                                                 self.account_invoice_id.sale_order_id.id)]).id
                #                                                           ), ('is_paid', '=', False)]):
                #
                #                 self.env['am.commission.line'].search([('agent_commission_id', '=',
                #                                                            self.env['agent.commission'].search([('so_id', '=',
                #                                                                                                  self.account_invoice_id.sale_order_id.id)]).id
                #                                                            ), ('is_paid', '=', False)])[0].write({
                #                     'date_paid': self.payment_date,
                #                     'is_paid': True,
                #                     'invoice_id': self.id,
                #                 })
                #             else:
                #                 pass
                #     else:
                #         if self.env['sa.commission.line'].search([('agent_commission_id','=', self.env['agent.commission'].search([('so_id', '=', self.account_invoice_id.sale_order_id.id)]).id
                #                                                    ),('is_paid','=',False)]):
                #
                #             self.env['sa.commission.line'].search([('agent_commission_id','=', self.env['agent.commission'].search([('so_id', '=', self.account_invoice_id.sale_order_id.id)]).id
                #                                                        ),('is_paid','=',False)])[0].write({
                #                 'date_paid': self.payment_date,
                #                 'is_paid':True,
                #                 'invoice_id':self.id,
                #             })
                #         else:
                #             pass
                #         if self.env['um.commission.line'].search([('agent_commission_id','=', self.env['agent.commission'].search([('so_id', '=', self.account_invoice_id.sale_order_id.id)]).id
                #                                                    ),('is_paid','=',False)]):
                #
                #             self.env['um.commission.line'].search([('agent_commission_id','=', self.env['agent.commission'].search([('so_id', '=', self.account_invoice_id.sale_order_id.id)]).id
                #                                                        ),('is_paid','=',False)])[0].write({
                #                 'date_paid': self.payment_date,
                #                 'is_paid':True,
                #                 'invoice_id':self.id,
                #             })
                #         else:
                #             pass
                #         if self.env['am.commission.line'].search([('agent_commission_id','=', self.env['agent.commission'].search([('so_id', '=', self.account_invoice_id.sale_order_id.id)]).id
                #                                                    ),('is_paid','=',False)]):
                #
                #             self.env['am.commission.line'].search([('agent_commission_id','=', self.env['agent.commission'].search([('so_id', '=', self.account_invoice_id.sale_order_id.id)]).id
                #                                                        ),('is_paid','=',False)])[0].write({
                #                 'date_paid': self.payment_date,
                #                 'is_paid':True,
                #                 'invoice_id':self.id,
                #             })
                #         else:
                #             pass
                # elif advance_payment_count <= 0:
                #     pass
                # else:
                #     unpaid_comm = self.env['sa.commission.line'].search_count([('agent_commission_id','=', self.env['agent.commission'].search([('so_id', '=', self.account_invoice_id.sale_order_id.id)]).id
                #                                                ),('is_paid','=',False)])
                #     if unpaid_comm < advance_payment_count:
                #         #print unpaid_comm
                #     else:
                #         unpaid_comm = 18
                #
                #     if self.env['sa.commission.line'].search([('agent_commission_id','=', self.env['agent.commission'].search([('so_id', '=', self.account_invoice_id.sale_order_id.id)]).id
                #                                                ),('is_paid','=',False)]):
                #         if advance_payment_count < unpaid_comm:
                #             for x in range(0,advance_payment_count):
                #                 self.env['sa.commission.line'].search([('agent_commission_id', '=',
                #                                                            self.env['agent.commission'].search([('so_id', '=',
                #                                                                                                     self.account_invoice_id.sale_order_id.id)]).id
                #                                                            ), ('is_paid', '=', False)])[0].write({
                #                     'date_paid': self.payment_date,
                #                     'is_paid': True,
                #                     'invoice_id': self.id,
                #                 })
                #         else:
                #             for x in range(0,self.env['sa.commission.line'].search_count([('agent_commission_id', '=',
                #                                                            self.env['agent.commission'].search([('so_id', '=',
                #                                                                                                     self.account_invoice_id.sale_order_id.id)]).id
                #                                                            ), ('is_paid', '=', False)])):
                #                 self.env['sa.commission.line'].search([('agent_commission_id', '=',f
                #                                                            self.env['agent.commission'].search([('so_id', '=',
                #                                                                                                     self.account_invoice_id.sale_order_id.id)]).id
                #                                                            ), ('is_paid', '=', False)])[0].write({
                #                     'date_paid': self.payment_date,
                #                     'is_paid': True,
                #                     'invoice_id': self.id,
                #                 })
                #     else:
                #         pass
                #     if self.env['um.commission.line'].search([('agent_commission_id','=', self.env['agent.commission'].search([('so_id', '=', self.account_invoice_id.sale_order_id.id)]).id
                #                                                ),('is_paid','=',False)]):
                #         if advance_payment_count < unpaid_comm:
                #             for x in range(0,advance_payment_count):
                #                 self.env['um.commission.line'].search([('agent_commission_id', '=',
                #                                                            self.env['agent.commission'].search([('so_id', '=',
                #                                                                                                     self.account_invoice_id.sale_order_id.id)]).id
                #                                                            ), ('is_paid', '=', False)])[0].write({
                #                     'date_paid': self.payment_date,
                #                     'is_paid': True,
                #                     'invoice_id': self.id,
                #                 })
                #         else:
                #             for x in range(0,self.env['um.commission.line'].search_count([('agent_commission_id', '=',
                #                                                            self.env['agent.commission'].search([('so_id', '=',
                #                                                                                                     self.account_invoice_id.sale_order_id.id)]).id
                #                                                            ), ('is_paid', '=', False)])):
                #                 self.env['um.commission.line'].search([('agent_commission_id', '=',
                #                                                            self.env['agent.commission'].search([('so_id', '=',
                #                                                                                                     self.account_invoice_id.sale_order_id.id)]).id
                #                                                            ), ('is_paid', '=', False)])[0].write({
                #                     'date_paid': self.payment_date,
                #                     'is_paid': True,
                #                     'invoice_id': self.id,
                #                 })
                #     else:
                #         pass
                #     if self.env['am.commission.line'].search([('agent_commission_id','=', self.env['agent.commission'].search([('so_id', '=', self.account_invoice_id.sale_order_id.id)]).id
                #                                                ),('is_paid','=',False)]):
                #         if advance_payment_count < unpaid_comm:
                #             for x in range(0,advance_payment_count):
                #                 self.env['am.commission.line'].search([('agent_commission_id', '=',
                #                                                            self.env['agent.commission'].search([('so_id', '=',
                #                                                                                                     self.account_invoice_id.sale_order_id.id)]).id
                #                                                            ), ('is_paid', '=', False)])[0].write({
                #                     'date_paid': self.payment_date,
                #                     'is_paid': True,
                #                     'invoice_id': self.id,
                #                 })
                #         else:
                #             for x in range(0,self.env['am.commission.line'].search_count([('agent_commission_id', '=',
                #                                                            self.env['agent.commission'].search([('so_id', '=',
                #                                                                                                     self.account_invoice_id.sale_order_id.id)]).id
                #                                                            ), ('is_paid', '=', False)])):
                #                 self.env['am.commission.line'].search([('agent_commission_id', '=',
                #                                                            self.env['agent.commission'].search([('so_id', '=',
                #                                                                                                     self.account_invoice_id.sale_order_id.id)]).id
                #                                                            ), ('is_paid', '=', False)])[0].write({
                #                     'date_paid': self.payment_date,
                #                     'is_paid': True,
                #                     'invoice_id': self.id,
                #                 })
                #
                #     else:
                #         pass


                amount_in = rec.amount


                if rec.invoice_is_terminated and rec.reactivation_fee_paid == False:
                        amount_in -= rec.reactivation_fee

                if rec.surcharge_included:
                    amount_in -= rec.surcharge

                amount_catered = 0
                current_index = 0

                down_payment_catered = 0
                monthly_payment_catered = 0



                while round(amount_catered, 2) < round(amount_in, 2):

                    current_line = pay_sched_line_id[current_index]
                    amount_to_pay = current_line.amount_due
                    amount_to_dispose = amount_in - amount_catered
                    
                    amount_to_register = amount_to_dispose if amount_to_pay > amount_to_dispose else amount_to_pay

                    if current_line.type == 'down':
                        down_payment_catered += amount_to_register

                    if current_line.type == 'install':
                        monthly_payment_catered += amount_to_register

                    sched_instance = self.env['invoice.installment.line']
                    sched_instance.register_payment(amount_to_register, rec.id, rec.payment_date, current_line.id)
                    current_index += 1
                    amount_catered += amount_to_register
               
                #print("+===========++++++++++++++++++++++++")
                
                if rec.invoice_is_terminated:
                    terminate_data = self.env['account.invoice.terminate.info'].search([('id','=',ai.curr_termination_id.id)])
                    if terminate_data.reactivation_paid == False:
                        terminate_data.update({'reactivation_paid':True,})
                    
                    if not terminate_data.surcharge_paid and rec.surcharge_included:
                        terminate_data.update({'surcharge_paid':True,})

                    self.env['account.invoice.terminate.payment'].create({
                                                                                'terminate_id':terminate_data.id,
                                                                                'payment':rec.terminate_due,
                                                                                'payment_id':rec.id,
                                                                            })

                if self.account_invoice_id.state == 'paid' and \
                        (self.account_invoice_id.product_type.name == 'Lot' or
                         self.account_invoice_id.product_type.name == 'MM Bundle' or
                         self.account_invoice_id.product_type.name == 'Columbary Vault' or
                         self.account_invoice_id.product_type.name == 'Community Vault'):
                    # #print "amo ni sa ang self.account_invoce_id",self.account_invoice_id
                    self.account_invoice_id.invoice_line_ids[0].lot_id.status = 'fp'
                elif self.account_invoice_id.state == 'open':
                    self.account_invoice_id.invoice_line_ids[0].lot_id.status = 'amo'
                else:
                    pass

                # invoice = self.env['account.invoice'].search([('number','=',rec.communication)], limit=1)


                entry_numbers = {
                                    'cash_credit':'15971000202101',
                                    'cash_debit':'15971000100250',
                                    'pcf':'15971000202102',
                                    'down_debit':'15431000100200',
                                    'down_credit':'15971000202601',
                                    'amort_debit':'15431000100200',
                                    'amort_credit':'15971000202601',
                                    'down_discount':'15431002223400',
                            }
                
                print("&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&")
                print(len(rec.brdc_account_move) == 0)
                print(rec.brdc_account_move == False)
                
                if len(rec.brdc_account_move) == 0:
                    if ai.purchase_term == 'cash':
                        
                        itemList = []
                        
                        brdc_move = self.env['account.brdc.move'].create({
                                                                            'name':"BC-" + str(ai.number) +"-"+ str(rec.or_reference),
                                                                            'journal_id':rec.journal_id.id,
                                                                            'date': ai.date_invoice,
                                                                            # 'company_id':self.env.user.company_id.id,
                                                                            'state':'draft',
                            })
                        
                        itemList.append({
                                            'brdc_move_id':brdc_move.id,
                                            'account_id':self.get_account_from_coa(entry_numbers['cash_debit']).id,
                                            'partner_id':ai.partner_id.id,
                                            'name': 'Cash in Bank',
                                            'debit':rec.amount,
                                            'credit':0,
                                            'date_maturity':ai.date_invoice,
                                            'reconciled':False,
                                    })

                        trans_cater_lot = False if not ai.lot_is_paid else True
                        excess_for_pcf = 0

                        if not ai.lot_is_paid:
                            
                            amount_to_credit = rec.amount if ai.amot_total_wo_pcf_n_disc > ai.total_paid else ai.amot_total_wo_pcf_n_disc - (ai.total_paid - rec.amount)
                            
                            itemList.append({
                                                'brdc_move_id':brdc_move.id,
                                                'account_id':self.get_account_from_coa(entry_numbers['cash_credit']).id,
                                                'partner_id':ai.partner_id.id,
                                                'name': 'Trade Receivable - Lot',
                                                'debit':0,
                                                'credit':amount_to_credit,
                                                'date_maturity':ai.date_invoice,
                                                'reconciled':False,
                                        })

                            if ai.total_paid >= ai.amot_total_wo_pcf_n_disc:
                                ai.update({'lot_is_paid':True,})
                                excess_for_pcf = rec.amount - amount_to_credit
                                trans_cater_lot = True

                        if trans_cater_lot:
                            pcf_value = rec.amount if excess_for_pcf == 0 else excess_for_pcf               
                            itemList.append({
                                            'brdc_move_id':brdc_move.id,
                                            'account_id':self.get_account_from_coa(entry_numbers['pcf']).id,
                                            'partner_id':ai.partner_id.id,
                                            'name': 'Trade Receivable - PCF',
                                            'debit':0,
                                            'credit': pcf_value,
                                            'date_maturity':ai.date_invoice,
                                            'reconciled':False,
                                        })
                        

                        brdc_move.update({'line_ids':itemList})
                        rec.write({
                                'brdc_account_move': [(4, brdc_move.id)]
                            })

                    if ai.purchase_term == 'install':

                        if down_payment_catered != 0:
                            
                            itemList = []
                            
                            brdc_move_down = self.env['account.brdc.move'].create({
                                                                            'name':"BC-" + str(ai.number) +"-"+ str(rec.or_reference),
                                                                            'journal_id':ai.product_type.downpayment.id if ai.is_paidup == True else ai.product_type.split_downpayment.id,
                                                                            'date': ai.date_invoice,
                                                                            # 'company_id':self.env.user.company_id.id,
                                                                            'state':'draft',
                            })
                            
                            if ai.is_paidup:

                                credit_value = down_payment_catered if down_payment_catered < ai.s_dp else ai.o_dp
                                
                                itemList.append({
                                                    'brdc_move_id':brdc_move_down.id,
                                                    'account_id':self.get_account_from_coa(entry_numbers['down_debit']).id,
                                                    'partner_id':ai.partner_id.id,
                                                    'name': 'Cash in Bank',
                                                    'debit':down_payment_catered,
                                                    'credit':0,
                                                    'date_maturity':ai.date_invoice,
                                                    'reconciled':False,
                                            })

                                if credit_value == ai.o_dp:
                                    itemList.append({
                                                        'brdc_move_id':brdc_move_down.id,
                                                        'account_id':self.get_account_from_coa(entry_numbers['down_discount']).id,
                                                        'partner_id':ai.partner_id.id,
                                                        'name': 'Sales Discount - Lot',
                                                        'debit': ai.o_dp - down_payment_catered,
                                                        'credit':0,
                                                        'date_maturity':ai.date_invoice,
                                                        'reconciled':False,
                                                })
                                
                                itemList.append({
                                                    'brdc_move_id':brdc_move_down.id,
                                                    'account_id':self.get_account_from_coa(entry_numbers['down_credit']).id,
                                                    'partner_id':ai.partner_id.id,
                                                    'name': 'Installment Contract Receivable - Lots',
                                                    'debit':0,
                                                    'credit':credit_value,
                                                    'date_maturity':ai.date_invoice,
                                                    'reconciled':False,
                                            })
                            if ai.is_split:

                                itemList.append({
                                                    'brdc_move_id':brdc_move_down.id,
                                                    'account_id':self.get_account_from_coa(entry_numbers['down_debit']).id,
                                                    'partner_id':ai.partner_id.id,
                                                    'name': 'Cash in Bank',
                                                    'debit':down_payment_catered,
                                                    'credit':0,
                                                    'date_maturity':ai.date_invoice,
                                                    'reconciled':False,
                                            })
                                
                                itemList.append({
                                                    'brdc_move_id':brdc_move_down.id,
                                                    'account_id':self.get_account_from_coa(entry_numbers['down_credit']).id,
                                                    'partner_id':ai.partner_id.id,
                                                    'name': 'Installment Contract Receivable - Lots',
                                                    'debit':0,
                                                    'credit':down_payment_catered,
                                                    'date_maturity':ai.date_invoice,
                                                    'reconciled':False,
                                            })
                        
                            brdc_move_down.update({'line_ids':itemList})
                            rec.write({
                                    'brdc_account_move': [(4, brdc_move_down.id)]
                                })
                                



                        if monthly_payment_catered != 0:
                            print("+++++++++++++++++++ monthly  +++++++++++++++++++++++++++++++++++++++")
                            print(monthly_payment_catered)

                            itemList = []
                            
                            brdc_move_install = self.env['account.brdc.move'].create({
                                                                            'name':"BC-" + str(ai.number) +"-"+ str(rec.or_reference),
                                                                            'journal_id':ai.product_type.amortization.id,
                                                                            'date': ai.date_invoice,
                                                                            # 'company_id':self.env.user.company_id.id,
                                                                            'state':'draft',
                            })

                            itemList.append({
                                                    'brdc_move_id':brdc_move_install.id,
                                                    'account_id':self.get_account_from_coa(entry_numbers['amort_debit']).id,
                                                    'partner_id':ai.partner_id.id,
                                                    'name': 'Cash in Bank',
                                                    'debit':monthly_payment_catered,
                                                    'credit':0,
                                                    'date_maturity':ai.date_invoice,
                                                    'reconciled':False,
                                            })

                            trans_cater_lot = False if not ai.lot_is_paid else True
                            excess_for_pcf = 0

                            if not ai.lot_is_paid:
                                
                                amount_to_credit = monthly_payment_catered if ai.amot_total_wo_pcf_n_disc > ai.total_paid else ai.amot_total_wo_pcf_n_disc - (ai.total_paid - monthly_payment_catered)
                                
                                itemList.append({
                                                    'brdc_move_id':brdc_move_install.id,
                                                    'account_id':self.get_account_from_coa(entry_numbers['amort_credit']).id,
                                                    'partner_id':ai.partner_id.id,
                                                    'name': 'Installment Contract Receivable - Lot',
                                                    'debit':0,
                                                    'credit':amount_to_credit,
                                                    'date_maturity':ai.date_invoice,
                                                    'reconciled':False,
                                            })

                                if ai.total_paid >= ai.amot_total_wo_pcf_n_disc:
                                    ai.update({'lot_is_paid':True,})
                                    excess_for_pcf = monthly_payment_catered - amount_to_credit
                                    trans_cater_lot = True

                            if trans_cater_lot:
                                pcf_value = monthly_payment_catered if excess_for_pcf == 0 else excess_for_pcf               
                                itemList.append({
                                                'brdc_move_id':brdc_move_install.id,
                                                'account_id':self.get_account_from_coa(entry_numbers['pcf']).id,
                                                'partner_id':ai.partner_id.id,
                                                'name': 'Trade Receivable - PCF',
                                                'debit':0,
                                                'credit': pcf_value,
                                                'date_maturity':ai.date_invoice,
                                                'reconciled':False,
                                            })
                            
                            brdc_move_install.update({'line_ids':itemList})
                            rec.write({
                                    'brdc_account_move': [(4, brdc_move_install.id)]
                                })
                                

                # if self.env['general.aging'].search([('id', '=', self.id)]):
                #     generate_general_aging = self.env['general.aging'].search([])
                #     dt = str(datetime.now().date())
                #     pl = 30
                #     # #print dt, pl
                #     for c in range(0, len(generate_general_aging)):
                #         generate_general_aging[c].get_days_passed(dt, pl)

                # self.account_invoice_id.lpd = self.payment_date

                # # or the loop approach, decide which is better # comment for the mean time
                # rec.account_invoice_id.total_principal_payment = rec.account_invoice_id.total_principal_payment + rec.amount
                # Ranz
                # if ai:
                #     rec.write({
                #         'payment_method_id': 1,
                #         'has_invoices': True,
                #         'account_invoice_id': ai.id
                #     })

                # return payments.write({'name': self.or_series.name}), self.dcr_line_vals(), True
                
                if ai:
                    rec.account_invoice_id = ai.id
                    # rec.with_surcharge()
                    ai.compute_residual()
                    ai.update_surcharge()
                
                # ai.sudo()._compute_residual()
                #print("%^%^%^%^%^%^%^%^%^%^%^%^")
                #print(rec.amount)

                if rec.payment_record_type == 'cashier':
                    search_result = self.env['daily.collection.record'].search([('date','=', datetime.strptime(fields.Date.today(), '%Y-%m-%d')),('collector_id','=', rec.user_id.id),('collection_type','=','cashier'),('state','=','draft')])
                    id_to_use = None
                    print("++++++++++++++++++++++++++++++++++++++++\n+++++++++++++++++++++++++++++++++++++++++\n+++++++++++++++++++++++++++++++++++")
                    print(search_result)

                    if search_result:
                        id_to_use = search_result[0]
                    else:
                        id_to_use = self.env['daily.collection.record'].create({
                                                                        'collector_id':rec.user_id.id,
                                                                        'date':datetime.strptime(fields.Date.today(), '%Y-%m-%d'),
                                                                        'collection_type':'cashier',
                                                                })
                    
                    
                    dcr_line = self.env['dcr.lines'].create({
                                    'partner_ids':rec.partner_id.id,
                                    'DailyCollectionRecord_id':id_to_use.id,
                                    'dcr_collector':rec.user_id.id,
                                    'cash_cheque_selection': rec.cash_cheque_selection,
                                    'or_reference':str(rec.or_reference),
                                    'amount_paid':rec.amount,
                                    'setdate':rec.payment_date,
                                    'state':'posted',
                                    'PA':rec.pa_reference,
                                    'invoice_id':ai.id,
                                    'journal_id':rec.journal_id.id,
                                    'description':rec.pa_reference+"-"+str(rec.or_reference),
                                    'payment_id':rec.id,
                    })
                    
                    print("+++++++++++++++++++++++++++++++++++++++++\n+++++++++++++++++++++++++++++++++++++\n+++++++++++++++++++++++++++++++++++")
                    print(id_to_use.id)
                    print(id_to_use.dcr_lines_ids)
                    # id_to_use.update({
                    #                     'dcr_lines_ids':[4, dcr_line],
                    #     })
                    print(id_to_use.dcr_lines_ids)
                    rec.update({
                                    'collected_id':dcr_line.id,
                                    'collection_id':id_to_use.id,
                            })
                    
                    
                    # dcr_line = {
                    #                 'partner_ids':rec.partner_id.id,
                    #                 'DailyCollectionRecord_id':id_to_use.id,
                    #                 'dcr_collector':rec.user_id.id,
                    #                 #'cash_cheque_selection':,
                    #                 'or_reference':str(rec.or_reference),
                    #                 'amount_paid':rec.amount,
                    #                 'setdate':rec.payment_date,
                    #                 'state':'posted',
                    #                 'PA':rec.pa_reference,
                    #                 'invoice_id':ai.id,
                    #                 'journal_id':rec.journal_id.id,
                    #                 'description':rec.pa_reference+"-"+str(rec.or_reference),
                    #                 'payment_id':rec.id,
                    # }

                rec.update({'amount':amount_in,})

            return True

    def get_account_from_coa(self, input_value):
        
        result = self.env['account.account'].search([('code','=',input_value)], limit=1)

        return result

    # @api.multi
    # def post(self):
    #     """ Create the journal items for the payment and update the payment's state to 'posted'.
    #         A journal entry is created containing an item in the source liquidity account (selected journal's default_debit or default_credit)
    #         and another in the destination reconciliable account (see _compute_destination_account_id).
    #         If invoice_ids is not empty, there will be one reconciliable move line per invoice to reconcile with.
    #         If the payment is a transfer, a second journal entry is created in the destination journal to receive money from the transfer account.
    #     """
    #     for rec in self:

    #         if rec.state != 'draft':
    #             raise UserError(_("Only a draft payment can be posted. Trying to post a payment in state %s.") % rec.state)

    #         if any(inv.state != 'open' for inv in rec.invoice_ids):
    #             raise ValidationError(_("The payment cannot be processed because the invoice is not open!"))

    #         # Use the right sequence to set the name
    #         if rec.payment_type == 'transfer':
    #             sequence_code = 'account.payment.transfer'
    #         else:
    #             if rec.partner_type == 'customer':
    #                 if rec.payment_type == 'inbound':
    #                     sequence_code = 'account.payment.customer.invoice'
    #                 if rec.payment_type == 'outbound':
    #                     sequence_code = 'account.payment.customer.refund'
    #             if rec.partner_type == 'supplier':
    #                 if rec.payment_type == 'inbound':
    #                     sequence_code = 'account.payment.supplier.refund'
    #                 if rec.payment_type == 'outbound':
    #                     sequence_code = 'account.payment.supplier.invoice'
    #         rec.name = self.env['ir.sequence'].with_context(ir_sequence_date=rec.payment_date).next_by_code(sequence_code)
    #         if not rec.name and rec.payment_type != 'transfer':
    #             raise UserError(_("You have to define a sequence for %s in your company.") % (sequence_code,))

    #         # Create the journal entry
    #         amount = rec.amount * (rec.payment_type in ('outbound', 'transfer') and 1 or -1)
    #         move = rec._create_payment_entry(amount)

    #         # In case of a transfer, the first journal entry created debited the source liquidity account and credited
    #         # the transfer account. Now we debit the transfer account and credit the destination liquidity account.
    #         if rec.payment_type == 'transfer':
    #             transfer_credit_aml = move.line_ids.filtered(lambda r: r.account_id == rec.company_id.transfer_account_id)
    #             transfer_debit_aml = rec._create_transfer_entry(amount)
    #             (transfer_credit_aml + transfer_debit_aml).reconcile()

    #         rec.write({'state': 'posted', 'move_name': move.name})

    @api.multi
    def num2word(self, num):
        value = num2words.num2words(num) + "  only"
        return value.title()

    or_reference = fields.Integer()
    
    @api.multi
    def _get_name(self):
        for s in self:
            s.name = s.or_reference
            
    name = fields.Char(compute=_get_name)

    or_series = fields.Many2one('or.series.line',
                                string='O.R. Number',
                                readonly=0,
                                # domain=[('state','=','unused')],
                                # default=lambda self: self.env['or.series.line'].search(
                                #     [('or_series_id.responsible', '=', self.env.user.name), ('state', '=', 'unused')])[
                                #     0].id
                                )
    

    account_invoice_id = fields.Many2one(comodel_name="account.invoice", string="", required=False)
    
    # @api.multi
    # def _get_invoice(self):
    #     for s in self:
    #         invoice = s.env['account.invoice'].search([('name', '=', s.communication)])
    #         #print invoice.id
    #         s.account_invoice_id = invoice.id

    @api.multi
    def get_false_label(self):
        move_line = self.env['account.move.line'].search([('name', '=', 'False' or False)])
        for line in move_line:
            payment = self.env['account.payment'].search([('id', '=', line.payment_id.id)])
            line.update({
                'name': payment.or_reference
            })

    @api.multi
    def print_or(self):
        return self.env['report'].get_action(self, 'brdc_account.official_receipt_view_line')

    @api.multi
    def print_tr(self):
        return self.env['report'].get_action(self, 'brdc_account.provisional_receipt_view')

    def get_pa(self):
        return self.env['account.invoice'].search([('number', '=', self.communication)]).pa_ref


    # def payment_is_for(self, payment_reference_id):
        
    #     payment_reference = self.env['account.payment'].search([('id','=',payment_reference_id)])
    #     invoice_refrence = self.env['account.invoice'].search([('pa_ref','=',payment_reference.pa_reference)])

    #     output_data = {}
        
    #     #for_reactive
        
    #     output_data['type'] = invoice_refrence.purchase_term

    #     output_data['past'] = 0
    #     output_data['current'] = 0
    #     output_data['advance'] = 0
    #     output_data['reactivate_fee'] = 0
    #     output_data['surcharge'] = 0


    #     return output_data


