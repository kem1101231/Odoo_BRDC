from odoo import api, fields, models,_

class AccountPayment(models.Model):
    # _name = 'loan.account.payment'
    _inherit = 'account.payment'

    # additional fields
    # payment_note_selection = fields.Selection(string="", selection=[('sm','Straight Monthly'),
    #                                                       ('dn','Deceased Name'),
    #                                                       ('ot','Others')],  required=False, default='sm')

    is_hide_1 = fields.Boolean(string="Straight Monthly", default=False,)
    is_hide_2 = fields.Boolean(string="Deceased Name", default=False,)
    is_hide_3 = fields.Boolean(string="Other Fees", default=False, )

    deceased_name = fields.Char(string="Deceased Name")
    straight_monthly = fields.Char(string="Straight Monthly")
    others_paymentfee = fields.Char(string="Other Payment")
    # is_hide_1 = fields.Boolean(default=False,compute="is_not_dn")
    # is_hide_2 = fields.Boolean(default=False, compute="is_not_sm")
    # is_hide_3 = fields.Boolean(default=False, compute="is_not_ot")

    # @api.onchange('payment_note_selection')
    # def is_not_dn(self):
    #     for dn in self:
    #         dn.straight_monthly = None
    #         dn.others_paymentfee = None
    #
    # @api.onchange('payment_note_selection')
    # def is_not_sm(self):
    #     for dn in self:
    #         dn.deceased_name = None
    #         dn.others_paymentfee = None
    #
    # @api.onchange('payment_note_selection')
    # def is_not_ot(self):
    #     for dn in self:
    #         dn.deceased_name = None
    #         dn.straight_monthly = None
    @api.onchange('is_hide_1')
    def straightmon_vals(self):
        if not self.is_hide_1:
            self.straight_monthly = None

    @api.onchange('is_hide_2')
    def deceasedname_vals(self):
        if not self.is_hide_2:
            self.deceased_name = None

    @api.onchange('is_hide_3')
    def others_paymentfee_vals(self):
        if not self.is_hide_3:
            self.others_paymentfee = None

# class BrdcTypePaymentNotes(models.Model):
#     _name = 'brdc.type.payment.notes'
#     _rec_name = 'name'
#
#     name = fields.Char(string="Payment Notes", required=False)
#     active = fields.Boolean(string="Active", default=True)