from odoo import api, fields, models, _
from odoo.exceptions import UserError
import time

class register_commission_payment(models.Model):
    _name = 'register.commission_payment'
    _rec_name = 'name'
    _description = 'registered commission payment'
    _inherit = ['mail.thread', 'ir.needaction_mixin']

    name = fields.Char()
    ac_id = fields.Many2one('agent.commission', string="PA Number", required=True, track_visibility='onchange')
    # so_id = fields.Many2one('sale.order', related="ac_id.so_id")
    or_id = fields.Many2one('account.payment', string="OR Number",domain="[('state','in',['posted','reconciled'])]", required=True, track_visibility='onchange')
    # , ('account_invoice_id.so_id', '=', 'so_id')
    # inv_id = fields.Many2one('account.invoice',related="or_id.account_invoice_id")
    currency_id = fields.Many2one('res.currency', default = lambda self: self.env.user.company_id.currency_id)
    payment = fields.Monetary(string="Payment", related="or_id.amount", required=True, readonly=True, track_visibility='onchange')
    number_of_commission_paid = fields.Integer(string="Number of paid commission", track_visibility='onchange')
    date_registered = fields.Date(string="Date Paid", default=lambda *a: time.strftime('%Y-%m-%d'), readonly=True)

    state = fields.Selection([
        ('draft', "Draft"),
        ('confirmed', "Confirmed"),
        ('cancelled', "Cancelled"),
    ], default='draft')

    @api.multi
    def action_confirm(self):
        self.state = 'confirmed'
        if self.env['sa.commission.line'].search_count([('invoice_id', '=', self.or_id[0].id)]) >= 1:
            raise UserError(_("The Payment had been used on other commissions."))
        # if self.or_id in self.ac_id.sa_commission_line.invoice_id:
        #     raise UserError(_("The Payment had been used on other commissions."))
        sa_line = self.ac_id.sa_commission_line.filtered(lambda r: r.is_paid is False)
        um_line = self.ac_id.um_commission_line.filtered(lambda r: r.is_paid is False)
        am_line = self.ac_id.am_commission_line.filtered(lambda r: r.is_paid is False)
        if sa_line or um_line or am_line:
            for x in range(0,self.number_of_commission_paid):
                # print "sa commission no:",
                sa_line[x].write({
                            'date_paid': fields.Date.today(),
                            'is_paid': True,
                            'invoice_id': self.or_id[0].id,
                        })
                um_line[x].write({
                            'date_paid': fields.Date.today(),
                            'is_paid': True,
                            'invoice_id': self.or_id[0].id,
                        })
                am_line[x].write({
                            'date_paid': fields.Date.today(),
                            'is_paid': True,
                            'invoice_id': self.or_id[0].id,
                        })
        else:
            raise UserError(_("No Commission generated."))
        return {
            "type": "ir.actions.do_nothing",
        }

    @api.multi
    def action_cancelled(self):
        self.state = 'cancelled'
        sa_line = self.ac_id.sa_commission_line.filtered(lambda r: r.is_paid is True and r.invoice_id == self.or_id)
        for x in sa_line:
            x.write({
                'date_paid': '',
                'is_paid': False,
                'invoice_id': '',
            })
        um_line = self.ac_id.um_commission_line.filtered(lambda r: r.is_paid is True and r.invoice_id == self.or_id)
        for y in um_line:
            y.write({
                'date_paid': '',
                'is_paid': False,
                'invoice_id': '',
            })
        am_line = self.ac_id.am_commission_line.filtered(lambda r: r.is_paid is True and r.invoice_id == self.or_id)
        for z in am_line:
            z.write({
                'date_paid': '',
                'is_paid': False,
                'invoice_id': '',
            })
        return {
            "type": "ir.actions.do_nothing",
        }

    @api.multi
    def unlink(self):
        for quo in self:
            if quo.state != 'draft':
                raise UserError(_("Cannot delete confirmed application"))
            return super(register_commission_payment, self).unlink()

    @api.onchange('or_id')
    def num_of_commission_paid(self):
        if self.or_id:
            monthly_payment = self.env['account.invoice'].search([('move_name','=',self.or_id.communication)]).monthly_payment
            print "amount:", self.or_id
            print "monthly payment", monthly_payment
            self.number_of_commission_paid = self.or_id.amount / monthly_payment
