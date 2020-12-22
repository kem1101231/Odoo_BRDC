from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CustomerApplicationTransient(models.TransientModel):
    _name = 'customer.application.transient'
    # _inherit = 'res.partner'


    first_name = fields.Char(string='Firstname')
    middle_name = fields.Char(string="Middlename")
    last_name = fields.Char(string="Lastname")
    suffix = fields.Selection([('jr', 'Jr'),
                               ('sr', 'Sr'),
                               ('iii', 'III'),
                               ('v', 'V'),
                               ('vi', 'VI'),
                               ('vii', 'VII')], string='Suffix')

    state = fields.Selection([('general','General Information'),('other','Other Information'),('done','Done')], default='general')

    birthdate = fields.Date()

    street = fields.Text()

    contact = fields.Char()

    @api.multi
    def register_customer(self):
        for s in self:
            partner = s.env['res.partner']
            middlename = '' if not s.middle_name else ' ' + s.middle_name
            suffix = '' if not s.suffix else ' ' + s.suffix

            fullname = '%s, %s%s%s' % (s.last_name, s.first_name, middlename, suffix)
            if partner.search([('name', '=ilike', fullname.upper().strip())]):
                raise UserError(_('Customer Exists!'))
            else:
                partner.create({
                    'name': fullname.upper().strip(),
                    'display_name': fullname.upper().strip(),
                    'active': True,
                    'street': s.street,
                    'type': 'contact',
                    'first_name': s.first_name.upper().strip(),
                    'last_name': s.last_name.upper().strip(),
                    'middle_name': s.middle_name.upper().strip(),
                    'suffix': s.suffix,
                    'birthdate': s.birthdate,
                    'phone': s.contact,
                })
            s.update({
                'first_name': '',
                'middle_name': '',
                'last_name': '',
                'suffix': '',
                'state': 'general',
                'birthdate': '',
                'street': '',
            })
        return True

    @api.multi
    def action_next(self):
        for s in self:
            partner = s.env['res.partner']
            middlename = '' if not s.middle_name else ' ' + s.middle_name
            suffix = '' if not s.suffix else ' ' + s.suffix

            fullname = '%s, %s%s%s' % (s.last_name, s.first_name, middlename, suffix)
            print(fullname)
            print(partner.search([('name', '=ilike', fullname)]).name)
            if partner.search([('name', '=ilike', fullname)]):
                raise UserError(_('Customer Exists!'))
            else:
                s.state = 'other'

    @api.multi
    def action_prev(self):
        for s in self:
            s.state = 'general'

    @api.multi
    def action_cancel(self):
        for s in self:
            s.update({
                'first_name': '',
                'middle_name': '',
                'last_name': '',
                'suffix': '',
                'state': 'general',
                'birthdate': '',
                'street': '',
            })

    @api.onchange('first_name','middle_name','last_name')
    def onchange_name(self):
        for s in self:
            firstname = s.first_name
            middlename = s.middle_name
            lastname = s.last_name

            if firstname:
                s.first_name = firstname.upper().strip()
            else:
                s.first_name = ''

            if middlename:
                s.middle_name = middlename.upper().strip()
            else:
                s.middle_name = ''

            if lastname:
                s.last_name = lastname.upper().strip()
            else:
                s.last_name = ''


