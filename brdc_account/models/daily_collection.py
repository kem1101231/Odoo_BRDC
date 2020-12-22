from odoo import api, fields, models
import datetime

class DailyCollection(models.TransientModel):
    _name = 'daily.collection'

    collector = fields.Many2one('res.users')
    barangay_id = fields.Many2one('config.barangay')
    date = fields.Date(required=False, default=fields.Date.today())
    payment_list = fields.Many2many('collection.list')
    collection_ids = fields.One2many(comodel_name="collection.list", inverse_name="collectionlist_ids", string="", required=False, )

    @api.multi
    def get_payment_schedule(self):
        partner = self.env['res.partner']
        dp = self.env['invoice.installment.line.dp']
        ins = self.env['invoice.installment.line']
        listofpayment = []
        partner_list = partner.search([('barangay_id', '=', self.barangay_id.id)]).id
        currentPaymentDP = dp.search([('customer_id','=',partner_list),('date_for_payment','<=', self.date),('is_paid','=',False)])
        currentPaymentI = ins.search([('customer_id','=',partner_list),('date_for_payment','<=', self.date),('is_paid','=',False)])

        dplist = []
        ilist = []
        for cdp in currentPaymentDP:
            dplist.append(['[DOWNPAYMENT] %s' % cdp.account_invoice_id.number,cdp.customer_id.name,cdp.date_for_payment,cdp.amount_to_pay])
        for ci in currentPaymentI:
            ilist.append(['[AMORTIZATION] %s' % ci.account_invoice_id.number, ci.customer_id.name, ci.date_for_payment, ci.amount_to_pay])


        for dpl in dplist:
            listofpayment.append(dpl)
        for il in ilist:
            listofpayment.append(il)

        # print listofpayment
        self.env['collection.list'].search([('collectionlist_ids', '=', self.id)]).unlink()
        for lop in listofpayment:
            self.env['collection.list'].create({
                'description': lop,
                'number': lop[0],
                'name': lop[1],
                'date': lop[2],
                'amount': lop[3],
                'collectionlist_ids': self.id
            })

        return True


    @api.multi
    def gen_rep(self):
        self.get_payment_schedule()
        return self.env['report'].get_action(self, 'brdc_account.daily_collection_report_template')


class collectionlist(models.TransientModel):
    _name = 'collection.list'

    description = fields.Text(required=False, )
    number = fields.Text(required=False, )
    name = fields.Text(required=False, )
    date = fields.Text(required=False, )
    amount = fields.Text(required=False, )
    collectionlist_ids = fields.Many2one('daily.collection')


