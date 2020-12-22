from odoo import api, fields, models, _

class AccountPayment(models.Model):
    _inherit = 'account.payment'

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

# class AccountMove()
