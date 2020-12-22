from odoo import api, fields, models, _
import json
import math
import datetime
from fractions import gcd


class CollectionEfficiencyReport(models.TransientModel):
    _name = 'collection.efficiency.report'

    all_docs_group = fields.Boolean(default=False, compute="get_group")

    @api.model
    @api.depends('user_id')
    def get_group(self):
        user = self.user_id
        if user.has_group('brdc_account.group_module_collection_efficiency_supervise'):
            self.all_docs_group = True
        else:
            self.all_docs_group = False

    collector_id = fields.Many2one('res.partner')
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user)
    collection_widget = fields.Text(compute="_get_collection_info_json")

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)

    @api.one
    @api.depends('company_id')
    def _get_currency_id(self):
        self.currency_id = self.company_id.currency_id

    currency_id = fields.Many2one('res.currency', compute='_get_currency_id', required=True,
                                  string='Default company currency')

    @api.model
    @api.depends('collector_id')
    def _get_collection_info_json(self):
        self.collection_widget = json.dumps(False)
        info = {'title': _('Collection Graph'), 'content': []}
        now = datetime.datetime.now()
        percentage_past = 0.0
        percentage_current = 0.0
        collections = self.env['collection.efficiency'].search(
            [('collector_id', '=', self.collector_id.id), ('year', '=', now.year)])
        for line in collections:
            print line.payment_line1_ids
            month = datetime.date(1900, line.current_month, 1).strftime('%B')
            collection_efficiency = self.env['collection.efficiency.payments'].search(
                [('collection_efficiency_id', '=', line.id)])
            total_collection = sum(line.amount for line in collection_efficiency)
            print line.total_target, 'total_target - ', total_collection, 'total_collection'
            if line.collection_past:
                percentage_past = line.collection_past / line.past_due
            if line.collection_current:
                percentage_current = line.collection_current / line.current_due
            info['content'].append({
                'month': month,
                'past_due': line.past_due,
                'current_due': line.current_due,
                'collection_past': line.collection_past,
                'collection_current': line.collection_current,
                'percentage_past': percentage_past * 100,
                'percentage_current': percentage_current * 100,
                'digits': [69, self.currency_id.decimal_places],
            })
        self.collection_widget = json.dumps(info)

    # @api.onchange('collector_id')
    # def _default_user(self):
    #     user = self.env['res.users'].search([('partner_id', '=', self.collector_id.id)])
    #     self.user_id = user

    collection_ids = fields.Many2many('collection.efficiency')

    @api.multi
    def generate_collection(self):
        pass

        # self.collection_ids = collections.ids
        # return {
        #     "type": "ir.actions.do_nothing",
        # }

# class CollectionEfficiency(models.Model):
#     _inherit = 'collection.efficiency'


