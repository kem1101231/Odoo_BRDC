from odoo import api, fields, models,_
from odoo.exceptions import UserError, ValidationError
import num2words
from dateutil.relativedelta import relativedelta
from datetime import datetime
import math
from re import sub
from decimal import Decimal
import locale

MAP_INVOICE_TYPE_PARTNER_TYPE = {
    'out_invoice': 'customer',
    'out_refund': 'customer',
    'in_invoice': 'supplier',
    'in_refund': 'supplier',
}

MAP_INVOICE_TYPE_PAYMENT_SIGN = {
    'out_invoice': 1,
    'in_refund': 1,
    'in_invoice': -1,
    'out_refund': -1,
}


class AccountPaymentType(models.Model):
    # _name = 'loan.account.payment'
    _inherit = 'account.payment'
    _rec_name = 'or_reference'