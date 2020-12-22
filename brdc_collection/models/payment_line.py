from odoo import api, fields, models, _
from itertools import groupby
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta


class DCRBank(models.Model):
    _name = 'dcr.bank'
    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Cheque Number is already existing!')
    ]

    dcr_line_id = fields.Many2one('dcr.lines')
    name = fields.Char('Check Number')
    bank_id = fields.Many2one('res.bank', 'Bank')
    date_issued = fields.Date()
    partner_id = fields.Many2one('res.partner', 'Customer')

    @api.depends('name', 'bank_id', 'date_issued', 'partner_id')
    def _state_(self):
        for rec in self:
            if not (rec.name and rec.bank_id and rec.date_issued and rec.partner_id):
                rec.state = 'incomplete'
            else:
                rec.state = 'complete'

    state = fields.Selection([('complete', 'Complete'), ('incomplete', 'Incomplete')], compute=_state_)

    @api.model
    def _get_payments(self):
        for rec in self:
            payments = self.env['account.payment'].search([('user_id', '=', rec.create_uid.id), ('cash_cheque_selection', '=', 'cheque'), ('check_number', '=', rec.name)])
            rec.partner_ids = [(6, 0, payments.ids)]

    payment_ids = fields.Many2many(comodel_name='account.payment', compute=_get_payments)


class DCRLines(models.Model):
    _name = 'dcr.lines'

    name = fields.Char(compute="_get_name")

    def _get_name(self):
        for s in self:
            s.name = s.or_reference
    partner_ids = fields.Many2one(comodel_name="res.partner", string="Customers")
    DailyCollectionRecord_id = fields.Many2one(comodel_name="daily.collection.record", string="Record of")#, domain=[('state','=','note')]
    dcr_collector = fields.Many2one(comodel_name="res.users", related="DailyCollectionRecord_id.collector_id")
    
    # @api.onchange('partner_ids')
    # def _change_partner_ids(self):
    #     if self.partner_ids:
    #         print("++++++++++++++++++++++++++++++++")
    #         print("returning domain")
    #         return {'domain':{'invoice_id':[('pa_ref_collector','=', self.dcr_collector.id)]}}

    # @api.onchange('dcr_collector')
    # def _change_dcr_coll(self):
    #     if self.dcr_collector:
    #         print("++++++++++++++++++++++++++++++++")
    #         print("returning domain")
    #         return {'domain':{'invoice_id':[('pa_ref_collector','=', self.dcr_collector.id)]}}

    # or_series = fields.Many2one(comodel_name="or.series.line", string="OR Series")

    cash_cheque_selection = fields.Selection(string="",
                                             selection=[('cash', 'Through Cash'), ('cheque', 'Through Cheque'), ],
                                             required=True, default='cash')
    or_reference = fields.Char()
    amount_paid = fields.Float(string="amount paid",)
    # date = fields.Date(default=fields.Date.today())
    setdate = fields.Char(compute='_get_dcr_set_date')
    state = fields.Selection(string="", selection=[('draft', 'draft'), ('confirmed', 'confirmed'), ('posted', 'posted'), ], required=False, default='draft')
    PA = fields.Char(compute='_get_PA')
    invoice_id = fields.Many2one('account.invoice')

    # @api.onchange('invoice_id')
    # def _change_inv(self):
    #     if self.invoice_id:
    #         print(":::::::::::::::::::::::::::::::::::::::::::")
    #         print(self.invoice_id.pa_ref_collector.name)
    #         self.PA = self.invoice_id.pa_ref

    journal_id = fields.Many2one('account.journal', string='Payment Journal', domain=[('type', 'in', ('bank', 'cash'))])
    description = fields.Text(string='payment description')

    # modify field date in lines, must be same with the daily collection record date and updates payment date --- ryl
    @api.onchange('DailyCollectionRecord_id')
    def _get_dcr_set_date(self):
        for s in self:
            s.setdate = datetime.strptime(s.DailyCollectionRecord_id.date, "%Y-%m-%d").strftime('%b/%d/%Y')
            # print type(s.setdate)
            # print s.setdate

    @api.model
    def _get_payment_id(self):
        for rec in self:
            if rec.id:
                payment = self.env['account.payment'].search([('collected_id', '=', rec.id)])
                rec.payment_id = payment.id

    payment_id = fields.Many2one('account.payment', string='Payment')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    drc_bank_id = fields.Many2one('dcr.bank', 'Cheque Information')
    payment_status = fields.Selection(related="payment_id.state")

    @api.onchange('cash_cheque_selection')
    def _clear_bank(self):
        self.drc_bank_id = False

    @api.one
    @api.depends('company_id')
    def _get_currency_id(self):
        self.update({
            'currency_id': self.company_id.currency_id
        })

        # self.currency_id = self.company_id.currency_id

    currency_id = fields.Many2one('res.currency', compute='_get_currency_id', required=True,
                                  string='Default company currency')

    @api.multi
    @api.onchange('partner_ids')
    def _domain_invoice(self):
        for rec in self:
            # print("++++++++++++++++++++++++++++++++++++++++++++++++")
            # print(rec.dcr_collector.name)
            invoice = self.env['account.invoice'].search([('partner_id', '=', rec.partner_ids.id), ('state', '=', 'open'), ('pa_ref_collector','=', rec.dcr_collector.id)])
            # print("%^%^%^%^%^%^%^%^%^%^%^%^%^%^%^%^%^%^%^%^%")
            # print(invoice)
            domain = {'invoice_id': [('id', 'in', invoice.ids)]}

            return {'domain': domain}

    @api.onchange('invoice_id')
    def _get_PA(self):
        for s in self:
            # print(":::::::::::::::::::::::::::::::::::::::::::")
            # print(s.invoice_id.pa_ref_collector.name if s.invoice_id.pa_ref_collector else "not indicated")
            s.PA = s.invoice_id.pa_ref

    @api.multi
    def show_invoice(self):
        for s in self:
            invoice = self.env['account.invoice'].search([('id', '=', s.invoice_id.id)])
            return {
                'name': "Invoice",
                'res_model': 'account.invoice',
                'res_id': invoice.id,
                'type': 'ir.actions.act_window',
                'target': 'self',
                'views': [(self.env.ref('brdc_account.account_invoice_from_inherit').id, 'form')],
                'view_mode': 'form',
                'view_id': False,
                'view_type': 'form'
            }   

    @api.multi
    def show_payment(self):
        payment = self.env['account.payment'].search([('collected_id', '=', self.id)])
        print payment.id
        return {
            'name': "Payment",
            'res_model': 'account.payment',
            'res_id': payment.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
            'views': [(self.env.ref('brdc_account.account_payment_form_view_inherit').id, 'form')],
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'flags': {'initial_mode': 'view'},
        }

    def show_payment_mm(self):
        payment = self.env['account.payment'].search([('collected_mm_id', '=', self.id)])
        print payment.id
        return {
            'name': "Payment",
            'res_model': 'account.payment',
            'res_id': payment.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
            'views': [(self.env.ref('brdc_account.account_payment_form_view_inherit').id, 'form')],
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'flags': {'initial_mode': 'view'},
        }

    def get_payment_info(self):
        for line in self:
            payment_sched_record = self.env['invoice.installment.line'].search([('account_invoice_id','=',line.invoice_id.id),('date_paid','=',line.setdate),('payment_transaction','=', line.payment_id.id)])

            sched_total = 0
            sched_past = 0
            sched_current = 0
            sched_advance = 0

            # line_date = datetime.strptime(line.setdate,'%Y-%m-%d')
            

            for payment in payment_sched_record:
                
                # payment_date = datetime.strptime(payment.date_paid, '%Y-%m-%d')
                # due_payment_date = datetime.strptime(payment.date_for_payment, '%Y-%m-%d')

                payment_value = payment.payable_balance if payment.balance == 0 else payment.balance
                # payment_value = payment_value if 
                
                sched_total += payment_value
                
                if payment.get_payment_date_status() == 'current':
                    sched_current += payment_value
                if payment.get_payment_date_status() == 'past':
                    sched_past += payment_value
                if payment.get_payment_date_status() == 'advance':
                    sched_advance += payment_value

            total_fees = line.amount_paid - sched_total

            return {
                    'total':sched_total,
                    'current':sched_current,
                    'past':sched_past,
                    'advance':sched_advance,
                    'fees':total_fees,
            }

class DCRLinesMM(models.Model):
    _name = 'dcr.lines.mm'
    _inherit = 'dcr.lines'

    product_id = fields.Many2one('product.product', 'Product', compute='_compute_product')
    service_id = fields.Many2one('service.order', 'Plan')

    @api.depends('partner_ids', 'DailyCollectionRecord_id.dcr_lines_mm_ids')
    @api.onchange('partner_ids', 'DailyCollectionRecord_id.dcr_lines_mm_ids')
    def _domain_product(self):
        for rec in self:
            # product_ids = []
            service = self.env['service.order'].search([('partner_id', '=', rec.partner_ids.id)])

            domain = {'service_id': [('id', 'in', service.ids), ('state', '=', 'ready')]}
            return {'domain': domain}

    @api.depends('service_id')
    def _compute_product(self):
        for rec in self:
            rec.update({
                'product_id': rec.service_id.product_id.id
            })

    @api.model
    def _get_payment_id(self):
        for rec in self:
            if rec.id:
                payment = self.env['account.payment'].search([('collected_mm_id', '=', rec.id)])
                rec.payment_id = payment.id

    payment_id = fields.Many2one('account.payment', string='PAYMENT', compute=_get_payment_id)


class DailyCollectionRecord(models.Model):
    _name = 'daily.collection.record'
    _order = 'date desc, id desc'

    def get_group(self):
        user = self.env.user
        if user.has_group('brdc_account.group_module_collection_efficiency_supervise'):
            self.all_docs_group = True
        else:
            self.all_docs_group = False

    def get_group_default(self):
        user = self.env.user
        if user.has_group('brdc_account.group_module_collection_efficiency_supervise'):
            return True
        else:
            return False

    all_docs_group = fields.Boolean(compute=get_group, default=get_group_default)

    @api.model
    def default_name(self):
        for s in self:
            return "Collections of %s for %s" % (s.collector_id.name, s.date)

    name = fields.Char(default=default_name)
    collector_id = fields.Many2one(comodel_name="res.users", default=lambda self: self.env.user, string='Collector')
    dcr_lines_ids = fields.One2many(comodel_name="dcr.lines", inverse_name="DailyCollectionRecord_id", string="Daily Collection Record", required=False, )
    dcr_lines_mm_ids = fields.One2many(comodel_name="dcr.lines.mm", inverse_name="DailyCollectionRecord_id", string="MM Daily Collection Record", required=False, )

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)

    @api.one
    @api.depends('company_id')
    def _get_currency_id(self):
        self.update({
            'currency_id': self.company_id.currency_id
        })
        # self.currency_id = self.company_id.currency_id

    currency_id = fields.Many2one('res.currency', compute='_get_currency_id', required=True, string='Default company currency')

    # @api.onchange('collector_id')
    # @api.multi
    # def or_value(self):
    #     or_series = []
    #     id = 0
    #     for dcr in self.dcr_lines_ids:
    #         or_series.append(dcr.or_series.id)
    #     print(or_series)
    #     or_0 = self.env['or.series.line'].search([('state','=','unused'),('responsible','=',self.env.user.id)])
    #     or_1 = self.env['or.series.line'].search([('state','=','unused'),('responsible','=',self.collector_id.id),('id','not in',or_series)])
    #     if not self.dcr_lines_ids:
    #         id = or_0[0].id
    #     else:
    #         id = or_1[0].id
    #     return id

    @api.multi
    def pa_value(self):
        for s in self:
            pa = []
            for dcr in s.dcr_lines_ids:
                pa.append(dcr.PA)
            return pa

    @api.multi
    def submit_collection(self):
        for s in self:
            # print s.pa_value()
            invoice = self.env['account.invoice']
            if not s.partner_ids or \
                    not s.or_reference or \
                    (not s.amount_paid or s.amount_paid == 0) or \
                    not s.invoice_id or not s.journal_id:
                raise UserError(_('field error!'))
            elif not invoice.search([('id','=',s.invoice_id.id),('partner_id','=',s.partner_ids.id)]):
                raise UserError(_(' P.A. No. %s and Customer %s not matched!' % (s.invoice_id.pa_ref, s.partner_ids.name)))
            elif not invoice.search([('id','=',s.invoice_id.id)]):
                raise UserError(_('PA does not exist!'))
            elif s.PA in s.pa_value():
                raise UserError(_('Payment from %s already registered.' % s.invoice_id.pa_ref))
            else:
                invoice = self.env['account.invoice'].search([('id','=',s.invoice_id.id)])
                dcr_line = s.env['dcr.lines']
                dcr_line.create({
                    'partner_ids': s.partner_ids.id,
                    'or_reference': s.or_reference,
                    'amount_paid': s.amount_paid,
                    'DailyCollectionRecord_id': s.id,
                    'PA': invoice.pa_ref,
                    'invoice_id': invoice.id,
                    'journal_id': s.journal_id.id,
                })
                self.update({
                    'partner_ids': False,
                    'or_reference': None,
                    'amount_paid': 0.00,
                    'PA': '',
                    'journal_id': False,
                    'invoice_id': None,
                })
        return True
    # or_filter = fields.Char(compute='or_value')
    invoice_id = fields.Many2one(comodel_name="account.invoice", string="P.A.", domain="[('partner_id', '=', partner_ids), ('state', '=', 'open')]")

    partner_ids = fields.Many2one(comodel_name="res.partner", string="Customers", domain=[('state', '=', 'note')])
    # or_series = fields.Many2one(comodel_name="or.series.line", string="OR Series", default=lambda self: self.or_value())
    or_reference = fields.Integer()
    amount_paid = fields.Float(string="amount paid",)
    total_collection = fields.Float(string='Total Cash Collection', default=0.00, compute='get_collection')
    total_collection_bank = fields.Float(string='Total Cheque Collection', default=0.00, compute='get_collection')
    date = fields.Date(default=fields.Date.today())
    PA = fields.Char(string='Purchase Agreement')
    journal_id = fields.Many2one('account.journal', string='Payment Journal', domain=[('type', 'in', ('bank', 'cash'))])
    collection_type = fields.Selection(selection=[('cashier','Cashier'),('collect','Collector')], string="Collection Type", default='collect')

    @api.onchange('collector_id','date')
    def name_onchange(self):
        for s in self:
            s.name = "Collections of %s for %s" % (s.collector_id.name, s.date)

    @api.multi
    def write(self, vals):
        for s in self:
            if 'collector_id' in vals and vals['collector_id']:
                c_id = vals['collector_id']
            elif 'collector_id' not in vals and s.collector_id:
                c_id = s.collector_id.id
            else:
                c_id = None

            if 'date' in vals and vals['date']:
                d = vals['date']
            elif 'date' not in vals and s.date:
                d = s.date
            else:
                d = ''

            # print c_id

            users = s.env['res.users'].search([('id','=',c_id)])
            vals['name'] = 'Collections of %s for %s' % (users.name if users.name else s.collector_id.name, d)

        rec = super(DailyCollectionRecord, self).write(vals)
        return rec

    @api.onchange('dcr_lines_ids', 'dcr_lines_mm_ids')
    @api.multi
    def get_collection(self):
        for s in self:
            dcr_cash = 0.0
            dcr_mm_cash = 0.0
            dcr_cash_b = 0.0
            dcr_mm_cash_b = 0.0

            for dcr in s.dcr_lines_ids:
                if dcr.cash_cheque_selection == 'cash':
                    dcr_cash += dcr.amount_paid
                else:
                    dcr_cash_b += dcr.amount_paid

            for dcr in s.dcr_lines_mm_ids:
                if dcr.cash_cheque_selection == 'cash':
                    dcr_mm_cash += dcr.amount_paid
                else:
                    dcr_mm_cash_b += dcr.amount_paid

            total_collection = dcr_cash + dcr_mm_cash
            total_collection_b = dcr_cash_b + dcr_mm_cash_b

            s.update({
                'total_collection': total_collection,
                'total_collection_bank': total_collection_b
            })

    def get_denomination(self):
        rec = ''
        for s in self:
            denomination = s.env['cash.count.config.line'].search([('active', '=', True)])
            s.env['cash.count.temp'].search([('dcr_id', '=', s.id)]).unlink()
            cash_count_line = s.env['cash.count.temp']

            array = []
            number = 1
            for d_ in denomination:
                array.append(d_.id)
                # print array
                rec = cash_count_line.create({
                    'dcr_id': s.id,
                    'cash_config_line_id': array[-1]
                })
        return rec

    cash_count_line_ids = fields.One2many(comodel_name="cash.count.temp",
                                      inverse_name="dcr_id",
                                      string="Denominations",
                                      required=False,
                                      # compute=get_denomination
                                      )

    @api.onchange('cash_count_line_ids')
    @api.multi
    def get_total_count(self):
        for s in self:
            s.total_count = sum(c.total_amount for c in s.cash_count_line_ids)
            # for c in s.cash_count_line_ids:
            #     s.total_count += c.total_amount
            s.count_difference = s.total_count - s.total_collection
    total_count = fields.Float(string='Total Count', default=0.00, compute=get_total_count)
    state = fields.Selection(string="", selection=[('draft', 'Draft'), ('submit', 'Submit'), ('confirm', 'Confirm')], required=False, default='draft')
    count_difference = fields.Float(string='Difference', compute=get_total_count)

    @api.multi
    def action_draft(self):
        self.state = 'draft'
    #     array = []
    #     for s in self:
    #         or_series = s.env['or.series.line']
    #         for dcr in s.dcr_lines_ids:
    #             array.append(dcr.or_series.id)
    #             for a in array:
    #                 os = or_series.search([('id', '=', a)])
    #                 os.write({
    #                     'state': 'unused'
    #                 })
    #         s.state = 'draft'
    #     return True

    @api.multi
    def action_submit(self):
        # self.state = 'submit'
        # array = []
        for s in self:
        #     for dcr in s.dcr_lines_ids:
        #         array.append(dcr.or_series.id)
        #         for x,y in groupby(sorted(array)):
        #             if len(list(y)) > 1:
        #                 raise UserError(_('O.R. Number duplicated!'))
            s.state = 'submit'
            if s.total_collection > s.total_count:
                raise UserError(_('Cash count does not match to total collection.'))
            pass

    @api.multi
    def action_confirm(self):
        # array = []
        # something to do hererrrrrrrrrrrerererererererererere
        state = []
        state_mm = []
        for s in self:
            dcr_lines = s.env['dcr.lines']
            
            # or_series = s.env['or.series.line']
            
            payment = s.env['account.payment']
            for dcr in s.dcr_lines_ids:
                
                # array.append(dcr.or_series.id)
                # if not dcr.payment_id:
                
                state.append(dcr.id)
                
                # for a in array:
                #     os = or_series.search([('id', '=', a)])
                #     os.write({
                #         'state': 'used'
                #     })

            for b in state:
                line = dcr_lines.search([('id', '=', b)])
                print("+++++++++++++++++++++++++++++++++++++")
                print("/////////////////////////////////////")
                print(line.payment_id)
                payment_ref = line.payment_id

                if s.collection_type == 'collect':
                    payment_ = payment.create({
                        'paymentType': 'collection',
                        'cash_cheque_selection': line.cash_cheque_selection,
                        'bank_id': line.drc_bank_id.bank_id.id if line.cash_cheque_selection == 'cheque' else None,
                        'check_number': line.drc_bank_id.name if line.cash_cheque_selection == 'cheque' else None,
                        'check_date': line.drc_bank_id.date_issued if line.cash_cheque_selection == 'cheque' else None,
                        'collection_id': s.id,
                        'collected_id': line.id,
                        'or_reference': line.or_reference,
                        'journal_id': line.journal_id.id,
                        'amount': line.amount_paid,
                        'amount_tender': line.amount_paid,
                        'amount_received': line.amount_paid,
                        'payment_difference_handling': 'open',
                        'payment_date': line.setdate,
                        'payment_record_type':'collect',
                        # 'payment_date': line.date
                        'partner_type': 'customer',
                        'payment_type': 'inbound',
                        'account_invoice_id': line.invoice_id.id,
                        'communication': line.invoice_id.number,
                        'partner_id': line.partner_ids.id,
                        'user_id': s.collector_id.id,
                        'payment_method_id': 1,
                        'has_invoices': True,
                        'invoice_ids': [(4,line.invoice_id.id)]
                    })

                    payment_ref = payment_
                    payment_.post()

                line.write({
                                'state': 'confirmed',
                                'payment_id': payment_ref.id
                    })
                    

            dcr_lines_mm = s.env['dcr.lines.mm']
            for dcr in s.dcr_lines_mm_ids:
                state_mm.append(dcr.id)
            for b in state_mm:
                line = dcr_lines_mm.search([('id', '=', b)])
                payment_ref = line.payment_id
                
                if s.collection_type == 'collect':
                    payment_ = payment.create({
                        'paymentType': 'collection',
                        'cash_cheque_selection': line.cash_cheque_selection,
                        'bank_id': line.drc_bank_id.bank_id.id if line.cash_cheque_selection == 'cheque' else None,
                        'check_number': line.drc_bank_id.name if line.cash_cheque_selection == 'cheque' else None,
                        'check_date': line.drc_bank_id.date_issued if line.cash_cheque_selection == 'cheque' else None,
                        'collection_id': s.id,
                        'collected_mm_id': line.id,
                        'or_reference': line.or_reference,
                        'journal_id': line.journal_id.id,
                        'amount': line.amount_paid,
                        'amount_tender': line.amount_paid,
                        'amount_received': line.amount_paid,
                        'payment_difference_handling': 'open',
                        'payment_date': line.setdate,
                        'payment_record_type':'collect',
                        # 'payment_date': line.date,
                        'partner_type': 'customer',
                        'payment_type': 'inbound',
                        'communication': line.service_id.name,
                        'partner_id': line.partner_ids.id,
                        'user_id': s.collector_id.id,
                        'payment_method_id': 1,
                        'has_invoices': False,
                    })
                    payment_ref = payment_
                    payment_.post()

                line.write({
                        'state': 'confirmed',
                        'payment_id': payment_ref.id
                })

            s.state = 'confirm'
            # pass


        return True
        # self.state = 'confirm'

    @api.multi
    def show_payments(self):
        payment = self.env['account.payment']
        payment_ = payment.search([('collection_id', '=', self.id)])
        return {
            'name': "Payment",
            'res_model': 'account.payment',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'view_id': False,
            'view_type': 'form',
            'domain': [('id', 'in', payment_.ids)]
        }


class CashConfig(models.Model):
    _inherit = 'cash.count.temp'

    dcr_id = fields.Many2one('daily.collection.record')



# class CollectionReports(models.TransientModel):
#     _name="brdc.collection.reports"

     
