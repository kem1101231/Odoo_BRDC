from odoo import api, fields, models
from datetime import datetime
import calendar
from dateutil.relativedelta import relativedelta
import xlwt
import base64
import StringIO
import xlsxwriter

class AllInfoDisplay(models.TransientModel):
	_name = 'report.account.commission'

	agent = fields.Many2one(comodel_name='res.partner', string="Agent")
	date_from = fields.Date(string="Date From")
	date_to = fields.Date(string="Date To")
	for_release = fields.Boolean(string="For Release Only")

	
	@api.multi
	def print_info(self):

		agent_commission_id = self.env['account.agent.commission'].search([('agent_id','=', self.agent.id)], limit=1)
		print("**************************")
		print(agent_commission_id.name)
		print(agent_commission_id[0].invoice_ids)
		print(agent_commission_id[0].account_commission_id)

		commissions_lines_complete = []
		payment_lines_complete = []
		invoice_lines_complete = []
		comm_summary_lines_complete = []
		
		commissions_lines = []
		payment_lines = []
		invoice_lines = []
		comm_summary_lines = []

		commission_total = 0
		payment_total = 0

		commission_search = [   		
								('partner_id','=', self.agent.id),
		                        ('released','=', False),
		                       #('invoice_id','=', invoice.id),
		                        ('release_date','<=', self.date_to),
		                       #('release_date','>=', self.date_from)
		                    ]

		if self.for_release:
			commission_search.append(('ready_for_release','=', True))
		
		commissions = self.env['account.commission'].search(commission_search, order="release_date asc",)

		print("^^^^^    Commissions   ^^^^^ GOT  ")
		# print(len(commissions))

		index = 0
		total_comm_gross = 0
		total_comm_withh = 0
		total_comm = 0

		overall_comm_gross = 0
		overall_comm_withh = 0
		overall_comm = 0

		# print(len(commissions))
		# print("pa       customer                      commission          series        status")
		
		for line in commissions:

			# print("******* --------------- ********")
			# print(line.partner_id.name)
			# print(line.series)
			# print(line.amount)
			# print(line.invoice_id.pa_ref)
			
			ready_for_release = 'Yes' if line.ready_for_release == True else 'No'

			if line.invoice_id.state not in ['draft','cancel']:


				# print(str(line.invoice_id.pa_ref)+"           "+str(line.invoice_id.partner_id.name)+"             "+str("{:,.2f}".format(float(line.amount))+"            "+line.series+"               "+ready_for_release))

				commissions_lines.append({
				 									'date':self.crop_date(line.release_date),
				 									'pa':line.invoice_id.pa_ref,
				 									'customer':line.invoice_id.partner_id.name,
				 									'gross':"{:,.2f}".format(float(line.gross)),
				 									'withholding':"{:,.2f}".format(float(line.withholding_tax)),
				 									'commission':"{:,.2f}".format(float(line.amount)),
				 									'ready': ready_for_release,
				 									'series': line.series, #+" - "+ str(line.invoice_id.id)
				 									#'':,
				 			})

				total_comm = total_comm + line.amount
				total_comm_gross = total_comm_gross + line.gross
				total_comm_withh = total_comm_withh + line.withholding_tax

				overall_comm = overall_comm + line.amount
				overall_comm_gross = overall_comm_gross + line.gross
				overall_comm_withh = overall_comm_withh + line.withholding_tax

				if index != 25:
					index = index + 1
				
				else:
					commissions_lines_complete.append({	
														'lines':commissions_lines,
														'gross':"{:,.2f}".format(float(total_comm_gross)),
														'withh':"{:,.2f}".format(float(total_comm_withh)),
														'commission':"{:,.2f}".format(float(total_comm)),
													})
					commissions_lines = []
					index = 0
					total_comm_gross = 0
					total_comm_withh = 0
					total_comm = 0

		# print(len(commissions_lines_complete))
		# print("________________-")
		# print(len(commissions_lines))
		# for ii in commissions_lines:
		# 	print(ii)

		if len(commissions_lines) != 0:
			commissions_lines_complete.append({	
														'lines':commissions_lines,
														'gross':"{:,.2f}".format(float(total_comm_gross)),
														'withh':"{:,.2f}".format(float(total_comm_withh)),
														'commission':"{:,.2f}".format(float(total_comm)),
													})



 		print(" ^^^^^^   Invoices ^^^^^^^ ")
 		payment_list = []

 		invoice_index = 0

 		print(len(agent_commission_id[0].invoice_ids))

	 	for invoice in agent_commission_id[0].invoice_ids:

	 		if invoice.state not in ['draft','cancel','terminate']:

	 			invoice_line = invoice.invoice_line_ids
	 			line_amount = 0
	 			comm_series = invoice.new_payment_term_id.no_months if invoice.new_payment_term_id.no_months < 18 else 18

	 			for line in invoice_line:
	 				if not line.is_free:
	 					product = line.product_id

	 					if (product.lst_price != 0) and (product.lst_price < invoice.amount_total):
	 						line_amount = product.lst_price
	 					else:
	 						line_amount = invoice.amount_total

	 			commission_rate = agent_commission_id.position_id.comm_percent / 100

	 			commission_value = line_amount * commission_rate

	 			total_invoice_comm_gross = 0
	 			total_invoice_comm_withh = 0
	 			total_invoice_comm = 0
	 			total_claimed = 0
	 			total_for_release = 0
	 			total_unclaimed = 0
	 			series = ''
	 			max_term = invoice.payment_count if invoice.payment_count < 18 else 18

	 			per_invoice_commissions = self.env['account.commission'].search([('partner_id','=', self.agent.id), ('invoice_id','=', invoice.id),])

	 			for comm_line in per_invoice_commissions:

	 				total_invoice_comm_gross = total_invoice_comm_gross + comm_line.gross
	 				total_invoice_comm_withh = total_invoice_comm_withh + comm_line.withholding_tax
	 				total_invoice_comm = total_invoice_comm + comm_line.amount

	 				if comm_line.released == True:
	 					total_claimed = total_claimed + comm_line.amount
	 				else:
	 					total_unclaimed = total_unclaimed + comm_line.amount

	 				if comm_line.ready_for_release == True and comm_line.released == False:
	 					total_for_release = total_for_release + comm_line.amount
	


	 			if total_claimed == 0:
		 			series = "1 - "+str(max_term) +" of "+ str(comm_series)
		 		
		 		# else:
		 		# 	from_s = total_claimed / (commission_value / comm_series)
		 		# 	series = str(int(from_s))+" - "+str(max_term) +" of "+ str(comm_series)	

		 		invoice_lines.append( {
				 								'pa': invoice.pa_ref,
				 								'customer':invoice.partner_id.name,
				 								'con_date':self.crop_date(invoice.date_invoice),
				 								'mon': "{:,.2f}".format(float(invoice.monthly_payment)),
				 								'paid_mon': invoice.payment_count,
				 								'term': str(invoice.new_payment_term_id.no_months) + " months",
				 								'current_month':int(invoice.payment_count + invoice.month_due),
				 								'comm': "{:,.2f}".format(float(commission_value / comm_series)),
				 								'unpaid_mon': int(invoice.month_due),
				 								'due':"{:,.2f}".format(float(invoice.monthly_due)),
		 								})

		 		comm_summary_lines.append({
		 										'pa':invoice.pa_ref,
		 										'customer':invoice.partner_id.name,
		 										'max_comm_term':comm_series,
		 										'comm_series': "{:,.2f}".format(float(commission_value / comm_series)),
		 										'total_gross':"{:,.2f}".format(float(total_invoice_comm_gross)),
		 										'total_withh':"{:,.2f}".format(float(total_invoice_comm_withh)),
		 										'total_comm':"{:,.2f}".format(float(total_invoice_comm)),
		 										'total_claimed':"{:,.2f}".format(float(total_claimed)),
		 										'for_release':"{:,.2f}".format(float(total_for_release)),
		 										'series':series,
		 										'unclaimed':"{:,.2f}".format(float(total_unclaimed)),
		 								})
		 		
	
		 		if invoice_index != 25:
		 			print("I came, I saw, I conquered")
		 			invoice_index = invoice_index + 1
		 			print(invoice_index)

		 		else:

		 			print("Done my part")
		 			invoice_lines_complete.append({'lines':invoice_lines,})
		 			comm_summary_lines_complete.append({'lines':comm_summary_lines})
		 			
		 			invoice_lines = []
		 			comm_summary_lines = []
		 			invoice_index = 0

		        payments = self.env['account.payment'].search([ 	
		        													('communication','=', invoice.number),
		                                                        	('partner_id','=',invoice.partner_id.id),
		                                                        	#('payment_date','>=',self.date_from),
		                                                            ('payment_date','<=',self.date_to),
		                                                        ], order="partner_id desc",)

		        for payment in payments:
		        	payment_list.append(payment)
		
		
		if len(invoice_lines) != 0:
		 	invoice_lines_complete.append({'lines':invoice_lines,})
		 		
		if len(comm_summary_lines) != 0:
		 	comm_summary_lines_complete.append({'lines':comm_summary_lines})


		print(len(invoice_lines_complete))
		print(" >>>>>> Invoices ")


		payment_index = 0
		payment_line_total = 0
		
		print(" ********** Payments ***********")

		for payment in payment_list:
			series = ''

			invoice_id = self.env['account.invoice'].search([('number', '=', payment.communication)], limit=1)

			if payment.state == 'posted':
				payment_lines.append({
			        							
			        					'pa': invoice_id.pa_ref, #+" - "+ str(payment.id) +" "+ str(payment.state)
			        					'customer':payment.partner_id.name,
			        					'or': payment.name,
			        					'date':self.crop_date(payment.payment_date),
			        					'amount':"{:,.2f}".format(float(payment.amount)),

			        					#'series':,
			        				})

				if payment_index != 25:
					payment_index = payment_index + 1
					payment_line_total = payment_line_total + payment.amount

				else:
					payment_lines_complete.append({'lines':payment_lines, 'total': "{:,.2f}".format(float(payment_line_total)),})
					payment_lines = []
					payment_index = 0
					payment_line_total = 0

		
		if len(payment_lines) != 0:
			payment_lines_complete.append({'lines':payment_lines, 'total': "{:,.2f}".format(float(payment_line_total)),})

		data = {'data':{
							'agent': self.agent.name,
							'position': agent_commission_id.position_id.name,
							'commissions':commissions_lines_complete,
							'payments':payment_lines_complete,
							'invoices': invoice_lines_complete,
							'summary':comm_summary_lines_complete,
							'all_comm':overall_comm,
							'all_comm_gross':overall_comm_gross,
							'all_comm_withh':overall_comm_withh,
						}}

		return self.env['report'].get_action(self, 'brdc_account.all_payments_template', data=data)



	carrier_xlsx_document_name = fields.Char(string="File Name")
	carrier_xlsx_document = fields.Binary(string="Document")

	@api.multi
	def generate_excel(self):
		file_name = 'temp'
		workbook = xlsxwriter.Workbook(file_name, {'in_memory': True})
		worksheet = workbook.add_worksheet()
		row = 0
		col = 0
		header = ['name','age','address']

		for e in header:
			worksheet.write(row, col, e)
			col += 1

		# row += 1
		# for vals in self.carrier_line_ids:
		# 	worksheet.write(row, 0, vals.reference)

		workbook.close()
		with open(file_name, "rb") as file:
			file_base64 = base64.b64encode(file.read())
		
		self.carrier_xlsx_document_name = 'test.xlsx'
		self.write({'carrier_xlsx_document': file_base64, })

	@api.model
	def crop_date(self, dateInput):

		str_date = str(dateInput).split(' ')
		date_of_request = datetime.strptime(str_date[0], '%Y-%m-%d')#%I:%M%
		return date_of_request.strftime('%b %d, %Y')

