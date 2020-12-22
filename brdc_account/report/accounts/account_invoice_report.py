from odoo import api, fields, models


class AccountInvoiceStatusLine(models.TransientModel):
    _name = 'account.invoice.status.line'

    invoice_id = fields.Many2one('account.invoice')
    currency_id = fields.Many2one('res.currency', related="invoice_id.currency_id")
    amount_total = fields.Monetary(related="invoice_id.amount_total")
    residual = fields.Monetary(related="invoice_id.residual")
    paid_total = fields.Monetary(related="invoice_id.total_paid")
    state = fields.Selection([
        ('terminated', 'Terminated'),
        ('restructured', 'Restructured'),
        ('reactivated', 'Reactivated')])


class AccountInvoiceStatus(models.TransientModel):
    _name = 'account.invoice.status'

    invoice_line = fields.Many2many('account.invoice.status.line')

    @api.model
    def count_(self, state):
        ids = []
        for line in self.invoice_line:
            if line.state == state:
                ids.append(line)
        return len(ids)

    @api.multi
    def account_status_report(self):
        line = self.env['account.invoice.status.line']
        account_invoice = self.env['account.invoice'].search(['|', '|', ('state', '=', 'terminate'), ('has_terminated', '=', True), ('restructured', '=', True)])
        print account_invoice
        line.search([]).unlink()
        ids = []
        for inv in account_invoice:
            invoice_line = line.create({
                'invoice_id': inv.id,
                'state': 'terminated' if inv.state == 'terminate' else (
                    'restructured' if inv.restructured else 'reactivated'
                )
            })
            ids.append(invoice_line.id)
        self.invoice_line = [(6, 0, ids)]

    def print_(self):
        return self.env['report'].get_action(self, 'brdc_account.invoice_status_template')
