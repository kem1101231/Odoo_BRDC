from odoo import api, fields, models , _


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    paymentType = fields.Selection(string="Type",
                                   selection=[('manual', 'Manual'), ('collection', 'Collection'), ],
                                   required=False,
                                   default='manual')
    collection_id = fields.Many2one(string='Collection', comodel_name='daily.collection.record')
    collected_id = fields.Many2one(string='Collected', comodel_name='dcr.lines')
    collected_mm_id = fields.Many2one(string='Collected', comodel_name='dcr.lines.mm')

    # @api.onchange('paymentType')
    # def _onchange_paymentType(self):
    #     for s in self:
    #         if s.paymentType == 'collection':
    #             s.or_reference = False
    #             s.amount = 0.00
    #             s.collection_id = False
    #             s.collected_id = False
    #         else:
    #             s.or_reference = False
    #             s.collection_id = False
    #             s.collected_id = False
    #             self.amount = self.get_default_amount()
    #
    # @api.onchange('collection_id')
    # def _onchange_collection_id(self):
    #     for s in self:
    #         s.collected_id = False
    #         s.or_reference = False
    #         # s.amount = 0.00
    #
    # @api.onchange('collected_id')
    # def _onchange_collected_id(self):
    #     for s in self:
    #         for cid in s.collected_id:
    #             s.or_series = cid.or_series.id
    #             s.amount = cid.amount_paid
    #
    #             # print s.or_series.name
    #
    # @api.multi
    # def dcr_line_vals(self):
    #     for s in self:
    #         dcr_line = s.env['dcr.lines'].search([('id', '=', s.collected_id.id)])
    #         dcr_line.write({
    #             'state': 'posted'
    #         })
    #     return True