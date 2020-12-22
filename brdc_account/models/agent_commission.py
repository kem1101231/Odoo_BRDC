from odoo import api, fields, models
from datetime import datetime, date
import calendar
from dateutil.relativedelta import relativedelta
import xlsxwriter
import base64
import odoo


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    tagged_commissions = fields.Many2one('released.commission')
    commission_able = fields.Integer()
    commission_released = fields.Boolean()

    agent_tagged = fields.Boolean(default=False)
    agent_excess_catered = fields.Boolean(default=False)
    agent_full_cater = fields.Boolean(default=False)
    agent_released = fields.Boolean(default=False)

    unit_m_tagged = fields.Boolean(default=False)
    unit_m_full_cater = fields.Boolean(default=False)
    unit_m_excess_catered = fields.Boolean(default=False)
    unit_m_released = fields.Boolean(default=False)

    agency_m_tagged = fields.Boolean(default=False)
    agency_m_full_cater = fields.Boolean(default=False)
    agency_m_excess_catered = fields.Boolean(default=False)
    agency_m_released = fields.Boolean(default=False)
    
    

    # @api.model
    # def create(self, values):

    #     result = super(AccountPayment, self).create(values)

    #     invoice_result = self.env['account.invoice'].search([('number','=',str(result.communication))], limit=1)
    #     invoice_result.update({'last_payment': invoice_result.last_payment + result.amount,})

    #     return result

    # @api.model
    # def get_payments(self):
    #     invoice_list = self.env['account.invoice'].search([('id','<',10)])

    #     print("**&&&&***&*&*&*&*&*&*&*&*&*&*&*&*&*&*&*")
    #     print(invoice_list) 

    @api.multi
    def set_commission_released(self):
        for payment in self:
            payment.commission_released = True
            payment.update({'commission_released':True})    

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    commission_generated = fields.Boolean(default=False)
    monthly_commission = fields.Float()
    last_payment = fields.Float(string="Last Uncommissioned Payment", compute="check_last_payment_amount")
    last_covered_comm_pay = fields.Integer(string="Last Commission Payment")
    last_rel_comm_date = fields.Date(string="Last Commission Date")

    @api.multi
    def get_posted_payments(self, reference, use_for, get_excess, set_date, start_date, end_date):
        for inv in self:
            output_data = {}

            total_payment = 0

            tag_boolean = False
            payments_search_ref = [ ('communication','=', inv.number),('state','=','posted'),]
            if use_for == 'get_tagged':
                payments_search_ref.append((reference+'_tagged','=',True))
                payments_search_ref.append((reference+'_released','=',False))

                if set_date == True:
                    payments_search_ref.append(('payment_date','>=', start_date))
                    payments_search_ref.append(('payment_date','<=', end_date))
            
            else:
                payments_search_ref.append((reference+'_tagged','=',False))

            payments = self.env['account.payment'].search( payments_search_ref, order="id asc")

            ids =[]
            for line in payments:
                total_payment += line.amount
                ids.append(line.id)

            output_data['count'] = len(payments)
            output_data['ids'] = ids
            output_data['list'] = payments
            output_data['total'] = total_payment

            if get_excess == True:
                uncatered_excess = self.env['account.payment'].search([

                                                                    ('communication','=', inv.number),
                                                                    ('state','=','posted'),
                                                                    ('agent_excess_catered','=',False),
                                                                    ('agent_tagged','=',True),
                                                                    ('agent_full_cater','=',False),

                                                                ])

                output_data['excess'] = uncatered_excess

            return output_data

    @api.model
    def check_last_payment_amount(self):
        for invoice in self:
            if invoice.last_payment == 0:
                invoice.last_payment = invoice.total_paid
                invoice.update({'last_payment': invoice.total_paid})

    @api.multi
    def generate_commission(self, invoice_id = None):
        if invoice_id:
            invoice = invoice_id
        else:
            invoice = self.env['account.invoice'].search([
                ('state', 'in', ['open', 'paid']),
                ('commission_generated', '=', False)
            ])
            self.env['account.commission'].search([]).unlink()

        for rec in invoice:
            rec.ensure_one()
            print rec.pa_ref
            amount = 0.0
            product = None
            contract_price = rec.amount_total
            terms = rec.new_payment_term_id.no_months
            invoice_line = rec.invoice_line_ids
            for line in invoice_line:
                if not line.is_free:
                    product = line.product_id

                    if (product.lst_price != 0) and (product.lst_price < rec.amount_total):
                        amount = product.lst_price
                        print "< amount"
                    else:
                        amount = rec.amount_total
                        print "> amount"
            
            pcf = rec.pcf
            vat = rec.vat
            gross = amount - pcf - vat
            print amount, pcf, vat, '=', gross

            sale = self.env['sale.order'].search([('name', '=', rec.origin), ('invoice_status', '=', 'invoiced'), ('state', 'in', ['done', 'sale'])])
            
            if sale.agent_id:
                rec.agent_commission(rec, sale.agent_id, terms, gross,'agent')

            if sale.um_id:
                rec.agent_commission(rec, sale.um_id, terms, gross, 'unit')

            if sale.am_id:
                rec.agent_commission(rec, sale.am_id, terms, gross,'agency')

    def agent_commission(self, rec, agent_id, term, gross, commission_type):
        commission_term = term if term < 18 else 18
        account_commission = self.env['account.commission']
        without_advances = rec.new_payment_term_id.bpt_wod

        agency_id = agent_id.agency_id
        with_tax_exception = agent_id.is_tax_excepted
        withholding_tax = 0.0

        comm_percent = agency_id.comm_percent
        withholding_tax_percent = agency_id.withholding_tax

        commission = (gross * (comm_percent / 100)) / commission_term

        if not with_tax_exception:
            withholding_tax = commission * (withholding_tax_percent / 100)

        total_commission = commission - withholding_tax

        release_date = datetime.strptime(rec.date_invoice, '%Y-%m-%d')
        if not without_advances:
            release_date + relativedelta(months=1)
        # number = 1
        for num in range(1, commission_term + 1):
            account_commission.create({
                'partner_id': agent_id.id,
                'invoice_id': rec.id,
                'currency_id': rec.currency_id.id,
                'gross': commission,
                'withholding_tax': withholding_tax,
                'amount': total_commission,
                'commission_type':commission_type,
                'release_date': release_date + relativedelta(months=num),
                'series': '%s/%s' % (num, commission_term)
            })
        rec.write({
            'monthly_commission': total_commission
        })


class ReleasedCommission(models.Model):
    _name = 'released.commission'
    _rec_name = 'date'

    date = fields.Date()
    # agent_id = fields.Many2one('res.partner', 'Agent')
    account_agent_commission_id = fields.Many2one('account.agent.commission')
    account_commission_ids = fields.Many2many('account.commission')
    commission_type = fields.Selection([('released', 'released'), ('outright', 'outright deduction')])

    gross = fields.Float(compute='amount_total')
    withholding_tax = fields.Float(compute='amount_total')
    net = fields.Float(compute='amount_total')

    tagged_payments = fields.Many2many('account.payment')
    
    pi_value = fields.Float(string="Purchase Incentive", compute='amount_total')
    orc_value = fields.Float(string="Overriding Commission", compute='amount_total')
    position_name = fields.Char(compute="amount_total")


    @api.depends('account_commission_ids')
    def amount_total(self):
        for commission in self:
            gross = 0;withholding_tax = 0;net = 0
            for rec in commission.account_commission_ids:
                gross += rec.gross
                withholding_tax += rec.withholding_tax
            net = gross - withholding_tax
            commission.gross = gross
            commission.withholding_tax = withholding_tax
            commission.net = net
            
            if commission.account_agent_commission_id.position_id.name == 'Agency Manager':

                commission.pi_value = net * 0.6
                commission.orc_value = net * 0.4
                commission.position_name = 'Agency Manager'

    @api.multi
    def print_commission(self):

        for commission in self:

            data_list = []
            
            current_client = ''
            current_pa = ''
            current_inv = None
            # current_max_comm = 0


            # client_by_commission = {}

            # for comm_line in commission.account_commission_ids:
                


            clients = {}

            all_gross = 0 
            all_withholding = 0
            all_commission_amount = 0

            for payment in commission.tagged_payments:

                if payment.state not in ['draft','cancel','terminate']:

                    if str(payment.partner_id.id) not in clients:
                        inv = self.env['account.invoice'].search([('number','=', payment.communication)])
                        clients[str(payment.partner_id.id)] = {}
                        # current_max_comm = 0

                    current = clients[str(payment.partner_id.id)]

                    if payment.communication not in current:
                            current[payment.communication] = {
                                                                'payments': [],
                                                                'pa': inv.pa_ref ,
                                                                'contract_price': inv.amount_total,
                                                                'pa_date': inv.date_invoice,
                                                                'monthly':inv.monthly_payment,
                                                                'rate':int(commission.account_agent_commission_id.agent_id.agency_id.comm_percent),
                                                                #'commission':{},

                                                            }
                    
                    current_line = current[payment.communication]

                    current_payments = current_line['payments']
                    
                    commissions = self.env['account.commission'].search([
                                                                                ('invoice_id','=', inv.id),
                                                                                ('partner_id','=',commission.account_agent_commission_id.agent_id.id),
                                                                                ('for_payment','=', payment.id),
                                                                        ],
                                                                    )



                    min_series = 0
                    max_series = 0
                    total_gross = 0
                    total_withh = 0
                    total_net = 0
                    series_text = ''
                    print("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
                    print("Commission Result")
                    for c_line in commissions:

                        print("****************************************************************")

                        print(c_line.amount)

                        series_v = c_line.series_value
                        total_gross += c_line.gross
                        total_withh += c_line.withholding_tax
                        total_net += c_line.amount

                        if min_series == 0:
                            min_series = series_v
                            max_series = series_v
                        else:
                            if series_v < min_series:
                                min_series = series_v
                            if series_v > max_series:
                                max_series = series_v

                    print("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
                    # if len(commissions) != 0: 

                    if min_series == max_series:
                        series_text = str(min_series)+' of 18th'
                    else:
                        series_text = str(min_series)+" - "+str(max_series)+" of 18th"
                    
                    current_payments.append({
                                                'or':payment.name,
                                                'amount':payment.amount,
                                                'cater_count':payment.amount/current_line['monthly'],
                                                'commission': {
                                                                'gross':"{:,.2f}".format(float(total_gross)),
                                                                'withhold':"{:,.2f}".format(float(total_withh)),
                                                                'net_comm':"{:,.2f}".format(float(total_net)),
                                                                'series': series_text,
                                                },
      
                                            })

                    # #inv.get_posted_payments()
                    # print("\n\n\n\n")
                    # print(" Inv ---------------------------------  ")
                    # print(inv.pa_ref)

                    recorded_pay = 0
                    for payment_line in current_payments:
                        recorded_pay += payment_line['cater_count']


                    all_gross += total_gross
                    all_withholding += total_withh
                    all_commission_amount += total_net

                    # print("cater max:" + str(recorded_pay))
                    


                    # else:
                    #     series_text = ''
                    #     latest_payment['gross'] = ''
                    #     latest_payment['withhold'] = ''
                    #     latest_payment['net_comm'] = ''
                    #     latest_payment['series'] = ''
                    
                    current[payment.communication] = current_line
                    clients[str(payment.partner_id.id)] = current

            current_client_c = ''

            for line_c in clients:

                client_data = self.env['res.partner'].search([('id','=',line_c)])

                if current_client_c == '':
                    current_client_c = client_data.name

                current_pa_c = ''

                for line_inv in clients[line_c]:
                    inv_data = clients[line_c][line_inv]

                    if current_pa_c == '':
                        current_pa_c = clients[line_c][line_inv]['pa']


                    for line_pay in clients[line_c][line_inv]['payments']:
                        if current_client_c != client_data.name and len(data_list) != 0:
                            current_client_c = client_data.name
                            data_list.append({
                                            'client':client_data.name,
                                            'pa':clients[line_c][line_inv]['pa'],
                                            'pa_date':self.crop_date(clients[line_c][line_inv]['pa_date']),
                                            'contract_price':"{:,.2f}".format(float(clients[line_c][line_inv]['contract_price'])),
                                            'payment':"{:,.2f}".format(float(line_pay['amount'])),
                                            'or':line_pay['or'],
                                            'rate':str(clients[line_c][line_inv]['rate'])+"%",
                                            'gross':line_pay['commission']['gross'],
                                            'withhold':line_pay['commission']['withhold'],
                                            'net_comm':line_pay['commission']['net_comm'],
                                            'remarks':line_pay['commission']['series'],
                                })
                        else:

  
                            if len(data_list) == 0:
                                data_list.append({
                                                'client':client_data.name,
                                                'pa':clients[line_c][line_inv]['pa'],
                                                'pa_date':self.crop_date(clients[line_c][line_inv]['pa_date']),
                                                'contract_price':"{:,.2f}".format(float(clients[line_c][line_inv]['contract_price'])),
                                                'payment':"{:,.2f}".format(float(line_pay['amount'])),
                                                'or':line_pay['or'],
                                                'rate':str(clients[line_c][line_inv]['rate'])+"%",
                                                'gross':line_pay['commission']['gross'],
                                                'withhold':line_pay['commission']['withhold'],
                                                'net_comm':line_pay['commission']['net_comm'],
                                                'remarks':line_pay['commission']['series'],
                                    })
                            else:

                                if current_pa_c != clients[line_c][line_inv]['pa']:
                                    data_list.append({
                                                    'client':'',
                                                    'pa':clients[line_c][line_inv]['pa'],
                                                    'pa_date':self.crop_date(clients[line_c][line_inv]['pa_date']),
                                                    'contract_price':"{:,.2f}".format(float(clients[line_c][line_inv]['contract_price'])),
                                                    'payment':"{:,.2f}".format(float(line_pay['amount'])),
                                                    'or':line_pay['or'],
                                                    'rate':str(clients[line_c][line_inv]['rate'])+"%",
                                                    'gross':line_pay['commission']['gross'],
                                                    'withhold':line_pay['commission']['withhold'],
                                                    'net_comm':line_pay['commission']['net_comm'],
                                                    'remarks':line_pay['commission']['series'],
                                        })

                                else:

                                    data_list.append({
                                                    'client':'',
                                                    'pa':'',
                                                    'pa_date':'',
                                                    'contract_price':'',
                                                    'payment':"{:,.2f}".format(float(line_pay['amount'])),
                                                    'or':line_pay['or'],
                                                    'rate':str(clients[line_c][line_inv]['rate'])+"%",
                                                    'gross':line_pay['commission']['gross'],
                                                    'withhold':line_pay['commission']['withhold'],
                                                    'net_comm':line_pay['commission']['net_comm'],
                                                    'remarks':line_pay['commission']['series'],
                                        })


                data_list.append({
                                                    'client':'',
                                                    'pa':'',
                                                    'pa_date':'',
                                                    'contract_price':'',
                                                    'payment':'',
                                                    'or':'',
                                                    'rate':'',
                                                    'gross':'',
                                                    'withhold':'',
                                                    'net_comm':'',
                                                    'remarks':'-',
                                        })


            data_y = {
                            'agent':commission.account_agent_commission_id.agent_id.name,
                            'position':commission.account_agent_commission_id.position_id.name,
                            'date_prepared':self.crop_date(fields.Date.today()),
                            'list':data_list,
                            'total_gross':"{:,.2f}".format(float(all_gross)),
                            'total_withh':"{:,.2f}".format(float(all_withholding)),
                            'total_net':"{:,.2f}".format(float(all_commission_amount)),
                    }
            print("++++++++++++++++++++++++++++")
            file_data = self.env['report'].get_action(self, 'brdc_account.agent_net_commission_voucher', data=data_y)
            print(file_data)
            return file_data
    
    @api.model
    def crop_date(self, dateInput):

        str_date = str(dateInput).split(' ')
        date_of_request = datetime.strptime(str_date[0], '%Y-%m-%d')#%I:%M%
        return date_of_request.strftime('%b %d, %Y')



class AccountCommission(models.Model):
    _name = 'account.commission'
    _order = 'invoice_id, release_date'
    _rec_name = 'release_date'

    partner_id = fields.Many2one('res.partner', 'Agent', required=True)
    currency_id = fields.Many2one('res.currency')
    account_agent_commission_id = fields.Many2one('account.agent.commission', 'Account Agent')
    invoice_id = fields.Many2one('account.invoice', 'Invoice Reference')
    customer = fields.Many2one(comodel_name="res.partner", related='invoice_id.partner_id', string="Client")
    invoice_state = fields.Char(compute="_get_invoice_state")

    for_payment = fields.Many2one(comodel_name="account.payment")

    commission_type = fields.Selection(string="Type", selection=[('agent','Sales Agent'),('unit','Unit Manager'),('agency','Agency Manager')])
    
    gross = fields.Float('Gross Commission', default=0.0, required=True)
    withholding_tax = fields.Float('Withholding Tax', default=0.0, required=True)
    amount = fields.Float('Commission Amount', default=0.0, required=True)
    
    release_date = fields.Date('Commission Release Date', required=True)
    ready_for_release = fields.Boolean()
    released = fields.Boolean()
    can_be_relesed = fields.Boolean()
    outright_deduction = fields.Boolean(default=False)
    
    date_released = fields.Date()
    released_by = fields.Many2one('res.users', 'Release by')
    series = fields.Char()

    @api.onchange('series')
    def _onchange_series(self):
        if self.series:
            string_list = str(comm.series).split('/')
            int_value = int(string_list[0])

            self.series_value = int_value 
            self.update({'series_value':int_value,})   

    series_value = fields.Integer(store=True)
    tagged_payment = fields.Many2one('account.payment')

    # @api.onchange('released', 'outright_deduction')
    # def state(self):
    #     print 'yeaaa'

    @api.multi
    def write(self, vals):
        result =  super(AccountCommission, self).write(vals)

        if self.series_value == 0:
            string_list = str(self.series).split('/')
            int_value = int(string_list[0])

            self.series_value = int_value 
            #self.update({'series_value':int_value,})   


    @api.model
    def latest_ready_for_release(self, invoice_id, agent_id):

        result = self.env['account.commission'].search([('ready_for_release','=', True),('released','=',True),('invoice_id','=', invoice_id), ('partner_id','=', agent_id)], order='series_value desc', limit=1)

        print(" ======== commission info =================")
        print(result.ready_for_release)
        print(result.series_value)
        print(result.partner_id.name)

        if len(result) == 0:
            return 0
        else:    
            return result.series_value

    @api.model
    def get_last_tagged_commission(self, invoice_id, agent_id):
        result = self.env['account.commission'].search([
                                                        ('invoice_id','=',invoice_id),
                                                        # ('for_payment','=', False)
                                                        ('ready_for_release','=', True),
                                                        ('partner_id','=', agent_id),
                                                    ],order='series_value desc', limit=1)
        if len(result) == 0:
            return 0
        else:    
            return result.series_value


    @api.model
    def multi_set_ready_for_release(self, start_series, end_series, invoice_id, payment_id):

        result = self.env['account.commission'].search([('invoice_id','=',invoice_id), ('series_value','>', start_series), ('series_value','<=', end_series)], order="series_value asc")
        # inv = self.env['account.invoice'].search(['id','=', invoice_id])
        # payments = inv.get_posted_payments(start_date, fields.Date.to)day()

        for commission in result:
            commission.ready_for_release = True
            commission.for_payment = payment_id
            commission.update({'ready_for_release':True, 'for_payment':payment_id}) #

    @api.depends('invoice_id')
    def _get_invoice_state(self):
        for commission in self:
            commission.invoice_state = str(commission.invoice_id.state)
            commission.update({'invoice_state': str(commission.invoice_id.state),})

    @api.depends('release_date')
    def _release_date(self):
        for rec in self:

            if rec.release_date <= datetime.today():
                rec.ready_for_release = True
            else:
                rec.ready_for_release = False

class AccountAgentCommission(models.Model):
    _name = 'account.agent.commission'
    _sql_constraints = [
        (
            'unique_commission',
            'unique(agent_id)',
            'Commission Info. is already existing'
        )
    ]
    _order = 'agent_id'

    @api.model
    def agent_domain(self):
        partner = self.env['res.partner'].search([('is_agent', '=', True)])

        return [('id', 'in', partner.ids)]

    def agent_default(self):
        partner = self.env['res.partner'].search([('is_agent', '=', True)])
        return partner[0].id

    @api.onchange('agent_id', 'current_month')
    def get_name(self):
        for rec in self:
            agent_name = rec.agent_id.name
            string = 'Commission of %s' % agent_name
            rec.name = string
            rec.update({
                'name': string
            })

    name = fields.Char(store=True)
    agent_id = fields.Many2one('res.partner', 'Agent', domain=agent_domain, default=agent_default)
    position_id = fields.Many2one()
    commission_type = fields.Selection(string="Type", selection=[('agent','Sales Agent'),('unit','Unit Manager'),('agency','Agency Manager')])
    commission_date = fields.Date('Commission Date', default=fields.Date.today())

    # @api.model
    # def create(self, vals):
    #     if ('name' and 'agent_id') in vals:
    #         agent_name = self.env['res.partner'].search([('id', '=', vals['agent_id'])]).name
    #         string = 'Commission of %s' % agent_name
    #         vals['name'] = string
    #         print vals['name']

    #     return super(AccountAgentCommission, self).create(vals)

    @api.multi
    def default_month(self):
        now = datetime.now()
        return int(now.month)

    current_month = fields.Selection([(1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
                                      (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
                                      (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'), ],
                                     string='Month', default=default_month)

    # @api.multi
    # def write(self, vals):
    #     for rec in self:
    #         agent_name = rec.agent_id.name
    #         # vals['current_month'] = self.current_month
    #         if 'current_month' in vals:
    #             string = 'Commission of %s' % agent_name

    #             vals['name'] = string

    #     return super(AccountAgentCommission, self).write(vals)

    @api.onchange('agent_id')
    def _get_invoices(self):
        if self.agent_id:    
            ids = []
            if self.agent_id.agent_ids:
                for list_ in self.agent_id.agent_ids:
                    ids.append(list_.id)
            else:
                ids.append(self.agent_id.id)

            invoice = self.env['account.invoice'].sudo().search([('agent_id', 'in', ids)])

            self.update({
                'invoice_ids': [(6, 0, invoice.ids)]
            })

    invoice_ids = fields.Many2many(comodel_name='account.invoice', string='Invoices')
    account_commission_id = fields.Many2many(comodel_name="account.commission")
    released_commission_id = fields.One2many(comodel_name='released.commission', inverse_name='account_agent_commission_id', string='Released Commissions')
    latest_release_date = fields.Date()

    carrier_xlsx_document_name = fields.Char(string="File Name")
    carrier_xlsx_document = fields.Binary(string="Document")

    commission_document = fields.Binary(string="Commissions")
    payment_document = fields.Binary(string="Payments")
    invoice_document = fields.Binary(string="Invoices")
    summary_document = fields.Binary(string="Commission Summary")
    
    commission_document_name = fields.Char(string="Commissions")
    payment_document_name = fields.Char(string="Payments")
    invoice_document_name = fields.Char(string="Invoices")
    summary_document_name = fields.Char(string="Commission Summary")
    
    @api.multi
    def generate_excel(self):

        # self.env['account.payment'].get_payments()
        # print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
        # print(self)
        # print(type(self))


        file_name = 'temp' 
        workbook = xlsxwriter.Workbook(file_name, {'in_memory': True})
        #worksheet = workbook.add_worksheet('Test sheet')

        commission_header = ['Release Date', 'Customer', 'PA Number', 'Gross', 'Withholding Tax', 'Commission', 'Series', 'For Release', 'Claimed', 'Date of Release']
        invoice_header = ['PA Number','Customer','Contract Date','Contract Term','Monthly','Commission Series','Current Series','No. of Paid Months','No. of Unpaid Months','Due Amount']
        payment_header = ['PA Number','Customer','OR Number', 'Date of Payment', 'Amount']
        summary_header = ['PA Number','Customer','Terms','Commission per Term','Total Gross','Withholding Tax','Total Commission','Total Claimed','Ready for Release','Series','Balance']

        commission_worksheet = workbook.add_worksheet('Commission')
        invoice_worksheet = workbook.add_worksheet('Purchase Agreement Reference')
        payment_worksheet = workbook.add_worksheet('Conducted Payments')
        summary_worksheet = workbook.add_worksheet('Summary of Commission per PA')


        comm_row = 0
        comm_col = 0
        for item in commission_header:
            commission_worksheet.write(comm_row, comm_col, item)
            comm_col += 1

        inv_row = 0
        inv_col = 0
        for item in invoice_header:
            invoice_worksheet.write(inv_row, inv_col, item)
            inv_col += 1

        payment_row = 0
        payment_col = 0
        for item in payment_header:
            payment_worksheet.write(payment_row, payment_col, item)
            payment_col += 1

        summ_row = 0
        summ_col = 0
        for item in summary_header:
            summary_worksheet.write(summ_row, summ_col, item)
            summ_col += 1

        comm_row += 1
        
        commission_total_gross = 0
        commission_total_withholding = 0
        commission_total = 0
        commission_total_for_release = 0
        commission_total_balance = 0

        for comm in self.account_commission_id:

                claimed = 'Yes' if comm.released == True else 'No'
                for_release = 'Yes' if comm.ready_for_release == True else 'No'
 
                commission_worksheet.write(comm_row, 0, comm.release_date)
                commission_worksheet.write(comm_row, 1, comm.customer.name)
                commission_worksheet.write(comm_row, 2, comm.invoice_id.pa_ref)
                commission_worksheet.write(comm_row, 3, "{:,.2f}".format(float(comm.gross)))
                commission_worksheet.write(comm_row, 4, "{:,.2f}".format(float(comm.withholding_tax)))
                commission_worksheet.write(comm_row, 5, "{:,.2f}".format(float(comm.amount)))
                commission_worksheet.write(comm_row, 6, str(comm.series).replace('/',' of '))
                commission_worksheet.write(comm_row, 7, for_release)
                commission_worksheet.write(comm_row, 8, claimed)
                commission_worksheet.write(comm_row, 9, comm.date_released if comm.date_released != False else '')

                commission_total_gross += comm.gross
                commission_total_withholding += comm.withholding_tax
                commission_total += comm.amount 



                if comm.ready_for_release == True and comm.released == False:
                    commission_total_for_release += comm.amount
                if comm.ready_for_release == False and comm.released == False:
                    commission_total_balance += comm.amount

                comm_row += 1

        commission_worksheet.write(3, 11, 'Total Gross')
        commission_worksheet.write(4, 11, 'Total Withholding Tax')
        commission_worksheet.write(5, 11, 'Total Commission')

        commission_worksheet.write(3, 12, "{:,.2f}".format(float(commission_total_gross)))
        commission_worksheet.write(4, 12, "{:,.2f}".format(float(commission_total_withholding)))
        commission_worksheet.write(5, 12, "{:,.2f}".format(float(commission_total)))

        
        pi_amount = commission_total * 0.6
        orc_amount = commission_total * 0.4

        if self.position_id.name == 'Agency Manager':
            commission_worksheet.write(5, 14, 'Purchase Incentive')
            commission_worksheet.write(6, 14, 'Overriding Commission')
            commission_worksheet.write(5, 15, "{:,.2f}".format(float(pi_amount)))
            commission_worksheet.write(6, 15, "{:,.2f}".format(float(orc_amount)))
            
            commission_worksheet.write(9, 14, 'Purchase Incentive (For Release)')
            commission_worksheet.write(10, 14, 'Overriding Commission (For Release)')
            commission_worksheet.write(9, 15, "{:,.2f}".format(float(commission_total_for_release * 0.6)))
            commission_worksheet.write(10, 15, "{:,.2f}".format(float(commission_total_for_release * 0.4)))


        
        commission_worksheet.write(9, 11, 'Ready for Release')
        commission_worksheet.write(10, 11, 'Balance Commssion')

        commission_worksheet.write(9, 12, "{:,.2f}".format(float(commission_total_for_release)))
        commission_worksheet.write(10, 12, "{:,.2f}".format(float(commission_total_balance)))         


        payment_list = []

        inv_row +=1
        for inv in self.invoice_ids:
            
            if inv.state not in ['draft','cancel','terminate']:
                
                line_amount = 0
                comm_series = inv.new_payment_term_id.no_months if inv.new_payment_term_id.no_months < 18 else 18

                for line in inv.invoice_line_ids:
                    if not line.is_free:
                        product = line.product_id

                        if (product.lst_price != 0) and (product.lst_price < inv.amount_total):
                            line_amount = product.lst_price
                        else:
                            line_amount = inv.amount_total

                commission_rate = self.position_id.comm_percent / 100

                commission_value = line_amount * commission_rate

                comm_series = inv.new_payment_term_id.no_months if inv.new_payment_term_id.no_months < 18 else 18
                
                invoice_worksheet.write(inv_row, 0, inv.pa_ref)
                invoice_worksheet.write(inv_row, 1, inv.partner_id.name)
                invoice_worksheet.write(inv_row, 2, inv.date_invoice)
                invoice_worksheet.write(inv_row, 3, inv.new_payment_term_id.no_months)# 
                invoice_worksheet.write(inv_row, 4, "{:,.2f}".format(float(inv.monthly_payment)))
                invoice_worksheet.write(inv_row, 5, "{:,.2f}".format(float(commission_value / comm_series)))
                invoice_worksheet.write(inv_row, 6, int(inv.payment_count + inv.month_due))
                invoice_worksheet.write(inv_row, 7, inv.payment_count)
                invoice_worksheet.write(inv_row, 8, int(inv.month_due))
                invoice_worksheet.write(inv_row, 9, "{:,.2f}".format(float(inv.monthly_due)))
                

                total_invoice_comm_gross = 0
                total_invoice_comm_withh = 0
                total_invoice_comm = 0
                total_claimed = 0
                total_for_release = 0
                total_unclaimed = 0
                series = ''
                max_term = inv.payment_count if inv.payment_count < 18 else 18

                per_invoice_commissions = self.env['account.commission'].sudo().search([('partner_id','=', self.agent_id.id), ('invoice_id','=', inv.id),])

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

                summary_worksheet.write(inv_row, 0, inv.pa_ref)
                summary_worksheet.write(inv_row, 1, inv.partner_id.name)
                summary_worksheet.write(inv_row, 2, comm_series)
                summary_worksheet.write(inv_row, 3, "{:,.2f}".format(float(commission_value / comm_series)))
                summary_worksheet.write(inv_row, 4, "{:,.2f}".format(float(total_invoice_comm_gross)))
                summary_worksheet.write(inv_row, 5, "{:,.2f}".format(float(total_invoice_comm_withh)))
                summary_worksheet.write(inv_row, 6, "{:,.2f}".format(float(total_invoice_comm)))
                summary_worksheet.write(inv_row, 7, "{:,.2f}".format(float(total_claimed)))
                summary_worksheet.write(inv_row, 8, "{:,.2f}".format(float(total_for_release)))
                summary_worksheet.write(inv_row, 9, series) 
                summary_worksheet.write(inv_row, 10, "{:,.2f}".format(float(total_unclaimed))) 

                payments = self.env['account.payment'].sudo().search([     
                                                                    ('communication','=', inv.number),
                                                                    ('partner_id','=',inv.partner_id.id),
                                                                    #('payment_date','>=',self.date_from),
                                                                ], order="partner_id desc",)

                for payment in payments:
                    if payment.state != 'draft':
                        payment_list.append(payment)


                inv_row += 1

        payment_row += 1
        for payment in payment_list:
 
            invoice_id = self.env['account.invoice'].sudo().search([('number', '=', payment.communication)], limit=1)
            
            payment_worksheet.write(payment_row, 0, invoice_id.pa_ref)
            payment_worksheet.write(payment_row, 1, invoice_id.partner_id.name)
            payment_worksheet.write(payment_row, 2, payment.name)
            payment_worksheet.write(payment_row, 3, payment.payment_date)
            payment_worksheet.write(payment_row, 4, "{:,.2f}".format(float(payment.amount)))

            payment_row += 1

        workbook.close()
        with open(file_name, "rb") as file:
            file_base64 = base64.b64encode(file.read())

        self.carrier_xlsx_document_name = self.agent_id.name+'_commission_info.xlsx'

        self.write({
                        'carrier_xlsx_document': file_base64,
                    })
    
    @api.model
    def crop_date(self, dateInput):

        str_date = str(dateInput).split(' ')
        date_of_request = datetime.strptime(str_date[0], '%Y-%m-%d')#%I:%M%
        return date_of_request.strftime('%b %d, %Y')

    @api.depends('invoice_ids', 'agent_id', 'current_month')
    def get_commission(self):

        invoice_class = self.env['account.invoice']
        payment_class = self.env['account.payment']
        #commission_class = 

        ids = []
        comm_ids = []
        payments_list = []
        self._get_invoices()
        
        for id_line in self.invoice_ids:

            if id_line.state not in ['draft','cancel','terminate']:
            
                commission = self.env['account.commission'].search([
                                                                        ('invoice_id', '=', id_line.id),
                                                                        ('partner_id', '=', self.agent_id.id),
                                                                    ])

                paid_amount = id_line.total_paid
                count_index = id_line.payment_count if id_line.last_covered_comm_pay == 0 else id_line.payment_count - id_line.last_covered_comm_pay

                payment_term = id_line.new_payment_term_id.no_months   

                for line in commission:
                    agent_id = line.partner_id

                    agency_id = agent_id.agency_id
                    withholding_tax = 0.0

                    comm_percent = agency_id.comm_percent
                    withholding_tax_percent = agency_id.withholding_tax
                    with_tax_exception = agent_id.is_tax_excepted

                    selling_price = line.invoice_id.invoice_line_ids[0].product_id.lst_price
                    contract_price = line.invoice_id.amount_total

                    gross = 0

                    if contract_price != 0 and selling_price != 0:
                        if contract_price < selling_price:
                            gross = contract_price
                        else:
                            gross = selling_price
                    else:
                        if contract_price == 0:
                            gross = selling_price
                        if selling_price == 0:
                            gross = contract_price

                    if gross != 0:

                        commission_term = int(payment_term) if int(payment_term) < 18 else 18
                            
                        commission_value = (gross * (comm_percent / 100)) / commission_term

                        if not with_tax_exception:
                            withholding_tax = commission_value * (withholding_tax_percent / 100)

                        total_commission = commission_value - withholding_tax
                            
                        line.update({'amount': total_commission,'withholding_tax': withholding_tax, 'gross': commission_value,})

                        #commission_rate = ((line.gross * commission_term) / gross) * 100


                reference_value = ''
                if self.position_id.name == "Agency Manager":
                    reference_value = 'agency_m'
                if self.position_id.name == "Unit Manager":
                    reference_value = 'unit_m'
                if self.position_id.name == "Sales Agent":
                    reference_value = 'agent'

                # start_date = id_line.date_invoice if self.latest_release_date == False else self.latest_release_date
                payments = id_line.get_posted_payments(reference_value,'to_tag', True, False, None, None)
                #catered_count = 0 if payments['total'] == 0 else int(payments['total'] / id_line.monthly_payment)
                latest_series_for_release = self.env['account.commission'].latest_ready_for_release(id_line.id, self.agent_id.id)

                current_excess = 0

                if len(payments['excess']) != 0:
                    for line_e in payments['excess']:
                        current_excess += (line_e.amount % id_line.monthly_payment)

                for idx,payment_line in enumerate(payments['list']):

                    catered_count = int((current_excess + payment_line.amount) / id_line.monthly_payment) # 0 if payment_line.amount == 0 else
                    last_tagged_commission = self.env['account.commission'].get_last_tagged_commission(id_line.id, self.agent_id.id)
                    
                    self.env['account.commission'].multi_set_ready_for_release(last_tagged_commission, last_tagged_commission + catered_count, id_line.id, payment_line.id)

                    excess = (current_excess + payment_line.amount) % id_line.monthly_payment
                    current_excess = excess

                    if idx != len(payments['list']) - 1:
                        payment_line.update({
                                            str(reference_value)+"_tagged":True, 
                                            str(reference_value)+'_full_cater': True,
                                        })
                    else: 
                        full_cater = True
                        if excess != 0:
                            full_cater = False
                        
                        payment_line.update({
                                            str(reference_value)+"_tagged":True, 
                                            str(reference_value)+'_full_cater': full_cater,
                                        })




                # if latest_series_for_release != id_line.payment_count:
                #     self.env['account.commission'].multi_set_ready_for_release(latest_series_for_release, latest_series_for_release + catered_count, id_line.id)

                for comm in commission:

                    if comm.commission_type == self.commission_type and (comm.invoice_id.state not in ['draft','cancel','terminate']):
                        comm_ids.append(comm.id)

        self.account_commission_id = [(6, 0, comm_ids)]

class ReleaseCommission(models.TransientModel):
    _name = 'release.commission'

    account_agent_commission_id = fields.Many2one('account.agent.commission')
    include_advances = fields.Boolean(string="Include Advances", default=True)
    indicate_start = fields.Boolean(string="Indicate a Start Date")

    account_commission_ids = fields.Many2many('account.commission', compute='get_commission_line') # 
    all_commission_for_time = fields.Many2many(comode_name='account.commission')
    payment_ref_list = fields.Many2many(comodel_name='account.payment')
    date_from = fields.Date(string="From Date", default=fields.Date.today())#
    date = fields.Date(string="To Date", default=fields.Date.today()) #
    gross = fields.Float(compute='amount_total')
    withholding_tax = fields.Float(compute='amount_total')
    net = fields.Float(compute='amount_total')
    
    pi_value = fields.Float(string="Production Incentive")
    orc_value = fields.Float(string="Overriding Commission")
    position_name = fields.Char()
   
    @api.multi
    def print_commission(self):

            comm_list = self.account_commission_ids
            payment_list = self.payment_ref_list
            all_comm_list = self.all_commission_for_time
            
            all_commissions = []
            commissions = []
            payments = []

            for lines in all_comm_list:
                state_string = 'No'
                if lines.ready_for_release:
                    state_string = 'Yes'
                
                all_commissions.append({
                                            'date':lines.date_released,
                                            'series':lines.series,
                                            'customer':lines.partner_id.name,
                                            'pa':lines.invoice_id.pa_ref,
                                            'gross':lines.gross,
                                            'withh':lines.withholding_tax,
                                            'commission':lines.amount,
                                            'status':state_string,
                                        })

            data = {'data':{    
                                'agent':self.account_agent_commission_id.agent_id.name,
                                'position':self.account_agent_commission_id.position_id.name,
                                'date_from':self.date_from,
                                'date_to':self.date,
                                'commission':commissions,
                                'payment':payments,

                            }
                    }

            out = self.env['report'].get_action(self, 'brdc_account.all_payments_template', data=data)
            return out
    
    @api.multi
    def print_payment(self):
            data = {'data':{    'vendor': 'vendor',
                            
                            }
                    }
            
            out = self.env['report'].get_action(self, 'brdc_account.all_payments_template', data=data)
            return out
    
    @api.depends('account_agent_commission_id', 'date', 'date_from', 'indicate_start', 'include_advances')
    def get_commission_line(self):

        # search_data = []
        payment_search = {}
        limit_indicated = False
        if self.include_advances == False and self.indicate_start == True:
            payment_search = {'start':self.date_from,'end':self.date}
            limit_indicated = True

        if self.include_advances == False and self.indicate_start == False:
            start_date = None if self.account_agent_commission_id.latest_release_date == False else self.account_agent_commission_id.latest_release_date
            payment_search = {'start':start_date,'end':self.date}
            limit_indicated = True

        if self.include_advances == True and self.indicate_start == False:
            start_date = None if self.account_agent_commission_id.latest_release_date == False else self.account_agent_commission_id.latest_release_date
            payment_search = {'start':start_date,'end':fields.Date.today()}

        
        if self.include_advances == True and self.indicate_start == True:
            payment_search = {'start':self.date_from,'end':fields.Date.today()}
            limit_indicated = True                          


        ids = []
        payment_list = []

        for invoice_line in self.account_agent_commission_id.invoice_ids:
            
            if invoice_line.state not in ['cancel', 'draft', 'terminate']:
                reference_value = ''
                if self.account_agent_commission_id.position_id.name == "Agency Manager":
                    reference_value = 'agency_m'
                if self.account_agent_commission_id.position_id.name == "Unit Manager":
                    reference_value = 'unit_m'
                if self.account_agent_commission_id.position_id.name == "Sales Agent":
                    reference_value = 'agent'

                payments = invoice_line.get_posted_payments(reference_value, 'get_tagged', False, limit_indicated, payment_search['start'], payment_search['end'])
                catered_count = 0 if payments['total'] == 0 else int(payments['total'] / invoice_line.monthly_payment)

                latest_series_for_release = self.env['account.commission'].latest_ready_for_release(invoice_line.id, self.account_agent_commission_id.agent_id.id)

                for payment_line_new in payments['list']:


                            commissions = self.env['account.commission'].search([
                                                                                    ('partner_id','=', self.account_agent_commission_id.agent_id.id),
                                                                                    ('ready_for_release','=', True),
                                                                                    ('released','=', False),
                                                                                    ('invoice_id','=', invoice_line.id),
                                                                                    ('for_payment','=', payment_line_new.id)
                                                                                ])

                            for lines in commissions:
                                ids.append(lines.id)
                            
                            payment_list.append(payment_line_new.id)


        self.account_commission_ids = [(6, 0, ids)]
        self.payment_ref_list = [(6, 0, payment_list)]
        #self.all_commission_for_time = [(6, 0, all_ids)]

    @api.depends('account_commission_ids')
    def amount_total(self):
        gross = 0;withholding_tax = 0;net = 0
        for rec in self.account_commission_ids:
            gross += rec.gross
            withholding_tax += rec.withholding_tax
        net = gross - withholding_tax
        self.gross = gross
        self.withholding_tax = withholding_tax
        self.net = net

        if self.account_agent_commission_id.position_id.name == 'Agency Manager':
            self.pi_value = net * 0.6
            self.orc_value = net * 0.4
            self.position_name = 'Agency Manager'


    @api.multi
    def release_commission(self):

        # def get_invoices():
        #     invoices = []
        #     t = []
        #     for line in self.account_commission_ids:
        #         t.append(line.invoice_id)
        #         for id_ in t:
        #             if id_ not in invoices:
        #                 invoices.append(id_)
        #     return invoices

        # def payment(invoices):
        #     ids_ = []
        #     payments = []
        #     for inv in invoices:
        #         for am in inv.move_id:
        #             for aml in am.line_ids:
        #                 if aml.account_id.reconcile:
        #                     ids_.extend(
        #                         [r.debit_move_id.id for r in aml.matched_debit_ids] if aml.credit > 0 else [
        #                             r.credit_move_id.id
        #                             for r in
        #                             aml.matched_credit_ids])
        #                     ids_.append(aml.id)
        #         move_line = self.env['account.move.line'].search([('id', 'in', ids_)]).sorted(key=lambda l: l.date,
        #                                                                                       reverse=False)
        #         for ml in move_line:
        #             if ml.payment_id and (ml.payment_id.commission_able > ml.payment_id.commission_released):
        #                 payments.append(ml.payment_id.id)

        #     return payments

        ids = []
        released_commission = self.env['released.commission']
        for rec in self.account_commission_ids:
            rec.write({
                'date_released': fields.Date.today(),
                'released_by':  self.env.user.id,
                'released': True
            })

            ids.append(rec.id)
        rc = released_commission.create({
            'date': fields.Date.today(),
            'account_agent_commission_id': self.account_agent_commission_id.id,
            'commission_type': 'released',
            'account_commission_ids': [(6, 0, ids)],
            # 'tagged_payments': [(6, 0, )]

        })


        # for invoice in get_invoices():
        #     for pay in payment(invoice):
        #         commission_able = 0
        #         account_payment = self.env['account.payment'].search([('id', '=', pay)])
        #         commission_able = int(account_payment.amount / invoice.monthly_payment) if account_payment.amount >= invoice.monthly_payment else 1
        #         account_payment.write({
        #             'tagged_commissions': rc.id,
        #             # 'commission_able': account_payment.commission_able + commission_able,
        #             'commission_released': account_payment.commission_released + 1
        #         })
        #         payment_ids.append(payment(invoice))
        #         # rc.write({
        #         #     'tagged_payments': [(4, pay)]
        #         # })
                
        #     invoice_class =  self.env['account.invoice'].search([('id','=', invoice.id)])
        #     invoice_class.update({'last_covered_comm_pay':invoice.payment_count})
        reference_value = ''
        if self.account_agent_commission_id.position_id.name == "Agency Manager":
            reference_value = 'agency_m'
        if self.account_agent_commission_id.position_id.name == "Unit Manager":
            reference_value = 'unit_m'
        if self.account_agent_commission_id.position_id.name == "Sales Agent":
            reference_value = 'agent'
        
        for payment in self.payment_ref_list:
                rc.write({
                    'tagged_payments': [(4, payment.id)]
                })
                payment.update({reference_value+'_released':True,})
                
        agent_account_comm = self.env['account.agent.commission'].search([('id','=', self.account_agent_commission_id.id)])
        agent_account_comm.update({'latest_release_date':fields.Date.today(),})

        # return True, {
        #     "type": "ir.actions.do_nothing",
        # }


class OutRightDeduction(models.TransientModel):
    _name = 'outright.deduction'

    release_commission_id = fields.Many2one(comodel_name='release.commission')
    amount_to_deduct = fields.Float(string="Amount to Deduct")
    account_agent_commission_id = fields.Many2one(comodel_name='account.agent.commission')
    agent_id = fields.Many2one(comodel_name='res.partner', string='Agent', related='account_agent_commission_id.agent_id')
    invoice_ids = fields.Many2many(comodel_name='account.invoice', string='Invoices')

    @api.multi
    def outright_deduction(self):
        print("+++++++++++++++++++++===")
        print("decuction")