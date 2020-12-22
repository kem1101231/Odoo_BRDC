from odoo import api, fields, models

class agent_hierarchy(models.Model):
    _name = 'agent.hierarchy'
    # _rec_name = 'name'
    _description = 'Agent Hierarchy'

    name = fields.Char(string="Position")
    comm_percent = fields.Float(string="Commission Percentage")
    withholding_tax = fields.Float(string="Withholding Tax")

    agent_list = fields.One2many('res.partner','agency_id')


#bokk
class LetterFormat(models.TransientModel):
    _inherit = 'brdc.letter.format'

    @api.model
    def _collector(self):
        collectors = self.env['res.partner'].search([('is_agent', '=', 1)])
        # print collectors.name

        ids = []
        for collector in collectors:
            if collector.is_co:
                ids.append(collector.id)
            else:
                pass

        # return {'domain': {'partner_id': [('id', 'in', ids)]}}
        domain = [('id', 'in', ids)]
        return domain

    @api.model
    def _default_collector(self):
        collectors = self.env['res.partner'].search([('is_agent', '=', 1), ('is_co', '=', 1)])

        return collectors[0].id

    partner_id = fields.Many2one(string='Collector', comodel_name='res.partner', domain=_collector, default=_default_collector, required=1)

    @api.onchange('partner_id')
    @api.depends('partner_id')
    def _add_area(self):
        self.area_id = [(6, 0, self.partner_id.collector_area_id.ids)]

    area_id = fields.Many2many(comodel_name="config.barangay", string='Area')


class CollectorAging(models.TransientModel):
    _inherit = 'collector.aging'

    @api.model
    def _collector(self):
        collectors = self.env['res.partner'].search([('is_agent', '=', 1)])
        # print collectors.name

        ids = []
        for collector in collectors:
            if collector.is_co:
                ids.append(collector.id)
            else:
                pass

        # return {'domain': {'partner_id': [('id', 'in', ids)]}}
        domain = [('id', 'in', ids)]
        return domain

    @api.model
    def _default_collector(self):
        collectors = self.env['res.partner'].search([('is_agent', '=', 1), ('is_co', '=', 1)])

        return collectors[0].id

    collector_id = fields.Many2one(string='Collector', comodel_name='res.partner', domain=_collector, default=_default_collector, required=1)

    @api.onchange('collector_id')
    @api.depends('collector_id')
    def _add_area(self):
        self.area_id = [(6, 0, self.collector_id.collector_area_id.ids)]

    area_id = fields.Many2many(comodel_name="config.barangay", string='Area')


class CollectionEfficiency(models.Model):
    _inherit = 'collection.efficiency'

    @api.model
    def _collector(self):
        collectors = self.env['res.partner'].search([('is_agent', '=', 1)])
        # print collectors.name

        ids = []
        for collector in collectors:
            if collector.is_co:
                ids.append(collector.id)
            else:
                pass

        # return {'domain': {'partner_id': [('id', 'in', ids)]}}
        domain = [('id', 'in', ids)]
        return domain

    @api.model
    def _default_collector(self):
        collectors = self.env['res.partner'].search([('is_agent', '=', 1), ('is_co', '=', 1)])

        return collectors[0].id

    collector_id = fields.Many2one(string='Collector', comodel_name='res.partner', domain=_collector,
                                   default=_default_collector, required=1)

    @api.onchange('collector_id')
    @api.depends('collector_id')
    def _add_area(self):
        self.area_id = [(6, 0, self.collector_id.collector_area_id.ids)]

    area_id = fields.Many2many(comodel_name="config.barangay", string='Area')


class CollectionEfficiencyReport(models.TransientModel):
    _inherit = 'collection.efficiency.report'

    @api.model
    def _collector(self):
        collectors = self.env['res.partner'].search([('is_agent', '=', 1)])
        # print collectors.name

        ids = []
        for collector in collectors:
            if collector.is_co:
                ids.append(collector.id)
            else:
                pass

        # return {'domain': {'partner_id': [('id', 'in', ids)]}}
        domain = [('id', 'in', ids)]
        return domain

    @api.model
    @api.depends('user_id', 'all_docs_group')
    def _default_collector(self):
        user = self.env.user
        # collectors = None
        if self.all_docs_group:
            collectors = self.env['res.partner'].search([('is_agent', '=', 1), ('is_co', '=', 1)])[0]
        elif not self.all_docs_group:
            collectors = user.partner_id
        else:
            collectors = self.env['res.partner'].search([('is_agent', '=', 1), ('is_co', '=', 1)])[0]

        return collectors.id

    collector_id = fields.Many2one(string='Collector', comodel_name='res.partner', domain=_collector,
                                   default=_default_collector, required=1)