from odoo import api, fields, models
from dateutil.relativedelta import relativedelta
from datetime import date, datetime
import locale


class PartnerSOALedger(models.TransientModel):
    _name = 'partner.soa.ledger'

    type = fields.Selection([('general', 'General'), ('individual', 'Individual')], default='general')
    partner_id = fields.Many2one('res.partner', 'Customer')
    current_year = datetime.now().year
    date_start = fields.Date(default=datetime.strptime('%s-01-01' % current_year, '%Y-%m-%d'), string='Start')
    date_end = fields.Date(default=fields.Date.today(), string='End')

    journal_ids = fields.Many2many('account.journal', string='Journals')
    payment_type = fields.Selection([('draft', 'Draft'), ('posted', 'Posted'), ('reconciled', 'Reconciled')], default='posted', string='Payment Type')
    partner_ids = fields.One2many(comodel_name='partner.soa.ledger.parent', inverse_name='soa_ledger_id')

    @api.multi
    def get_report(self):
        # model = self.env['partner.soa.ledger'].search([('soa_ledger_id', '=', self.id)])
        return self.env['report'].get_action(self, 'brdc_account.partner_soa_ledger_report_template_1')

    def generate(self):
        payments = self.env['account.payment']
        partners = self.env['res.partner']
        print 'start line'
        parents = self.env['partner.soa.ledger.parent'].search([])
        parents.unlink()
        children = self.env['partner.soa.ledger.child'].search([])
        children.unlink()
        print 'end line'
        partner_ids = None
        payment_list = None
        print 'proceed'

        if self.type == 'general':
            partner_ids = partners.search([('active', '=', True)])
        if self.type == 'individual':
            partner_ids = partners.search([('id', '=', self.partner_id.id)])

        for partner in partner_ids:
            payment_list = payments.search([('partner_id', '=', partner.id),
                                            ('state', '=', self.payment_type)]
                                           ).filtered(
                lambda rec: (rec.payment_date >= self.date_start) and (rec.payment_date <= self.date_end)
            )
            if sum(rec.amount for rec in payment_list) != 0:
                parent = parents.create({
                    'soa_ledger_id': self.id,
                    'partner_id': partner.id,
                    'date_start': self.date_start,
                    'date_end': self.date_end,
                    'total_payment': sum(rec.amount for rec in payment_list),
                })
                # print parent.partner_id.name
                for list_ in payment_list:
                    child = children.create({
                        'parent_id': parent.id,
                        'date': list_.payment_date,
                        'invoice': list_.communication,
                        'payment_id': list_.id,
                        'description': list_.journal_id.name,
                        'payment': list_.amount,
                    })
                    # print child.payment, child.description
        print len(payment_list)

        return True


class PartnerSOALedgerChild(models.TransientModel):
    _name = 'partner.soa.ledger.child'
    _order = 'invoice, date'

    parent_id = fields.Many2one('partner.soa.ledger.parent')
    date = fields.Date()
    invoice = fields.Char()
    payment_id = fields.Many2one('account.payment')
    description = fields.Char()
    payment = fields.Float()

    @api.multi
    def get_currency(self, amount=None):
        return '{:20,.2f}'.format(amount)


class PartnerSOALedgerParent(models.TransientModel):
    _name = 'partner.soa.ledger.parent'

    partner_id = fields.Many2one('res.partner')
    soa_ledger_id = fields.Many2one('partner.soa.ledger')
    date_start = fields.Date()
    date_end = fields.Date()
    child_ids = fields.One2many(comodel_name='partner.soa.ledger.child', inverse_name='parent_id', string='Child')
    total_payment = fields.Float()
















