from odoo import api, fields, models
from datetime import datetime
import calendar


class AgentWithholdingTax(models.TransientModel):
    _name = 'agent.withholding.tax'

    @api.multi
    def default_month(self):
        now = datetime.now()
        return int(now.month)

    type = fields.Selection([('monthly','Monthly Agent Commission'), ('general', 'General Agent Commission')], default='monthly')
    current_month = fields.Selection([(1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
                                      (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
                                      (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'), ],
                                     string='Month', default=default_month)
    # account_commission_ids = fields.Many2many('account.commission')
    released_commission_ids = fields.Many2many('released.commission')

    @api.model
    def get_date(self):
        now = datetime.now()
        return "%s, %s" % (calendar.month_name[self.current_month], now.year)

    @api.multi
    def generate(self):
        for rec in self:
            released_commission = self.env['released.commission'].search([])
            if rec.type == 'monthly':
                month = self.current_month
                year = datetime.now().year
                start_date = "%s-%s-1" % (int(year), int(month))
                date_ = calendar.monthrange(int(year), int(month))[1]
                end_date = "%s-%s-%s" % (int(year), int(month), int(date_))
                d1 = datetime.strptime(start_date, '%Y-%m-%d')
                d2 = datetime.strptime(end_date, '%Y-%m-%d')

                ids = released_commission.filtered(lambda res: (res.date >= d1.strftime('%Y-%m-%d')) and
                                                               (res.date <= d2.strftime('%Y-%m-%d'))
                                                   ).ids
            else:
                ids = released_commission.ids

            rec.released_commission_ids = [(6, 0, ids)]

    def print_(self):
        return self.env['report'].get_action(self, 'brdc_account.agent_withholding_tax_template')