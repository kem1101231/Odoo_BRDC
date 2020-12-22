from odoo import api, fields, models, exceptions

class inherited_res_partner(models.Model):
    _inherit = 'res.partner'

    # agency_id = fields.Selection(string="Position", selection=[('am','Agency Manager'),
    #                                                            ('um','Unit Manager'),
    #                                                            ('sa','Sales Agent')], default='am')
    # agent_manager_id = fields.Many2one('res.partner', string="Agency Manager",domain="[('is_agent','=',True),('agency_id','=','am')]", )
    # unit_manager_id = fields.Many2one('res.partner', string="Unit Manager", domain="[('is_agent','=',True),('agency_id','=','um')]")
    # sales_agent_id = fields.Many2one('res.partner', string="Sales Agent", domain="[('is_agent','=',True),('agency_id','=','sa')]")
    # domain = "[('','','')]"

    collector_area_id = fields.Many2many('config.barangay', string="Barangay assigned")

    agency_id = fields.Many2one('agent.hierarchy', string="Position", track_visibility='onchange')

    agent_manager_id = fields.Many2one('res.partner', string="Agency Manager",domain="[('is_agent','=',True),('agency_id','=','Agency Manager')]",store=True,)
    unit_manager_id = fields.Many2one('res.partner', string="Unit Manager", domain="[('is_agent','=',True),('agency_id','=','Unit Manager')]", )
    sales_agent_id = fields.Many2one('res.partner', string="Sales Agent", domain="[('is_agent','=',True),('agency_id','=','Sales Agent')]", )

    is_am = fields.Boolean(default=False, store=False,onchange='onchange_is_agent')
    is_um = fields.Boolean(default=False, store=False,onchange='onchange_is_agent')
    is_sa = fields.Boolean(default=False, store=False,onchange='onchange_is_agent')
    is_co = fields.Boolean(default=False, store=True,onchange='onchange_is_agent')

    @api.onchange('unit_manager_id','agent_manager_id')
    # @api.multi
    def onchange_unit_manager(self):
        for sa in self.unit_manager_id:
            self.agent_manager_id = sa.agent_manager_id.id if sa.agent_manager_id else False

    @api.onchange('is_agent')
    def onchange_is_agent(self):
        # self.agency_id = 'am'
        self.agent_manager_id = 0
        self.unit_manager_id = 0
        self.sales_agent_id = 0

    @api.onchange('agency_id')
    def onchange_position(self):
        if self.agency_id:
            if self.agency_id.name == "Agency Manager":
                self.agent_manager_id = 0
                self.is_am = True
            else:
                self.is_am = False
            
            if self.agency_id.name == "Unit Manager":
                self.unit_manager_id = 0
                self.is_um = True
            else:
                self.is_um = False
            
            if self.agency_id.name == "Sales Agent":
                self.sales_agent_id = 0
                self.is_sa = True
            else:
                self.is_sa = False
            
            if self.agency_id.name == "Collector":
                self.is_co = True
            else:
                self.is_co = False

            agency_id_name_array = str(self.agency_id.name).split(' ')
            
            print("_+++++++++++++++++++++++++++++++++++++++++____________________________________________-")
            print(self.name)
            
            self.name = self.name + " - ["+str(agency_id_name_array[0][0])+str(agency_id_name_array[1][0])+"]" 
            
            print(self.name) 
            print self.is_sa, self.is_am, self.is_um, self.is_co

    @api.onchange('sales_agent_id','unit_manager_id','agent_manager_id')
    def onchange_sale_id(self):
        for sa in self.sales_agent_id:
            self.unit_manager_id = sa.unit_manager_id.id if sa.unit_manager_id else False
            self.agent_manager_id = sa.agent_manager_id.id if sa.agent_manager_id else False

    agent_ids = fields.Many2many('res.partner', 'Agents', compute='_agent_list')

    @api.multi
    def _agent_list(self):
        agent = self.env['res.partner']
        for s in self:
            # self.ensure_one()
            if s.is_am or s.agency_id.name == "Agency Manager":
                agent_ids = agent.search([('agent_manager_id', '=', s.id)])
                s.update({
                    'agent_ids': [(6, 0, agent_ids.ids)]
                })
            elif s.is_um or s.agency_id.name == "Unit Manager":
                agent_ids = agent.search([('unit_manager_id', '=', s.id)])
                s.update({
                    'agent_ids': [(6, 0, agent_ids.ids)]
                })
