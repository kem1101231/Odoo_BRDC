from odoo import fields, api, _, models
from odoo.exceptions import ValidationError, UserError

import time
from dateutil.parser import parse
from odoo.exceptions import UserError

class BRDCPaymentFormTemplate(models.AbstractModel):
    _name = 'report.brdc_account.all_payments_template'
    
    @api.model
    def render_html(self, docids, data):
        docargs = {
            'doc_ids': self.ids,
            'doc_model': 'account.Request',
            'docs': {'1':'one','2':'two','3':'three','4':'four','5':'five'},
            'dataInput': data['data'],
        }
        
        return self.env['report'].render('brdc_account.all_payments_template', docargs)

# class MGCRequestFormTemplate(models.AbstractModel):
#     _name = 'report.brdc_account.request_form_template'
    
#     @api.model
#     def render_html(self, docids, data):
#         docargs = {
#             'doc_ids': self.ids,
#             'doc_model': 'account.Request',
#             'docs': {'1':'one','2':'two','3':'three','4':'four','5':'five'},
#             'dataInput': data['data'],
#         }
        
#         return self.env['report'].render('brdc_account.request_form_template', docargs)
