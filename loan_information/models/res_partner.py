from odoo import api, fields, models, _
from odoo.exceptions import UserError

class ResPartner(models.Model):
    _inherit= 'res.partner'
    
    interment_loan_request = fields.One2many(comodel_name="interment.quotation.request", inverse_name="customer_id", string="interment quotation", required=True, index=True )
    count_request = fields.Integer(compute='_count_request')


    def _count_request(self):
        request_data = self.env['interment.quotation.request'].read_group(domain=[('customer_id','child_of',self.ids)],
                                                                          fields=['customer_id'], groupby=['customer_id'])
        parntner_child_ids = self.read(['child_ids'])
        mapped_data = dict([(m['customer_id'][0],m['customer_id_count']) for m in request_data])

        for partner in self:
            partner_ids = filter(lambda r: r['id'] == partner.id, parntner_child_ids)[0]
            partner_ids = [partner_ids.get('id')] + partner_ids.get('child_ids')
            partner.count_request = sum(mapped_data.get(child, 0) for child in partner_ids)

    @api.multi
    def unlink(self):
        loan_range = self.env['interment.quotation.request']
        rule_ranges = loan_range.search([('customer_id','in',self.ids)])
        if rule_ranges:
            raise UserError(_("You are trying to delete a record that is still referenced!"))
        return super(ResPartner, self).unlink()
