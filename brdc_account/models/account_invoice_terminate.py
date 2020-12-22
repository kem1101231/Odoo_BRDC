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

class AccountInvoiceTerminate(models.Model):
	_inherit = 'account.invoice'

	has_terminated = fields.Boolean(default=False)
	restructured = fields.Boolean(default=False)
	curr_termination_id = fields.Many2one(comodel_name="account.invoice.terminate.info", string="Current Termination Info")
	# curr_termination_reason = fields.Text(related="curr_termination_id.reason", string="Reason to Terminate")
	curr_termination_state = fields.Selection(related="curr_termination_id.trans_state", selection=[('draft','For Termination'),('terminate','Terminated'), ('cancel', 'Canceled'),('reactive', 'Reactivation'),('bypass','Bypassed and Reactivated')], default="draft", store=False)
	# curr_termination_cancel = fields.Text(related="curr_termination_id.cancel_reason", string="Reason to Cancel")
	# curr_termination_date_terminated = fields.Date(related="curr_termination_id.date_terminated", string="Termination Date")

	# curr_termination_reactivation_paid = fields.Boolean(string="Reactivation Fee Paid", related="curr_termination_id.reactivation_paid")
	# curr_termination_surcharge_paid = fields.Boolean(string="Surcharge Paid", related="curr_termination_id.surcharge_paid")
	# curr_termination_term_of_payment = fields.Selection(string="Payment Term", related="curr_termination_id.term_of_payment", selection=[('1','Paid-up'),('2','2 mon. installment'),('3','3 mon. installment'),('4','4 mon. installment'),('5','5 mon. installment')], help="Payment Term in months")

	# curr_termination_amount_per_collection = fields.Float(string="Amount per Collection", related="curr_termination_id.amount_per_collection")

	# curr_termination_advance = fields.Float(string="Advance Payment", related="curr_termination_id.advance")
	# curr_termination_amount_due = fields.Float(string="Amount Due", related="curr_termination_id.amount_due")
	# curr_termination_num_of_paid_term = fields.Integer(string="No. of Paid Terms", related="curr_termination_id.num_of_paid_term")
	# curr_termination_remaining_balance = fields.Float(string="Remaning Balance",related="curr_termination_id.remaining_balance")

	curr_termination_id_total_pay = fields.Float(related="curr_termination_id.total_to_pay", string="Total Amount to Pay")
	curr_termination_id_balance = fields.Float(related="curr_termination_id.balance", string="Amount to Pay")
	curr_termination_id_amount_paid = fields.Float(related="curr_termination_id.total_paid_amount", string="Amount Paid")
	# curr_term_reactivation_fee = fields.Float(string="Reactivation Fee", related="curr_termination_id.reactivation_fee")

	# curr_termination_surcharge = fields.Float(string="Surcharge", related="curr_termination_id.surcharge", store=False)
	# curr_termination_monthly_due = fields.Monetary(string="Unpaid Due", related="monthly_due", store=False)
	# curr_termination_month_due = fields.Float(string="Month Due", related="month_due", store=False)

	# total_termination_due = fields.Monetary(string="Total ")
	# curr_termination_payment_line = fields.One2many(related="curr_termination_id.payment_line")
	
	termination_info_line = fields.One2many(comodel_name="account.invoice.terminate.info", inverse_name="invoice_id", string="Termination Info Lines")


	@api.multi
	def terminate_account(self):
		for s in self.filtered(lambda rec: rec.state not in ['draft', 'cancel']):
			if s.state == 'pre_terminate':
				s.state = 'terminate'
				s.has_terminated = True
				# move = self.move_id
				# move.button_cancel()

				curr_termination_data = s.curr_termination_id
				curr_termination_data.update({
                                                'trans_state':'terminate',
                                                'name': 'TRMT-'+s.number+'-'+'{0:03}'.format(len(s.termination_info_line)),
                                            })
			elif s.state == 'pre_active':
				s.state = 'open'
	@api.multi
	def cancel_reactivation(self):
		for invoice in self:
			invoice.state = 'terminate'
			invoice.update({'state':'terminate'})

			curr_termination_data = invoice.curr_termination_id
			curr_termination_data.update({
                                                'trans_state':'terminate',
                                            })

	@api.depends('curr_termination_id_balance')
	def _get_cater_status(self):
		for inv in self:
			output = False

			if inv.curr_termination_id_balance <= inv.curr_termination_id.total_paid_amount:
				output = True

			if inv.curr_termination_id_balance != 0:
				inv.terminate_balance_cater = output
				inv.update({'terminate_balance_cater':output,})

	terminate_balance_cater = fields.Boolean(string="Catered Terminate Balance", compute="_get_cater_status")
	adviced_for_termination = fields.Boolean(string="Advised for Termination")


	def print_remind_letter(self):
		return self.env['report'].get_action(self, 'brdc_account.reminder_letter_template') 
	
	def print_final_demand(self):
		return self.env['report'].get_action(self, 'brdc_account.final_demand_letter_template')
	
	def print_terminate(self):
		return self.env['report'].get_action(self, 'brdc_account.notice_of_termination_template') 
	
	def print_reactive(self):
		return self.env['report'].get_action(self, 'brdc_account.notice_of_reactivation_template') 


class TerminateInvoiceInfo(models.Model):
    _name="account.invoice.terminate.info"
    _order = 'id desc'

    name = fields.Char(string="Termination Number", default="DRAFT-TERMINATION")
    invoice_id = fields.Many2one(comodel_name="account.invoice", string="Invoice Reference")
    reason = fields.Text(string="Reason")
    cancel_reason = fields.Text(string="Reson to Cancel")
    date_terminated = fields.Date(string="Date Terminated")
    # terminated_by = fields.Many2one()
    trans_state = fields.Selection(selection=[('draft','For Termination'),('terminate','Validated and Terminated'), ('cancel', 'Canceled Termination'),('reactive', 'For Reactivation'), ('bypass','Bypassed and Reactivated')], default="draft")
    requested_to_bypass = fields.Boolean(string="Requested for Bypass")
    current_bypass = fields.Many2one(comodel_name="account.invoice.terminate.bypass", string="Current Bypass Request")

    reactivation_paid = fields.Boolean(string="Reactivation Fee Paid", default=False)
    reactivation_fee = fields.Float(string="Reactivation Fee", default=200)
    surcharge_paid = fields.Boolean(string="Surcharge Paid", default=False)
    surcharge = fields.Float(string="Surcharge")
    
    balance = fields.Float(string="Balance to Pay")
    total_to_pay = fields.Float(string="Total Amount to Pay")
    term_of_payment = fields.Selection(string="Payment Term", selection=[('1','Paid-up'),('2','2 mon. installment'),('3','3 mon. installment'),('4','4 mon. installment'),('5','5 mon. installment')], help="Payment Term in months")
    amount_per_collection = fields.Float(string="Amount per Collection")

    advance = fields.Float(string="Advance Payment", compute="_get_amount")
    amount_due = fields.Float(string="Amount Due", compute="_get_amount")
    num_of_paid_term = fields.Integer(string="No. of Paid Terms", compute="_get_amount")
    total_paid_amount = fields.Float(string="Total Paid Amount", compute="_get_amount")
    remaining_balance = fields.Float(string="Remaning Balance", compute="_get_amount")
    payment_line = fields.One2many(comodel_name='account.invoice.terminate.payment', inverse_name="terminate_id", string="Payment History")
    payment_sched = fields.One2many(comodel_name="account.invoice.terminate.payment.sched", inverse_name="terminate_id", string="Payment Schedule")
    bypass_history = fields.One2many(comodel_name="account.invoice.terminate.bypass.history", inverse_name="termination_id", string="Bypass History")

    @api.depends('payment_line')
    def _get_amount(self):
        for trans in self:
            total_paid = 0

            for line in trans.payment_line:
                total_paid += line.payment

            num_of_paid_term = total_paid / trans.amount_per_collection if total_paid > 0 else 0
            advance = total_paid % trans.amount_per_collection if total_paid > 0 else 0
            amount_due = trans.amount_per_collection - advance

            trans.num_of_paid_term = num_of_paid_term
            trans.advance = advance
            trans.amount_due = amount_due
            trans.total_paid_amount = total_paid
            trans.remaining_balance = trans.balance - total_paid
    


class TerminationPaymentLine(models.Model):
    _name='account.invoice.terminate.payment'

    terminate_id = fields.Many2one(comodel_name="account.invoice.terminate.info", string="Terminate ID")
    payment = fields.Float(string="Amount Paid")
    payment_id = fields.Many2one(comodel_name="account.payment", string="Payment")
    or_number = fields.Integer(related="payment_id.or_reference", string="O.R. Number") 
    payment_date = fields.Date(related="payment_id.payment_date", string="Payment Date")

class TerminationPaymentLine(models.Model):
    _name='account.invoice.terminate.payment.sched'

    terminate_id = fields.Many2one(comodel_name="account.invoice.terminate.info", string="Terminate ID")
    schedule_date = fields.Date(string="Schedule Date")
    amount_due = fields.Float(string="Amount to Pay")
    surcharge = fields.Float(string="Surcharge")
    reactivate_fee = fields.Float(string="Reactivation Fee")
    amount_total = fields.Float(string="Amount Total")
    #payment = fields.Float(string="Amount Paid")
    payment_id = fields.Many2one(comodel_name="account.invoice.terminate.payment", string="Payment")
    or_number = fields.Integer(related="payment_id.or_number", string="O.R. Number") 
    payment_date = fields.Date(related="payment_id.payment_date", string="Payment Date")
    payment = fields.Float(string="Amount Paid", related="payment_id.payment")

class TerminateInvoice(models.TransientModel):
    _name = 'accoount.invoice.terminate.reason'

    invoice_id = fields.Many2one(comodel_name="account.invoice", string="Invoice")
    reason = fields.Text(string="Reason of Termination", help="The reason of terminating the plan.")


    def terminate_invoice(self):
        for invoice in self:

            termination = self.env['account.invoice.terminate.info']
            termination_id  = termination.create({
                                                    'invoice_id':invoice.invoice_id.id,
                                                    'reason':invoice.reason,
                                                    'date_terminated': date.today(),
                })
            invoice_ref = invoice.invoice_id
            invoice_ref.update({'state':'pre_terminate', 'curr_termination_id':termination_id.id, 'has_terminated':True})

            
            item = self.env['report'].get_action(self, 'brdc_account.reminder_letter_template') 
            print(item)

            return True


class CancelTerminateInvoice(models.TransientModel):
    _name = 'accoount.invoice.terminate.cancel.reason'

    invoice_id = fields.Many2one(comodel_name="account.invoice", string="Invoice")
    reason = fields.Text(string="Reason to Cancel", help="The reason of terminating the plan.")


    def cancel_terminate_invoice(self):
        for invoice in self:

            termination = self.env['account.invoice.terminate.info']
            termination_id  = termination.search([('id','=', invoice.invoice_id.curr_termination_id.id)])
            
            termination_id.update({'trans_state':'cancel', 'cancel_reason':invoice.reason})
            invoice_ref = invoice.invoice_id
            invoice_ref.update({'state':'open'})

class ReactiveTerminateInvoice(models.TransientModel):
    _name = 'accoount.invoice.terminate.reactivate'

    invoice_id = fields.Many2one(comodel_name="account.invoice", string="Invoice")
    currency_id = fields.Many2one('res.currency', 'Currency', required=True, default=lambda self: self.env.user.company_id.currency_id.id)
    current_termination = fields.Many2one(comodel_name="account.invoice.terminate.info", related="invoice_id.curr_termination_id")
    balance = fields.Monetary(string="Balance to Pay", related="invoice_id.monthly_due")
    surcharge_amount = fields.Monetary(string="Surcharge Amount", related="invoice_id.surcharge")
    reactivation_fee = fields.Monetary(string="Reactivation Fee", default=200)
    amount_validity = fields.Date(string="Valid Until", related="invoice_id.current_due_date")

    @api.depends('balance','surcharge_amount','reactivation_fee')
    def get_total(self):
        for trans in self:
            trans.total_amount = trans.balance + trans.surcharge_amount + trans.reactivation_fee

    total_amount = fields.Monetary(string="Total amount to Pay", compute="get_total") 
    term_of_payment = fields.Selection(string="Payment Term", selection=[('1','Paid-up'),('2','2 mon. installment'),('3','3 mon. installment'),('4','4 mon. installment'),('5','5 mon. installment')], help="Payment Term in months")

    @api.depends('balance','term_of_payment')
    def get_amount_per_collection(self):
        for trans in self:
            trans.amount_per_collection = trans.balance / int(trans.term_of_payment) if trans.term_of_payment != False else 0  

    amount_per_collection = fields.Monetary(string="Amount per Collection", compute="get_amount_per_collection")

    def request_for_reactivation(self):
        for invoice in self:

            termination = invoice.current_termination
            invoice_ref = invoice.invoice_id

            termination.update({
                                    'trans_state':'reactive',
                                    'term_of_payment':invoice.term_of_payment,
                                    'amount_per_collection':invoice.amount_per_collection,
                                    'balance':invoice.balance,
                                    'total_to_pay':invoice.total_amount,
                                    'surcharge':invoice.surcharge_amount,
                        })
            
            for line in range(0, int(invoice.term_of_payment)):
                print("&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&")
                print(line)
            	self.env['account.invoice.terminate.payment.sched'].create({	
            																	'terminate_id':termination.id,
            																	'schedule_date': datetime.strptime(invoice.invoice_id.month_to_pay, "%Y-%m-%d") + relativedelta(months=int(line)),
            																	'amount_due':invoice.amount_per_collection,
            																	'surcharge':invoice.surcharge_amount if line == 0 else 0,
            																	'reactivate_fee':invoice.reactivation_fee  if line == 0 else 0,
            																	'amount_total':invoice.amount_per_collection if line != 0 else invoice.amount_per_collection + invoice.surcharge_amount + invoice.reactivation_fee,		
            													})
            invoice_ref.update({'state':'pre_active'})


class AccountInvoiceterminateBypass(models.Model):
    _name = "account.invoice.terminate.bypass"

    name = fields.Char(string="Bypass ID", default="DRAFT-TRANSACTION")
    termination_id = fields.Many2one(comodel_name="account.invoice.terminate.info", string="Termination ID") 
    invoice_id = fields.Many2one(comodel_name="account.invoice", string="Invoice", related="termination_id.invoice_id")
    bypass_state = fields.Selection(selection=[('draft','Draft'),('done','Validatetd'),('cancel','Canceled')], string="State", default="draft")
    transaction_type = fields.Selection(selection=[('spot','Spot-on Reactivation'),('payment','Reactivation with Payment'),('extend','Term Extension')], string="Transaction Type", default="spot")
    requesting_personel = fields.Many2one(comodel_name='res.users', string="Requesting Personnel")
    include_payment = fields.Boolean(string="includde Payment")
    payment_to_include = fields.Float(string="Amount to Pay")
    include_surcharge = fields.Boolean(string="Include Surcharge")
    include_reactivation_fee = fields.Boolean(string="includde Reactivation Fee")
    total_amount_to_pay = fields.Float(string="Total Amount to Pay")
    installment_term = fields.Selection(string="Payment Term", selection=[('1','Paid-up'),('2','2 mon. installment'),('3','3 mon. installment'),('4','4 mon. installment'),('5','5 mon. installment')], help="Payment Term in months")
    compute_amount_divided = fields.Selection(selection=[('multiply','Multiply the Amount to Pay By Terms'),('divide','Divide Amount to Pay by Terms')], string="Compute Term by")
    month_extention = fields.Integer(string="Months to Extend")
    payment_sched = fields.One2many(comodel_name="account.invoice.terminate.payment.sched", related="termination_id.payment_sched")

	# def vali

class AccountTerminationBypassHistory(models.Model):
	_name="account.invoice.terminate.bypass.history"

	bypass_id = fields.Many2one(comodel_name="account.invoice.terminate.bypass")
	termination_id = fields.Many2one(comodel_name="account.invoice.terminate.info", string="Termination ID") 
	requesting_personel = fields.Many2one(comodel_name="res.users", related="bypass_id.requesting_personel", string="Requesting Personnel")
	bypass_type = fields.Selection(selection=[('spot','Spot-on Reactivation'),('payment','Reactivation with Payment'),('extend','Term Extension')], string="Transaction Type", related="bypass_id.transaction_type")
	bypass_status = fields.Selection(selection=[('draft','Draft'),('done','Validatetd'),('cancel','Canceled')], string="Status", related="bypass_id.bypass_state")

class AccountTerminateBypassPayment(models.Model):
    _name = 'account.invoice.terminate.bypass.payment'

    bypass_id = fields.Many2one(comodel_name="account.invoice.terminate.bypass")
    schedule_date = fields.Date(string="Schedule Date")
    amount_to_pay = fields.Float(string="Amount to Pay")
    reactivation_fee = fields.Float(string="Reactivation Fee")


