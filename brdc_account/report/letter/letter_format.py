from odoo import api, fields, models, _
from datetime import datetime, date


class PartnerLine(models.TransientModel):
    _name = 'brdc.partner.line'

    invoice_id = fields.Many2one(comodel_name='account.invoice')
    partner_id = fields.Many2one(comodel_name='res.partner', related='invoice_id.partner_id')
    product_id = fields.Many2one(comodel_name='product.product')
    lot_id = fields.Many2one(comodel_name='stock.production.lot')
    monthly_due = fields.Float(string='Monthly Due')
    month_due = fields.Float(string='Month Due')
    surcharge = fields.Float(string='Surcharge')
    letter_id = fields.Many2one(comodel_name='brdc.letter.format')

    @api.depends('partner_id')
    def _get_address(self):
        for s in self:
            s.address = s.partner_id.street_b

    address = fields.Text(string='Billing Address', compute=_get_address)


class LetterFormat(models.TransientModel):
    _name = 'brdc.letter.format'
    # agent_hierarchy.py

    # collector_id = fields.Many2one(string='position', comodel_name='agent.hierarchy')
    partner_id = fields.Many2one(string='Collector', comodel_name='res.partner')
    date = fields.Datetime(string='Date', default=fields.Datetime.now())
    # new_field = fields.Datetime(string="", required=False, )
    type = fields.Selection(string="Letter Type", selection=[('remind', 'REMINDER LETTER'),
                                                   ('demand', 'FINAL DEMAND LETTER'),
                                                   ('terminate', 'NOTICE OF TERMINATION')],
                             required=True,
                             default='remind')
    partner_line_ids = fields.One2many(comodel_name="brdc.partner.line", inverse_name="letter_id", string="", required=False)

    area_id = fields.Many2many(comodel_name="config.barangay", string="")


    @api.multi
    def invoice_due(self):
        for r in self.env['account.invoice'].search([('state', '=', 'open')]):
            print r.month_due

    def generate(self):
        for s in self:
            invoice_line = s.env['brdc.partner.line']
            invoice_line.search([]).unlink()
            invoices = None
            product_id = None
            lot_id = None
            ids = []
            # for r in self.env['account.invoice'].search([('state', '=', 'open')]):
            #     print r.month_due
            self._cr.execute("""select a.id, a.partner_id, a.monthly_due, a.month_due, a.surcharge, b.product_id, b.lot_id,
            c.barangay_id_b
            from account_invoice as a  
            join account_invoice_line as b
            on a.id = b.invoice_id
            join res_partner as c
            on c.id = a.partner_id
            where a.state = 'open' and a.month_due > 2.99999999999 and c.barangay_id_b in (%s)
            order by a.month_due""" % str(self.area_id.ids)[1:-1])
            res = self._cr.fetchall()
            # res
            # print res[0]
            # invoices = self.env['account.invoice'].search([('id', 'in', res[0])])
            # print invoices
            for r in res:
                invoices = self.env['account.invoice'].search([('id', '=', r[0])])
                print invoices.number
                invoice_line.create({
                    'invoice_id': r[0],
                    'partner_id': r[1],
                    'letter_id': s.id,
                    'monthly_due': r[2],
                    'month_due': r[3],
                    'surcharge': r[4],
                    'product_id': r[5],
                    'lot_id': r[6],
                })

    def print_due(self):
        return self.env['report'].get_action(self, 'brdc_account.termination_letter')

    def send_due(self):
        # template = self.env.ref('brdc_account.email_template_customers_due', False)
        # template.send_mail(self.id, force_send=True)
        pass

    # @api.multi
    # @api.onchange('type')
    # def _letter_context(self):
    #     for s in self:
    #         _invoice = s.env['account.invoice'].browse(self._context.get('active_ids', []))
    #         _type = s.type
    #         _content = None
    #         _date = date.today()
    #         print _date
    #         # s.partner_id = _invoice.partner_id.id
    #         if _type == 'terminate':
    #             # _content = '''
    #             # <p style="font-size: smaller;">
    #             # <h1><center>NOTICE OF TERMINATION</center></h1>
    #             #
    #             # <br/>
    #             #
    #             # %s<br/>
    #             # %s<br/>
    #             # %s<br/>
    #             # <center>Re: TERMINATION OF ACCOUNT WITH PA No.: </center>
    #             # </p>
    #             # ''' % (date(day=_date.day, month=_date.month, year=_date.year).strftime('%d %B %Y'), s.partner_id.name, s.partner_id.street)
    #             pass
    #         elif _type == 'demand':
    #             pass
    #         elif _type == 'remind':
    #             pass
    #
    #         return self.update({
    #             'content': _content
    #         })

    content = fields.Text(string='Letter Content')

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.model
    def view_with_due(self):
        self._cr.execute("""select a.id, a.partner_id, a.monthly_due, a.month_due, b.product_id, b.lot_id 
                        from account_invoice as a  
                        join account_invoice_line as b
                        on a.id = b.invoice_id
                        where state = 'open' and month_due != 0
                        order by a.month_due""")
        res = self._cr.fetchall()
        return {
            'name': "Payment",
            'res_model': 'account.payment',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'view_id': False,
            'view_type': 'form',
            'domain': [('id', 'in', res)]
        }