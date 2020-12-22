from odoo import api, fields, models


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'
    _rec_name = 'pa_ref'


class SoaTransient(models.TransientModel):
    _name = 'report.soa'

    @api.multi
    def invoice_domain(self):

        return [('partner_id', '=', self.partner_id.id)]

    partner_id = fields.Many2one('res.partner', 'Customer')
    @api.onchange('partner_id')
    def parnter_change(self):
        self.invoice_id = None
    invoice_id = fields.Many2one('account.invoice', 'Invoice', domain="[('partner_id', '=', partner_id)]")

    @api.depends('invoice_id')
    def _get_amount(self):
        for s in self:
            s.amount_paid = s.invoice_id.total_paid
            s.due = s.invoice_id.monthly_due
            s.surcharge = s.invoice_id.surcharge
            s.total_due = s.due + s.surcharge
            s.pa_ref = s.invoice_id.pa_ref

    amount_paid = fields.Float('Amount Paid', compute=_get_amount)
    due = fields.Float('Due', compute=_get_amount)
    surcharge = fields.Float('Surcharge', compute=_get_amount)
    total_due = fields.Float('Total Due', compute=_get_amount)
    pa_ref = fields.Char('Purchase Agreement', compute=_get_amount)
    payment_ids = fields.Many2many(comodel_name="account.payment", string="", )
    soa_line = fields.One2many(comodel_name="report.soa.line", inverse_name="soa_id", string="SOA Line", required=False, )
    type = fields.Selection(string="type", selection=[('soa', 'Statement of Account'), ('led', 'Customer Ledger'), ], required=False, )

    @api.multi
    def check_report(self):
        data = {}
        data['form'] = self.read(['partner_id', 'invoice_id'])[0]
        self.payments()
        return self._print_report(data)

    @api.depends('invoice_id')
    def payments(self):
        soa_line = self.env['report.soa.line']
        soa_line.search([]).unlink()
        ids = []
        payment_ids = []
        payments = []
        date = []
        or_ref = []
        description = []
        amount = 0.0
        # balance = []
        for am in self.invoice_id.move_id:
            for aml in am.line_ids:
                if aml.account_id.reconcile:
                    ids.extend(
                        [r.debit_move_id.id for r in aml.matched_debit_ids] if aml.credit > 0 else [r.credit_move_id.id
                                                                                                    for r in
                                                                                                    aml.matched_credit_ids])
                    ids.append(aml.id)
        move_line = self.env['account.move.line'].search([('id', 'in', ids)])
        for ml in move_line:
            payment_ids.append(ml.payment_id.id)
            payments.append(ml.payment_id.amount)
            date.append(ml.payment_id.payment_date)
            or_ref.append(ml.payment_id.or_reference)
            description.append(ml.payment_id.journal_id.name)

        amount = self.invoice_id.amount_total

        # self.payment_ids = [(6, 0, payment_ids)]
        rec = None
        for x in range(0, len(payments)):
            amount -= payments[x]
            if payment_ids[x]:
                rec = soa_line.create({
                    'soa_id': self.id,
                    'payment_id': payment_ids[x],
                    'amount': payments[x],
                    'date': date[x],
                    'or_ref': or_ref[x],
                    'description': description[x],
                    'balance': amount,
                })
        # self.update({
        #     'payment_ids': [(6, 0, payment_ids)]
        # })

        return True

    def _print_report(self, data=None):
        data['form'].update(self.read(['partner_id', 'invoice_id'])[0])
        return self.env['report'].get_action(self, 'brdc_account.soa_details', data=data)


class SoaLine(models.TransientModel):
    _name = 'report.soa.line'

    soa_id = fields.Many2one('report.soa', 'soa')
    payment_id = fields.Many2one('account.payment', 'Payment')
    amount = fields.Float('Payment')
    date = fields.Date('Date')
    or_ref = fields.Char('ORNo.')
    description = fields.Text('Description')
    balance = fields.Float('Balance')

class ReportSoaDetails(models.AbstractModel):
    _name = 'report.brdc_account.soa_details'

    @api.model
    def render_html(self, docids, data=None):
        self.model = self.env.context.get('active_model')
        docs = self.env[self.model].browse(self.env.context.get('active_id'))
        installment_line_ids = self.env['invoice.installment.line'].search(
            [('account_invoice_id', '=', docs.invoice_id.id)]
        )
        payment_ids = self.env['account.payment']
        soa_lines = []
        amort_lines = []
        payment_lines = []

        for i_line in installment_line_ids:
            amort_lines.append(i_line)



            docargs = {
                'doc_ids': self.ids,
                'doc_model': self.model,
                'docs': docs,
                # 'amort_lines': amort_lines,
                'payment_ids': docs.payment_ids,
                'invoice_id': docs.invoice_id,
                'pa_ref': docs.invoice_id.pa_ref,
                'partner_id': docs.partner_id,
                'monthly_due': docs.invoice_id.monthly_payment,
                'amort_start': docs.invoice_id.date_invoice,
            }

            print docs.payment_ids
            return self.env['report'].render('brdc_account.soa_details', docargs)

