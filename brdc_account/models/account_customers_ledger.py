from odoo import api, fields, models, _
from datetime import date, datetime,timedelta
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_compare
from odoo.tools.misc import formatLang
import json
import calendar
import time
import math


class BRDCCustomerLedger(models.Model):
	_name="account.invoice.customer.ledger"

	name = fields.Char(string="Ledger NId")
	invoice_ref = fields.Many2one(comodel_name="account.invoice", string="Invoice Reference")
	customer = fields.Many2one(comodel_name="res.partner", string="Customer")


class BRDCCustomerLedgerLine(models.Model):
	_name="account.invoice.customer.ledger.line"

	ledger_id = fields.Many2one(comodel_name="account.invoice.customer.ledger", string="Ledger ID"
	payment_id =fields.Many2one(comodel_name="account.payment", string="Payment Refernce")
	


	



