from odoo import api, fields, models, _


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    def compute_general_aging(self):
        active_ai = self.env['account.invoice'].search([('state', 'in', ['open', 'terminate']),
                                                        ('purchase_term', '=', 'install'),
                                                        # ('monthly_due', '>=', 1)
                                                        ]
                                                       )
        total_paid = 0.0
        invoice_id = None
        monthly_payment = 0.0
        total_due = 0.0
        aging = self.env['general.aging.list'].search([])
        aging.unlink()
        for rec in active_ai:
            invoice_id = rec.id
            total_paid = rec.total_paid
            total_due = rec.monthly_due
            monthly_payment = rec.monthly_payment

            quotient = total_due / monthly_payment
            due_current = 0.0
            due_30 = 0.0
            due_60 = 0.0
            due_90 = 0.0
            due_over_90 = 0.0

            
            # for_30 = 0
            # for_60 = 0
            # for_90 = 0
            # for_91 = 0

            # payment_sched = self.env['invoice.installment.line'].search([('account_invoice_id','=', invoice_info.id), ('date_for_payment','<=', date_range),('is_paid','=',False)])
            
            # for line in payment_sched:
            #     dfp = datetime.strptime(line.date_for_payment, "%Y-%m-%d")
            #     diff_in_days = abs((datetime.today() - dfp).days)
                
            #     if not datetime(int(date.today().year), int(date.today().month),1) < dfp < date_range:

            #         if diff_in_days <= 30:
            #             for_30 = for_30 + line.amount_to_pay
            #         if diff_in_days <= 60 and diff_in_days >= 31:
            #             for_60 = for_60 + line.amount_to_pay
            #         if diff_in_days <= 90 and diff_in_days >= 61:
            #             for_90 = for_90 + line.amount_to_pay
            #         if diff_in_days >= 91:
            #             for_91 = for_91 + line.amount_to_pay

            if quotient < 2:
                print "has current"
                due_current = monthly_payment if total_due >= 1 else 0.0
            elif quotient < 3:
                print "has 30"
                due_current = monthly_payment if total_due >= 1 else 0.0
                due_30 = due_current
            elif quotient < 4:
                print "has 60"
                due_current = monthly_payment if total_due >= 1 else 0.0
                due_30 = due_current
                due_60 = due_current
            elif quotient < 5:
                print "has 90"
                due_current = monthly_payment if total_due >= 1 else 0.0
                due_30 = due_current
                due_60 = due_current
                due_90 = due_current
            elif quotient >= 5:
                print "over 90"
                due_current = monthly_payment if total_due >= 1 else 0.0
                due_30 = due_current
                due_60 = due_current
                due_90 = due_current
                due_over_90 = total_due - (due_current * 4)
            else:
                print "no due"

            aging.create({
                'invoice_id': rec.id,
                'partner_id': rec.partner_id.id,
                'doc_date': rec.date_invoice,
                'amount_total': rec.amount_total,
                'paid_total': total_paid,
                'balance': rec.amount_total - total_paid,
                'due_total': total_due,
                'due_current': due_current,
                'due_30': due_30,
                'due_60': due_60,
                'due_90': due_90,
                'due_over_90': due_over_90,
                'days_passed': 0.0,
            })

            # print invoice_id, total_paid


# class DueLines(models.Model):
#     _name = "aging.due.line"
#
#     due_30 = fields.Float('1-30Days')
#     due_30_date = fields.Float('1-30Days Date')
#     due_60 = fields.Float('31-60Days')
#     due_60_date = fields.Float('31-60Days Date')
#     due_90 = fields.Float('61-90Days')
#     due_90_date = fields.Float('61-90Days Date')
#     due_over_90 = fields.Float('91Days Over')
#     due_over_90_date = fields.Float('91Days Over Date')


class CollectorAgingList(models.Model):
    _name = "general.aging.list"

    invoice_id = fields.Many2one('account.invoice', 'Invoice Reference')
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
    collector = fields.Many2one('res.partner', 'Collector')


class CollectionLine(models.TransientModel):
    _name = 'collection.line'

    invoice_id = fields.Many2one('account.invoice', 'Reference')
    service_id = fields.Many2one('service.order', 'Reference')
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
    collection_aging_id = fields.Many2one('collector.aging')
    collection_aging_mm_id = fields.Many2one('collector.aging.mm')

    @api.depends('partner_id')
    def _get_address(self):
        for s in self:
            s.address = s.partner_id.street_b

    address = fields.Text(string='Billing Address', compute=_get_address)


class CollectorAging(models.TransientModel):
    _name = 'collector.aging'

    type = fields.Selection(string='Type', selection=[('general', 'General Aging'), ('collection', 'Per Collector'), ('product', 'Per Product')], default='general')
    collector_id = fields.Many2one('res.partner', 'Collector')
    date = fields.Datetime(string='Date', default=fields.Datetime.now())
    area_id = fields.Many2many(comodel_name="config.barangay", string="Area")

    # collection_line_ids = fields.One2many(comodel_name="collection.line", inverse_name="collection_aging_id", string="", required=False, default=lambda self:self._get_items())
    
    collection_line_ids = fields.One2many(comodel_name="collection.line", inverse_name="collection_aging_id", string="", required=False)
    product_type = fields.Many2one('payment.config', domain=[('is_parent', '=', True)])

    # @api.multi
    # def _get_items(self):
    #     return self.env['collection.line'].search([('invoice_id.state','in','["open","terminate"]')], order='invoice_id.month_due desc')


    @api.onchange('collector_id')
    def _collector_area(self):
        if self.collector_id:
            barangay_id_b = self.collector_id.barangay_id_b
            self.area_id = self.env['config.barangay'].search([('id','=',barangay_id_b.id)])
            print(self.area_id)

    # @api.onchange('area_id')
    # def _area_collector(self):
    #     if self.area_id:
    #         self.collector_id = self.env['res.partner'].search('brangay_id_b.id','in',self.area_id)
    #


class CollectorAgingMM(models.TransientModel):
    _name = 'collector.aging.mm'
    _inherit = 'collector.aging'

    collection_line_mm_ids = fields.One2many(comodel_name="collection.line", inverse_name="collection_aging_mm_id", string="",
                                          required=False, )






