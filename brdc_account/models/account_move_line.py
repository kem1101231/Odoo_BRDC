from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    installment_line_id = fields.Many2one('invoice.installment.line')
    downpayment_line_id = fields.Many2one('invoice.installment.line.dp')


# custom journal entry
class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    custom_account_id = fields.Many2one('account.move', 'BRDC Journal Entry', readonly=1)

    @api.multi
    def update_move_id_asddddd(self):
        invoices = self.env['account.invoice'].search([('state', 'in', ['open', 'paid'])]) or self.filtered(
            lambda res: res.state in ['open', 'paid'])
        for rec in invoices:
            # print rec.pa_ref
            move_id = rec.move_id
            pcf = self.env['account.move.line'].search([('move_id', '=', move_id.id), ('is_pcf', '=', True)])
            credit = self.env['account.move.line'].search(
                [('move_id', '=', move_id.id), ('is_credit', '=', True)]).filtered(lambda res: res.balance < 0)
            if move_id.state == 'draft':
                print move_id.name
                move_id.post()
            if rec.purchase_term == 'install' and rec.product_type.name == 'Lot' and rec.pa_ref and rec.amount_total != 0.0:
                account_id = self.env['account.account'].search([('code', '=', '15971000202800')])
                name = 'Unrealized Gross Profit'
            # if pcf or credit:
            # # if pcf or credit:
                print move_id.name
                self._cr.execute("""
                                update account_move_line set account_id = %s, name = '%s' where id = %s
                                """ % (account_id.id, name, credit.id)
                                 )
                self._cr.commit()
                # move_id.button_cancel()
                # self._cr.execute("""
                # update account_move_line set debit = %s, credit = %s, balance = %s where id = %s
                # """ % (round(credit.debit + pcf.debit, 2), round(credit.credit + pcf.credit, 2), round(credit.balance + pcf.balance, 2), credit.id)
                # )
                # self._cr.commit()
                #
                # self._cr.execute("""
                #                 delete from account_move_line where id = %s
                #                 """ % pcf.id)
                # self._cr.commit()
                # move_id.post()
                pass

    def update_move_id_posttt(self):
        invoices = self.env['account.invoice'].search([('state', 'in', ['open', 'paid'])]) or self.filtered(
            lambda res: res.state in ['open', 'paid'])
        for rec in invoices:
            print rec.pa_ref
            move_id = rec.move_id
            credit = 0.0
            debit = 0.0
            if move_id.state == 'draft':
                for line in move_id.line_ids:
                    debit += line.debit if line.balance > 0 else False
                    credit += line.credit
                print debit, credit
                # if debit == credit:
                #     move_id.post()

    @api.multi
    def create_journal_entry(self):
        # invoices = self.env['account.invoice'].search([('state', 'in', ['open', 'paid'])]) or self.filtered(
        #     lambda res: res.state in ['open', 'paid'])
        invoices = self.env['account.invoice'].search([
            ('state', 'in', ['open', 'paid']),
            # ('purchase_term', '=', 'cash'),
            ('purchase_term', '=', 'install')
            ('custom_account_id', '=', False),
            ('amount_total', '!=', 0.0)
        ]) \
        #            or self.filtered(
        #     lambda res: res.state in ['open', 'paid'] and
        #     res.purchase_term == 'cash' and
        #     not res.custom_account_id and
        #     not res.amount_total
        # )
        print len(invoices), 'create_journal_entry'
        for rec in invoices:
        # for rec in self.filtered(lambda res: res.state in ['open', 'paid']):
            rec.ensure_one()
            move_line = []
            move = self.env['account.move']
            move_id = rec.move_id
            print rec.pa_ref
            if rec.product_type.category != 'service':
                print 'create_journal_entry'
                def getPCF(invoice):
                    for inv in invoice:
                        pcf = 0 - inv.pcf
                        account_id = None
                        for lines in inv.invoice_line_ids[0]:
                            if lines.product_id.pcf_account_id and lines.product_id.type == 'product':
                                account_id = lines.product_id.pcf_account_id

                        return {
                            'amount': pcf,
                            'account_id':  account_id
                        }

                sequence = 1
                if getPCF(rec)['account_id']:
                    for line in move_id.line_ids:
                        if not line.is_tax:
                            if line.balance != 0:
                                move_line.append((0, 0, {
                                    'partner_id': line.partner_id.id,
                                    'journal_id': line.journal_id.id,
                                    'date': line.date,
                                    'name': line.name,
                                    'company_id': line.company_id.id,
                                    'account_id': line.account_id.id,
                                    'debit': line.debit,
                                    'credit': line.credit + getPCF(rec)['amount'] if line.balance < 0 else 0,
                                    'balance': line.balance - getPCF(rec)['amount'] if line.balance < 0 else 0,
                                    'quantity': line.quantity,
                                    'date_maturity': line.date_maturity,
                                    'company_currency_id': line.company_currency_id.id,
                                    'invoice_id': line.invoice_id.id,
                                    'is_debit': line.is_debit,
                                    'is_credit': line.is_credit,
                                    'sequence': sequence
                                }))
                                sequence += 1
                        elif line.is_tax:
                            move_line.append((0, 0, {
                                'partner_id': line.partner_id.id,
                                'journal_id': line.journal_id.id,
                                'date': line.date,
                                'name': line.name,
                                'company_id': line.company_id.id,
                                'account_id': line.account_id.id,
                                'credit': line.credit,
                                'balance': line.balance,
                                'quantity': line.quantity,
                                'date_maturity': line.date_maturity,
                                'company_currency_id': line.company_currency_id.id,
                                'invoice_id': line.invoice_id.id,
                                'is_tax': True,
                                'sequence': 4
                            }))
                        pass
                    move_line.append((0, 0, {
                        'partner_id': rec.partner_id.id,
                        'journal_id': rec.journal_id.id,
                        'date': rec.date_invoice,
                        'name': 'Perpetual Care Payable',
                        'company_id': rec.company_id.id,
                        'account_id': getPCF(rec)['account_id'].id,
                        'credit': getPCF(rec)['amount'] * -1,
                        'balance': getPCF(rec)['amount'],
                        'quantity': 1,
                        'date_maturity': rec.date_invoice,
                        'company_currency_id': rec.company_id.currency_id.id,
                        'invoice_id': rec.id,
                        'is_pcf': True,
                        'sequence': 3
                    }))
                    print move_line
                    rec.custom_move(move, rec, move_line)
                else:
                    pass

    def custom_move(self, move, invoice, lines):
        move.search([('id', '=', self.custom_account_id.id)]).button_cancel()
        move.search([('id', '=', self.custom_account_id.id)]).unlink()
        vals = {
            'name': invoice.number.replace('INV', 'BRDC'),
            'company_id': invoice.company_id.id,
            'currency_id': invoice.currency_id.id,
            'partner_id': invoice.partner_id.id,
            'journal_id': invoice.journal_id.id,
            'ref': invoice.number,
            'date': invoice.date_invoice,
            'line_ids': lines
        }
        # custom_move = move.search([])
        print vals
        custom = move.create(vals)

        custom.post()
        self._cr.execute("""
                    update account_invoice set custom_account_id = %s where id = %s
                    """ % (custom.id, invoice.id))
        self._cr.commit()
