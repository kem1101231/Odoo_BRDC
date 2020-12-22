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


class BRDCAccountMove(models.Model):
	_name = 'account.brdc.move'

	name = fields.Char(string="Entry")
	journal_id = fields.Many2one(string="Journal", comodel_name="account.journal")
	date = fields.Date(string="Date")
	state = fields.Selection(string="State", selection=[('draft','Draft'),('reconcile','Reconciled')], defaut="draft")
	line_ids = fields.One2many(comodel_name="account.brdc.move.line", inverse_name="brdc_move_id", string="Entry Lines")

	@api.model
	def reconcile_entries(self):
		for move in self:
			for line in move.line_ids:
				line.update({'reconciled': True})

			move.update({'state':'reconcile'})
	
	@api.model
	def unreconcile_entries(self):
		for move in self:
			for line in move.line_ids:
				line.update({'reconciled': False})
			move.update({'state':'draft'})

class BRDCAccountMoveLine(models.Model):
	_name = 'account.brdc.move.line'

	brdc_move_id = fields.Many2one(string="Entr ID", comodel_name="account.brdc.move")
	account_id = fields.Many2one(comodel_name="account.account", string="Account")
	partner_id = fields.Many2one(comodel_name="res.partner", string="Partner")
	name = fields.Char(string="Label")
	debit = fields.Float(string="Debit")
	credit = fields.Float(string="Credit")
	date_maturity = fields.Date(string="Date Due")
	reconciled = fields.Boolean(string="Reconciled")


class BRDCTransAcctConf(models.Model):
	_name = 'brdc.transaction.acct.conf'

	name = fields.Char(string="Configuration Name", required=True)
	conf_code = fields.Char(string="Code", required=True, help="This code will be used on the functions to find this config thus keep it short and unique with each other.")
	model_reference = fields.Char(string="Model Reference", required=True)
	reference_fields = fields.One2many(comodel_name="brdc.transaction.acct.conf.line", inverse_name="conf_id", string="References")
	account_journal = fields.Many2one(comodel_name="account.journal", string="Journal", required=True)

	# field_references = fields.Selection(selection='get_fields', string="Field Reference")

	# # @api.one
	# def get_fields(self):

	# 		context = self.env.context
	# 		print("************** &&&&&& ********************")
	# 		print(context)

	# 		if 'params' in context: 

	# 			print("************ ()()()()()() ***************")    
	# 			if 'id' in context['params']:
	# 				print("here ==================")
	# 				id_num = context['params']['id']
	# 				conf = self.env['brdc.transaction.acct.conf'].search([('id','=', id_num)])
	# 				model = conf[0].model_reference 
	# 				fields = self.env[model].fields_get()

	# 				return [(k, v['string']) for k, v in fields.items()]

	# 			else:
	# 				return [('test1','Test 1'),('test2','Test 2')]

	def create_entries(self, model_ref_id, name_input, time_to_use):
		for entry in self:
	        # acct_conf = self.env['brdc.transaction.acct.conf'].search([('model_reference','=','service.order')])
			
			model_ref = self.env[entry.model_reference].search([('id','=', model_ref_id)])
			new_journal_entry = self.env['account.brdc.move'].create({
	                                                                'name':"BC-" + name_input,
	                                                                'journal_id':entry.account_journal.id,
	                                                                'date': time_to_use,
	                                                                # 'company_id':self.env.user.company_id.id,
	                                                                'state':'draft',
	                                                            })
			itemList = []
			for line in entry.reference_fields:
				field_value = model_ref[line.field_reference]
				
				debit_value = 0
				credit_value = 0
				if line.account_type == 'debit':
					debit_value = field_value
					credit_value = 0
				else:
					credit_value = field_value
					debit_value = 0

				itemList.append({
	                                    'brdc_move_id':new_journal_entry.id,
	                                    'account_id':line.account.id,
	                                    'partner_id':model_ref.partner_id.id,
	                                    'name': line.label,
	                                    'debit':debit_value,
	                                    'credit':credit_value,
	                                    'date_maturity':time_to_use,
	                                    'reconciled':False,
	                                    # 'company_id':self.env.user.company_id.id,
	                            })

			new_journal_entry.update({'line_ids':itemList})
			#new_journal_entry.reconcile_entries()
			
			return new_journal_entry 


	@api.model
	def update_journal_entries(self, journal_id, model_ref_id):

		for acct_conf in self:
			journal_entry = self.env['account.move'].search([('id','=', journal_id)])
			model_ref = self.env[acct_conf.model_reference].search([('id','=',model_ref_id)])

			highest_debit_value = 0
			highest_debit_id = 0
			highest_credit_value = 0
			highest_credit_id = 0


			journal_result_to_remove = []
			for line in journal_entry.line_ids:
				journal_result_to_remove.append(line.id)
				if line.debit > highest_debit_value:
					highest_debit_value = line.debit
					highest_debit_id = line.id

				if line.credit > highest_credit_value:
					highest_credit_value = line.credit
					highest_credit_id = line.id
			
			self.journal_update('unpost', journal_entry.id)
			
			# print("****************** dfdfd *******************")
			# print(highest_debit_id)
			# print(highest_credit_id)

			highest_debit_line = self.env['account.move.line'].search([('id','=',highest_debit_id)])
			highest_credit_line = self.env['account.move.line'].search([('id','=',highest_credit_id)])
			
			# print("+++++++++++++++++++++++++++++")
			# print(highest_credit_line)
			# print(highest_debit_line)
			# print("''''''''''''''''''''''''")
			# print(highest_credit_line.invoice_id)

			itemList = []

			for line in acct_conf.reference_fields:
				line_ref = None
				field_value = model_ref[line.field_reference]
				debit_value = 0
				credit_value = 0

				if line.account_type == 'debit':
					debit_value = field_value
					credit_value = 0

					line_ref = highest_debit_line
				else:
					credit_value = field_value
					debit_value = 0

					line_ref = highest_credit_line

				itemList.append({
	                                        'move_id':journal_entry.id,
	                                        'account_id':line.account.id,
	                                        'partner_id':line_ref.partner_id,
	                                        'name': line.label,
	                                        'debit':debit_value,
	                                        'credit':credit_value,
	                                        'amount_residual':field_value,
	                                        # 'balance':field_value,
	                                        'date_maturity':line_ref.date_maturity,
	                                        'reconciled':False,
	                                        'company_id':self.env.user.company_id.id,
	                                        'invoice_id':line_ref.invoice_id.id,
	                                        'product_uom_id':line_ref.product_uom_id.id,
	                                        #'balance':line_ref.balance,
	                                        'payment_id':line_ref.payment_id.id,

									    # # 'create_date':line_ref.,
									    # 'statement_id':line_ref.statement_id,
									    # 'journal_id':line_ref.journal_id,
									    # 'currency_id':line_ref.currency_id,
									    # 'date_maturity':line_ref.date_maturity,
									    # 'user_type_id':line_ref.user_type_id,
									    # 'partner_id':line_ref.partner_id,
									    # 'blocked': line_ref.blocked,
									    # 'analytic_account_id':line_ref.analytic_account_id,
									    # 'amount_residual':line_ref.amount_residual,
									    # 'company_id':line_ref.company_id,
									    # 'credit_cash_basis':credit_value,
									    # 'amount_residual_currency':line_ref.amount_residual_currency,
									    # 'debit':debit_value,
									    # 'ref':line_ref.ref,
									    # 'account_id':line_ref.account_id,
									    # 'debit_cash_basis':debit_value,
									    # 'reconciled':line_ref.reconciled,
									    # 'tax_exigible': line_ref.tax_exigible,
									    # 'balance_cash_basis':line_ref.balance_cash_basis,
									    # # 'write_date':line_ref.write_date,
									    # 'date':line_ref.date,
									    # # 'write_uid':line_ref.,
									    # 'move_id':line_ref.move_id,
									    # 'product_id':line_ref.product_id,
									    # 'payment_id':line_ref.payment_id,
									    # 'company_currency_id':line_ref.company_currency_id,
									    # 'name':line.label,
									    # 'invoice_id':line_ref.invoice_id,
									    # 'full_reconcile_id':line_ref.full_reconcile_id,
									    # 'tax_line_id':line_ref.tax_line_id,
									    # 'credit':credit_value,
									    # 'product_uom_id':line_ref.product_uom_id,
									    # 'amount_currency':line_ref.amount_currency,
									    # 'balance':line_ref.balance,
									    # 'quantity':line_ref.quantity,
									    # 'is_debit': line_ref.is_debit,
									    # 'is_pcf': line_ref.is_pcf,
									    # 'is_credit': line_ref.is_credit,
									    # 'is_tax': line_ref.is_tax,
									    # # 'sequence':line_ref.,
									    # 'account_invoice_id':line_ref.account_invoice_id,
									    # 'is_surcharge': line_ref.is_surcharge,
	                                })

			journal_entry.update({'line_ids':itemList})

			self.clean_journal_lines(journal_result_to_remove)
			self.journal_update('post', journal_entry.id)    

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

	def clean_journal_lines(self, journal_result_to_remove):
		if journal_result_to_remove != []:
			for id in journal_result_to_remove:
				print("deleting")
				self.env.cr.execute("delete from account_move_line where id = " + str(id) + "")


class BRDCTransAcctConfLine(models.Model):
	_name = 'brdc.transaction.acct.conf.line'

	conf_id = fields.Many2one(comodel_name="brdc.transaction.acct.conf", string="Configuration")
	field_reference = fields.Char(string="Field Reference")
	field_reference_name = fields.Char(string="Field Reference")
	label = fields.Char(string="Account Label")
	# field_reference_sel = fields.Selection(string="Field Reference", related="conf_id.field_references")
	account = fields.Many2one(comodel_name="account.account", string="Account Code")
	account_type =  fields.Selection(selection=[('credit','Credit'),('debit','Debit')], string="Account Type")
	


class BRDCAddConfLine(models.TransientModel):
	_name = 'brdc.trans.acct.conf.line.add'
	
	conf_id = fields.Many2one(comodel_name="brdc.transaction.acct.conf", string="Configuration")
	#field_reference = fields.Selection(string="Field Reference", )#related="conf_id.field_references"
	account = fields.Many2one(comodel_name="account.account", string="Account Code")
	label = fields.Char(string="Account Label")
	account_type =  fields.Selection(selection=[('credit','Credit'),('debit','Debit')], string="Account Type")
	
	field_references = fields.Selection(selection='get_fields', string="Field Reference")

	# @api.one
	def get_fields(self):

			context = self.env.context
			if 'active_id' in context:     

				id_num = context['active_id']
				conf = self.env['brdc.transaction.acct.conf'].search([('id','=', id_num)])
				model = conf[0].model_reference 
				fields = self.env[model].fields_get()

				return [(k, v['string']) for k, v in fields.items()]


	def update_fields(self):

		print("*&*&*&*&*&*&*&*&*&*&*&*&*&*&*&*&")
		print(self['field_references'])
		
		for transaction in self:

			dataa = self._fields['field_references']._description_selection(self.env)
			print("+++++++++++++++++++++++++++++++++++++++++++++++++")
			print(dataa)

			data_value = ''
			for item in dataa:
				if transaction.field_references in item and transaction.field_references:
					data_value = item[1]

			self.env['brdc.transaction.acct.conf.line'].create({
																
																'conf_id':transaction.conf_id.id,
																'field_reference':transaction.field_references,
																'field_reference_name':data_value,
																'label':transaction.label,
																'account':transaction.account.id,
																'account_type':transaction.account_type,
															})
