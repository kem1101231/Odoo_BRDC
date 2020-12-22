from odoo import api, fields, models
from datetime import datetime, date, timedelta
import calendar


class SalesReportLine(models.TransientModel):
    _name = 'accounting.sales.report.line'
    #_order = 'partner_id.name asc'

    report_id = fields.Many2one('accounting.sales.report')
    invoice_id = fields.Many2one('account.invoice', 'Invoice')
    invoice_status = fields.Char('Status')
    partner_id = fields.Many2one('res.partner', 'Customer')
    partner_address = fields.Text(related="partner_id.street")
    move_id = fields.Many2one('account.move', 'Journal Entry')
    date_invoice = fields.Date(related='invoice_id.date_invoice')
    product = fields.Many2one('product.product')
    purchase_term = fields.Selection([('cash', 'Cash'), ('install', 'Install')])

    @api.depends('invoice_id')
    def _get_sale_order(self):
        for line in self:
            so_id = self.env['sale.order'].search([('pa_ref','=',line.invoice_id.pa_ref)], limit=1)
            line.update({
                            'sale_order':so_id.id,
                            })
            line.sale_order = so_id.id

    sale_order = fields.Many2one(comodel_name="sale.order",string="Sales Order", compute="_get_sale_order")

    @api.depends('invoice_id')
    def _get_agents(self):
        for line in self:
            agent_id = line.sale_order.agent_id
            unit_man = line.sale_order.um_id
            agency_man = line.sale_order.am_id

            line.sale_agent_id = agent_id.id
            line.unit_man = unit_man.id
            line.agency_man = agency_man.id

    sale_agent_id = fields.Many2one(comodel_name="res.partner", compute="_get_agents")
    unit_man = fields.Many2one(comodel_name="res.partner", compute="_get_agents")
    agency_man = fields.Many2one(comodel_name="res.partner", compute="_get_agents")

    @api.depends('invoice_id')
    def _get_location_info(self):
        for line in self:
            invoice_line = line.invoice_id.invoice_line_ids[0]
            
            line.area_class = str(invoice_line.product_id.categ_id.name)
            line.area_number = str(invoice_line.product_id.area_number.name)
            line.block_number = str(invoice_line.lot_id.block_number) 
            line.lot_number = str(invoice_line.lot_id.lot_number)


    area_class = fields.Char(compute="_get_location_info")
    area_number = fields.Char(compute="_get_location_info")
    block_number = fields.Char(compute="_get_location_info")
    lot_number = fields.Char(compute="_get_location_info")

class ProductReportLine(models.TransientModel):
    _name = 'product.report.line'

    report_id = fields.Many2one('accounting.sales.report')
    product = fields.Many2one('product.product')
    purchase_term = fields.Selection([('cash', 'Cash'), ('install', 'Install')])


class SalesReport(models.TransientModel):
    _name = 'accounting.sales.report'

    type = fields.Selection(string="", selection=[('general', 'General Sales` Report'), ('month', 'Month Sales Report'), ], required=True, default='month')
    statistics = fields.Boolean(string="Include Statistics")


    @api.multi
    def default_month(self):
        now = datetime.now()
        return int(now.month)
    
    current_month = fields.Selection([(1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
                          (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
                          (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'), ],
                          string='Month', default=default_month)
    
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

    for_year = fields.Selection(selection='year_selection', string="Report Year")

    invoice_ids = fields.Many2many('account.invoice')
    move_ids = fields.Many2many('account.move')
    install_line_ids = fields.One2many(comodel_name="accounting.sales.report.line", inverse_name="report_id", string="", required=False, domain=[('purchase_term', '=', 'install')])
    cash_line_ids = fields.One2many(comodel_name="accounting.sales.report.line", inverse_name="report_id", string="", required=False, domain=[('purchase_term', '=', 'cash')])
    product_line_ids = fields.One2many(comodel_name="product.report.line", inverse_name="report_id", string="", required=False)
    install_product_class = fields.Many2many('product.product')
    cash_product_class = fields.Many2many('product.product')
    date_range = fields.Char()


    total_lot_price = fields.Float()
    total_pcf_price = fields.Float()
    total_vat_price = fields.Float()
    total_contract_price = fields.Float()
    total_discount_price = fields.Float()
    total_amort_price = fields.Float()

    # invoice_status = fields.Selection([('open', 'Ongoing Accounts'), ('paid', 'Paid Accounts')])

    @api.multi
    def generate(self):
        invoices = self.env['account.invoice'].search([('state', 'in', ['open', 'paid'])])
        month = self.current_month
        year = int(self.for_year)
        start_date = "%s-%s-1" % (int(year), int(month))
        date_ = calendar.monthrange(int(year), int(month))[1]
        end_date = "%s-%s-%s" % (int(year), int(month), int(date_))
        d1 = datetime.strptime(start_date, '%Y-%m-%d')
        d2 = datetime.strptime(end_date, '%Y-%m-%d')
        product_info = []
        line = self.env['accounting.sales.report.line'].search([])
        product_line = self.env['product.report.line'].search([])
        line.unlink()
        product_line.unlink()
        self.date_range = '%s to %s' % (d1.strftime('%B/%d/%Y'), d2.strftime('%B/%d/%Y'))
        if self.type == 'month':
            ids = invoices.filtered(lambda rec: (rec.date_invoice >= d1.strftime('%Y-%m-%d') and (
                        rec.date_invoice <= d2.strftime('%Y-%m-%d')))).sorted(key=lambda x: x.date_invoice and x.state)
        else:
            ids = invoices.sorted(key=lambda x: x.date_invoice and x.state)

        journal_ids = []
        for res in self.invoice_ids:
            journal_ids.append(res.move_id.id)

        for invoice in ids:
            invoice_line = self.env['account.invoice.line'].search([('invoice_id', '=', invoice.id)])
            line_ = line.create({
                'report_id': self.id,
                'invoice_id': invoice.id,
                'partner_id': invoice.partner_id.id,
                'move_id': invoice.custom_account_id.id,
                'product': invoice_line.product_id.id,
                'invoice_status': invoice.state,
                'purchase_term': invoice.purchase_term,
            })
            product_info.append({
                'id': line_.product.id,
                'purchase_term': line_.purchase_term,
            })
        s = []
        for product in product_info:
            if {product['id'], product['purchase_term']} not in s:
                s.append({product['id'], product['purchase_term']})
                product_line.create({
                    'report_id': self.id,
                    'product': product['id'],
                    'purchase_term': product['purchase_term'],
                })

        return True

    @api.multi
    def print_(self):
        for trans in self:
            print("_________________________________")
            print(trans.install_line_ids)
            data_out = {
                            'date_range':trans.date_range,
                            'install_line':[],
                            'install_total_sales':{
                                                    'count':0,
                                                    'total_lot':0,
                                                    'total_pcf':0,
                                                    'total_vat':0,
                                                    'total_contract':0,
                                                    'total_discount':0,
                                                    'total_monthly':0,
                                            },
                            'install_products':[],
                            'cash_line':[],
                            'cash_total_sale':{
                                                'count':0,
                                                'total_lot':0,
                                                'total_pcf':0,
                                                'total_vat':0,
                                                'total_contract':0,
                                                'total_discount':0,
                                                'total_monthly':0,
                                            },
                            'cash_products':[],
                            'total_sale':{
                                                'count':0,
                                                'total_lot':0,
                                                'total_pcf':0,
                                                'total_vat':0,
                                                'total_contract':0,
                                                'total_discount':0,
                                                'total_monthly':0,
                                            },
                            # 'type':'gen' if trans.type != 'collection' else 'collect',
                            'stat':trans.statistics,
                            'print_date':(datetime.strptime(fields.Datetime.now(), '%Y-%m-%d %H:%M:%S') + timedelta(hours=8)).strftime('%a %b %d, %Y - %H:%M'),

                        }
            index_i = 0
            number_i = 1
            print("()()()()()()()()()()()()()()")
            print(len(trans.install_line_ids))

            page_number = 1

            install_products = []
            install_products_ref = {}


            for line in trans.install_line_ids:
                print("___________________________")
                print("executing line")
                to_install_line = {
                                    'num':number_i,
                                    'payment': 'Installment',
                                    'start_payment':line.date_invoice,
                                    'pa_number':line.invoice_id.pa_ref,
                                    'or_number':'---',
                                    'client':line.partner_id.name,
                                    'address':line.partner_address,
                                    's_agent':line.sale_agent_id.name,
                                    'a_agent':line.agency_man.name,
                                    'u_agent':line.unit_man.name,
                                    'product':line.invoice_id.product_type.name,
                                    'area_class':line.area_class,
                                    'area_no':line.area_number,
                                    'block_no':line.block_number,
                                    'lot_no':line.lot_number,
                                    'lot_price':"{:,.2f}".format(float(line.invoice_id.lot_price)),
                                    'pcf':"{:,.2f}".format(float(line.invoice_id.pcf)),
                                    'vat':"{:,.2f}".format(float(line.invoice_id.vat)),
                                    'contract':"{:,.2f}".format(float(line.invoice_id.amount_total)),
                                    'discount':"{:,.2f}".format(float(line.invoice_id.inv_total_discount_amount)),
                                    'term':line.invoice_id.new_payment_term_id.no_months,
                                    'monthly':"{:,.2f}".format(float(line.invoice_id.monthly_payment)),
                                }
                
                if str(line.product.name) not in install_products_ref:
                    install_products_ref[str(line.product.name)] = len(install_products)
                    install_products.append({
                                        'product_type':line.invoice_id.product_type.name,
                                        'area_no':line.area_number,
                                        'area_class':line.area_class,
                                        'count':1,
                                        'lot':line.invoice_id.lot_price,
                                        'pcf':line.invoice_id.pcf,
                                        'vat':line.invoice_id.vat,
                                        'contract':line.invoice_id.amount_total,
                                        'discount':line.invoice_id.inv_total_discount_amount,
                                        'monthly':line.invoice_id.monthly_payment,
                    })
                
                else:
                    install_products_ref_index = install_products_ref[str(line.product.name)]
                    line_to_update = install_products[install_products_ref_index]
                    line_to_update['count'] += 1
                    line_to_update['lot'] += line.invoice_id.lot_price
                    line_to_update['pcf'] += line.invoice_id.pcf
                    line_to_update['vat'] += line.invoice_id.vat
                    line_to_update['contract'] += line.invoice_id.amount_total
                    line_to_update['discount'] += line.invoice_id.inv_total_discount_amount
                    line_to_update['monthly'] += line.invoice_id.monthly_payment


                print(index_i)
                if index_i == 0:
                        data_out['install_line'].append({
                                                            'number':page_number,
                                                            'page_lines':[],
                                                            'total_lot':0,
                                                            'total_pcf':0,
                                                            'total_vat':0,
                                                            'total_contract':0,
                                                            'total_discount':0,
                                                            'total_monthly':0,
                                                        })

                print(len(data_out['install_line']))
                # page['lines'].append()

                # data_out['']
                current_line = data_out['install_line'][len(data_out['install_line'])-1]
                # print(len(data_out['install_line'][len(data_out['install_line'])-1]))
                # print(len(data_out['install_line']))
                current_line['page_lines'].append(to_install_line)
                current_line['total_lot'] += float(to_install_line['lot_price'].replace(',',''))
                current_line['total_pcf'] += float(to_install_line['pcf'].replace(',',''))
                current_line['total_vat'] += float(to_install_line['vat'].replace(',',''))
                current_line['total_contract'] += float(to_install_line['contract'].replace(',',''))
                current_line['total_discount'] += float(to_install_line['discount'].replace(',',''))
                current_line['total_monthly'] += float(to_install_line['monthly'].replace(',',''))


                data_out['install_total_sales']['total_lot'] += float(to_install_line['lot_price'].replace(',',''))
                data_out['install_total_sales']['total_pcf'] += float(to_install_line['pcf'].replace(',',''))
                data_out['install_total_sales']['total_vat'] += float(to_install_line['vat'].replace(',',''))
                data_out['install_total_sales']['total_contract'] += float(to_install_line['contract'].replace(',',''))
                data_out['install_total_sales']['total_discount'] += float(to_install_line['discount'].replace(',',''))
                data_out['install_total_sales']['total_monthly'] += float(to_install_line['monthly'].replace(',',''))
                
                data_out['total_sale']['total_lot'] += float(to_install_line['lot_price'].replace(',',''))
                data_out['total_sale']['total_pcf'] += float(to_install_line['pcf'].replace(',',''))
                data_out['total_sale']['total_vat'] += float(to_install_line['vat'].replace(',',''))
                data_out['total_sale']['total_contract'] += float(to_install_line['contract'].replace(',',''))
                data_out['total_sale']['total_discount'] += float(to_install_line['discount'].replace(',',''))
                data_out['total_sale']['total_monthly'] += float(to_install_line['monthly'].replace(',',''))
                index_i += 1
                
                print(index_i)

                if index_i == 20:
                    print("resetting index_i")
                    index_i = 0
                    page_number += 1

                number_i += 1
                #
            data_out['install_total_sales']['count'] = number_i - 1
            data_out['total_sale']['count'] += number_i - 1
            data_out['install_products'] = install_products    
            
            page_number += 1
            index_c = 0
            number_c = 1
            
            cash_products = []
            cash_products_ref = {}
            
            for line in trans.cash_line_ids:
                to_cash_line = {
                                    'num':number_c,
                                    'payment': 'Cash',
                                    'start_payment':line.date_invoice,
                                    'pa_number':line.invoice_id.pa_ref,
                                    'or_number':'---',
                                    'client':line.partner_id.name,
                                    'address':line.partner_address,
                                    's_agent':line.sale_agent_id.name,
                                    'a_agent':line.agency_man.name,
                                    'u_agent':line.unit_man.name,
                                    'product':line.invoice_id.product_type.name,
                                    'area_class':line.area_class,
                                    'area_no':line.area_number,
                                    'block_no':line.block_number,
                                    'lot_no':line.lot_number,
                                    'lot_price':"{:,.2f}".format(float(line.invoice_id.lot_price)),
                                    'pcf':"{:,.2f}".format(float(line.invoice_id.pcf)),
                                    'vat':"{:,.2f}".format(float(line.invoice_id.vat)),
                                    'contract':"{:,.2f}".format(float(line.invoice_id.amount_total)),
                                    'discount':"{:,.2f}".format(float(line.invoice_id.inv_total_discount_amount)),
                                    'term':line.invoice_id.new_payment_term_id.no_months,
                                    'monthly':"{:,.2f}".format(float(line.invoice_id.monthly_payment)),
                                }
                
                if str(line.product.name) not in cash_products_ref:
                    cash_products_ref[str(line.product.name)] = len(cash_products)
                    cash_products.append({
                                        'product_type':line.invoice_id.product_type.name,
                                        'area_no':line.area_number,
                                        'area_class':line.area_class,
                                        'count':1,
                                        'lot':line.invoice_id.lot_price,
                                        'pcf':line.invoice_id.pcf,
                                        'vat':line.invoice_id.vat,
                                        'contract':line.invoice_id.amount_total,
                                        'discount':line.invoice_id.inv_total_discount_amount,
                                        'monthly':line.invoice_id.monthly_payment,
                    })
                
                else:
                    cash_products_ref_index = cash_products_ref[str(line.product.name)]
                    line_to_update = cash_products[cash_products_ref_index]
                    line_to_update['count'] += 1
                    line_to_update['lot'] += line.invoice_id.lot_price
                    line_to_update['pcf'] += line.invoice_id.pcf
                    line_to_update['vat'] += line.invoice_id.vat
                    line_to_update['contract'] += line.invoice_id.amount_total
                    line_to_update['discount'] += line.invoice_id.inv_total_discount_amount
                    line_to_update['monthly'] += line.invoice_id.monthly_payment
                
                # if index_c == 0:
                #         data_out['cash_line'].append([])

                
                # # data_out['']
                # index_c += 1

                # if index_c == 20:
                #     index_c = 0

                # number_c += 1
                
                if index_c == 0:
                        data_out['cash_line'].append({
                                                            'number':page_number,
                                                            'page_lines':[],
                                                            'total_lot':0,
                                                            'total_pcf':0,
                                                            'total_vat':0,
                                                            'total_contract':0,
                                                            'total_discount':0,
                                                            'total_monthly':0,
                                                        })

                # print(len(data_out['install_line']))
                # page['lines'].append()

                # data_out['']
                current_line = data_out['cash_line'][len(data_out['cash_line'])-1]
                # print(len(data_out['install_line'][len(data_out['install_line'])-1]))
                # print(len(data_out['install_line']))
                current_line['page_lines'].append(to_cash_line)
                current_line['total_lot'] += float(to_cash_line['lot_price'].replace(',',''))
                current_line['total_pcf'] += float(to_cash_line['pcf'].replace(',',''))
                current_line['total_vat'] += float(to_cash_line['vat'].replace(',',''))
                current_line['total_contract'] += float(to_cash_line['contract'].replace(',',''))
                current_line['total_discount'] += float(to_cash_line['discount'].replace(',',''))
                current_line['total_monthly'] += float(to_cash_line['monthly'].replace(',',''))
                
                data_out['cash_total_sale']['total_lot'] += float(to_cash_line['lot_price'].replace(',',''))
                data_out['cash_total_sale']['total_pcf'] += float(to_cash_line['pcf'].replace(',',''))
                data_out['cash_total_sale']['total_vat'] += float(to_cash_line['vat'].replace(',',''))
                data_out['cash_total_sale']['total_contract'] += float(to_cash_line['contract'].replace(',',''))
                data_out['cash_total_sale']['total_discount'] += float(to_cash_line['discount'].replace(',',''))
                data_out['cash_total_sale']['total_monthly'] += float(to_cash_line['monthly'].replace(',',''))
                
                data_out['total_sale']['total_lot'] += float(to_cash_line['lot_price'].replace(',',''))
                data_out['total_sale']['total_pcf'] += float(to_cash_line['pcf'].replace(',',''))
                data_out['total_sale']['total_vat'] += float(to_cash_line['vat'].replace(',',''))
                data_out['total_sale']['total_contract'] += float(to_cash_line['contract'].replace(',',''))
                data_out['total_sale']['total_discount'] += float(to_cash_line['discount'].replace(',',''))
                data_out['total_sale']['total_monthly'] += float(to_cash_line['monthly'].replace(',',''))
                
                index_c += 1
                
                #print(index_i)

                if index_c == 20:
                    print("resetting index_c")
                    index_c = 0
                    page_number += 1

                number_c += 1

            data_out['cash_total_sale']['count'] = number_c - 1
            data_out['total_sale']['count'] += number_c - 1
            data_out['cash_products'] = cash_products 
            
            print(data_out['cash_line'])

            # print self.product_line_ids, 'product_line_ids'
            # print("----------------------------------------")
            # print(data_out)
            # print("()()()()()()()()()()()()()()()()(")

            return self.env['report'].get_action(self, 'brdc_account.account_sales_report_template', data=data_out)


class ReportSalesReport(models.AbstractModel):
    _name = 'report.brdc_account.account_sales_report_template'
    
    @api.model
    def render_html(self, docids, data):
        print("gg")
        docargs = {
            'doc_ids': self.ids,
            'doc_model': None,
            'docs': {'1':'one','2':'two','3':'three','4':'four','5':'five'},
            # 'time': time,
            'dataInput': data,
        }

        return self.env['report'].render('brdc_account.account_sales_report_template', docargs)
