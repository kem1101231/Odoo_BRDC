from odoo import api, fields, models
#Change Agent Access


class ResPartner(models.Model):
    _inherit = 'res.partner'

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Client is already existing!')
    ]

    

    def get_group(self):
        for partner in self:

            user = self.env.user
            flag_data = False

            if user.has_group('brdc_security.brdc_group_can_change_agent'):
                flag_data = True
            
            partner.can_edit_agent = flag_data
            partner.update({'can_edit_agent':flag_data,})

    def get_group_default(self):
        user = self.env.user
        if user.has_group('brdc_security.brdc_group_can_change_agent'):
            return True
        else:
            return False
    
    #can_edit_agent = fields.Boolean(default=False)
    can_edit_agent = fields.Boolean(compute=get_group, default=get_group_default)



class SaleOrder(models.Model):
    _inherit = 'sale.order'


    def get_group(self):
        user = self.env.user
        print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
        print(user.has_group('brdc_security.brdc_group_can_change_agent'))
        if user.has_group('brdc_security.brdc_group_can_change_agent'):
            self.can_edit_agent = True
        else:
            self.can_edit_agent = False

    def get_group_default(self):
        user = self.env.user
        if user.has_group('brdc_security.brdc_group_can_change_agent'):
            return True
        else:
            return False
    
    #can_edit_agent = fields.Boolean(default=False)
    can_edit_agent = fields.Boolean(compute=get_group, default=get_group_default)


