from odoo import api, fields, models


class ServiceBundleLine(models.Model):
    _name = 'service.bundle.line'
    _sql_constraints = [('name_unique', 'UNIQUE(name)', 'Already Existing.')]

    name = fields.Char()
    description = fields.Text()
    service_bundle_id = fields.Many2one('service.bundle', 'Plan/Service')


class ServiceBundle(models.Model):
    _name = 'service.bundle'
    _rec_name = 'parent_id'
    _sql_constraints = [('parent_id_unique', 'UNIQUE(parent_id)', 'Already Existing')]

    # name = fields.Char()
    parent_id = fields.Many2one('payment.config', 'Parent', domain=[('category', '=', 'service')])
    child_ids = fields.One2many(comodel_name='service.bundle.line', inverse_name='service_bundle_id', string='Default Included Items')


class ServiceOrder(models.Model):
    _inherit = 'service.order'

    service_bundle_line_ids = fields.Many2many(comodel_name='service.bundle.line',)
    service_bundle_id = fields.Many2one('service.bundle',  compute='_compute_default')


    @api.model
    @api.depends('product_type')
    def _compute_default(self):
        bundle_items = self.env['service.bundle.line']

        item_ids = []
        for rec in self:
            bundle = self.env['service.bundle'].search([('parent_id', '=', rec.product_type.id)])
            rec.service_bundle_id = bundle.id
            if rec.service_bundle_id:
                for item in bundle_items.search([('service_bundle_id', '=', rec.service_bundle_id.id)]):
                    item_ids.append(item.id)
                rec.service_bundle_line_ids = [(6, 0, item_ids)]

