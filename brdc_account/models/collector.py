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
import xlrd
import os
import unicodedata
from xlrd import open_workbook
# import base64
import StringIO

class CollectionsCollector(models.Model):
	_name = "brdc.collection.collector"

	@api.depends('collector_id')
	def _get_collector_name(self):
		for collector in self:
			collector.name = collector.sudo().collector_id.name

	name = fields.Char(string="Collector's Name", compute="_get_collector_name")
	collector_id = fields.Many2one(string="Collector Name", comodel_name="res.users")
	area_id = fields.Many2many(string="Area", comodel_name="brdc.collection.area")
	status = fields.Selection(selection=[('current','Currently Assigned Collector'),('former','Former Collector')], string="Display by")
	history_line = fields.One2many(comodel_name="brdc.invoice.collector.history", inverse_name="collector_id", string="Assigned P.A.")
	transfer_request = fields.One2many(comodel_name="brdc.invoice.transfer.collector", inverse_name="from_collector", string="Account Transfer Requests")
	#transfer_ids = fields.One2many()

class CollectionsArea(models.Model):
	_name = 'brdc.collection.area'

	name = fields.Char(string="Area Name", required=True)
	
	province_id = fields.Many2one(string="Province", comodel_name="config.province")
	municipality_id = fields.Many2one(string="Municipality", comodel_name="config.municipality")
	barangay_ids = fields.Many2many(string="Barangay", comodel_name="config.barangay")

	specify_brgy = fields.Boolean(string="Specify Barangay")

	# primary_collector = fields.Many2one(comodel_name="res.users", string="Main Collector")
	collector_id_list = fields.Many2many(comodel_name="res.users", string="Collectors")
	collector_ids = fields.Many2many(comodel_name="brdc.collection.collector", string="Collector")

	# @api.onchange('secondary_collector')
	# def change_secon_collector(self):
	# 	if self.secondary_collector:
	# 		latest_added = self.secondary_collector[len(self.secondary_collector) - 1]
	# 		if self.primary_collector.id == latest_added.id:
	# 			# print("Exist")
	# 			raise UserError('Collector was already set as Primary Collector')
	# 		# else:
	# 		# 	print("May be added")


	@api.model
	def create(self, values):
		
		result = super(CollectionsArea, self).create(values)
		
		for collector in result.collector_id_list:

			collector_info = self.env['brdc.collection.collector'].search([('collector_id','=', collector.id)], limit=1)

			if len(collector_info) == 0:
				self.env['brdc.collection.collector'].create({
																'name':collector.name,
																'collector_id':collector.id,
																'area_id':[(6, 0, [result.id])],
															})

			else:
				all_collector_area = []

				for line in collector_info.area_id:
					all_collector_area.append(line.id)

				if result.id not in all_collector_area:
					collector_info.update({
											'area_id':[(4, result.id)]
									})

		return result

	def write(self, vals):
		result = super(CollectionsArea, self).write(vals)
		

		collector_ids_array = []
		for collector in self.collector_ids:
			collector_ids_array.append(collector.id)


		collector_id_list_array = []
		
		for collector in self.collector_id_list:
			collector_info = self.env['brdc.collection.collector'].search([('collector_id','=', collector.id)], limit=1)
			
			collector_id_list_array.append(collector.id)
			
			collector_to_add = False
			
			if len(collector_info) == 0:
				collector_to_add = self.env['brdc.collection.collector'].create({
																'name':collector.name,
																'collector_id':collector.id,
																'area_id':[(6, 0, [self.id])],
					})

			else:
				all_collector_area = []

				for line in collector_info.area_id:
					all_collector_area.append(line.id)

				if self.id not in all_collector_area:
					collector_info.update({
											'area_id':[(4, self.id)]
									})

				collector_to_add = collector_info
			
			if collector_to_add.id not in collector_ids_array:
					
				self.update({
					'collector_ids':[(4, collector_to_add.id)],
				})

		for collector in self.collector_ids:
			if collector.collector_id.id not in collector_id_list_array:
				self.update({
								'collector_ids':[(3, collector.id)]

					})


		return result


# class CollectionsAreaCollectors(models.Model):
# 	_name='brdc.collection.area.collector'

# 	

class TaggedCollectorHistory(models.Model):
	_name = 'brdc.invoice.collector.history'

	invoice_id = fields.Many2one(string="Invoice", comodel_name="account.invoice")
	collector_id = fields.Many2one(string="Collector", comodel_name="brdc.collection.collector")
	status = fields.Selection(selection=[('current','Currently Assigned Collector'),('former','Former Collector')], string="Status")
	date_assigned = fields.Date(string="Assignment Date")
	date_removal = fields.Date(string="Date Unassigned")


class TransferAssignedCollectorRequest(models.Model):
	_name="brdc.invoice.transfer.collector"

	name = fields.Char(string="Tranfer ID")
	state = fields.Selection(selection=[('draft','Draft'),('done','Validated'),('cancel','Canceled')], state="Status", default="draft")
	transfer_type = fields.Selection(selection=[('bypa','Transfer by P.A.'),('area','Tranfer by Area')], string="Type", default='bypa')

	from_collector = fields.Many2one(comodel_name="brdc.collection.collector", string="From Collector")
	collector_id_ref = fields.Many2one(comodel_name="res.users", string="Collector", related="from_collector.collector_id")
	to_collector = fields.Many2one(comodel_name="brdc.collection.collector", string="To Collector")

	@api.onchange('from_collector')
	def _coll_area_change(self):
		if self.from_collector:
			reference = []
			for line in self.from_collector.area_id:
				reference.append(line.sudo().id)
			
			return {'domain':{'area_to_tranfer':[('id','in', reference)]}}
		else:
			return {'domain':{'area_to_tranfer':[('id','in', [])]}}


	area_to_tranfer = fields.Many2many(comodel_name="brdc.collection.area",string="Area to Transfer")
	pa_to_transfer = fields.Many2many(comodel_name="account.invoice",string="P.A. to Transfer")

	def validate_request(self):
		for trans in self:

			invoice_list=[]

			if trans.transfer_type == 'area':
				
				so_list = self.env['sale.order'].search([('collector_area','=',trans.area_to_tranfer.id),('collector','=', trans.collector_id_ref.id)])
				if len(so_list) != 0:
					for line in so_list:
						for line_invoice in line.invoice_ids:
							invoice_list.append(line_invoice.id)

			else:
				for line in trans.pa_to_transfer:
					invoice_list.append(line.id)

			for item in invoice_list:
				invoice = self.env['account.invoice'].search([('id','=',item), ('state','=','open')])
				
				if invoice:
					invoice_collector = self.env['brdc.collection.collector'].search([('collector_id','=',invoice.pa_ref_collector.id)])
					so_ref = self.env['sale.order'].search([('collector','=',invoice_collector.id), ('pa_ref','=', int(invoice.pa_ref))])
					
					if invoice_collector:
						current_collector = self.env['brdc.invoice.collector.history'].search([('invoice_id','=', item), ('collector_id','=', invoice_collector.id)])
						current_collector.update({
													'status':'former',
													'date_removal':date.today(),
												})
						self.env['brdc.invoice.collector.history'].create({
																		
																		'invoice_id':item,
																		'collector_id':trans.to_collector.id,
																		'status':'current',
																		'date_assigned':date.today(),		
															})

						invoice.update({
										'pa_ref_collector':trans.to_collector.collector_id.id,
									})
						
						so_ref.update({
										'collector':trans.to_collector.collector_id.id
									})

			trans.update({'state':'done'})



class UpdateCollectors(models.TransientModel):
	_name = 'brdc.update.collectors'
	
	file1 = fields.Binary("Source File")
	file1_name = fields.Char('Source File')
	
	# file2 = fields.Binary("Upload file2")
	# file2_name = fields.Char('File Name2')
	

	def get_book_form_file(self):

		try:
			inputx = StringIO.StringIO()
			inputx.write(base64.decodestring(self.file1))
			book = open_workbook(file_contents=inputx.getvalue())

			return book
		except TypeError as e:
			raise ValidationError(u'ERROR: {}'.format(e))



	def update_collectors(self):

		# file = ("2016_to_2020_fnal.xlsx")
		# print(os.getcwd())
		# print("************************************************************************************************")
		# print("Executing Collector Update")

		wb = self.get_book_form_file()
		sheet = wb.sheet_by_index(0)

		updated_data = []


		print("Reading file")

		for row in range(sheet.nrows):
			print("++++++++++++++++++++++++++++++++++++++++++++++++++++++")
			print("Reading Row")
			print(sheet.cell_value(row, 5))
			print(type(sheet.cell_value(row, 5)))


			if row != 0 and type(sheet.cell_value(row, 5)) != int:
				pa_number = sheet.cell_value(row, 0)
				collector_name = unicodedata.normalize('NFKD', sheet.cell_value(row, 5)).encode('ascii', 'ignore')
				
				# print("#$#$#$#$#$#$#$#$#$#$#$#$#$#$")
				# print(collector_name)
				# print("tpye"+str(type(collector_name)))
				# print(pa_number)
				
				print("Reading information")
				print("PA: "+str(pa_number))
				print("Collector: "+str(collector_name))

				last_name = ''
				first_name = ''

				name_array = collector_name.split(', ')
				
				last_name = name_array[0]
				
				first_name = name_array[len(name_array)-1]
				first_name_array = first_name.split(' ')
				first_name = first_name_array[0]


				print("Generated name_array")
				print(name_array)
				print(last_name)
				print(any(char.isdigit() for char in last_name))
				print(first_name)
				print(any(char.isdigit() for char in first_name))
				print("can it pass through if: "+ ('Yes' if not any(char.isdigit() for char in last_name) and not any(char.isdigit() for char in first_name) else 'No'))

				if not any(char.isdigit() for char in last_name) and not any(char.isdigit() for char in first_name):

					last_name_ref = 'GALEN' if last_name.upper() == 'BRDC' else last_name.upper()
					first_name_ref = 'JAMANTOC' if first_name.upper() == 'OFFICE' else first_name.upper()

					print("Name for search")
					print("Last Name: "+last_name_ref)
					print("First name: "+first_name_ref)

					partner_search = self.env['res.partner'].search([('name','like', last_name_ref),('name','like', first_name_ref)])

					print("Searching partner id")
					print("Partner information found")
					print(partner_search)

					
					# print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
					# print("partner found "+str(len(partner_search)))
					
					user_found = []
					print("Finding users with the partner info")

					for partner in partner_search:
						print('+++++++++++++++++++++++++++++++')
						print("Finding user")
						user = self.env['res.users'].search([('partner_id','=', partner.id)])
						print("User Found")
						print(user)
						
						if len(user) > 0:
							user_found.append(user)
							# print("users found " + str(len(user)))
					

					print("Showing all users found")
					print(user_found)
					# print("naa bai" if len(user_found) > 0 else "wala bai")
					# print("tama ra bai" if len(user_found) <= 1 else "sobra bai")
					# print(str(int(pa_number))+" - " +str(collector_name)) 
					print("Proceed to Updating Collector")
					print("Can continue: " + 'Yes' if len(user_found) == 1 else 'No')

					if len(user_found) == 1:

						# print("\n\n + ================================= \nLocating PA")
						print("Finding PA and its Invoice")

						pa = self.env['sale.order'].search([('pa_ref','=', str(int(pa_number)))], limit=1)
						pa_invoice = self.env['account.invoice'].search([('pa_ref','=', str(int(pa_number)))], limit=1)

						# print("pa found")
						# print(pa)
						print("SO: " + str(pa.pa_ref))
						print("Invoice " + str(pa_invoice.pa_ref))

						# print("user to be added")
						# print(user_found[0])
						# print(user)

						collector_area = 0

						area_selected = self.env['brdc.collection.area'].search([('barangay_ids','in', pa.partner_id.barangay_id.id), ('specify_brgy','=', True)])
						
						if len(area_selected) > 0:
							collector_area = area_selected.id
						else:
							area_selected = self.env['brdc.collection.area'].search([('municipality_id','=',pa.partner_id.municipality_id.id), ('specify_brgy','=', False)])
							collector_area = area_selected.id

						collector_list = self.env['brdc.collection.collector'].search([('collector_id','=',user_found[0].id)], limit=1)

						pa.update({
										'collector_area':collector_area,
										'collector_list':collector_list.id,

								})

						pa_invoice.update({'pa_ref_collector':user_found[0].id})

						updated_data.append({
												'pa':pa.pa_ref,
												'collector':user_found[0].name,
							})

		print("============================\nPrinting Updated PA")
		for bb in updated_data:
			print("^^^^^^^^^^^")
			print(bb)
			print("----")

	def update_collector_history(self):

		invoices = self.env['account.invoice'].search([('id','!=',0)])

		for line in invoices:
			assinged_collector = line.pa_ref_collector
			
			if assinged_collector:

				collector = self.env['brdc.collection.collector'].search([('collector_id','=', assinged_collector.id)], limit=1)
				if collector and len(collector.history_line) < 1:
					print("updating history")
					self.env['brdc.invoice.collector.history'].create({
																		'invoice_id':line.id,
																		'collector_id':collector.id,
																		'status':'current',
																		'date_assigned':line.date_invoice,
																})

	def update_collection(self):
		# file = ("register_payment.xlsx")
		# print(os.getcwd())
		# print("************************************************************************************************")
		# print("Executing Collector Update")

		wb = self.get_book_form_file()
		sheet = wb.sheet_by_index(0)

		updated_data = []

		print("Reading file")

		found_id = {}
		found_name = {}

		for row in range(sheet.nrows):
			# print("++++++++++++++++++++++++++++++++++++++++++++++++++++++")
			# print("Reading Row")
			# print(sheet.cell_value(row, 2))
			# print(type(sheet.cell_value(row, 5)))


			if row != 0 and type(sheet.cell_value(row, 2)) != int:
				
				date_of_payment_tuple = xlrd.xldate_as_tuple(sheet.cell_value(row, 0),wb.datemode)
				date_of_payment = datetime(date_of_payment_tuple[0], date_of_payment_tuple[1], date_of_payment_tuple[2])
				pa_number = sheet.cell_value(row, 1)
				or_number = sheet.cell_value(row, 4)
				collector_name = unicodedata.normalize('NFKD', sheet.cell_value(row, 2)).encode('ascii', 'ignore')
				
				# print("#$#$#$#$#$#$#$#$#$#$#$#$#$#$")
				# print(collector_name)
				# print("tpye"+str(type(collector_name)))
				# print(pa_number)
				
				print("\n\n*******************************\nReading information")
				print("Date: "+ str(date_of_payment))
				print("PA: "+str(int(pa_number)))
				print("OR: "+str(int(or_number)))
				print("Collector: "+str(collector_name))

				last_name = ''
				first_name = ''

				name_array = collector_name.split(', ')
				
				last_name = name_array[0]
				
				first_name = name_array[len(name_array)-1]
				first_name_array = first_name.split(' ')
				first_name = first_name_array[0]


				# print("Generated name_array")
				# print(name_array)
				# print(last_name)
				# print(any(char.isdigit() for char in last_name))
				# print(first_name)
				# print(any(char.isdigit() for char in first_name))
				# print("can it pass through if: "+ ('Yes' if not any(char.isdigit() for char in last_name) and not any(char.isdigit() for char in first_name) else 'No'))

				if not any(char.isdigit() for char in last_name) and not any(char.isdigit() for char in first_name):

					last_name_ref = 'GALEN' if last_name.upper() == 'BRDC' else last_name.upper()
					first_name_ref = 'JAMANTOC' if first_name.upper() == 'OFFICE' else first_name.upper()

					print("Name for search")
					print("Last Name: "+last_name_ref)
					print("First name: "+first_name_ref)

					partner_search = self.env['res.partner'].search([('name','like', last_name_ref),('name','like', first_name_ref)])

					print("Searching partner id")
					print("Partner information found")
					print(partner_search)

					
					# print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
					# print("partner found "+str(len(partner_search)))
					
					user_found = []
					print("Finding users with the partner info")

					for partner in partner_search:
						print('+++++++++++++++++++++++++++++++')
						print("Finding user")
						user = self.env['res.users'].search([('partner_id','=', partner.id)])
						print("User Found")

						if len(user) > 0:
							user_found.append(user)
							# print("users found " + str(len(user)))
					
					print(user_found)
					# print("Showing all users found")
					# print(user_found)
					# # print("naa bai" if len(user_found) > 0 else "wala bai")
					# # print("tama ra bai" if len(user_found) <= 1 else "sobra bai")
					# # print(str(int(pa_number))+" - " +str(collector_name)) 
					# print("Proceed to Updating Collector")
					# print("Can continue: " + 'Yes' if len(user_found) == 1 else 'No')

					if len(user_found) == 1:
						print("++++++++++++++")
						print(user_found[0].name)
						collector_id = self.env['brdc.collection.collector'].search([('collector_id','=',user_found[0].id)])
						
						id_collector_date = str(user_found[0].id)+"/"+str(date_of_payment)
						invoice_ref = self.env['account.invoice'].search([('pa_ref','=', str(int(pa_number)))])
						# print("()()()()()()()()()()()()()()()()()()")
						# print(invoice_ref)
						# print(invoice_ref[0].number)
						payment_reference = self.env['account.payment'].search([('or_reference','=', str(int(or_number))), ('communication','=', invoice_ref[0].number),('state','=','posted')], limit=1)
						payment_reference.update({'user_id':user_found[0].id})

						for x in payment_reference:
							print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
							print(x.or_reference)
							print(x.id)

						if id_collector_date not in found_id:
							
							collection_search = self.env['daily.collection.record'].search([('date','=', date_of_payment), ('collector_id','=', user_found[0].id)])

								
							print("&*&*&*&*&*&*&*&*&*&*&*&*&*")
							print(user_found[0].id)
							print(user_found[0].name)
								
							id_to_use = self.env['daily.collection.record'].create({
		                                                                        'collector_id':user_found[0].id,
		                                                                        'date':date_of_payment,
		                                                                        'collection_type':'cashier' if last_name.upper() == 'BRDC' else 'collect',
		                                                                })
							print("%^%^%^%^%^%^%^%^%^%^%^%^%")
							print(id_to_use.collector_id.name)
							found_id[id_collector_date] = id_to_use
							found_name[user_found[0].name] = id_collector_date

						
						collection_ref = found_id[id_collector_date]
						print("&*&*&*&*&*&*&*&*&*&*&*&*&*")
						print(collection_ref.collector_id.name)

						if payment_reference.state != 'draft':

							dcr_line = self.env['dcr.lines'].create({
			                                    'partner_ids':payment_reference.partner_id.id,
			                                    'DailyCollectionRecord_id':collection_ref.id,
			                                    'dcr_collector':payment_reference.user_id.id,
			                                    #'cash_cheque_selection': payment_reference.cash_cheque_selection,
			                                    'or_reference':str(payment_reference.or_reference),
			                                    'amount_paid':payment_reference.amount,
			                                    'setdate':payment_reference.payment_date,
			                                    'state':'posted',
			                                    'PA':payment_reference.pa_reference,
			                                    'invoice_id':invoice_ref.id,
			                                    'journal_id':payment_reference.journal_id.id,
			                                    'description':str(payment_reference.pa_reference)+"-"+str(payment_reference.or_reference),
			                                    'payment_id':payment_reference.id,
			                    })

						payment_reference.update({
		                                    'collected_id':dcr_line.id,
		                                    'collection_id':collection_ref.id,
		                            })
		for item in found_id:
			collection = found_id[item]
			total_collection = collection.total_collection
			
			collection.get_denomination()
			print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
			print("Total collection -------")
			print(total_collection)

			print("+++++++++++ Start denomination +++++++")
			for line_item in  collection.cash_count_line_ids:
				print("***********************")
				print(line_item.description)
				value_to_enter = total_collection/line_item.description
				print(int(value_to_enter))

				if int(value_to_enter) > 0:

					line_item.update({'bill_number':int(value_to_enter), 'total_amount':(int(value_to_enter)*line_item.description)})

					total_collection = total_collection - (int(value_to_enter)*line_item.description)

			collection.action_submit()
			collection.update({'state':'confirm',})
			# collection.action_confirm()


		# print("&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&7")
		# for x in found_name:
		# 	print("******************")
		# 	print(x)
		# 	print(found_name[x])
		# 	print("()()()()()()()()9")


	def update_payments_post(self):
		all_payments = self.env['account.payment'].search([('state','=','posted')])
		print("++++++++++++++++++++++++++++++++")

		for line in all_payments:
			print("**********************************s")
			print(line.name)
			self.post_it(line)

	@api.multi
	def post_it(self, rec):
        
        #bug here! need to finddddddd T_T
        
        # for rec in self:

            # if rec.state == 'draft' :

            	# rec.update({'state':'draft'})
                # rec.refresh()

                ai = None
                if rec.communication:
                    ai = rec.env['account.invoice'].search([('number','=',rec.communication)]) or \
                         rec.env['account.invoice'].browse(rec._context.get('active_ids', [])) #or \
                         # rec.env['service.order'].browse(rec._context.get('active_ids', []))

                if ai != None:
	                paid_amount = rec.amount
	                advance_payment_count = 0
	                
	                pay_sched_line_id = None
	                sched_instance = self.env['invoice.installment.line']
	                
	                print("++++++++++++++++++^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
	                print(ai.name)
	                print("Blank: " + 'yes' if ai.name == '' else 'no')
	                print(ai.purchase_term)


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
	                    

	                rec.with_surcharge()
	                # rec.on_post()
	              

	                amount_in = rec.amount if not rec.surcharge_included else rec.amount - rec.surcharge


	                if rec.invoice_is_terminated and rec.reactivation_fee_paid == False:
	                        amount_in -= rec.reactivation_fee

	                amount_catered = 0
	                current_index = 0

	                down_payment_catered = 0
	                monthly_payment_catered = 0

	                if len(pay_sched_line_id) != 0:
	 
		                while round(amount_catered, 2) < round(amount_in, 2):
		                	
		                	print("&&&&&&&&&&&&&==================================================")

			                print(len(pay_sched_line_id))
			                print(current_index)

			                current_line = pay_sched_line_id[current_index]
			                amount_to_pay = current_line.amount_to_pay - current_line.balance
			                amount_to_dispose = amount_in - amount_catered
			                amount_to_register = 0

			                if amount_to_pay < amount_to_dispose:
			                	amount_to_register = amount_to_pay
			                else:
			                	amount_to_register = amount_to_dispose
			                if current_line.type == 'down':
			                	down_payment_catered = amount_to_register
			                if current_line.type == 'install':
			                	monthly_payment_catered = amount_to_register

			                sched_instance = self.env['invoice.installment.line']
			                sched_instance.register_payment(amount_to_register, rec.id, rec.payment_date, current_line.id)
			                current_index += 1
			                amount_catered += amount_to_pay
		               
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

	                # if rec.account_invoice_id.state == 'paid' and \
	                #         (rec.account_invoice_id.product_type.name == 'Lot' or
	                #          rec.account_invoice_id.product_type.name == 'MM Bundle' or
	                #          rec.account_invoice_id.product_type.name == 'Columbary Vault' or
	                #          rec.account_invoice_id.product_type.name == 'Community Vault'):
	                #     # #print "amo ni sa ang rec.account_invoce_id",rec.account_invoice_id
	                #     rec.account_invoice_id.invoice_line_ids[0].lot_id.status = 'fp'
	                # elif rec.account_invoice_id.state == 'open':
	                #     rec.account_invoice_id.invoice_line_ids[0].lot_id.status = 'amo'
	                # else:
	                #     pass

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
	                if not rec.brdc_account_move:
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
	                                            'account_id':rec.get_account_from_coa(entry_numbers['cash_debit']).id,
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
	                                                'account_id':rec.get_account_from_coa(entry_numbers['cash_credit']).id,
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
	                                            'account_id':rec.get_account_from_coa(entry_numbers['pcf']).id,
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
	                                                    'account_id':rec.get_account_from_coa(entry_numbers['down_debit']).id,
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
	                                                        'account_id':rec.get_account_from_coa(entry_numbers['down_discount']).id,
	                                                        'partner_id':ai.partner_id.id,
	                                                        'name': 'Sales Discount - Lot',
	                                                        'debit': ai.o_dp - down_payment_catered,
	                                                        'credit':0,
	                                                        'date_maturity':ai.date_invoice,
	                                                        'reconciled':False,
	                                                })
	                                
	                                itemList.append({
	                                                    'brdc_move_id':brdc_move_down.id,
	                                                    'account_id':rec.get_account_from_coa(entry_numbers['down_credit']).id,
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
	                                                    'account_id':rec.get_account_from_coa(entry_numbers['down_debit']).id,
	                                                    'partner_id':ai.partner_id.id,
	                                                    'name': 'Cash in Bank',
	                                                    'debit':down_payment_catered,
	                                                    'credit':0,
	                                                    'date_maturity':ai.date_invoice,
	                                                    'reconciled':False,
	                                            })
	                                
	                                itemList.append({
	                                                    'brdc_move_id':brdc_move_down.id,
	                                                    'account_id':rec.get_account_from_coa(entry_numbers['down_credit']).id,
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
	                                                    'account_id':rec.get_account_from_coa(entry_numbers['amort_debit']).id,
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
	                                                    'account_id':rec.get_account_from_coa(entry_numbers['amort_credit']).id,
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
	                                                'account_id':rec.get_account_from_coa(entry_numbers['pcf']).id,
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
	                                


	                # if ai:
	                #     rec.account_invoice_id = ai.id
	                #     ai.compute_residual()
	                #     ai.update_surcharge()

	               	# rec.update({'state':'posted'})
	                

	                # if rec.payment_record_type == 'cashier':
	                #     search_result = self.env['daily.collection.record'].search([('date','=', datetime.strptime(fields.Date.today(), '%Y-%m-%d')),('collector_id','=', rec.user_id.id),('collection_type','=','cashier'),('state','=','draft')])
	                #     id_to_use = None


	                #     if search_result:
	                #         id_to_use = search_result[0]
	                #     else:
	                #         id_to_use = self.env['daily.collection.record'].create({
	                #                                                         'collector_id':rec.user_id.id,
	                #                                                         'date':datetime.strptime(fields.Date.today(), '%Y-%m-%d'),
	                #                                                         'collection_type':'cashier',
	                #                                                 })
	                    
	                    
	                #     dcr_line = self.env['dcr.lines'].create({
	                #                     'partner_ids':rec.partner_id.id,
	                #                     'DailyCollectionRecord_id':id_to_use.id,
	                #                     'dcr_collector':rec.user_id.id,
	                #                     'cash_cheque_selection': rec.cash_cheque_selection,
	                #                     'or_reference':str(rec.or_reference),
	                #                     'amount_paid':rec.amount,
	                #                     'setdate':rec.payment_date,
	                #                     'state':'posted',
	                #                     'PA':rec.pa_reference,
	                #                     'invoice_id':ai.id,
	                #                     'journal_id':rec.journal_id.id,
	                #                     'description':str(rec.pa_reference)+"-"+str(rec.or_reference),
	                #                     'payment_id':rec.id,
	                #     })
	                    
	                #     rec.update({
	                #                     'collected_id':dcr_line.id,
	                #                     'collection_id':id_to_use.id,
	                #             })

	def check_and_update_invoices(self):
		file = open("update.txt", "w")
		
		all_invoices = self.env['account.invoice'].search([('id','!=',0),('state','in',['open','paid'])])
		
		print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++\nUpdating Invoices")
		file.write("\n"+"++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++\nUpdating Invoices")

		for invoice in all_invoices:

			print("=========================\n"+ str(invoice.pa_ref))
			file.write("\n"+"=========================\n"+ str(invoice.pa_ref))

			total_payment_sched = 0
			
			for item in invoice.InvoiceInstallmentLine_ids:
				if item.is_paid or item.balance != 0:
					total_payment_sched += item.payable_balance if item.balance == 0 else item.balance

			print("total payment on sched: "+str(total_payment_sched))
			print("total paid: "+str(invoice.total_paid))
			print("their the same: "+'yes' if total_payment_sched == invoice.total_paid else 'no')

			file.write("\n"+"total payment on sched: "+str(total_payment_sched))
			file.write("\n"+"total paid: "+str(invoice.total_paid))
			file.write("\n"+"their the same: "+'yes' if total_payment_sched == invoice.total_paid else 'no')

			if total_payment_sched != invoice.total_paid:

				difference = invoice.total_paid - total_payment_sched
				pay_sched_search_ref = [('account_invoice_id','=', invoice.id)]
				order_str = ''
				trans_type = ''

				print("*****************\nupdating the invoice")
				print("difference: " +str(difference))

				file.write("\n"+"*****************\nupdating the invoice")
				file.write("\n"+"difference: " +str(difference))


				
				if difference > 0:
					pay_sched_search_ref.append(('is_paid','=', False))
					order_str = "id asc"
					trans_type = 'add'
				else:
					pay_sched_search_ref.append(('is_paid','=', True))
					order_str = "id desc"
					trans_type = 'subtract'

				print("results of ifs:\n-- serach_ref: "+str(pay_sched_search_ref)+"\n-- order_str: "+ order_str+"\n-- trans_type: "+trans_type)

				file.write("\n"+"results of ifs:\n-- serach_ref: "+str(pay_sched_search_ref)+"\n-- order_str: "+ order_str+"\n-- trans_type: "+trans_type)
				payment_sched = self.env['invoice.installment.line'].search(pay_sched_search_ref, order=order_str)

				print("***************** \nsearch result")
				print(payment_sched)

				file.write("\n"+"***************** \nsearch result")
				file.write("\n"+str(payment_sched))


				amount_to_cater = abs(difference)
				amount_catered = 0
				current_index = 0

				while round(amount_to_cater, 2) != round(amount_catered, 2):
					
					current_line = payment_sched[current_index]
					
					if trans_type == 'add':
						
						line_amount_to_cater = current_line.amount_due

						amount_to_register = line_amount_to_cater if amount_to_cater > line_amount_to_cater else amount_to_cater

						# current_line.register_payment(amount_to_register, , date_of_payment, sched_id)

						current_index += 1

					else:
						paid_amount =  current_line.amount_to_pay if current_line.balance == 0 else current_line.balance
						uncatered_amount = amount_to_cater - amount_catered
						line_amount_to_cater = paid_amount if uncatered_amount > paid_amount else uncatered_amount
						current_line.unregister_payment(line_amount_to_cater, current_line.id)
						amount_catered += line_amount_to_cater

			# payment_sched_lines = self.env['invoice.installment.line'].search([('account_invoice_id','=', invoice.id)], order='id asc')

			# total_amount = 0
			# amount_from_paid = 0
			# amount_from_advance = 0

			# current_line_for_update = False
			# current_line_for_update_index = 0

			# for index,payment_line in enumerate(payment_sched_liness):
				
			# 	# if payment_line.is_paid or payment_line.balance != 0:
			# 	# 	total_amount += payment_line.payable_balance if payment_line.balance == 0 else payment_line.balance
			# 	# 	amount_from_paid += payment_line.payable_balance if payment_line.is_paid else 0
			# 	# 	amount_from_advance += payment_line.balance if payment_line.balance != 0 else 0

			# 	if not payment_line.is_paid and not current_line_for_update:
			# 		current_line_for_update = payment_line
			# 		current_line_for_update_index = index

			# 	if current_line_for_update != payment_line:
			# 		total_amount_to_cater = payment_line.payable_balance if payment_line.balance == 0 and payment_line.is_paid else payment_line.balance

			# 		if total_amount_to_cater != 0:
			# 			while total_amount_to_cater != 0 and current_line_for_update != payment_line: 
			# 				amount_to_pay_here = payment_line.amount_to_pay if payment_line.amount_to_pay <= total_amount_to_cater else total_amount_to_cater
			# 				current_line_for_update.register_payment(amount_to_pay_here, None, rec.payment_date, current_line.id)

			# 				total_amount_to_cater -= amount_to_pay_here

			# 				if total_amount_to_cater != 0:


		file.close()


	# def print_to_file(self, input):

	# 	prin
	# 	file.write("\n"+ str(input))
	# 	file.close()						


	def update_payments_and_sched(self):
		file = open("update_payment_sched.txt", "w")
		
		all_invoices = self.env['account.invoice'].search([('id','!=',0),('state','in',['open','paid'])])
		# self.env['invoice.installment.line'].set_sched_to_draft_all()

		for invoice in all_invoices:
			payments = self.env['account.payment'].search([('communication','=',invoice.number),('state','not in',['draft',])])

			if payments:

				self.env['invoice.installment.line'].set_sched_to_draft_by_invoice(invoice.id)
				
				for payment in payments:
					sched_instance = self.env['invoice.installment.line']
					sched_instance.register_payment_amount(payment, invoice)

	def delete_double_payment(self):

		all_element = self.env['account.payment'].search([('id','!=',0)])
		print(":::::::::::::::::::::::::::::::\n"+str(len(all_element)) +" items")
		index = 1
		for element in all_element:
			print("+++++++++++++++++++++\n"+str(index))
			index+=1
			print("========================\nSearching Duplicates")
			search_result = self.env['account.payment'].search([('or_reference','=',element.or_reference),('communication','=',element.communication),('payment_date','=',element.payment_date),('amount','=',element.amount),('state', '!=', 'draft')])

			if len(search_result) > 1:
				print("+++++++++++++++++\nDuplicate Found")
				for idx, item in enumerate(search_result):
					if idx != 0:
						item.cancel()
					# item.unlink()
					# print("==================================\nDeleting Data")

	def coll_with_draft_payment(self):
		file = open("update_drafts.txt", "w")
		dcr_lines = self.env['dcr.lines'].search([('id','!=',0)])
		file.write("\n"+"++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++\nUpdating Invoices\n")

		for item in dcr_lines:

			if item.or_reference and item.DailyCollectionRecord_id.id:
				print("++++++++++++++++++++= checking line")
				if item.payment_id.state == 'draft':
					print("++++++++++ unlink line")

					item.unlink()

				duplicates = self.env['dcr.lines'].search([('or_reference','=', item.or_reference),('DailyCollectionRecord_id','=',item.DailyCollectionRecord_id.id),('id','!=',item.id)])
				print("+++++++++++++++++++++++++++++++++++++")
				print(len(duplicates))
				print(len(dcr_lines))
				print(len(duplicates) > 1)
				file.write("+++++++++++++++++++++++++++++++++++++"+"\n")
				file.write(str(len(duplicates))+"\n")
				file.write(str(len(dcr_lines))+"\n")
				file.write(str(len(duplicates) > 1)+"\n")
				file.write(str(item.or_reference)+"\n")
				file.write(str(item.payment_id.id)+"\n")
				file.write(str(item.DailyCollectionRecord_id.id)+"\n")

				file.write("\n\n+++ the duplicates ++++++"+"\n")
				for oo in duplicates:
					file.write(str("____________________")+"\n")
					file.write(str(item.id)+"\n")
					file.write(str(oo.id)+"\n")
					file.write(str(oo.payment_id.id)+"\n")
					file.write(str(oo.or_reference)+"\n")
					file.write(str(oo.DailyCollectionRecord_id.id)+"\n")

				if len(duplicates) > 0:
					print("++++++++++ unlink line")
					item.unlink()

