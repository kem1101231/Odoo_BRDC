from odoo import api, fields, models
from datetime import datetime, timedelta
import time

class collector_col_eff(models.TransientModel):
    _name = 'collector.col_eff_handler'
    # _rec_name = 'name'
    _description = 'collector collection efficiency handler'

