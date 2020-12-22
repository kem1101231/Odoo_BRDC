from odoo import api, fields, models

class BrdcSettings(models.TransientModel):
    _name = 'brdc.config.settings'
    _inherit = 'res.config.settings'

    @api.one
    @api.depends('company_id')
    def _get_currency_id(self):
        self.currency_id = self.company_id.currency_id

    @api.one
    def _set_currency_id(self):
        if self.currency_id != self.company_id.currency_id:
            self.company_id.currency_id = self.currency_id

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', compute='_get_currency_id', inverse='_set_currency_id', required=True,
                                  string='Default company currency', help="Main currency of the company.")

    agent_commission_fund = fields.Float(default=50000, string='Agent Commission Fund')

    #surcharge settings
    surcharge_active = fields.Float(string='Surcharge for Active Account', default=1.17)
    surcharge_terminated = fields.Float(string='Surcharge for Terminated Account', default=3)

    @api.model
    def _get_default_journal(self):
        journal = self.env['account.journal'].search([('code', '=ilike', 'SUR')])
        print journal.code, 'asdassssjournal'
        return journal.id

    surcharge_journal = fields.Many2one('account.journal',
                                        string='Journal',
                                        default=lambda self: self._get_default_journal(),
                                        required=True,
                                        )

    @api.multi
    def execute(self):
        ir_property = self.env['ir.property']
        ir_model = self.env['ir.model.fields'].search([('model','=','account.invoice'),('name','=','surcharge_journal')])
        if ir_property.search([('name', '=', 'brdc_surcharge_property_id')]):
            ir_property.write({
                'id': 'brdc_surcharge_property_1',
                'name': 'brdc_surcharge_property_id',
                'fields_id': ir_model.id,
                'value_reference': 'account.journal,%s' % self.surcharge_journal.id,
                'company_id': self.company_id.id,
            })
        else:
            ir_property.create({
                'id': 'brdc_surcharge_property_1',
                'name': 'brdc_surcharge_property_id',
                'fields_id': ir_model.id,
                'value_reference': 'account.journal,%s' % self.surcharge_journal.id,
                'company_id': self.company_id.id,
            })
        res = super(BrdcSettings, self).execute()
        return res




class SettingHolder(models.Model):
    _name = 'brdc.setting.holder'

