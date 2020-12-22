from odoo import api, fields, models

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    has_pcf = fields.Boolean(default=False, string='Has PCF')
    pcf_account_id = fields.Many2one('account.account', string='PCF Account')
    installment_contract_rec_id = fields.Many2one('account.account', string='Installment Contract Receivable')
    property_account_cost_id = fields.Many2one('account.account', string='Cost Account')
    gross_profit_id = fields.Many2one('account.account', string='Unrealized Gross Profit')

class ProductPricelist(models.Model):
	_inherit = 'product.pricelist'

	# ==================
	# Payment Configuration that will use the pricelist (Labeled as Product Type on Forms)

	payment_config_id = fields.Many2one(comodel_name="payment.config", string="Product Type", help="Set the -Product Type- where this pricelist will be shown as the Sale Order is prepared.")

class ProductPricelistLine(models.Model):
    _inherit = 'product.pricelist.item'

    #pricelist_id
    @api.depends('pricelist_id')
    def _get_conf_id(self):
        for item in self:
            print("^%^%^%^%^%^%^%^%^%^%^%^%^%^%^%^")
            # item.payment_parent_id = item.pricelist_id.payment_config_id
            # item.update({'payment_parent_id':item.pricelist_id.payment_config_id,})


    @api.onchange('pricelist_id')
    def _pl_id_change(self):
        print("++++++++++++++++++++++++++++++++++++=")



    payment_parent_id = fields.Many2one(comodel_name="payment.config", string="Parent", compute="_get_conf_id")
    attach_to_pay_conf = fields.Boolean(string="With Payment Config.")
    
    @api.onchange('attach_to_pay_conf')
    def _attach_flag_change(self):

        self.payment_parent_id = self.pricelist_id.payment_config_id.id

        # flag = self.env.user.has_group('mgc_request.group_request_trade_requester')  

        # domain_description = []

        # if flag == True:
        #     domain_description = ['&','|','|', ('department', '=', self.request_id.department_id.id), ('for_all_use','=',True), ('for_trade_requester','=',True), ('request_name','=',self.request_id.request_type_line_id.id)]

        # else:
        #     domain_description = ['&','|',('department', '=', self.request_id.department_id.id), ('for_all_use','=',True), ('request_name','=',self.request_id.request_type_line_id.id)]
        
        # if self.request_id:
        #     result['domain'] = {'description': domain_description}
        # self.descripList = []

        # return result

    pay_conf_id = fields.Many2one(comodel_name="payment.config", string="For Payment Config.")
    selling_price = fields.Float(string="Selling Price")
