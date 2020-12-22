from odoo import api, fields, models
from dateutil.relativedelta import relativedelta
from datetime import date, datetime
import numpy as np
import calendar
from collections import defaultdict
import itertools


class CollectionEfficiencyLine(models.Model):
    _name = 'collection.efficiency.line'
    _order = 'doc_date'

    invoice_id = fields.Many2one('account.invoice', 'Reference')
    partner_id = fields.Many2one('res.partner', 'Customer')
    doc_date = fields.Date('Doc. Date')
    amount_total = fields.Float('Contract Price')
    paid_total = fields.Float('Accumulated Payment')
    balance = fields.Float('Balance')
    due_total = fields.Float('Due')
    due_current = fields.Float('Current')
    due_current_date = fields.Date('Current Date')
    due_30 = fields.Float('1-30Days')
    due_30_date = fields.Date('1-30Days Date')
    due_60 = fields.Float('31-60Days')
    due_60_date = fields.Date('31-60Days Date')
    due_90 = fields.Float('61-90Days')
    due_90_date = fields.Date('61-90Days Date')
    due_over_90 = fields.Float('91Days Over')
    due_over_90_date = fields.Date('91Days Over Date')
    days_passed = fields.Float('Days Passed')
    collection_efficiency_id = fields.Many2one('collection.efficiency')
    past_due = fields.Float('Past Due')

    @api.depends('partner_id')
    def _get_address(self):
        for s in self:
            s.address = s.partner_id.street_b

    address = fields.Text(string='Billing Address', compute=_get_address)


class CollectionEfficiencyLineMM(models.Model):
    _name = 'collection.efficiency.line.mm'
    _inherit = 'collection.efficiency.line'

    service_id = fields.Many2one('service.order', 'Reference')
    product_id = fields.Many2one('product.product', 'Product')


class CollectionEfficiencyPayments(models.Model):
    _name = 'collection.efficiency.payments'

    payment_id = fields.Many2one('account.payment')
    user_id = fields.Many2one('res.users')
    amount = fields.Float('amount')
    collection_efficiency_id = fields.Many2one('collection.efficiency')
    date_paid = fields.Date(related="payment_id.payment_date")
    state = fields.Char()
    partner_id = fields.Many2one('res.partner', related='payment_id.partner_id')
    invoice_id = fields.Many2one('account.invoice', compute='get_invoice')

    @api.model
    def get_invoice(self):
        for rec in self:
            invoice = self.env['account.invoice'].search([('number', '=', rec.payment_id.communication)])
            rec.invoice_id = invoice.id



class CollectionPerformance(models.Model):
    _name = 'collection.performance'
    _order = 'date'

    date = fields.Date('Date')
    partner_id = fields.Many2one('res.partner', 'Customer')
    current = fields.Float('Current')
    past = fields.Float('Past Due')
    invoice_id = fields.Many2one('account.invoice', 'Reference')
    description = fields.Char('Reference')
    collection_efficiency_id = fields.Many2one('collection.efficiency')


class CollectionPerformanceTotal(models.Model):
    _name = 'collection.performance.total'
    _order = 'date'

    date = fields.Date('Date')
    current = fields.Float('Current')
    past = fields.Float('Past Due')
    collection_efficiency_id = fields.Many2one('collection.efficiency')


class CollectionEfficiency(models.Model):
    _name = 'collection.efficiency'
    _sql_constraints = [
        ('name_uniq', 'UNIQUE(name)', 'Collection Efficiency record is already existing!')
    ]
    _order = 'current_month, year'

    name = fields.Char()
    def default_month(self):
        now = datetime.now()
        return int(now.month)
    current_month = fields.Selection([(1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
                          (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
                          (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'), ],
                          string='Month', default=default_month)

    @api.model
    def get_years(self):
        year_list = []
        for i in range(2016, 2036):
            year_list.append((i, str(i)))
        return year_list

    def default_year(self):
        now = datetime.now()
        return int(now.year)

    # year = fields.Selection(get_years, string='Year', default=default_year)
    year = fields.Char(default=default_year)

    collector_id = fields.Many2one('res.partner', string='Collector')
    user_id = fields.Many2one('res.users', compute="get_user", store=True)

    @api.depends('collector_id')
    def get_user(self):
        for rec in self:
            res_user = self.env['res.users'].search([('partner_id', '=', rec.collector_id.id)])
            rec.user_id = res_user.id

    area_id = fields.Many2many(comodel_name="config.barangay", string='Area')

    collection_efficiency_line_ids = fields.One2many(comodel_name="collection.efficiency.line", inverse_name="collection_efficiency_id", string="Collection Efficiency Lawn Lots", required=False)
    collection_efficiency_line_mm_ids = fields.One2many(comodel_name="collection.efficiency.line.mm", inverse_name="collection_efficiency_id", string="Collection Efficiency MM", required=False)

    payment_line_ids = fields.One2many(comodel_name='collection.efficiency.payments', inverse_name="collection_efficiency_id", compute='get_payments')

    collection_performance_ids = fields.One2many(comodel_name='collection.performance', inverse_name='collection_efficiency_id', string='Collection Performance')
    collection_performance_total_ids = fields.One2many(comodel_name='collection.performance.total', inverse_name='collection_efficiency_id', string='Collection Performance')
    payment_line1_ids = fields.Many2many('account.payment', compute="get_payments")

    @api.model
    def get_payments(self):
        for rec in self:
            if rec.state != 'draft':
                partner_ids = [];descriptions = [];numbers = [];names = []
                month = rec.current_month
                year = rec.year
                date_ = calendar.monthrange(int(year), int(month))[1]
                start_date = "%s-%s-1" % (int(year), int(month))
                end_date = "%s-%s-%s" % (int(year), int(month), int(date_))
                d1 = datetime.strptime(start_date, '%Y-%m-%d')
                d2 = datetime.strptime(end_date, '%Y-%m-%d')

                print d1, '-', d2, 'get_payments'
                for line in rec.collection_performance_ids:
                    if line.partner_id.id not in partner_ids:
                        partner_ids.append(line.partner_id.id)
                    descriptions.append(line.description)

                invoices = self.env['account.invoice'].search([('pa_ref', 'in', descriptions)])
                for invoice in invoices:
                    if invoice.number not in numbers:
                        numbers.append(invoice.number)
                services = self.env['service.order'].search([('name', 'in', descriptions)])
                for service in services:
                    if service.name not in names:
                        names.append(service.name)
                res_user = self.env['res.users'].search([('partner_id', '=', rec.collector_id.id)])
                payments = self.env['account.payment'].search([('user_id', '=', rec.user_id.id),
                                                               ('state', '=', 'posted'),
                                                               ('partner_id', 'in', partner_ids),
                                                               ('communication', 'in', numbers or names)
                                                               ]).filtered(
                lambda r: (r.payment_date >= d1.strftime('%Y-%m-%d')) and
                          (r.payment_date <= d2.strftime('%Y-%m-%d'))
                )
                payment_list = []
                total_payment = 0.0
                collection_current = []
                collection_past = []
                for payment in payments:
                    payment_list.append({
                                        'communication': payment.communication,
                                        'amount': payment.amount
                                        })
                for k,v in itertools.groupby(payment_list,key=lambda x:x['communication']):
                    total_payment = sum(int(d['amount']) for d in v)
                    # total_payment += (d['amount'] for d in v)
                    print k, total_payment, 'total_payment'
                    invoices = self.env['account.invoice'].search([('number', '=', k)])
                    services = self.env['service.order'].search([('name', '=', k)])
                    target = self.env['collection.performance'].search(
                        [('description', '=', invoices.pa_ref or services.name), ('collection_efficiency_id', '=', rec.id)])
                    print target, 'target'
                    if target.past >= total_payment:
                        collection_past.append(total_payment)
                    else:
                        collection_current.append(total_payment - target.past)

                rec.collection_past = sum(collection_past)
                rec.collection_current = sum(collection_current)
                rec.payment_line1_ids = payments.ids
            else:
                pass

    due_total = fields.Float('Total Due', compute='compute_collectibles_total')
    due_current = fields.Float('Current', compute='compute_collectibles_total')
    collectibles_total = fields.Float(string="Total Collectibles", compute='compute_collectibles_total')
    collected_total = fields.Float(string="Total Collection")

    state = fields.Selection(string="", selection=[('draft', 'Draft'), ('ready', 'Ready for Collection'), ('confirm', 'Confirmed')], required=False, default='draft')

    @api.depends('collection_performance_total_ids', 'payment_line1_ids')
    def _get_total(self):
        for rec in self:
            total_collection = 0.0
            current = sum(line.current for line in rec.collection_performance_total_ids)
            past = sum(line.past for line in rec.collection_performance_total_ids)
            total_target = current + past
            # rec.total_target = total_target

            # rec.total_collection = total_collection
            collection_efficiency = self.env['collection.efficiency.payments'].search([('collection_efficiency_id', '=', rec.id)])
            # if collection_efficiency:
            total_collection = sum(line.amount for line in rec.payment_line1_ids)

            rec.update({
                'past_due': past,
                'current_due': current,
                'total_target': total_target,
                'total_collection': total_collection,
            })
    past_due = fields.Float(compute=_get_total)
    current_due = fields.Float(compute=_get_total)
    collection_past = fields.Float(compute=get_payments)
    collection_current = fields.Float(compute=get_payments)
    total_target = fields.Float(compute=_get_total)
    total_collection = fields.Float(compute=_get_total)

    @api.multi
    def state_ready(self):
        for rec in self:
            if rec.state == 'draft':
                rec.state = 'ready'

    def state_confirm(self):
        for rec in self:
            if rec.state == 'ready':
                rec.state = 'confirm'

    def state_draft(self):
        for rec in self:
            if rec.state in ['confirm', 'ready']:
                rec.state = 'draft'

    def compute_collectibles_total(self):
        for rec in self:
            total_due = 0.0
            total_current = 0.0
            past_due = 0.0
            month = rec.current_month
            year = rec.year
            start_date = "%s-%s-1" % (int(year), int(month))
            d1 = datetime.strptime(start_date, '%Y-%m-%d')
            num = 0
            if rec.collection_efficiency_line_ids:
                for line in rec.collection_efficiency_line_ids:
                    if line.due_current_date < d1.strftime('%Y-%m-%d'):
                        past_due += line.due_current
                    else:
                        total_current += line.due_current
                    total_due += line.due_total
                    print num
                    num += 1
                rec.collectibles_total = total_due - total_current
            #
            #     total_due = sum(line.due_total for line in rec.collection_efficiency_line_ids)
            #     total_current = sum(line.due_current for line in rec.collection_efficiency_line_ids)
            #     rec.collectibles_total = total_due - total_current
            # else:
            #     rec.collectibles_total = total_due - total_current

            rec.due_total = total_due
            rec.due_current = total_current

    @api.onchange('collector_id', 'current_month', 'year')
    def default_name(self):
        for rec in self:
            month = dict(self._fields['current_month'].selection).get(self.current_month)
            rec.name = "Target of %s for the month [%s] and year [%s]" % (rec.collector_id.name, month, rec.year)
        pass

    @api.multi
    def compute_general_efficiency(self):
        active_ai = None
        month = self.current_month
        year = self.year

        def get_due(ref_id):
            date_ = calendar.monthrange(int(year), int(month))[1]
            end_date = "%s-%s-%s" % (int(year), int(month), int(date_))
            d2 = datetime.strptime(end_date, '%Y-%m-%d')
            total_due = 0.0
            total_paid = ref_id.total_paid
            amounts = []
            ids = []
            installment_line = self.env['invoice.installment.line'].search([('account_invoice_id', '=', ref_id.id)])
            for line in installment_line:
                amounts.append(line.amount_to_pay)
                if sum(amounts) <= total_paid:
                    ids.append(line.id)
            due_list = installment_line.filtered(
                lambda lines: (lines.id not in ids) and (lines.date_for_payment <= d2.strftime('%Y-%m-%d')))
            sched_ = installment_line.filtered(lambda lines: lines.date_for_payment <= d2.strftime('%Y-%m-%d'))
            sched_count = len(sched_) - 1
            for _list in due_list:
                total_due += _list.amount_to_pay
            return {
                'total_due': total_due,
                'month_to_pay': datetime.strptime(ref_id.date_invoice, '%Y-%m-%d') + relativedelta(months=sched_count),
                'total_paid': total_paid
            }

        self._cr.execute("""select a.id
                        from account_invoice as a  
                        join account_invoice_line as b
                        on a.id = b.invoice_id
                        join res_partner as c
                        on c.id = a.partner_id
                        where a.state = 'open' and a.month_due > 1 and c.barangay_id_b in (%s)
                        order by a.month_due""" % str(self.area_id.ids)[1:-1])
        res = self._cr.fetchall()
        active_ai = self.env['account.invoice'].search([('id', 'in', res)])
        col_per = self.env['collection.performance']
        col_per.search([('collection_efficiency_id', '=', self.id)]).unlink()
        col_per_tot = self.env['collection.performance.total'].search([('collection_efficiency_id', '=', self.id)])
        col_per_tot.unlink()

        # self.get_current('account_invoice_id', active_ai, 'account.invoice')
        # print active_ai.month_due

        if active_ai:
            efficiency = self.env['collection.efficiency.line'].search([('collection_efficiency_id', '=', self.id)])
            efficiency.unlink()
            due_date = None
            total_paid = 0.0
            invoice_id = None
            monthly_payment = 0.0
            total_due = 0.0
            for rec in active_ai:
                invoice_id = rec.id
                # dute_date = datetime.strptime(rec.month_to_pay, '%Y-%m-%d')
                due_date = get_due(rec)['month_to_pay']
                dates = []
                # dute_date = rec.month_to_pay
                total_paid = get_due(rec)['total_paid']
                total_due = get_due(rec)['total_due']
                monthly_payment = rec.monthly_payment

                quotient = total_due / monthly_payment
                due_current = 0.0
                due_current_date = None
                due_30 = 0.0
                due_30_date = None
                due_60 = 0.0
                due_60_date = None
                due_90 = 0.0
                due_90_date = None
                due_over_90 = 0.0
                due_over_90_date = None
                past_due = 0.0
                for q in range(0, int(quotient)):
                    res = due_date - relativedelta(months=q)
                    dates.append(res)

                # print dates

                # def selection_sort(x):
                #     for i in range(len(x)):
                #         swap = i + np.argmin(x[i:])
                #         (x[i], x[swap]) = (x[swap], x[i])
                #     return x
                #
                # selection_sort(dates)
                if dates:
                    print quotient, 'quotient'

                    if quotient < 1 and dates:
                        pass
                    elif quotient < 2 and dates:
                        print "has current"
                        due_current = total_due
                        due_current_date = dates[0]
                    elif quotient < 3 and dates:
                        print "has 30"
                        due_current = monthly_payment if total_due >= 1 else 0.0
                        due_current_date = dates[0]
                        due_30 = total_due - due_current
                        due_30_date = dates[1]
                        past_due = due_30
                    elif quotient < 4 and dates:
                        print "has 60"
                        due_current = monthly_payment if total_due >= 1 else 0.0
                        due_current_date = dates[0]
                        due_30 = due_current
                        due_30_date = dates[1]
                        due_60 = total_due - (due_current * 2)
                        due_60_date = dates[2]
                        past_due = due_30 + due_60
                    elif quotient < 5 and dates:
                        print "has 90"
                        due_current = monthly_payment if total_due >= 1 else 0.0
                        due_current_date = dates[0]
                        due_30 = due_current
                        due_30_date = dates[1]
                        due_60 = due_current
                        due_60_date = dates[2]
                        due_90 = total_due - (due_current * 3)
                        due_90_date = dates[3]
                        past_due = due_30 + due_60 + due_90
                    elif quotient >= 5 and dates:
                        print "over 90"
                        due_current = monthly_payment if total_due >= 1 else 0.0
                        due_current_date = dates[0]
                        due_30 = due_current
                        due_30_date = dates[1]
                        due_60 = due_current
                        due_60_date = dates[2]
                        due_90 = due_current
                        due_90_date = dates[3]
                        due_over_90 = total_due - (due_current * 4)
                        due_over_90_date = dates[-1]
                        past_due = total_due - due_current
                    else:
                        print "no due"

                    if dates:
                        efficiency.create({
                            'invoice_id': rec.id,
                            'partner_id': rec.partner_id.id,
                            'doc_date': rec.date_invoice,
                            'amount_total': rec.amount_total,
                            'paid_total': total_paid,
                            'balance': rec.amount_total - total_paid,
                            'due_total': total_due,
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
                            'collection_efficiency_id': self.id,
                            'past_due': past_due,
                        })
                    else:
                        pass
            self.get_current('collection.efficiency.line', 'collection_efficiency_id')
        else:
            efficiency = self.env['collection.efficiency.line'].search([('collection_efficiency_id', '=', self.id)])
            efficiency.unlink()

        self.compute_general_efficiency_mm()

    def compute_general_efficiency_mm(self):
        month = self.current_month
        year = self.year

        def get_due(ref_id):
            date_ = calendar.monthrange(int(year), int(month))[1]
            end_date = "%s-%s-%s" % (int(year), int(month), int(date_))
            d2 = datetime.strptime(end_date, '%Y-%m-%d')
            total_due = 0.0
            total_paid = ref_id.total_paid
            amounts = []
            ids = []
            installment_line = self.env['invoice.installment.line'].search([('service_order_id', '=', ref_id.id)])
            for line in installment_line:
                amounts.append(line.amount_to_pay)
                if sum(amounts) <= total_paid:
                    ids.append(line.id)
            due_list = installment_line.filtered(
                lambda lines: (lines.id not in ids) and (lines.date_for_payment <= d2.strftime('%Y-%m-%d')))
            sched_ = installment_line.filtered(lambda lines: lines.date_for_payment <= d2.strftime('%Y-%m-%d'))
            sched_count = len(sched_) - 1
            for _list in due_list:
                total_due += _list.amount_to_pay
            return {
                'total_due': total_due,
                'month_to_pay': datetime.strptime(ref_id.order_date, '%Y-%m-%d') + relativedelta(months=sched_count)
            }

        partner_ids = self.env['res.partner'].search([('active', '=', True),
                                                      ('barangay_id_b', 'in', self.area_id.ids)
                                                      ])
        service_ids = self.env['service.order'].search([('state', '=', 'ready'),
                                                        ('partner_id', 'in', partner_ids.ids)]).filtered(
            lambda r: r.total_due > 0
        )


        # self.get_current('service_order_id', service_ids, 'service.order')
        aging = self.env['collection.efficiency.line.mm'].search([])
        aging.unlink()
        if service_ids:
            for rec in service_ids:
                amort = rec.monthly_amort
                due = get_due(rec)['total_due']
                quotient = due / amort

                due_date = get_due(rec)['month_to_pay']
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
                if dates:
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
                        'collection_efficiency_id': self.id
                    })
        self.get_current('collection.efficiency.line.mm', 'collection_efficiency_id')

    def get_current(self, model_ref=None, field_ref=None):
        # invoice = self.env['account.invoice'].search([('id', '=', record)])
        col_per = self.env['collection.performance']
        # col_per.search([('collection_efficiency_id', '=', self.id)]).unlink()
        # for rec in record:
        month = self.current_month
        year = self.year
        date_ = calendar.monthrange(int(year), int(month))[1]
        start_date = "%s-%s-1" % (int(year), int(month))
        sd = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = "%s-%s-%s" % (int(year), int(month), int(date_))
        ed = datetime.strptime(end_date, '%Y-%m-%d')
        model = self.env[model_ref].search([(
            field_ref, '=', self.id
        )])

        if model:
            for rec in model:
                col_per_ = col_per.search([])
                col_per_.create({
                    'date': rec.due_current_date,
                    'partner_id': rec.partner_id.id,
                    'current': rec.due_current,
                    'past': rec.due_total - rec.due_current,
                    'description': rec.invoice_id.pa_ref if rec.invoice_id else rec.service_id.name,
                    'collection_efficiency_id': self.id,
                })

        # installment_line = self.env['invoice.installment.line'].search([(field, '=', rec.id)])


        #     if installment_line:
        #         if 'residual' in self.env[model]._fields:
        #             total_paid = rec.amount_total - rec.residual
        #             print 'residual invoice'
        #         else:
        #             total_paid = rec.total_paid
        #             print 'service order model'
        #         line_array_id = []
        #         last_id = []
        #         result_amount = []
        #         advance_payment_count = 0
        #         a = 0
        #         amount = total_paid
        #         for line in installment_line:
        #             a += (line.payable_balance if line.payable_balance != 0 else line.amount_to_pay)
        #             payments = (line.payable_balance if line.payable_balance != 0 else line.amount_to_pay)
        #
        #             if a <= amount:
        #                 result_amount.append(payments)
        #                 line_array_id.append(line.id)
        #         for i in line_array_id:
        #             last_id.append(i)
        #             advance_payment_count = advance_payment_count + 1
        #
        #         current_due = self.env['invoice.installment.line'].search([
        #             (field, '=', rec.id),
        #             ('id', 'not in', line_array_id)
        #         ]).filtered(
        #             lambda r: (r.date_for_payment >= sd.strftime('%Y-%m-%d')) and
        #                       (r.date_for_payment <= ed.strftime('%Y-%m-%d'))
        #                     )
        #
        #         past_due = self.env['invoice.installment.line'].search([
        #             (field, '=', rec.id),
        #             ('id', 'not in', line_array_id)
        #         ]).filtered(lambda r: r.date_for_payment < sd.strftime('%Y-%m-%d'))
        #         total_current_due = 0
        #         current_payment_date = None
        #         if current_due:
        #             for due in current_due:
        #                 total_current_due += due.amount_to_pay
        #                 current_payment_date = due.date_for_payment
        #
        #         total_past_due = 0
        #         if past_due:
        #             for due in past_due:
        #                 total_past_due += due.amount_to_pay
        #
        #         col_per_ = col_per.search([])
        #         col_per_.create({
        #             'date': current_payment_date,
        #             'partner_id': rec.partner_id.id,
        #             'current': total_current_due,
        #             'past': total_past_due,
        #             'description': rec.name if rec.name else rec.pa_ref,
        #             'collection_efficiency_id': self.id,
        #         })
        self.get_current_total(col_per.search([('collection_efficiency_id', '=', self.id)]))
        # return True

    @api.multi
    def get_current_total(self, record):
        total_current = 0
        col_per_tot = self.env['collection.performance.total'].search([('collection_efficiency_id', '=', self.id)])
        col_per_tot.unlink()
        results = []
        for rec in record:
            results.append((rec.date, rec.current, rec.past))
        res_current = defaultdict(list)
        res_past = defaultdict(list)

        for a, b, c in results:
            res_current[a].append(b)
            res_past[a].append(c)
        col_per_tot_current = self.env['collection.performance.total'].search([])
        for r in res_current:
            print r, sum(res_current[r]), 'current'
            col_per_tot_current.create({
                'date': r,
                'current': sum(res_current[r]),
                'past': 0.0,
                'collection_efficiency_id': self.id,
            })

        for r in res_past:
            col_per_tot_past = self.env['collection.performance.total'].search(
                [('collection_efficiency_id', '=', self.id), ('date', '=', r)])
            print r, sum(res_past[r]), 'past'
            col_per_tot_past.write({
                'past': sum(res_past[r])
            })
        # for r in res_current:
        #     print r, sum(res_current), 'current'


