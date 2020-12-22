import time
from odoo import api, models
from dateutil.parser import parse
from odoo.exceptions import UserError


class AgentCommissionVoucher(models.AbstractModel):
    _name = 'report.brdc_account.agent_net_commission_voucher'
    
    @api.model
    def render_html(self, docids, data):
        docargs = {
            'doc_ids': self.ids,
            'doc_model': None,
            'docs': {'1':'one','2':'two','3':'three','4':'four','5':'five'},
            'time': time,
            'dataInput': data,
        }
        return self.env['report'].render('brdc_account.agent_net_commission_voucher_template', docargs)
