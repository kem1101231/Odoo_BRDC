from odoo import api, fields, models,_
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.misc import formatLang
from odoo.exceptions import ValidationError,UserError
import num2words

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.multi
    def action_confirm(self):
        for order in self:
            print 'igatttt'
            if order.product_type.category == 'product':
                if not order.pa_ref:
                    raise UserError(_('please enter P.A. Number!'))
                if not order.order_line.lot_id:
                    raise UserError(_('Block and Lot Empty!'))
                else:
                    order.state = 'sale'
                    order.confirmation_date = fields.Datetime.now()
                    if self.env.context.get('send_email'):
                        self.force_quotation_send()
                    order.order_line._action_procurement_create()
        if self.env['ir.values'].get_default('sale.config.settings', 'auto_done_setting'):
            self.action_done()
    #   return True

    # InvoiceInstallmentLine_ids = fields.One2many(comodel_name="invoice.installment.line",
    #                                              inverse_name="account_invoice_id", string="", required=False, )
    date_for_payment = fields.Date(string='Date for Payment', default=fields.Date.today())
    purchase_term = fields.Selection([('cash', 'Cash'), ('install', 'Installment')], string='Payment Type',
                                     default='install')
    @api.onchange('purchase_term')
    def pu_term_change(self):
        if self.purchase_term:
            self.is_split = False
            self.is_paidup = False
            self.downpayment_type = False

            if self.purchase_term == 'cash':
                self.is_paidup = True

            for line in self.order_line:

                line.update_line = False if line.update_line else True


    user_id = fields.Many2one('res.users', string='Salesperson', track_visibility='onchange',
                              readonly=True,
                              default=lambda self: self.env.user)

    pa_required = fields.Boolean(default=False, compute='pa_required_')

    @api.onchange('product_type')
    def pa_required_(self):
        for s in self:
            if s.product_type.category != 'service':
                s.pa_required = True
            else:
                s.pa_required = False

    # ranzu
    pa_ref = fields.Char(string="Purchase Agreement", required=False)

    _sql_constraints = [
        ('pa_ref_unique',
         'UNIQUE(pa_ref)',
         "The PA Number already Exist!"),]

    def num2word(self, num):
        value = num2words.num2words(num)
        return value.title()

    @api.onchange('product_type', 'purchase_term')
    def new_payment_term_id_value(self):
        for s in self:
            array = []
            if s.purchase_term == 'install':
                payment_config = s.env['payment.config'].search(
                    [('parent_id', '=', s.product_type.id), ('payment_type', '=', s.purchase_term), ('bpt', '=', True)])
                for p in payment_config:
                    array.append(p.id)
                # print array
                s.new_payment_term_id = False if not array else array[0]
            else:
                payment_config = s.env['payment.config'].search(
                    [('parent_id', '=', s.product_type.id), ('payment_type', '=', s.purchase_term), ('bpt', '=', True)])
                for p in payment_config:
                    array.append(p.id)
                # print array
                s.new_payment_term_id = False if not array else array[0]

    # @api.onchange('purchase_term')
    # @api.multi
    # def new_payment_term_id_domain(self):
    #     for s in self:
    #         if s.purchase_term == 'install':
    #             return "[('parent_id', '=', product_type),('payment_type','=','install'),('bpt','=',True)]"
    #         else:
    #             return "[('parent_id', '=', product_type),('payment_type','=','cash')]"

    new_payment_term_id = fields.Many2one('payment.config', string='Payment Terms',
                                          domain="[('parent_id', '=', product_type),('payment_type','=',purchase_term),('bpt','=',True)]",
                                          # domain=new_payment_term_id_domain,
                                          )

    new_payment_term_with_dp = fields.Boolean(related="new_payment_term_id.bpt_wod")
    downpayment_type = fields.Selection(selection=[('split','Split Downpayment'),('full','Full Downpayment')], string="Downpayment Type")

    @api.onchange('downpayment_type')
    def dp_type_change(self):
        if self.downpayment_type:
            if self.downpayment_type == 'split':
                self.is_split = True
                self.is_paidup = False
            else:
                self.is_split = False
                self.is_paidup = True

    # @api.onchange('product_type')
    # def get_def(self):
    #     # is_product = (self.product_type == 'product')
    #     # payment_conf = self.env['payment.config']
    #     # domain = []
    #
    #     if self.product_type == 'product':
    #         domain = ['&', ('bpt', '=', True),('name', 'not like', '%Service ')]
    #     else:
    #         domain = [('name', 'ilike', '%Service ')]
    #
    #     return domain

    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms', oldname='payment_term',
                                      default= lambda self: self.search([('name','=','Immediate Payment')]))
    # product_type = fields.Selection([('product','product'),('service','service')], string="Product Type", default='product')
    

    product_type = fields.Many2one('payment.config', string='Product Type',domain="[('is_parent', '=', 1)]",default= lambda self: self.env['payment.config'].search([('is_parent', '=', 1)])[0].id)


#     product_category = fields.Boolean(default=False)
    
#     @api.onchange('product_type')
#     def get_product_categ(self):
#         res = None
#         for s in self:
#         res = {'required': {'order_line.lot_id': [('is_bundle', '=', True)]}}
#         return res

    @api.depends('partner_id')
    def _get_collector_from_partner(self):
        for order in self:
            if order.partner_id:

                order.collector_list = False

                area_selected = self.env['brdc.collection.area'].search([('barangay_ids','in', order.partner_id.barangay_id.id), ('specify_brgy','=', True)])
 
                if len(area_selected) > 0:
                    order.collector_area = area_selected.id
                else:
                    area_selected = self.env['brdc.collection.area'].search([('municipality_id','=',order.partner_id.municipality_id.id), ('specify_brgy','=', False)])
                    order.collector_area = area_selected.id

                print("================================================")
                print(area_selected.name)
    
    collector_area = fields.Many2one(comodel_name="brdc.collection.area", string="Collector Area", compute="_get_collector_from_partner")
    
    @api.onchange('collector_area')
    def _coll_area_change(self):
        if self.collector_area:
            reference = []
            for line in self.collector_area.collector_ids:
                reference.append(line.sudo().id)
                
            return {'domain':{'collector_list':[('id','in', reference)]}}
        else:
            return {'domain':{'collector_list':[('id','in', [])]}}

    collector_list = fields.Many2one(comodel_name="brdc.collection.collector", string="Assign to Collector")

    collector = fields.Many2one(comodel_name="res.users", string="Assigned Collector", related="collector_list.collector_id")
    
    ############################################################################

    # @api.depends('partner_id')
    # def _get_collector_from_partner(self):
    #     for order in self:
    #         if order.partner_id:

    #             order.collector_list = False
    #             order.collector = False

    #             area_selected = self.env['brdc.collection.area'].search([('barangay_ids','in', order.partner_id.barangay_id.id), ('specify_brgy','=', True)])
 
    #             if len(area_selected) > 0:
    #                 order.collector_area = area_selected.id
    #             else:
    #                 area_selected = self.env['brdc.collection.area'].search([('municipality_id','=',order.partner_id.municipality_id.id), ('specify_brgy','=', False)])
    #                 order.collector_area = area_selected.id
    
    # collector_area = fields.Many2one(comodel_name="brdc.collection.area", string="Collector Area", compute="_get_collector_from_partner", store=True)
    # # collector_list = fields.Many2one(comodel_name="brdc.collection.collector", string="Assign Collector")
    # collector_list = fields.Many2many(comodel_name="res.users", related="collector_area.collector_id_list", store=False)

    # @api.onchange('collector_list')
    # def _coll_change(self):
    #     if self.collector_list:
    #         reference = []
    #         for line in self.collector_list:
    #             reference.append(line.sudo().id)

    #         return {'domain':{'collector_selection':[('id','in', reference)]}}

    # # collector = fields.Many2one(comodel_name="res.users", string="Assigned Collector", related="collector_list.collector_id")
    # collector_selection = fields.Many2one(comodel_name="res.users", string="Assign to Collector", store=False)
    # @api.onchange('collector_selection')
    # def _coll_sel_change(self):
    #     if self.collector_selection:
    #         self.collector = self.collector_selection.id

    # collector = fields.Many2one(comodel_name="res.users", string="Assigned Collector")

    #-------------------------------------------------------------------------------------------------------

    order_line = fields.One2many('sale.order.line', 'order_id', string='Order Lines',
                                 states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=True)

    is_split = fields.Boolean(default=False, string='Split Downpayment/Cash')
    is_paidup = fields.Boolean(default=False, string='Paid-up')

    o_dp = fields.Float(string='Downpayment', default=0.00, compute='get_value_from_line', store=0)
    # o_dp_disc_value = fields.Float(string='Downpayment', default=0.00, compute='get_value_from_line', store=0)
    # o_dp_disc_rate = fields.Float(string='Downpayment', default=0.00, compute='get_value_from_line', store=0)

    s_dp = fields.Float(string='Paid-up DP', default=0.00, compute='get_value_from_line', store=0)
    # s_dp_disc_value = fields.Float(string='Downpayment', default=0.00, compute='get_value_from_line', store=0)
    # s_dp_disc_rate = fields.Float(string='Downpayment', default=0.00, compute='get_value_from_line', store=0)
    
    st4_dp = fields.Float(string='Split DP', default=0.00, compute='get_value_from_line', store=0)
    # st4_dp_disc_value = fields.Float(string='Downpayment', default=0.00, compute='get_value_from_line', store=0)
    # st4_dp_disc_rate = fields.Float(string='Downpayment', default=0.00, compute='get_value_from_line', store=0)
    
    spot_cash = fields.Float(string='Spot Cash', default=0.00, compute='get_value_from_line', store=0)
    # spot_cah_disc_value = fields.Float(string='Downpayment', default=0.00, compute='get_value_from_line', store=0)
    # spot_cash_disc_rate = fields.Float(string='Downpayment', default=0.00, compute='get_value_from_line', store=0)
    
    split_cash = fields.Float(string='Split Cash', default=0.00, compute='get_value_from_line', store=0)
    # split_cash_disc_value = fields.Float(string='Downpayment', default=0.00, compute='get_value_from_line', store=0)
    # split_cash_disc_rate = fields.Float(string='Downpayment', default=0.00, compute='get_value_from_line', store=0)
    
    balance_payment = fields.Float(string='Balance', default=0.00, compute='get_value_from_line', store=0)
    # balance_payment_disc_value = fields.Float(string='Downpayment', default=0.00, compute='get_value_from_line', store=0)
    # balance_payment_disc_rate = fields.Float(string='Downpayment', default=0.00, compute='get_value_from_line', store=0)
    
    balance_payment_wi = fields.Float(string='Balance with Interest', default=0.00, compute='get_value_from_line', store=0)
    monthly_payment = fields.Float(string='Monthly Payment', default=0.00, compute='get_value_from_line', store=0)

    discount = fields.Float(string="Discount Amount", compute='_amount_all')
    discount_rate = fields.Float(string="Discount Rate", compute='get_value_from_line',)

    def get_monthly_payment(self, num):
        for s in self:
            if s.monthly_payment % 1 == 0:
                amount = num
            else:
                amount = round(num + 0.5)
            return amount

    is_bundle = fields.Boolean(string="Bundled?", default=False)
    
    @api.onchange('order_line','new_payment_term_id','product_type','purchase_term')
    def get_value_from_line(self):

        payment = self.env['payment.config']

        for s in self:
            # total_price = sum(line.price_subtotal for line in s.order_line)

            # dp = payment.search([('parent_id','=',s.product_type.id), ('name', '=', 'downpayment')])
            # s_dp = payment.search([('parent_id','=',s.product_type.id), ('name', '=', 'paid up DP')])
            # st4_dp = payment.search([('parent_id','=',s.product_type.id), ('name', '=', ' mos split dp')])

            # balance_payment = payment.search([('parent_id','=',s.product_type.id), ('name', '=', 'Balance')])

            # spot_cash = payment.search([('parent_id', '=', s.product_type.id), ('name', '=', 'spotcash')])

            # cash = payment.search([('parent_id', '=', s.product_type.id), ('name', '=', '3-months deferred')])
            

            # for orderline in s.order_line:
                
            #     installable = orderline[0].product_id.installable_product
                
            #     if s.product_type.category == 'product' and installable:
            #         if s.purchase_term == 'install' and s.new_payment_term_id.bpt_wod:
            #             # print "kirto"
            #             balance_payment_wi = total_price * s.new_payment_term_id.less_perc
            #             s.balance_payment_wi = 0.00

            #             s.o_dp = 0.00
            #             s.s_dp = 0.00
            #             s.st4_dp = 0.00

            #             s.spot_cash = 0.00
            #             s.split_cash = 0.00
            #             s.balance_payment = 0.00
                    
            #         else:
            #             #dp = payment.search([('parent_id','=',s.product_type.id), ('name', '=', 'downpayment')])
            #             s.o_dp = total_price * dp.less_perc if dp else 0.00
            #             #s_dp = payment.search([('parent_id','=',s.product_type.id), ('name', '=', 'paid up DP')])
            #             s.s_dp = s.o_dp * s_dp.less_perc if s_dp else 0.00
            #             #st4_dp = payment.search([('parent_id','=',s.product_type.id), ('name', '=', '4 mos split dp')])
            #             s.st4_dp = (s.o_dp * st4_dp.less_perc) / 4 if st4_dp else 0.00

            #             #spot_cash = payment.search([('parent_id','=',s.product_type.id), ('name', '=', 'spotcash')])
            #             s.spot_cash = total_price - (total_price * 0.15)  #* spot_cash.less_perc if spot_cash else 0.00
            #             #cash = payment.search([('parent_id','=',s.product_type.id), ('name', '=', '3-months deferred')])
            #             split_cash = total_price - (total_price * 0.05) #* cash.less_perc if cash else 0.00
            #             s.split_cash = split_cash / 3
                        
            #             if s.new_payment_term_id.years >= 5:
            #                 s.balance_payment = total_price
            #                 s.balance_payment_wi = s.balance_payment * s.new_payment_term_id.less_perc
            #                 balance_payment_wi = s.balance_payment_wi
                        
            #             else:
            #                 #balance_payment = payment.search([('parent_id','=',s.product_type.id), ('name', '=', 'Balance')])
            #                 s.balance_payment = total_price * balance_payment.less_perc if balance_payment else 0.00
            #                 s.balance_payment_wi = s.balance_payment * s.new_payment_term_id.less_perc
            #                 balance_payment_wi = s.balance_payment_wi
                    
            #         # s.monthly_payment = 0.00 if not s.new_payment_term_id else round(balance_payment_wi / s.new_payment_term_id.no_months)
            #         s.monthly_payment = 0.00 if not s.new_payment_term_id else (balance_payment_wi / s.new_payment_term_id.no_months)
                
            #     elif s.product_type.category == 'service' and installable:
                    
            #         payment_wi = 0.00
                    
            #         #dp = payment.search([('parent_id', '=', s.product_type.id), ('name', '=', 'downpayment')])
            #         s.o_dp = total_price * dp.less_perc if dp else 0.00
            #         #s_dp = payment.search([('parent_id', '=', s.product_type.id), ('name', '=', 'paid up DP')])
            #         s.s_dp = s.o_dp * s_dp.less_perc if s_dp else 0.00
            #         #st4_dp = payment.search([('parent_id', '=', s.product_type.id), ('name', '=', '4 mos split dp')])
            #         s.st4_dp = (s.o_dp * st4_dp.less_perc) / 4 if st4_dp else 0.00
                    
            #         #spot_cash = payment.search([('parent_id', '=', s.product_type.id), ('name', '=', 'spotcash')])
            #         s.spot_cash = total_price #* spot_cash.less_perc if spot_cash else 0.00
            #         #cash = payment.search([('parent_id', '=', s.product_type.id), ('name', '=', '3-months deferred')])
            #         split_cash = total_price #* cash.less_perc if cash else 0.00
            #         s.split_cash = split_cash / 3 if cash else 0.00
                    
            #         #balance_payment = payment.search([('parent_id', '=', s.product_type.id), ('name', '=', 'Balance')])
            #         s.balance_payment = total_price * balance_payment.less_perc if balance_payment else 0.00
            #         s.balance_payment_wi = s.balance_payment * s.new_payment_term_id.less_perc if s.balance_payment != 0 else 0.00
                    
            #         if s.purchase_term == 'install' and s.new_payment_term_id.bpt_wod:
                        
            #             s.balance_payment_wi = 0.00
            #             payment_wi = (s.balance_payment_wi if s.balance_payment_wi != 0 else total_price) * s.new_payment_term_id.less_perc
            #             # s.monthly_payment = round(payment_wi / s.new_payment_term_id.no_months)
            #             s.monthly_payment = (payment_wi / s.new_payment_term_id.no_months)
            #             s.o_dp = 0.00
            #             s.s_dp = 0.00
            #             s.st4_dp = 0.00
                        
            #             s.spot_cash = 0.00
            #             s.split_cash = 0.00
            #             s.balance_payment = 0.00
            #                     # s.new_payment_term_id = term_id
            #         else:
                        
            #             payment_wi = (s.balance_payment_wi if s.balance_payment_wi != 0 else total_price) * s.new_payment_term_id.less_perc
            #             # s.monthly_payment = 0.00 if not s.new_payment_term_id else round(payment_wi / s.new_payment_term_id.no_months)
            #             s.monthly_payment = 0.00 if not s.new_payment_term_id else (payment_wi / s.new_payment_term_id.no_months)
                
            #     elif s.product_type.category == 'service' and s.purchase_term == 'cash':
            #         s.spot_cash = total_price
                
            #     else:
            #         # print 'go lng'
            #         # s.monthly_payment = round(total_price)
            #         s.monthly_payment = total_price
            #         # s.split_cash = 0.00
            # held = 0.0
            # if s.other_taxes:
            #     held = (s.other_taxes * (-1)) / s.new_payment_term_id.no_months
            #     # s.monthly_payment = round(s.monthly_payment - held)
            #     s.monthly_payment = s.monthly_payment - held
            
            up_discount_value = 0
            up_pwd_discount = 0
            up_total_contract = 0
            pcf_value = 0
            up_total_tax = 0
            up_lot_price = 0
            up_downpayment = 0
            up_subtotal = 0
            up_all_price_fixed = 0

            for line_data in s.order_line:

                if s.purchase_term == 'cash':
                    up_subtotal += line_data.price_subtotal
                else:
                    up_discount_value += line_data.line_discount_value
                    # up_pwd_discount += line_data.pwd_discount_value
                    up_total_contract += line_data.price_unit
                    # pcf_value += line_data.pcf_inline_value
                    # up_total_tax += line_data.line_vat_value
                    # up_lot_price += line_data.lot_price

                    up_downpayment += line_data.downpayment_value

                    up_all_price_fixed += line_data.price_fixed

            s.update({
                'o_dp': up_downpayment,
                's_dp': up_downpayment - up_discount_value,
                'st4_dp':  up_downpayment / 4,
                'spot_cash': up_subtotal,
                'split_cash': up_subtotal / 3,
                'balance_payment':up_total_contract - up_downpayment,
                'balance_payment_wi': up_all_price_fixed * s.new_payment_term_id.no_months,
                'monthly_payment': up_all_price_fixed,
            })


    @api.onchange('is_split','purchase_term')
    def on_check_1(self):
        for s in self:
            if s.is_split:
                s.is_paidup = False
            elif s.is_paidup:
                s.is_split = False
            
            for line in self.order_line:
                line.update_line = False if line.update_line else True

    @api.onchange('is_paidup')
    def on_check_2(self):
        for s in self:
            if s.is_paidup:
                s.is_split = False
            
            for line in self.order_line:
                line.update_line = False if line.update_line else True

    @api.onchange('pricelist_id')
    def pricelist_change(self):
        if self.pricelist_id:
            for line in self.order_line:
                line.update_line = False if line.update_line else True
    
    @api.onchange('new_payment_term_id')
    def payment_term_change(self):
        if self.new_payment_term_id:
            for line in self.order_line:
                line.update_line = False if line.update_line else True              

    # changes/additional
    # *************************************************************************************************************************

    unit_price = fields.Monetary(string='Lot Price', store=True, readonly=True, compute='_amount_all',
                                 track_visibility='always')
    pcf = fields.Monetary(string='PCF', store=True, readonly=True, compute='_amount_all',
                          track_visibility='always')
    amount_tax = fields.Monetary(string='VAT', store=True, readonly=True, compute='_amount_all',
                                 track_visibility='always')

    other_taxes = fields.Monetary(string='Taxes', store=True, readonly=True, compute='_amount_all',
                                  track_visibility='always')
    amount_untaxed = fields.Monetary(string='Untaxed Amount', track_visibility='always', compute="_amount_all")
    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_amount_all',
                                track_visibility='always')
    amount_total_wo_pcf = fields.Monetary(string='Total without PCF', store=True, readonly=True, compute='_amount_all',
                                track_visibility='always')
    amot_total_wo_pcf_n_disc = fields.Monetary(string='Total without PCF and Discount', store=True, readonly=True, compute='_amount_all',
                                track_visibility='always')
    lot_price_wo_disc =  fields.Monetary(string='Lot Price with Discount', store=True, readonly=True, compute='_amount_all',
                                track_visibility='always')
    pwd_sp_discount = fields.Boolean(string="PWD/SP Discounted")
    pwd_sp_discount_value = fields.Float(string="PWD/SP Discount Amount", compute="_amount_all")
    cost_of_sales = fields.Float(string="Cost of Sales", default=518.63)
    net_profit = fields.Float(string="Net Profit", compute="_amount_all")
    gross_profit_rate = fields.Float(string="Gross Profit Rate", compute="_amount_all")



 
    # *************************************************************************************************************************

    def get_all_pa_values(self):    

            pcf = 0
            discount = 0




    @api.depends('order_line','purchase_term','new_payment_term_id','is_split','product_type','spot_cash','is_paidup')
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        payment = self.env['payment.config']
        for order in self:
            # product = order.env['product.template']

            # amount_untaxed = 0.0
            # amount_untaxed_f = 0.0
            # amount_untaxed_t = 0.0
            # amount_tax = 0.0
            # total_price = sum(line.price_subtotal for line in order.order_line)
            # contract_pr = 0.0
            # _vat = []
            # _held = []
            # vat = 0.0
            # held = 0.0
            # has_pcf = False
            # pcf = 0.0
            # _adv = 0.00
            # for orderline in order.order_line:
            #     installable = orderline[0].product_id.installable_product
            #     if order.product_type.category == 'product' and installable:
            #         # name = payment.search([('parent_id','=','product'),('name', 'like', '%60 ')]).name
            #         if order.purchase_term == 'install' and order.new_payment_term_id.bpt_wod:
            #             amount_untaxed = order.monthly_payment * order.new_payment_term_id.no_months
            #             # contract_pr = amount_untaxed - order.monthly_payment
            #             contract_pr = amount_untaxed
            #             order.is_split = False
            #         else:
            #             for line in order.order_line:
            #                 if order.purchase_term == 'install':
            #                     if not order.is_split and not order.is_paidup:
            #                         amount_untaxed = (order.monthly_payment * order.new_payment_term_id.no_months) + order.o_dp
            #                         _adv = order.o_dp
            #                     elif order.is_paidup:
            #                         amount_untaxed = (order.monthly_payment * order.new_payment_term_id.no_months) + (
            #                             order.s_dp if order.s_dp != 0 else order.o_dp)
            #                         _adv = order.s_dp if order.s_dp != 0 else order.o_dp
            #                     elif order.is_split:
            #                         amount_untaxed = (order.monthly_payment * order.new_payment_term_id.no_months) + (
            #                             (order.st4_dp * 4) if order.st4_dp != 0 else order.o_dp)
            #                         _adv = (order.st4_dp * 4) if order.st4_dp != 0 else order.o_dp
            #                     # contract_pr = amount_untaxed - _adv
            #                     contract_pr = amount_untaxed
            #                     # contract_pr = order.balance_payment_wi
            #                 elif order.purchase_term == 'cash' and order.is_split:
            #                     # amount_untaxed = order.split_cash * 3
            #                     amount_untaxed = total_price
            #                     contract_pr = amount_untaxed
            #                 elif order.purchase_term == 'cash' and not order.is_split:
            #                     # spot_cash = payment.search(
            #                     #     [('parent_id', '=', order.product_type.id), ('name', '=', 'spotcash')])
            #                     # amount_untaxed = order.spot_cash if order.new_payment_term_id.id == spot_cash.id else sum(line.price_subtotal for line in self.order_line)
            #                     amount_untaxed = total_price
            #                     contract_pr = amount_untaxed

            #     elif order.product_type.category == 'service':
            #         for line in order.order_line:
            #             payment = order.env['payment.config']
            #             if order.purchase_term == 'install':
            #                 amount_untaxed = (order.monthly_payment * order.new_payment_term_id.no_months) + order.o_dp if order.o_dp != 0 else (order.monthly_payment * order.new_payment_term_id.no_months)
            #             elif order.purchase_term == 'cash':
            #                 spot_cash = payment.search(
            #                     [('parent_id', '=', order.product_type.id), ('name', '=', 'spotcash')])
            #                 amount_untaxed = order.spot_cash #if order.new_payment_term_id.id == spot_cash.id else sum(
            #                     #line.price_subtotal for line in self.order_line)
            #         contract_pr = amount_untaxed
                
            #     elif not installable:
            #         amount_untaxed = order.monthly_payment * order.new_payment_term_id.no_months
            #         contract_pr = amount_untaxed
            #     else:
            #         amount_untaxed = 0.0
            #         print 'dre'
            #     for p in orderline.product_id:
            #         if p.has_pcf:
            #             has_pcf = True
            #     if has_pcf:
            #         # if order.product_type.category == 'product':
            #         pcf = orderline.pcf_inline_value #amount_untaxed * 0.10 
            #         # else:
            #         #     pcf = 0.00
            #     else:
            #         pcf = 0.00
                
            #     #compute vat and tax with held only
            #     if orderline.tax_id:
            #         for tax_ids in orderline.tax_id:
            #             if tax_ids.amount_type == 'vat':
            #                 _vat.append(tax_ids.amount)
            #             elif tax_ids.amount_type == 'held':
            #                 _held.append(tax_ids.amount)
            #             else:
            #                 pass
                
            #     vat = sum(_vat)
            #     held = sum(_held)
                
            #     print vat

            #     amount_untaxed_f = (order.pricelist_id.currency_id.round(contract_pr) - pcf) / (
            #                 1 + (vat or 0.0) / 100.0)
            #     price = amount_untaxed_f * (1 - (orderline.discount or 0.0) / 100.0)
            #     taxes = orderline.tax_id.compute_all(price, orderline.order_id.currency_id, orderline.product_uom_qty,
            #                                     product=orderline.product_id, partner=order.partner_shipping_id)
            #     if order.company_id.tax_calculation_rounding_method == 'round_globally':
            #         amount_tax += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
            #     else:
            #         amount_tax = amount_untaxed_f * (vat or 0.0) / 100.0
            #     amount_untaxed_t = (order.pricelist_id.currency_id.round(amount_untaxed) - pcf) - order.pricelist_id.currency_id.round(amount_tax)
            # on_held = amount_untaxed_f * (held or 0.0) / 100.0

            up_discount_value = 0
            up_pwd_discount = 0
            up_total_contract = 0
            pcf_value = 0
            up_total_tax = 0
            up_lot_price = 0

            for line_data in order.order_line:
                up_discount_value += line_data.line_discount_value
                up_pwd_discount += line_data.pwd_discount_value
                up_total_contract += line_data.price_unit
                pcf_value += line_data.pcf_inline_value
                up_total_tax += line_data.line_vat_value
                up_lot_price += line_data.lot_price

            net_sales = up_lot_price - up_discount_value
            net_profit = net_sales - order.cost_of_sales
            gross_profit_rate = net_profit/net_sales if net_sales != 0 else 0

            order.update({
                'unit_price': up_lot_price,
                'pcf': pcf_value,
                'amount_untaxed':  up_total_contract,
                'discount': up_discount_value,
                'pwd_sp_discount_value': up_pwd_discount,
                'amount_tax': up_total_tax,#order.pricelist_id.currency_id.round(amount_tax),
                #'other_taxes': 0 - on_held,
                'amount_total': up_total_contract - up_discount_value - up_pwd_discount,
                'amount_total_wo_pcf': up_total_contract - pcf_value,
                'amot_total_wo_pcf_n_disc':up_total_contract - up_discount_value - pcf_value,
                'lot_price_wo_disc':net_sales,
                'net_profit': net_profit,
                'gross_profit_rate':gross_profit_rate,
            })
            # print 'edi wow, perfect SMALL'

    @api.multi
    def _prepare_invoice(self):
        """
        Prepare the dict of values to create the new invoice for a sales order. This method may be
        overridden to implement custom invoice generation (making sure to call super() to establish
        a clean extension chain).
        """
        # print 'bokiboki'
        # print 'wow MAGIC'
        # print self.monthly_payment
        
        account_id = False
        if self.product_type.account_id:
            account_id = self.product_type.account_id.id
        elif self.purchase_term == 'install':
            account_id = self.env['account.account'].search([('code', '=', '15971000202600')]).id
        elif self.purchase_term == 'cash':
            account_id = self.env['account.account'].search([('code', '=', '15971000100100')]).id
            
        self.ensure_one()
        payment_term_id = self.env['account.payment.term'].search([('name','=','Immediate Payment')])
        journal_id = self.env['account.invoice'].default_get(['journal_id'])['journal_id']
        if not journal_id:
            raise UserError(_('Please define an accounting sale journal for this company.'))
        payment_term = False if not self.new_payment_term_id.id else self.new_payment_term_id.id
        invoice_vals = {
            'name': self.client_order_ref or '',
            'origin': self.name,
            'type': 'out_invoice',
            'account_id': account_id,
            'partner_id': self.partner_invoice_id.id,
            'partner_shipping_id': self.partner_shipping_id.id,
            'journal_id': journal_id,
            'currency_id': self.pricelist_id.currency_id.id,
            'comment': self.note,
            'payment_term_id': payment_term_id.id,
            'fiscal_position_id': self.fiscal_position_id.id or self.partner_invoice_id.property_account_position_id.id,
            'company_id': self.company_id.id,
            'user_id': self.user_id and self.user_id.id,
            'team_id': self.team_id.id,
            'purchase_term': self.purchase_term,
            'product_type': self.product_type.id,
            'new_payment_term_id': payment_term,
            'is_split': self.is_split,
            'is_paidup': self.is_paidup,
            'o_dp': self.o_dp,
            's_dp': self.s_dp,
            'st4_dp': self.st4_dp,
            'spot_cash': self.spot_cash,
            'split_cash': self.split_cash,
            'balance_payment': self.balance_payment,
            'balance_payment_wi': self.balance_payment_wi,
            'monthly_payment': self.monthly_payment,
            'sale_order_id': self.id,
            'amount_untaxed': self.unit_price,
            'unit_price': self.amount_untaxed,
            'amount_tax': self.amount_tax,
            'pa_ref': self.pa_ref,
            'contract_price': self.amount_total,
            'service_order_id': False if not self.service_order_id else self.service_order_id.id
        }

        return invoice_vals

    # @api.multi
    # def action_confirm(self):
    #     sale = super(SaleOrder, self).action_confirm()
    #     for s in self:
    #         if not s.pa_ref:
    #             raise UserError(_('please enter P.A. Number!'))
    #         if s.product_type.category != 'service':
    #             if not s.order_line.lot_id:
    #                 raise UserError(_('Block and Lot Empty!'))
    #
    #     return sale

#     @api.depends('order_line')
#     def _onchange_order_line(self):
#         for order in self:
#             if order.product_type.category == 'product':
#                     if not order.order_line.lot_id:
#                         raise UserError(_('Block and Lot Empty!'))


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    price_unit_copy = fields.Float(string="Price Unit Copy")
    is_free = fields.Boolean(default=False, string='Free')
    selling_price = fields.Float(string="Contract Price")
    line_discount_value = fields.Float(string="Discount")
    pcf_inline_value= fields.Float(string="PCF")
    price_fixed = fields.Float(string="Fixed Price")
    pwd_discount_value = fields.Float(string="PWD/SP Discount")
    downpayment_value = fields.Float(string="Downpayment")
    #tax_value = fields.Float(string="Taxes")
    lot_price = fields.Float(string="Lot Price")
    line_vat_value = fields.Float(string="VAT")

    # is_split = fields.Boolean()
    # is_paidup = fields.Boolean()
    # purchase_term = fields.Selection(selection=[('install','Installment'),('cash','Cash')])
    # pricelist_id = fields.Many2one(comodel_name="product.pricelist")

    update_line = fields.Boolean()

    bogo_field = fields.Char(compute="test_func")

    @api.depends('update_line', 'product_id')
    def test_func(self):
        print("Running ====================== ******************* ===========================")
        self.set_values_to_line()

    discount_list = {
                        'spot_cash': 0.15,
                        'split_cash': 0.05,
                        'full_dp': 0.1,
                    }

    @api.multi
    def _prepare_invoice_line(self, qty):
        print("*********************************************")
        print("Executing _prepare_invoice_line")

        """
        Prepare the dict of values to create the new invoice line for a sales order line.

        :param qty: float quantity to invoice
        """
        self.ensure_one()
        sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))
        res = {}
        account = self.product_id.property_account_income_id or self.product_id.categ_id.property_account_income_categ_id
        if not account:
            raise UserError(
                _('Please define income account for this product: "%s" (id:%d) - or for its category: "%s".') %
                (self.product_id.name, self.product_id.id, self.product_id.categ_id.name))

        fpos = self.order_id.fiscal_position_id or self.order_id.partner_id.property_account_position_id
        if fpos:
            account = fpos.map_account(account)

        res = {
            'name': self.name,
            'sequence': self.sequence,
            'origin': self.order_id.name,
            'account_id': account.id,
            'price_unit': self.price_unit,
            'quantity': qty,
            'discount': self.discount,
            'line_discount_value':self.line_discount_value,
            'line_vat_value':self.line_vat_value,
            'uom_id': self.product_uom.id,
            'product_id': self.product_id.id or False,
            'layout_category_id': self.layout_category_id and self.layout_category_id.id or False,
            'invoice_line_tax_ids': [(6, 0, self.tax_id.ids)],
            'account_analytic_id': self.order_id.project_id.id,
            'analytic_tag_ids': [(6, 0, self.analytic_tag_ids.ids)],
            'is_free': self.is_free,
            'price_subtotal':self.price_subtotal,
        }
        return res

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        for line in self:
            #price = line.price_unit_copy - line.line_discount_value #* (1 - (line.discount or 0.0) / 100.0)
            # taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty,
            #                                 product=line.product_id, partner=line.order_id.partner_shipping_id)
            line.update({
                'price_unit':line.price_unit_copy,
                # 'price_tax': (taxes['total_included'] - taxes['total_excluded']),
                # 'price_total': taxes['total_included'],
                'price_subtotal': line.price_unit_copy - line.line_discount_value,
            })
            # print(taxes['total_included1'])
            # print(taxes['total_excluded1'])

    # @api.onchange('product_id')
    # def p_id_change(self):
    #     if self.product_id:
    #         self.set_values_to_line()

    @api.model
    def set_values_to_line(self):

        for line in self:

            if line.product_id:

                price_list = {}

                line.price_unit = 0

                for item in line.order_id.pricelist_id.item_ids:
                    price_list[str(item.name).replace(' ','')+"-"+(str(item.pay_conf_id.id) if item.attach_to_pay_conf == True else 'cash')] = [item.id, item.product_tmpl_id.name, item.fixed_price, item.selling_price, item.pay_conf_id]

                search_ref_string = str(line.product_id.name).replace(' ','') +"-"+ (str(line.order_id.new_payment_term_id.id) if line.order_id.purchase_term == 'install' else 'cash')

                
                if search_ref_string in price_list:
                    price_to_use = price_list[search_ref_string]
                    
                    output_values = line.generate_line_value(line.order_id, line.product_id, price_to_use[2], price_to_use[3])

                    if 'discount' in output_values:
                        line.line_discount_value = output_values['discount']
                    else:
                        line.line_discount_value = 0

                    line.price_unit = output_values['contract_price']
                    line.price_unit_copy = output_values['contract_price']
                    line.selling_price = price_to_use[3]
                    line.price_fixed = price_to_use[2]
                    line.pcf_inline_value = output_values['pcf']
                    line.price_subtotal = output_values['subtotal']
                    
                    if 'downpayment' in output_values:
                        line.downpayment_value = output_values['downpayment']
                    else:
                        line.downpayment_value = 0
                    
                    line.line_vat_value = output_values['vat'] 
                    line.lot_price = output_values['lot_price']
                    #line.tax_value

                    if 'pwd_discount' in output_values:
                        line.pwd_discount_value = output_values['pwd_discount']

                else:
                    line.product_id = False
                    # raise UserError("Product price hasn't been set")


    @api.model
    def generate_line_value(self, order_ref, product, product_fixed_price, product_selling_price):
        
        output_values = {}    

        purchase_term = order_ref.purchase_term
        payment_term = order_ref.new_payment_term_id
        is_paidup = order_ref.is_paidup
        is_split = order_ref.is_split

        #product_selling_price = product.list_price

        # ==== Get if a discount will be deducted ====================

        discount_ref_string = ''

        if purchase_term  == 'cash':
            if is_paidup:
                discount_ref_string = 'spot_cash'
            if is_split:
                discount_ref_string = 'split_cash'

        else:
            if payment_term.no_months <= 48:
                
                if is_paidup:
                    discount_ref_string = 'full_dp'


        print("+++++++++++++++++++++++++++++++++")
        print(discount_ref_string)

        discount = 0 if discount_ref_string == '' else self.discount_list[discount_ref_string]
        print("**********")
        print(discount)

        # ==== Get the discount value ================================

        if purchase_term  == 'cash':
                print("++++++++")
                print("Here")

                output_values['discount'] = product_fixed_price * discount
                output_values['contract_price'] = product_fixed_price

                print(output_values)
            
        else:
            if payment_term.no_months <= 48:
                downpayment_amount = product_selling_price * 0.2                
                
                if is_paidup:
                    output_values['discount'] = downpayment_amount * discount

                installment_cost = product_fixed_price * order_ref.new_payment_term_id.no_months
                output_values['contract_price'] = downpayment_amount + installment_cost
                output_values['downpayment'] = downpayment_amount
            
            else:
                output_values['contract_price'] = product_fixed_price * order_ref.new_payment_term_id.no_months


        if order_ref.pwd_sp_discount:
            pwd_discount = (product_selling_price / 1.12) * 0.2
            output_values['pwd_discount'] = pwd_discount

        output_values['subtotal'] = output_values['contract_price'] - (0 if 'discount' not in output_values else output_values['discount'] + 0 if 'pwd_discount' not in output_values else output_values['pwd_discount'] )
        output_values['pcf'] = ((product_fixed_price if product_selling_price == 0 else product_selling_price) * 0.1) if product.has_pcf else 0 
        output_values['vat'] = (output_values['subtotal']-output_values['pcf']) / 1.12 * 0.12
        output_values['lot_price'] = output_values['contract_price'] - output_values['vat'] - output_values['pcf']

        return output_values









