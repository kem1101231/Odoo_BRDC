from odoo import api, fields, models, _


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    realize_entry_id = fields.Many2one('account.move', 'Realized Entry', readonly=1)

    @api.multi
    def realized_entry(self):
        invoice = self.env['account.invoice'].browse(self._context.get('active_ids', []))
        for rec in self:
            if invoice:
                move_line = []
                if invoice.purchase_term == 'install':
                    account = None
                    for cost in invoice.cost_of_sale_id.line_ids:
                        if cost.is_debit:
                            account = cost.account_id
                    for line in rec.move_line_ids:
                        move_line.append((0, 0, {
                            'partner_id': line.partner_id.id,
                            'journal_id': line.journal_id.id,
                            'date': line.date,
                            'name': account.name if line.balance > 0 else self.env['account.account'].search([('code', '=', '15971003642700')]).name,
                            'company_id': line.company_id.id,
                            'account_id': account.id if line.balance > 0 else self.env['account.account'].search([('code', '=', '15971003642700')]).id,
                            'debit': line.debit,
                            'credit': line.credit,
                            'balance': line.balance,
                            'quantity': line.quantity,
                            'date_maturity': line.date_maturity,
                            'company_currency_id': line.company_currency_id.id,
                            'invoice_id': line.invoice_id.id,
                            'is_debit': True if line.balance > 0 else False,
                            'is_credit': True if line.balance < 0 else False,
                        }))

                    move = self.env['account.move']
                    move.search([('id', '=', rec.realize_entry_id.id)]).button_cancel()
                    move.search([('id', '=', rec.realize_entry_id.id)]).unlink()

                    vals = {
                        'name': invoice.number.replace('INV', 'RGP'),
                        'company_id': invoice.company_id.id,
                        'currency_id': invoice.currency_id.id,
                        'partner_id': invoice.partner_id.id,
                        'journal_id': invoice.journal_id.id,
                        'ref': invoice.number,
                        'date': invoice.date_invoice,
                        'line_ids': move_line
                    }

                    real = move.create(vals)
                    real.post()
                    self._cr.execute("""
                                        update account_payment set realize_entry_id = %s where id = %s
                                        """ % (real.id, rec.id))
                    self._cr.commit()

                pass
