from odoo import api, fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    is_customers_deposit = fields.Boolean(default=False, string="Customer's Deposit")
