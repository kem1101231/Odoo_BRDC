from odoo import api, fields, models
from dateutil.relativedelta import relativedelta
from datetime import date, datetime, timedelta
import numpy as np


class CollectionLine(models.TransientModel):
    _inherit = 'collection.line'

    product_id = fields.Many2one('product.product', 'Product')


class CollectorAging(models.TransientModel):
    _inherit = 'collector.aging'

    @api.multi 
    def compute_general_aging(self):
        print("--------------------------------")
        print("doing Agings")
        print(self.type)
        active_ai = None
        if self.type == 'general':
            # self._cr.execute("""select a.id
            #             from account_invoice as a
            #             join account_invoice_line as b
            #             on a.id = b.invoice_id
            #             join res_partner as c
            #             on c.id = a.partner_id
            #             where a.state in ('open','terminate')
            #             and a.purchase_term = 'install' and a.month_due > 2.99999999999
            #             order by a.month_due""")
            
            # res = self._cr.fetchall()
            
            # invoice_line = self.env['account.invoice.line'].search([('invoice_id.id','=')])
            # account_invoice = self.env['account.invoice'].search()
            
            # >> active_ai = self.env['account.invoice'].search([('id', 'in', res),('date_invoice','<=',self.date)])
            
            # active_ai = self.evn['account.invoice'].search([('state','=','open')])
            # active_ai = self.env['account.invoice'].search([('state', 'in', ['open', 'terminate']),
            #                                                 ('purchase_term', '=', 'install'),
            #                                                 ]
            #                                                )
            active_ai = self.env['account.invoice'].search([('state','in',['open','terminate','pre_terminate','pre_active','for_reactive']),('purchase_term','=','install')])

        elif self.type == 'collection':
            # self._cr.execute("""select a.id
            #             from account_invoice as a  
            #             join account_invoice_line as b
            #             on a.id = b.invoice_id
            #             join res_partner as c
            #             on c.id = a.partner_id
            #             where a.state = 'open' 
            #             and a.purchase_term = 'install' 
            #             and a.month_due > 2.99999999999 
            #             and c.barangay_id_b in (%s)
            #             order by a.month_due""" % str(self.area_id.ids)[1:-1])
            # res = self._cr.fetchall()
            # active_ai = self.env['account.invoice'].search([('id', 'in', res),('date_invoice','<=',self.date)])

            user_id = self.env['res.users'].search([('partner_id','=', self.collector_id.id)])
            active_ai = self.env['account.invoice'].search([('state','in',['open','terminate','pre_terminate','pre_active','for_reactive']),('purchase_term','=','install'),('pa_ref_collector','=',user_id.id)])

        elif self.type == 'product':
            self._cr.execute("""select a.id
                        from account_invoice as a  
                        join account_invoice_line as b
                        on a.id = b.invoice_id
                        join res_partner as c
                        on c.id = a.partner_id
                        join payment_config as d
                        on d.id = a.product_type
                        where a.state in ('open','terminate') 
                        and a.purchase_term = 'install' 
                        and a.month_due > 2.99999999999
                        order by a.month_due""")
            
            res = self._cr.fetchall()
            active_ai = self.env['account.invoice'].search([('id', 'in', res),('date_invoice','<=',self.date),('product_type','=',self.env['payment.config'].search([('is_parent', '=', 1),('id','=',self.product_type.id)])[0].id)])
            # active_ai = self.env['account.invoice'].search([('state', 'in', ['open', 'terminate']),
            #                                                 ('purchase_term', '=', 'install'),
            #                                                 ('product_type', '=', self.product_type.id)
            #                                                 ]
            #                                                )

        if active_ai:
            aging = self.env['collection.line'].search([])
            aging.unlink()
            dute_date = None
            total_paid = 0.0
            invoice_id = None
            monthly_payment = 0.0
            total_due = 0.0

            index_cater = 0

            for rec in active_ai:
                print(" +++++++++++++++++++++++++++++ Catering  Line ")
                invoice_id = rec.id
                # due_date = datetime.strptime(rec.month_to_pay, '%Y-%m-%d')
                dates = []
                # dute_date = rec.month_to_pay
                total_paid = rec.total_paid
                total_due = rec.monthly_due
                monthly_payment = rec.monthly_payment
                

                for_30 = 0
                for_60 = 0
                for_90 = 0
                for_91 = 0

                payment_sched = self.env['invoice.installment.line'].search([('account_invoice_id','=', rec.id), ('is_paid','=',False)])
                
                for line in payment_sched:
                    dfp = datetime.strptime(line.date_for_payment, "%Y-%m-%d")
                    diff_in_days = abs((datetime.today() - dfp).days)
                    
                    if not datetime(int(date.today().year), int(date.today().month),1) < dfp:

                        if diff_in_days <= 30:
                            for_30 = for_30 + line.amount_to_pay
                        if diff_in_days <= 60 and diff_in_days >= 31:
                            for_60 = for_60 + line.amount_to_pay
                        if diff_in_days <= 90 and diff_in_days >= 61:
                            for_90 = for_90 + line.amount_to_pay
                        if diff_in_days >= 91:
                            for_91 = for_91 + line.amount_to_pay
                

                # quotient = total_due / monthly_payment
                # due_current = 0.0
                # due_current_date = None
                # due_30 = 0.0
                # due_30_date = None
                # due_60 = 0.0
                # due_60_date = None
                # due_90 = 0.0
                # due_90_date = None
                # due_over_90 = 0.0
                # due_over_90_date = None
                # for q in range(0, int(quotient)):
                #     res = due_date - relativedelta(months=q)#past due date e.g., july 4 > june 4 > may 4
                #     dates.append(res)

                # def selection_sort(x):
                #     for i in range(len(x)):
                #         swap = i + np.argmin(x[i:])
                #         (x[i], x[swap]) = (x[swap], x[i])
                #     return x
                

                # if dates:
                #     dates = selection_sort(dates)
                #     if quotient < 2:
                #         print "has current"
                #         due_current = monthly_payment if total_due >= 1 else 0.0
                #         due_current_date = dates[-1]
                #     elif quotient < 3:
                #         print "has 30"
                #         due_current = monthly_payment if total_due >= 1 else 0.0
                #         due_current_date = dates[-1]
                #         due_30 = due_current
                #         due_30_date = dates[-2]
                #     elif quotient < 4:
                #         print "has 60"
                #         due_current = monthly_payment if total_due >= 1 else 0.0
                #         due_current_date = dates[-1]
                #         due_30 = due_current
                #         due_30_date = dates[-2]
                #         due_60 = due_current
                #         due_60_date = dates[-3]
                #     elif quotient < 5:
                #         print "has 90"
                #         due_current = monthly_payment if total_due >= 1 else 0.0
                #         due_current_date = dates[-1]
                #         due_30 = due_current
                #         due_30_date = dates[-2]
                #         due_60 = due_current
                #         due_60_date = dates[-3]
                #         due_90 = due_current
                #         due_90_date = dates[-4]
                #     elif quotient >= 5:
                #         print "over 90"
                #         due_current = monthly_payment if total_due >= 1 else 0.0
                #         due_current_date = dates[-1]
                #         due_30 = due_current
                #         due_30_date = dates[-2]
                #         due_60 = due_current
                #         due_60_date = dates[-3]
                #         due_90 = due_current
                #         due_90_date = dates[-4]
                #         due_over_90 = total_due - (due_current * 4)
                #         due_over_90_date = dates[0]
                #     else:
                #         print "no due"

                aging.create({
                        'invoice_id': rec.id,
                        'partner_id': rec.partner_id.id,
                        'doc_date': rec.date_invoice,
                        'amount_total': rec.amount_total,
                        'paid_total': total_paid,
                        'balance': rec.amount_total - total_paid,
                        'due_total': for_30 + for_60 + for_90 + for_91 + rec.current_due,
                        'due_current': rec.current_due,
                        #'due_current_date': due_current_date,
                        'due_30': for_30,
                        # 'due_30_date': due_30_date,
                        'due_60': for_60,
                        # 'due_60_date': due_60_date,
                        'due_90': for_90,
                        # 'due_90_date': due_90_date,
                        'due_over_90': for_91,
                        # 'due_over_90_date': due_over_90_date,
                        'days_passed': 0.0,
                        'collection_aging_id': self.id
                    })
                index_cater += 1

        else:
            aging = self.env['collection.line'].search([])
            aging.unlink()



    # def get_invoice_info(self, inv_id):
    #     for collect in self:
            
    #         out_data = {}
            
    #         invoice_info = self.env['account.invoice'].search([('id','=', inv_id)], limit=1)

    #         out_data['invoice_pa'] = invoice_info.pa_ref
    #         out_data['partner_name'] = invoice_info.partner_id.name 
    #         out_data['partner_address'] = invoice_info.partner_id.street # invoice_info.partner_id.barangay_id.name if invoice_info.partner_id.barangay_id.name else '' +", "+ invoice_info.partner_id.municipality_id.name if invoice_info.partner_id.municipality_id.name else '' +", "+invoice_info.partner_id.province_id.name if invoice_info.partner_id.province_id.name else ''
    #         out_data['partner_contact'] = str(invoice_info.partner_id.mobile) if invoice_info.partner_id.mobile else 'Not Indicated'
    #         out_data['status'] = 'Active'
    #         out_data['collector'] = invoice_info.sudo().pa_ref_collector.name
    #         out_data['product'] = invoice_info.product_type.name 

    #         invoice_line = invoice_info.invoice_line_ids[0]

    #         out_data['area_class'] = invoice_line.product_id.categ_id.name
    #         out_data['area'] = invoice_line.product_id.area_number.name
    #         out_data['block'] = invoice_line.lot_id.block_number 
    #         out_data['lot'] =  invoice_line.lot_id.lot_number
    #         out_data['term'] = invoice_info.new_payment_term_id.no_months 

    #         date_range = datetime(int(date.today().year), int(date.today().month), calendar.monthrange(int(date.today().year),int(date.today().month))[1])
    #         for_30 = 0
    #         for_60 = 0
    #         for_90 = 0
    #         for_91 = 0

    #         payment_sched = self.env['invoice.installment.line'].search([('account_invoice_id','=', invoice_info.id), ('date_for_payment','<=', date_range),('is_paid','=',False)])
            
    #         for line in payment_sched:
    #             dfp = datetime.strptime(line.date_for_payment, "%Y-%m-%d")
    #             diff_in_days = abs((datetime.today() - dfp).days)
                
    #             if not datetime(int(date.today().year), int(date.today().month),1) < dfp < date_range:

    #                 if diff_in_days <= 30:
    #                     for_30 = for_30 + line.amount_to_pay
    #                 if diff_in_days <= 60 and diff_in_days >= 31:
    #                     for_60 = for_60 + line.amount_to_pay
    #                 if diff_in_days <= 90 and diff_in_days >= 61:
    #                     for_90 = for_90 + line.amount_to_pay
    #                 if diff_in_days >= 91:
    #                     for_91 = for_91 + line.amount_to_pay

    #         out_data['net_con'] = invoice_info.amount_total,
    #         out_data['down'] = invoice_info.s_dp if invoice_info.s_dp != 0 else '-'
    #         out_data['month'] = invoice_info.monthly_payment
    #         out_data['date_invoice'] = invoice_info.date_invoice
    #         out_data['balance'] = invoice_info.residual
    #         out_data['due'] = datetime.strptime(invoice_info.month_to_pay, '%Y-%m-%d').day if invoice_info.month_to_pay else '-'
    #         out_data['total_due'] = for_30 + for_60 + for_90 + for_91 + invoice_info.current_due
    #         out_data['current_due'] = invoice_info.current_due
    #         out_data['1_30'] = for_30 if for_30 != 0 else '-'
    #         out_data['31_60'] = for_60 if for_60 != 0 else '-'
    #         out_data['61_90'] = for_90 if for_90 != 0 else '-'
    #         out_data['91'] =  for_91 if for_91 != 0 else '-'

    #         return out_data


    def print_aging(self):
    #     data = {}

        # return self.print_report(data)

        for trans in self:
            aging_line = trans.collection_line_ids

            data_out = {
                        'lines':[],
                        'type': 'gen' if trans.type != 'collection' else 'collect',
                        'date_range': datetime.strptime(trans.date, '%Y-%m-%d %H:%M:%S').strftime('%b %d, %Y'),
                        'collector': '',
                        'print_date':(datetime.strptime(fields.Datetime.now(), '%Y-%m-%d %H:%M:%S') + timedelta(hours=8)).strftime('%a %b %d, %Y - %H:%M'),
            }
         
            for item in trans.collection_line_ids:
                line_to_add = {

                                
                                'collector':item.invoice_id.pa_ref_collector.name,
                                'pa':item.invoice_id.pa_ref,
                                'client':item.invoice_id.partner_id.name,
                                'date': datetime.strptime(item.invoice_id.date_invoice, '%Y-%m-%d').strftime('%m/%d/%Y'),
                                'product':item.invoice_id.product_type.name,
                                'product_des':item.invoice_id.invoice_line_ids[0].product_id.name,
                                'area':item.invoice_id.invoice_line_ids[0].product_id.area_number.name,
                                'area_class':item.invoice_id.invoice_line_ids[0].product_id.categ_id.name,
                                'lot':item.invoice_id.invoice_line_ids[0].lot_id.lot_number,
                                'block':item.invoice_id.invoice_line_ids[0].lot_id.block_number,
                                'contract_price':item.invoice_id.amount_total,
                                'payment':item.invoice_id.total_paid,
                                'balance':item.invoice_id.residual,
                                'total_due':item.due_30 + item.due_60 + item.due_90 + item.due_over_90 + item.due_current,
                                'current_due':item.due_current,
                                '30':item.due_30,
                                '60':item.due_60,
                                '90':item.due_90,
                                '91':item.due_over_90,
                            }

                data_out['lines'].append(line_to_add)
                data_out['collector'] = item.invoice_id.pa_ref_collector.name
              

            data_out['lines'] = self.sort_result(data_out['lines'], 'client')
            data_out['lines'] = self.number_lines(data_out['lines'])
            data_out['lines'] = self.cut_to_pages(data_out['lines'], 23, ['balance','total_due','current_due','30','60','90','91'])

            return self.env['report'].get_action(self, 'brdc_account.aging_report_report_template', data=data_out)

    def number_lines(self, inputList):
        index = 1
        data_out = inputList

        for idx, item in enumerate(inputList):
            data_out[idx]['no'] = index
            index += 1

        return data_out

    def cut_to_pages(self, inputData, lines_per_pages, total_reference):
        
        index = 0
        
        new_data = []
        totals = {}

        pages = []

        for x in inputData:

            if index == 0:
                new_data = []
                totals = {}
                for ref in total_reference:
                    totals[ref] = 0

            new_data.append(x)
            for line in total_reference:
                totals[line] += x[line]
            
            index += 1

            if index == lines_per_pages or x == inputData[len(inputData)-1]:
                pages.append({
                                'page':new_data,
                                'totals':totals,
                                'page_num':len(pages)+1

                    })

                index = 0
        print("++++++++++++++++++++++++++++++++++++++++++++++")
        print(len(pages))

        return pages
    
    def sort_result(self, inputList, reference):
        # data = [{'1':7,'2':8,'3':9,},{'1':1,'2':2,'3':3,},{'1':4,'2':5,'3':6,}]
        inputList.sort(key=lambda tup: tup[reference])  
        return inputList
class ReportGeneralAgingReport(models.AbstractModel):
    _name = 'report.brdc_account.aging_report_report_template'
    
    @api.model
    def render_html(self, docids, data):
        
        docargs = {
            'doc_ids': self.ids,
            'doc_model': None,
            'docs': {'1':'one','2':'two','3':'three','4':'four','5':'five'},
            #'time': time,
            'dataInput': data,
        }

        return self.env['report'].render('brdc_account.aging_report_report_template', docargs)



class CollectorAgingMM(models.TransientModel):
    _inherit = 'collector.aging.mm'

    @api.multi
    def generate_mm_aging(self):
        service_ids = None
        if self.type == 'general':
            service_ids = self.env['service.order'].search([('state', '=', 'ready')])
            amort = 0.0

        elif self.type == 'collection':
            print self.area_id.ids
            partner_ids = self.env['res.partner'].search([('active', '=', True),
                                                          ('barangay_id_b', 'in', self.area_id.ids)
                                                          ])
            service_ids = self.env['service.order'].search([('state', '=', 'ready'),
                                                            ('partner_id', 'in',  partner_ids.ids)
                                                            ])
        elif self.type == 'product':
            pass

        aging = self.env['collection.line'].search([])
        aging.unlink()
        if service_ids:
            for rec in service_ids.filtered(lambda r: r.total_due > 0.0):
                # sql = """select id, monthly_amort, total_due, month_to_pay from service_order where id = '%s'""" % rec.id
                # self._cr.execute(sql)
                # res = self._cr.fetchall()
                #
                # print res
                amort = rec.monthly_amort
                due = rec.total_due
                quotient = due / amort

                due_date = datetime.strptime(rec.month_to_pay, '%Y-%m-%d')
                due_current = 0.0
                due_30 = 0.0
                due_60 = 0.0
                due_90 = 0.0
                due_over_90 = 0.0
                due_current_date = due_30_date = due_60_date = due_90_date = due_over_90_date = None
                dates = []

                for q in range(0, int(quotient)):
                    res = due_date - relativedelta(months=q)
                    dates.append(res)
                print dates

                due_current = amort if rec.due_count >= 1 else 0.0
                due_current_date = dates[0]
                if quotient < 2:
                    due_current = amort if rec.due_count >= 1 else 0.0
                    due_current_date = dates[0]
                elif quotient < 3:
                    due_30_date = dates[1]
                    due_30 = due_current
                elif quotient < 4:
                    due_30_date = dates[1]
                    due_60_date = dates[2]
                    due_30 = due_60 = due_current
                elif quotient < 5:
                    due_30_date = dates[1]
                    due_60_date = dates[2]
                    due_90_date = dates[3]
                    due_30 = due_60 = due_90 = due_current
                elif quotient >= 5:
                    due_30_date = dates[1]
                    due_60_date = dates[2]
                    due_90_date = dates[3]
                    due_over_90_date = dates[-1]
                    due_30 = due_60 = due_90 = due_current
                    due_over_90 = due - (due_current * 4)
                else:
                    pass

                aging.create({
                    'service_id': rec.id,
                    'product_id': rec.product_id.id,
                    'partner_id': rec.partner_id.id,
                    'doc_date': rec.order_date,
                    'amount_total': rec.amount_total,
                    'paid_total': rec.total_paid,
                    'balance': rec.amount_total - rec.total_paid,
                    'due_total': due,
                    'due_current': due_current,
                    'due_current_date': due_current_date,
                    'due_30': due_30,
                    'due_30_date': due_30_date,
                    'due_60': due_60,
                    'due_60_date': due_60_date,
                    'due_90': due_90,
                    'due_90_date': due_90_date,
                    'due_over_90': due_over_90,
                    'due_over_90_date': due_over_90_date,
                    'days_passed': 0.0,
                    'collection_aging_mm_id': self.id
                })
