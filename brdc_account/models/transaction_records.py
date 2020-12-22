from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, date
import calendar
from dateutil.relativedelta import relativedelta
import xlsxwriter
import base64
import odoo
import num2words
import json
import numpy as np

class BRDCTransactionRecords(models.Model):
	_name = 'brdc.transactions'

	name = fields.Char(string="Tranasaction Name")
	invoice_id = fields.Many2one(comodel_name="account.invoice", string="Invoice")
	invoice_number = fields.Char(related="invoice_id.number", string="Invoice Number")
	ref_type = fields.Selection(string="Reference Type", selection=[('service','Service Order'),('sale','Sales Order'),('pay','Payment')])
	state = fields.Selection(selection=[('draft','Draft'),('done','Accounted')], string="State", default="draft")
	ser_number = fields.Many2one(comodel_name="service.order", string="Service Ord. No.")
	pa_number = fields.Char(string="P.A. Number", related="invoice_id.pa_ref")
	customer = fields.Many2one(comodel_name="res.partner", string="Customer", related="invoice_id.partner_id")
	payment_type = fields.Selection(string="Payment Type", selection=[('cash','Cash'),('install','Installment')], related="invoice_id.purchase_term")
	
	@api.depends('invoice_id')
	def _get_payment_term(self):
		for trans in self:
			trans.payment_term = trans.invoice_id.new_payment_term_id.name

	payment_term = fields.Char(string="Payment Term", compute="_get_payment_term")
	invoice_gross = fields.Float(string="", related="")
	invoice_pcf_value = fields.Float(string="", related="")
	invoice_vat = fields.Float(string="", related="")
	invoice_total = fields.Float(string="", related="")
	invoice_line = fields.One2many(related="invoice_id.invoice_line_ids")
	journal_entry = fields.Many2one(comodel_name="account.move")
	journal_entry_line = fields.One2many(related="journal_entry.line_ids")

	# hr_field = fields.Selection(selection='empl_to_exp', string="Pilih Kolom")

	# def empl_to_exp(self):
	#     fields = self.env['hr.employee'].fields_get()
	#     return [(k, v['string']) for k, v in fields.items()]


	@api.multi
	def post_entries(self):
		for transaction in self:
			transaction.state = 'done'
			self.journal_update('post',transaction.journal_entry.id)


	def journal_update(self, update_type, id_entry):

		journal = self.env['account.move'].search([('id','=', id_entry)], limit=1)
		journal_state = ''
		journal_line_reconcile = False

		if update_type == 'post':
			journal.write({'state': 'posted'})

			for journal_item in journal.line_ids:
				item = self.env['account.move.line'].search([('id','=',journal_item.id),])
				item.write({'reconciled':True})

		else:
			self.env.cr.execute("update account_move set state = 'draft' where id = "+ str(id_entry))
			
			for journal_item in journal.line_ids:
				self.env.cr.execute("update account_move_line set reconciled = FALSE where id = "+str(journal_item.id))


class UpdateAccounts(models.TransientModel):
	_name='brdc.update.accounts'

	trans_id = fields.Many2one(comodel_name="brdc.transactions", string="Transaction Reference")
	update_type = fields.Selection(selection=[('add','Add Account'),('change', 'Change Account Code')])
	add_entries = fields.Boolean(string="Add Entries")

	@api.onchange('trans_id')
	def _onchange_trans_id(self):
		if self.trans_id:
			journal_entry = self.trans_id.journal_entry
			line_ids = []
			for entry in journal_entry.line_ids:
				line_ids.append({
								'update_ref':self.id,
								'account_line':entry.id,
								'label':entry.name,
								'account_code':entry.account_id.id,
								'credit':entry.credit,
								'debit':entry.debit,
								'd_credit':entry.credit,
								'd_debit':entry.debit,


							})
			self.entries = line_ids
			self.update({'entries':line_ids,})

	entries = fields.One2many(comodel_name="brdc.update.accounts.line", inverse_name="update_ref", string="Entries")
	
	@api.depends('entries')
	def _get_de_values(self):
		for transaction in self:
			total_d_credit = 0
			total_d_debit = 0

			for line in transaction.entries:
				total_d_credit += line.d_credit
				total_d_debit += line.d_debit

			transaction.de_credit = total_d_credit
			transaction.de_debit = total_d_debit

			transaction.update({
									'de_debit':total_d_debit,
									'de_credit':total_d_credit,
								})

	de_credit = fields.Float(compute="_get_de_values")
	de_debit = fields.Float(compute="_get_de_values")
	
	@api.depends('entries')
	def _get_total_values(self):
		for transaction in self:
			total_credit = 0
			total_debit = 0

			for line in transaction.entries:
				total_credit += line.credit
				total_debit += line.debit

			transaction.credit_total = total_credit
			transaction.debit_total = total_debit

			transaction.update({
									'debit_total':total_debit,
									'credit_total':total_credit,
								})

	debit_total = fields.Float(compute="_get_total_values")
	credit_total = fields.Float(compute="_get_total_values")

	new_entries = fields.One2many(comodel_name="brdc.update.accounts.line.new", inverse_name="update_ref", string="New Entries")

	@api.depends('entries')
	def _get_balance_check(self):
		for transaction in self:

			balance_check = ''

			if transaction.debit_total == transaction.credit_total:
				balance_check = 'balance'
			else:
				balance_check = 'unbalance'
			# if total_debit > transaction.de_debit or total_credit > transaction.de_credit:
			# 	balance_check = 'over'
			# if total_debit < transaction.de_debit or total_credit < transaction.de_credit:
			# 	balance_check = 'under'

			transaction.balance_status = balance_check
			transaction.update({
									'balance_status':balance_check,
				})
	
	@api.depends('entries')
	def _get_alter_check(self):
		for transaction in self:
			balance_check = ''
			alter_check = False
			if transaction.balance_status == 'balance':
				if transaction.debit_total 	!= transaction.de_debit:

					print(transaction.debit_total)
					print(transaction.de_debit)
					
					if transaction.debit_total < transaction.de_debit:
						print("under")
						
						balance_check = 'under'
						alter_check = True
					
					if transaction.debit_total > transaction.de_debit:
						print("over")
						
						balance_check = 'over'
						alter_check = True
				else:
					balance_check = ''
					alter_check = False

			transaction.alter_entries = balance_check
			transaction.show_alter = alter_check
			transaction.update({
									'alter_entries':balance_check,
									'show_alter':alter_check,
				})

	@api.depends('entries')
	def _get_unbalanced_info(self):
		for transaction in self:
			balance_check = ''
			cred_deficit = 0
			deb_deficit = 0
			if transaction.balance_status == 'unbalance':
				if transaction.debit_total > transaction.credit_total:
					balance_check = 'credit'
					cred_deficit = transaction.debit_total - transaction.credit_total
				
				else:
					balance_check = 'debit'
					deb_deficit =  transaction.credit_total - transaction.debit_total

			transaction.status_cause = balance_check
			transaction.debit_def = deb_deficit
			transaction.credit_def = cred_deficit

			transaction.update({
									'status_cause':balance_check,
									'debit_def':deb_deficit,
									'credit_def':cred_deficit,
				})


	balance_status = fields.Selection(selection=[('balance','Balanced Entries'),('unbalance','Unbalanced Entries'),], string="Status", compute="_get_balance_check")
	show_alter = fields.Boolean(compute="_get_alter_check")
	alter_entries = fields.Selection(selection=[('over','Excess Value Input'),('under','Under Value Input')], string="Altered Entries", compute="_get_alter_check")
	status_cause = fields.Selection(selection=[('credit','Credit Entries'),('debit','Debit Entries'),('credit_debit','Credit & Debit Entries')], string="Unbalanced at", compute="_get_unbalanced_info")
	credit_def = fields.Float(string="Credit Deficit", compute="_get_unbalanced_info")
	debit_def = fields.Float(string="Debit Deficit", compute="_get_unbalanced_info")


	@api.depends('entries')
	def _get_recomendation(self):
		for transaction in self:

			#"+ str(transaction.status_cause) +" , "+ "credit" if str(transaction.status_cause) == 'debit' else 'debit' +","+ "lower" if str(transaction.alter_entries) == "under" else "higher" +"
			out_dict = {
							'unbalance_c':"You're credit entries have lower value to your debit entries. Please try adding the indicated amount to the entries with deficit to balance the entries.",
							'unbalance_d':"You're debit entries have lower value to your credit entries. Please try adding the indicated amount to the entries with deficit to balance the entries.",
							'over': "You have balanced the entries with total values higher than the original total debit/credit values. Please update the value of your entries to match the original total values.",
							'under': "You have balanced the entries with total values lower than the original total debit/credit values. Please update the value of your entries to match the original total values.",
						}

			out_string = ""

			if transaction.balance_status == 'balance':
				if transaction.show_alter == True:
					if transaction.alter_entries == 'over':
						out_string = out_dict['over']
					else:
						out_string = out_dict['under']		

			
			else:
				if transaction.status_cause == 'debit':
					out_string = out_dict['unbalance_d']
				else:
					out_string = out_dict['unbalance_c']

			transaction.recomendation = out_string
			transaction.update({
									'recomendation':out_string,
				})	


	recomendation = fields.Text(string="Recomendation", compute="_get_recomendation")

	@api.multi
	def update_entry(self):
		for transaction in self:
			if transaction.balance_status == 'unbalance' or transaction.show_alter == True:
				raise ValidationError("Unable to update entries. \n * There were some issues we have detected on the entries. \n * Your entries may be unbalanced or you may have balanced it with amount lower or higher amount that the original amount.\n * Please cater these issues to update the entries.")

			else:
				for line in transaction.entries:

					if len(line.account_line) == 0 :
						self.env['account.move.line'].create({
																'name':line.label,
																'partner_id':transaction.trans_id.customer.id,
																'journal_id':transaction.trans_id.journal_entry.journal_id.id,
																'date':transaction.trans_id.journal_entry.date,
																'company_id':transaction.trans_id.journal_entry.company_id.id,
																'account_id':line.account_code.id,
																'debit':line.debit,
																'credit':line.credit,
																'quantity':1,
																'move_id':transaction.trans_id.journal_entry.id,
																'date_maturity':transaction.trans_id.journal_entry.date,
																# 'ref':,
							})
					
					else:
						self.env.cr.execute("update account_move_line set credit = "+str(line.credit)+", debit = "+str(line.debit)+", account_id = "+str(line.account_code.id)+", name ='"+line.label+"' where id = "+str(line.account_line.id))

class UpdateAccountsLine(models.TransientModel):
	_name='brdc.update.accounts.line.new'

	update_ref = fields.Many2one(comodel_name="brdc.update.accounts", string="Update ID")
	entry_description = fields.Char(string="Description")
	entry_code = fields.Many2one(comodel_name="account.account", string="Account Code")
	entry_debit_amount = fields.Float(string="Debit")
	entry_credit_amount = fields.Float(string="Credit")

class UpdateAccountsLine(models.TransientModel):
	_name='brdc.update.accounts.line'

	update_ref = fields.Many2one(comodel_name="brdc.update.accounts", string="Update ID")
	#currency_id = fields.Many2one('res.currency', 'Currency', required=True, default=lambda self: self.env.user.company_id.currency_id.id, store=False)
	account_line = fields.Many2one(comodel_name="account.move.line", string="Account Line")
	label = fields.Char(string="Label")
	account_code = fields.Many2one(comodel_name="account.account", string="Account Code")
	credit = fields.Float(string="Credit")
	debit = fields.Float(string="Debit" )
	d_credit = fields.Float(string="Credit")
	d_debit = fields.Float(string="Debit" )
	adjust_account = fields.Boolean(string="Remove Entry")
	adjust_amount = fields.Float(string="Adjust Amount")


	