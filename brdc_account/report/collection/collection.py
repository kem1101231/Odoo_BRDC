from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, date, timedelta
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
import pytz 

# utc = pytz.utc
date_today = datetime.utcnow()
# utc_dt = datetime(date_today.year, date_today.month, date_today.day, date_today.hour, date_today.minute, date_today.second, tzinfo=utc)
# eastern = pytz.timezone('Asia/Manila')
loc_dt = date_today + timedelta(hours=8)

class CollectionReport(models.TransientModel):
	_name="brdc.report.collect.main"


	report_type = fields.Selection(selection=[('col', 'Collection Report'),('ccl',"Collector's Collectible List"), ('clf', 'Collection Efficiency')], string="Report Type")
	group_result = fields.Selection(selection=[('col','Collector'),('pro','Product'),('gen','General/Abstract')], string="Group By")
	generate_daily = fields.Boolean(string="Daily Report")
	generate_cashier = fields.Boolean(string="Generate for Cashier")
	select_collector = fields.Boolean(string="Specify Collector")
	collector = fields.Many2one(string="Collector", comodel_name="brdc.collection.collector")

	date_for_daily = fields.Date(string="Daily Report Date", default=fields.Datetime.now())

	@api.multi
	def default_month(self):
		now = datetime.now()
		return int(now.month)

	current_month = fields.Selection([(1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
                          (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
                          (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'), ],
                          string='Report Month', default=default_month)

	def year_selection(self):
		today = datetime.today()
		index = 0
		out_selection = []
		while index <= 10:
			the_year = str(today.year - index)
			out_selection.append((the_year, the_year))
			index += 1
		return out_selection

	def get_current_year(self):
		today = datetime.today()
		return str(today.year)

	for_year = fields.Selection(selection='year_selection', string="Report Year", default=get_current_year)



	@api.onchange('report_type')
	def group_type_update(self):
		if self.report_type:
			self.group_result = False

	@api.onchange('group_result')
	def group_res_update(self):
		if self.group_result:
			self.select_collector = False
			self.collector = False



	@api.multi
	def print_collection_report(self):

		for report in self:
			data_in = {}

			template = ''

			if report.report_type == 'col' and report.group_result == 'gen':
				if report.generate_daily:
					template = 'brdc_account.report_collection_dcb_template'
					data_in = self.daily_coll_data()
				else:
					template = 'brdc_account.report_collection_col_rep_abstract_template'
					data_in = self.collection_report_data()

			if report.report_type == 'col' and report.group_result == 'col':
				if report.generate_daily:
					template = 'brdc_account.report_collection_dcb_template'
					data_in = self.daily_coll_data()
				else:
					data_in = self.collection_report_data()
					template = 'brdc_account.report_collection_col_rep_template'

			if report.report_type == 'ccl' and report.group_result == 'col':
				template = 'brdc_account.report_collection_ccl_per_coll_template'
				data_in = self.ccl_report_data()
			if report.report_type == 'ccl' and report.group_result == 'gen':
				template = 'brdc_account.report_collection_ccl_absract_template'
				data_in = self.ccl_report_data()

			if report.report_type == 'clf':
				template = 'brdc_account.report_collection_dcr_template'
			
			#return self.env['report'].get_action(self, 'brdc_account.report_collection_ccl_template', data=data_y)
			# print("______________________________________")
			
			file_data = self.env['report'].get_action(self, template, data=data_in)
			
			# print(file_data)

			return file_data

	def collection_report_data(self):

		print("++++++++++++++++++++++++++++++++++++++++++++")
		print(calendar.month_name[datetime.today().month])
		print(datetime.today().year)
		
		selected_date = datetime(int(self.for_year),int(self.current_month),1)
		data_out = {
						'lines':[],
						'lines_by_collector':[],
						'type':'',
						'month':calendar.month_name[selected_date.month],
						'year':selected_date.year,
						'total_current_due':0,
						'total_past_due':0,
						'total_surcharge':0,
						'total_advance':0,
						'total_collected':0,
						'print_date': loc_dt.strftime('%a %b %d, %Y - %I:%M:%S %p'),
		}

		collector_check = {}
		index = 0

		all_line = []
		all_line_per_collector = []
		
		collection_search = [('id','!=','0'), ('date','>', datetime(int(self.for_year),int(self.current_month),1)),('date','<',datetime(int(self.for_year),int(self.current_month),calendar.monthrange(int(self.for_year), int(self.current_month))[1])),('state','=','confirm')]

		if self.select_collector:
			collection_search.append(('collector_id','=', self.collector.sudo().collector_id.id))
		
		col_type_ref = 'cashier' if self.generate_cashier else 'collect'
		if self.group_result == 'col':
			collection_search.append(('collection_type','=', col_type_ref))

		collector_list = self.env['daily.collection.record'].search(collection_search)
		
		for line in collector_list:

			for item in line.dcr_lines_ids:

				if len(item.invoice_id.invoice_line_ids) != 0:
					invoice_line = item.invoice_id.invoice_line_ids[0]
					payment_info = item.get_payment_info()
					
					line_data = {

										'client':item.partner_ids.name,
										'product_type':item.invoice_id.product_type.name,
										'status':'Active' if item.invoice_id.has_terminated == False else 'Reactivated',
										'pa_number':item.invoice_id.pa_ref,
										'collector':line.sudo().collector_id.name,
										'product':item.invoice_id.product_type.name,
										'area_class':invoice_line.product_id.categ_id.name,
										'area':invoice_line.product_id.area_number.name,
										'block_number':invoice_line.lot_id.block_number ,
										'lot_number':invoice_line.lot_id.lot_number,
										'or':item.or_reference,
										'or_date':line.date,
										'current_due':payment_info['current'],
										'past_due':payment_info['past'],
										'surcharge':payment_info['fees'],
										'advance':payment_info['advance'],
										'collected':item.amount_paid,
								}

					if self.group_result == 'col': 
						
						if str(line.collector_id.id) not in collector_check:
							collector_check[str(line.sudo().collector_id.id)] = len(data_out['lines_by_collector'])
							data_out['lines_by_collector'].append({
																			
																			'collector': line.sudo().collector_id.name,
																			'lines':[],
																			'line_length':0,																
																			'total_current_due':0,
																			'total_past_due':0,
																			'total_surcharge':0,
																			'total_advance':0,
																			'total_collected':0,
																	})

						curr_line = data_out['lines_by_collector'][collector_check[str(line.sudo().collector_id.id)]]
						curr_line['lines'].append(line_data)

					
					if self.group_result == 'gen':
						data_out['lines'].append(line_data)

		for_totals = ['current_due','past_due','surcharge','advance', 'collected']

		if self.group_result == 'col': 
			for line in data_out['lines_by_collector']:
				line['lines'] = self.sort_result(line['lines'], 'client')
				line['lines'] = self.num_the_lines(line['lines'])
				line['lines'] = self.cut_to_pages(line['lines'], 25, for_totals)
			data_out['type'] = 'cashier' if self.generate_cashier else 'collect' 
		
		if self.group_result == 'gen': 
			data_out['lines'] = self.sort_result(data_out['lines'], 'client')
			data_out['lines'] = self.num_the_lines(data_out['lines'])
			data_out['lines'] = self.cut_to_pages(data_out['lines'], 25, for_totals)
			data_out['type'] = 'gen'


		print("----------------------------------------------")
		print(data_out['lines_by_collector'])
		return data_out

	def cut_to_pages(self, inputData, lines_per_pages, total_reference):
		
		index = 0
		
		new_data = []
		totals = {}

		pages = []
		page_number = 0

		# for x in total_reference:
		# 	totals[x] = 0

		# print("&*&*&*&*&*&*&*&*&*&*&")
		# print(inputData)

		for x in inputData:

			# print("x\n***********************")
			
			# print(x)
			# print("============\n"+str(type(x)))
			

			if index == 0:
				totals = {}
				new_data = []
				for ref in total_reference:
					totals[ref] = 0

				page_number += 1
			
			# print(x)
			new_data.append(x)
			# print("+++++++")
			# print(totals)
			# print(new_data)
			# print(x['collected'])

			for line in total_reference:
				totals[line] += x[line]
			
			index += 1

			if index == lines_per_pages or x == inputData[len(inputData)-1]:
				pages.append({
								'page':new_data,
								'totals':totals,
								'page_number':page_number,
					})
				print("=======================")
				print(totals)
				
				index = 0

		# for ne in new_data:

		# print(totals)
		# print("000000000000000000000000")
		return pages
	
	def sort_result(self, inputList, reference):
		print("++++++++++++++++++++++++++++++++++++")
		print(inputList)
		# data = [{'1':7,'2':8,'3':9,},{'1':1,'2':2,'3':3,},{'1':4,'2':5,'3':6,}]
		inputList.sort(key=lambda tup: tup[reference])  
		return inputList

	def num_the_lines(self, inputList):
		index = 1
		data_out = inputList

		for idx, item in enumerate(inputList):
			data_out[idx]['no'] = index
			index += 1

		return data_out

	def daily_coll_data(self):
		data_out = {
					'dcr':{},
					'dcb':{},
					'collector':'',
					'col_type':'',
					'type':'abstract',
					'print_date':loc_dt.strftime('%a %b %d, %Y - %I:%M:%S %p'),
					'date_gen':datetime.strptime(self.date_for_daily, '%Y-%m-%d').strftime('%b %d, %Y'),
		}
	
		# print("++++++++++++++++++++++++++++++++++++++++++++")
		# print(calendar.month_name[datetime.today().month])
		# print(datetime.today().year)
		

		selected_date = datetime.strptime(self.date_for_daily, '%Y-%m-%d')
		data_out_dcr = {
						'lines':[],
						'lines_by_collector':[],
						'month':calendar.month_name[selected_date.month],
						'year':selected_date.year,				
					}

		collector_check = {}
		index = 0

		all_line = []
		all_line_per_collector = []
		
		collection_search = [('id','!=','0'), ('date','=', selected_date),('state','=','confirm')]

		if self.select_collector:
			collection_search.append(('collector_id','=', self.collector.sudo().collector_id.id))
			data_out['collector'] = self.collector.name
			data_out['type'] = 'collect'

		col_type_ref = 'cashier' if self.generate_cashier else 'collect'
		if self.group_result == 'col':
			collection_search.append(('collection_type','=', col_type_ref))



		print("***********************")
		print(collection_search)
		collector_list = self.env['daily.collection.record'].search(collection_search)

		print(collector_list)
		
		cc_line_ref = {}
		cc_line = []
		cc_line_total = 0

		cash_collection = 0
		installment_collection = 0
		fees_collection = 0


		for line in collector_list:
			
			for item in line.dcr_lines_ids:

				if len(item.invoice_id.invoice_line_ids) != 0:
					invoice_line = item.invoice_id.invoice_line_ids[0]
					
					line_data = {

										'client':item.partner_ids.name,
										'product_type':item.invoice_id.product_type.name,
										'status':'Active' if item.invoice_id.has_terminated == False else 'Reactivated',
										'payment_type':'Cash' if item.cash_cheque_selection == 'cash' else 'Check',
										'pa_number':item.invoice_id.pa_ref,
										'collector':line.sudo().collector_id.name,
										'product':item.invoice_id.product_type.name,
										'area_class':invoice_line.product_id.categ_id.name,
										'area':invoice_line.product_id.area_number.name,
										'block_number':invoice_line.lot_id.block_number ,
										'lot_number':invoice_line.lot_id.lot_number,
										'particular':item.journal_id.name,
										'or':item.or_reference,
										'or_date':line.date,
										'current_due':0,
										'past_due':0,
										'surcharge':0,
										'advance':0,
										'collected':item.amount_paid,
								}


					if item.invoice_id.purchase_term == 'cash':
						cash_collection += item.amount_paid
					if item.invoice_id.purchase_term == 'install':
						installment_collection += item.amount_paid

					data_out_dcr['lines'].append(line_data)

			# if self.group_result == 'col': 
				
			# 	if str(line.collector_id.id) not in collector_check:
			# 		collector_check[str(line.sudo().collector_id.id)] = len(data_out_dcr['lines_by_collector'])
			# 		data_out_dcr['lines_by_collector'].append({
																	
			# 														'collector': line.sudo().collector_id.name,
			# 														'lines':[],
			# 														'line_length':0,																
			# 														'total_current_due':0,
			# 														'total_past_due':0,
			# 														'total_surcharge':0,
			# 														'total_advance':0,
			# 														'total_collected':0,
			# 												})

			# 	curr_line = data_out_dcr['lines_by_collector'][collector_check[str(line.sudo().collector_id.id)]]
			# 	curr_line['lisnes'].append(line_data)

			# if self.group_result == 'gen':
			

			# print("====================================")


			for count in line.cash_count_line_ids:


				# print("------")
				# print("Deno:     " + str(count.description))
				# print("Bill Num: " + str(count.bill_number))
				# print("Amount:   " +str(count.total_amount))

				if str(count.description) not in cc_line_ref:
					
					line_data = {
									'deno': count.description,
									'billnum':count.bill_number,
									'amount':count.total_amount,
								}

					cc_line_ref[str(count.description)] = len(cc_line)
					cc_line.append(line_data)
				
				else:
					cc_line[cc_line_ref[str(count.description)]]['amount'] += count.total_amount
					cc_line[cc_line_ref[str(count.description)]]['billnum'] += count.bill_number
				
				cc_line_total += count.total_amount


			# cc_line_ref = {}
			# print("**********************************")
			# print("Total: " + str(cc_line_total))
			# print("**********************************")

		for_totals = ['current_due','past_due','surcharge','advance', 'collected']

		# if self.group_result == 'col': 
		# 	for line in data_out_dcr['lines_by_collector']:
		# 		line['lines'] = self.sort_result(line['lines'], 'client')
		# 		line['lines'] = self.num_the_lines(line['lines'])
		# 		line['lines'] = self.cut_to_pages(line['lines'], 19, for_totals)
		
		# if self.group_result == 'gen': 
		data_out_dcr['lines'] = self.sort_result(data_out_dcr['lines'], 'client')
		data_out_dcr['lines'] = self.num_the_lines(data_out_dcr['lines'])
		data_out_dcr['lines'] = self.cut_to_pages(data_out_dcr['lines'], 19, for_totals)


		print("----------------------------------------------")
		print(data_out_dcr['lines_by_collector'])

		data_out['dcr'] = data_out_dcr
		data_out['dcb']['denomination'] = cc_line
		data_out['dcb']['denomination_total'] = cc_line_total
		data_out['dcb']['cash_collection'] = cash_collection
		data_out['dcb']['installment_collection'] = installment_collection
		data_out['dcb']['fees_collection'] = fees_collection
		data_out['dcb']['total_conso_collection'] = cash_collection + installment_collection + fees_collection

		data_out['col_type'] = col_type_ref

		print(data_out['dcr'])

		return data_out

	def ccl_report_data(self):
		
		data_out = {
						'lines':[],
						'lines_by_collector':[],
						'month':calendar.month_name[datetime.today().month],
						'year':datetime.today().year,
						'line_length':0,
						'total_due':0,
						'total_current_due':0,
						'total_30':0,
						'total_60':0,
						'total_90':0,
						'total_91':0,
						'print_date': loc_dt.strftime('%a %b %d, %Y - %I:%M:%S %p'),
					}

		invoice_search = [('state','=','open'), ('pa_ref_collector','!=', False)]

		if self.select_collector:
			invoice_search.append(('pa_ref_collector','=', self.collector.sudo().collector_id.id))

		invoices = self.env['account.invoice'].search(invoice_search)

		collectors = {}

		# if self.group_result == 'col':
		# 	if self.select_collector:
		# 		collectors[self.collector.sudo().collector_id.name] = {
		# 															'lines':[],
		# 															'total_current_due':0,
		# 															'total_30':0,
		# 															'total_60':0,
		# 															'total_90':0,
		# 															'total_91':0,
		# 														}

		# 	else:
		# 		collector_result = self.env['brdc.collection.collector'].search([('id','!=', 0)])
		# 		for line in collector_result:
		# 			collectors[line.sudo().collector_id.name] = {
		# 													'lines':[],
		# 													'total_current_due':0,
		# 													'total_30':0,
		# 													'total_60':0,
		# 													'total_90':0,
		# 													'total_91':0,
		# 												}
		# 	data_out['lines'] = collectors

		collector_data = {
						
						'collector':'',
						'lines':[],
						'total_due':0,
						'total_current_due':0,
						'total_30':0,
						'total_60':0,
						'total_90':0,
						'total_91':0,
		}
		report_page = []
		
		page_number = 1

		for item in invoices:
			
			invoice_info = self.get_invoice_info(item.id)

			item_line = {
							'pa':invoice_info['invoice_pa'],
							'name':invoice_info['partner_name'],
							'address':invoice_info['partner_address'],
							'contact':invoice_info['partner_contact'],
							'status':invoice_info['status'],
							'collector':invoice_info['collector'],
							'product':invoice_info['product'],
							'area_class':invoice_info['area_class'],
							'area':invoice_info['area'],
							'block':invoice_info['block'],
							'lot':invoice_info['lot'],
							'term':invoice_info['term'],
							'net_con':invoice_info['net_con'][0],
							'down':invoice_info['down'],
							'mon':invoice_info['month'],
							'date_invoice':invoice_info['date_invoice'],
							'balance':invoice_info['balance'],
							'due':invoice_info['due'],
							'total_due':invoice_info['total_due'],
							'current_due':invoice_info['current_due'],
							'1_30':invoice_info['1_30'],
							'31_60':invoice_info['31_60'],
							'61_90':invoice_info['61_90'],
							'91':invoice_info['91'],
						}

			if self.group_result == 'col':

				if str(item.sudo().pa_ref_collector.id) not in collectors:
					
					collectors[str(item.sudo().pa_ref_collector.id)] = len(data_out['lines_by_collector'])
					data_out['lines_by_collector'].append({
																
																'collector': item.sudo().pa_ref_collector.name,
																'lines':[],
																'line_length':0,																
																'total_due':0,
																'total_current_due':0,
																'total_30':0,
																'total_60':0,
																'total_90':0,
																'total_91':0,
														

														})
				#40
				collector_data = data_out['lines_by_collector'][collectors[str(item.sudo().pa_ref_collector.id)]]

				# if collector_data['line_length'] == 0:

				# 	collector_data['lines'].append({

				# 										'page':page_number,
				# 										'page_line':[],
				# 										'total_due':0,
				# 										'total_current_due':0,
				# 										'total_30':0,
				# 										'total_60':0,
				# 										'total_90':0,
				# 										'total_91':0,
				# 								})
				

				# line_to_add = collector_data['lines'][len(collector_data['lines']) - 1]
				
				collector_data['lines'].append(item_line)
				
				# line_to_add['total_due'] += float(invoice_info['total_due']) if invoice_info['total_due'] != '-' else 0
				# line_to_add['total_current_due'] += float(invoice_info['current_due']) if invoice_info['current_due'] != '-' else 0
				# line_to_add['total_30'] += float(invoice_info['1_30']) if invoice_info['1_30'] != '-' else 0
				# line_to_add['total_60'] += float(invoice_info['31_60']) if invoice_info['31_60'] != '-' else 0
				# line_to_add['total_90'] += float(invoice_info['61_90']) if invoice_info['61_90'] != '-' else 0
				# line_to_add['total_91'] += float(invoice_info['91']) if invoice_info['91'] != '-' else 0



				# collector_data['total_current_due'] += item.current_due
				# collector_data['line_length'] += 1

				# line_to_add['page_line'] = sort_result(line_to_add['page_line'])

				
				# if collector_data['line_length'] == 31:
				# 	collector_data.update(line_length = 0)

				# 	page_number += 1



				
			else:
				# if data_out['line_length'] == 0:
				# 	#data_out['lines'].append([])
				# 	data_out['lines'].append({

				# 										'page':page_number,
				# 										'page_line':[],
				# 										'total_due':0,
				# 										'total_current_due':0,
				# 										'total_30':0,
				# 										'total_60':0,
				# 										'total_90':0,
				# 										'total_91':0,
				# 							})

				# line_to_add = data_out['lines'][len(data_out['lines'])-1]
				
				data_out['lines'].append(item_line)
				# data_out['total_due'] += float(invoice_info['total_due']) if invoice_info['total_due'] != '-' else 0
				# data_out['total_current_due'] += float(invoice_info['current_due']) if invoice_info['current_due'] != '-' else 0
				# data_out['total_30'] += float(invoice_info['1_30']) if invoice_info['1_30'] != '-' else 0
				# data_out['total_60'] += float(invoice_info['31_60']) if invoice_info['31_60'] != '-' else 0
				# data_out['total_90'] += float(invoice_info['61_90']) if invoice_info['61_90'] != '-' else 0
				# data_out['total_91'] += float(invoice_info['91']) if invoice_info['91'] != '-' else 0

				# data_out['line_length'] += 1

				# if data_out['line_length'] == 22:
				# 	data_out.update(line_length = 0)
				# 	page_number += 1
		
		for_totals = ['balance','total_due','current_due','1_30','31_60','61_90','91']
		if len(data_out['lines_by_collector']) != 0:
			for item in data_out['lines_by_collector']:
				item['lines'] = self.sort_result(item['lines'], 'name')
				item['lines'] = self.num_the_lines(item['lines'])
				item['lines'] = self.cut_to_pages(item['lines'], 25, for_totals)
		else:

			data_out['lines'] = self.sort_result(data_out['lines'], 'name')
			data_out['lines'] = self.num_the_lines(data_out['lines'])
			data_out['lines'] = self.cut_to_pages(data_out['lines'], 20, for_totals)



		return data_out

	def get_invoice_info(self, inv_id):
		for collect in self:
			
			out_data = {}
			
			invoice_info = self.env['account.invoice'].search([('id','=', inv_id)], limit=1)

			out_data['invoice_pa'] = invoice_info.pa_ref
			out_data['partner_name'] = invoice_info.partner_id.name 
			out_data['partner_address'] = invoice_info.partner_id.street # invoice_info.partner_id.barangay_id.name if invoice_info.partner_id.barangay_id.name else '' +", "+ invoice_info.partner_id.municipality_id.name if invoice_info.partner_id.municipality_id.name else '' +", "+invoice_info.partner_id.province_id.name if invoice_info.partner_id.province_id.name else ''
			out_data['partner_contact'] = str(invoice_info.partner_id.mobile) if invoice_info.partner_id.mobile else 'Not Indicated'
			out_data['status'] = 'Active'
			out_data['collector'] = invoice_info.sudo().pa_ref_collector.name
			out_data['product'] = invoice_info.product_type.name 

			invoice_line = invoice_info.invoice_line_ids[0]

			out_data['area_class'] = invoice_line.product_id.categ_id.name
			out_data['area'] = invoice_line.product_id.area_number.name
			out_data['block'] = invoice_line.lot_id.block_number 
			out_data['lot'] =  invoice_line.lot_id.lot_number
			out_data['term'] = invoice_info.new_payment_term_id.no_months 

			date_range = datetime(int(date.today().year), int(date.today().month), calendar.monthrange(int(date.today().year),int(date.today().month))[1])
			for_30 = 0
			for_60 = 0
			for_90 = 0
			for_91 = 0

			payment_sched = self.env['invoice.installment.line'].search([('account_invoice_id','=', invoice_info.id), ('date_for_payment','<=', date_range),('is_paid','=',False)])
			
			for line in payment_sched:
				dfp = datetime.strptime(line.date_for_payment, "%Y-%m-%d")
				diff_in_days = abs((datetime.today() - dfp).days)
				
				if not datetime(int(date.today().year), int(date.today().month),1) < dfp < date_range:

					if diff_in_days <= 30:
						for_30 = for_30 + line.amount_to_pay
					if diff_in_days <= 60 and diff_in_days >= 31:
						for_60 = for_60 + line.amount_to_pay
					if diff_in_days <= 90 and diff_in_days >= 61:
						for_90 = for_90 + line.amount_to_pay
					if diff_in_days >= 91:
						for_91 = for_91 + line.amount_to_pay

			out_data['net_con'] = invoice_info.amount_total,
			out_data['down'] = invoice_info.s_dp
			out_data['month'] = invoice_info.monthly_payment
			out_data['date_invoice'] = invoice_info.date_invoice
			out_data['balance'] = invoice_info.residual
			out_data['due'] = datetime.strptime(invoice_info.month_to_pay, '%Y-%m-%d').day if invoice_info.month_to_pay else '-'
			out_data['total_due'] = for_30 + for_60 + for_90 + for_91 + invoice_info.current_due
			out_data['current_due'] = invoice_info.current_due
			out_data['1_30'] = for_30 #if for_30 != 0 else '-'
			out_data['31_60'] = for_60 #if for_60 != 0 else '-'
			out_data['61_90'] = for_90 #if for_90 != 0 else '-'
			out_data['91'] =  for_91 #if for_91 != 0 else '-'

			return out_data

	def colef_report_data(self):
		pass



	# @api.model
	# def render_html(self, docids, data):

	# 	template = ''

	# 	if self.report_type == 'col' and self.group_result == 'gen':
	# 		template = 'brdc_account.report_collection_col_rep_abstract_template'
	# 	if self.report_type == 'col' and self.group_result == 'col':
	# 		template = 'brdc_account.report_collection_col_rep_template'
	# 	if self.report_type == 'ccl' and self.group_result == 'col':
	# 		template = 'brdc_account.report_collection_ccl_per_coll_template'
	# 	if self.report_type == 'ccl' and self.group_result == 'gen':
	# 		template = 'brdc_account.report_collection_ccl_absract_template'

	# 	docargs = {
 #            'doc_ids': self.ids,
 #            'doc_model': None,
 #            'docs': {'1':'one','2':'two','3':'three','4':'four','5':'five'},
 #            'time': time,
 #            'dataInput': data,
 #        }
	# 	print(template)

	# 	return self.env['report'].render(template, docargs)

# class CollectionReportCCL(models.TransientModel):
# 	_name='brdc.report.collect.ccl'


class ReportCollectionCCL(models.AbstractModel):
    _name = 'report.brdc_account.report_collection_ccl'
    
    @api.model
    def render_html(self, docids, data):
        
        docargs = {
            'doc_ids': self.ids,
            'doc_model': None,
            'docs': {'1':'one','2':'two','3':'three','4':'four','5':'five'},
            'time': time,
            'dataInput': data,
        }

        return self.env['report'].render('brdc_account.report_collection_ccl_template', docargs)


class ReportCollectionCCLPerCol(models.AbstractModel):
	_name='report.brdc_account.report_collection_ccl_per_coll_template'

	@api.model
	def render_html(self, docids, data):
		
		report = self.env['report']._get_report_from_name('brdc_account.report_collection_ccl_per_coll_template')
		
		docargs = {
            'doc_ids': self.ids,
            'doc_model': report.model,
            'docs': {'1':'one','2':'two','3':'three','4':'four','5':'five'},
            # 'time': time,
            'dataInput': data,
        }
		
		return self.env['report'].render('brdc_account.report_collection_ccl_per_coll_template', docargs)

class ReportCollectionCCLPerCol(models.AbstractModel):
	_name='report.brdc_account.report_collection_ccl_absract_template'

	@api.model
	def render_html(self, docids, data):
		
		report = self.env['report']._get_report_from_name('brdc_account.report_collection_ccl_absract_template')
		
		docargs = {
            'doc_ids': self.ids,
            'doc_model': report.model,
            'docs': {'1':'one','2':'two','3':'three','4':'four','5':'five'},
            # 'time': time,
            'dataInput': data,
        }
		
		return self.env['report'].render('brdc_account.report_collection_ccl_absract_template', docargs)

class ReportCollectionReport(models.AbstractModel):
    _name = 'report.brdc_account.report_collection_col_rep_template'
    
    @api.model
    def render_html(self, docids, data):
        
        docargs = {
            'doc_ids': self.ids,
            'doc_model': None,
            'docs': {'1':'one','2':'two','3':'three','4':'four','5':'five'},
            #'time': time,
            'dataInput': data,
        }

        return self.env['report'].render('brdc_account.report_collection_col_rep_template', docargs)

class ReportCollectionReportAbstract(models.AbstractModel):
    _name = 'report.brdc_account.report_collection_col_rep_abstract_template'
    
    @api.model
    def render_html(self, docids, data):
        
        docargs = {
            'doc_ids': self.ids,
            'doc_model': None,
            'docs': {'1':'one','2':'two','3':'three','4':'four','5':'five'},
            #'time': time,
            'dataInput': data,
        }

        return self.env['report'].render('brdc_account.report_collection_col_rep_abstract_template', docargs)

class ReportDailyCollectionReportAbstract(models.AbstractModel):
    _name = 'report.brdc_account.report_collection_dcb_template'
    
    @api.model
    def render_html(self, docids, data):
        
        docargs = {
            'doc_ids': self.ids,
            'doc_model': None,
            'docs': {'1':'one','2':'two','3':'three','4':'four','5':'five'},
            #'time': time,
            'dataInput': data,
        }

        return self.env['report'].render('brdc_account.report_collection_dcb_template', docargs)




class CollectionReportInvoices(models.AbstractModel):
	_name='brdc.report.coll.ccl.invoice'
	
	invoice_id = fields.Many2one(comodel_name="account.invoice")
	pa = fields.Char(string="P.A. Number", related="invoice_id.pa_ref")
	customer_name = fields.Many2one(comodel_name="res.partner", string="Customer", related="invoice_id.partner_id")
	address = fields.Char(string="Address")
	contact = fields.Char(string="Contact")
	status = fields.Char(strting="Status")
	collector = fields.Many2one(comodel_name="res.users", related="invoice_id.pa_ref_collector")
	product = fields.Many2one(comodel_name="payment.config", related="invoice_id.product_type")
	area_class = fields.Char()
	area = fields.Char()
	block = fields.Char()
	lot = fields.Char()
	term = fields.Many2one(comodel_name="payment.config", related="invoice_id.new_payment_term_id")
	net_con = fields.Float()
	down = fields.Float()
	mon = fields.Float()
	date_invoice = fields.Date()
	balance = fields.Float()
	due = fields.Float()
	total_due = fields.Float()
	current_due = fields.Float()
	value_1_30 = fields.Float()
	value_31_60 = fields.Float()
	value_61_90 = fields.Float()
	value_91 = fields.Float()

class CollectionReportCCLGeneral(models.AbstractModel):
	_name="brdc.report.coll.ccl.list"

	# list_type = s
	total_due_value = fields.Float()
	total_current_due_value = fields.Float()
	total_30_value = fields.Float()
	total_60_value = fields.Float()
	total_90_value = fields.Float()
	total_91_value = fields.Float()

	line_list = fields.Many2many(comodel_name="brdc.report.coll.ccl.invoice")

