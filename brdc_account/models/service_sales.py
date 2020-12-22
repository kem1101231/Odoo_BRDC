from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import num2words
import json
import numpy as np


class AccountCustomerDeposit(models.TransientModel):
    _name = 'account.customer.deposit'

    or_ref = fields.Char('O.R. No.')
    amount = fields.Monetary(string='Payment Amount', required=True)

    @api.model
    def _default_journal(self):
        sale_order = self.env['service.order'].browse(self._context.get('active_ids', []))
        return sale_order.product_type.journal_id.id

    journal_id = fields.Many2one('account.journal', required=1, string='Journal', default=lambda self: self._default_journal())
    payment_date = fields.Date(default=fields.Date.today())

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)

    @api.one
    @api.depends('company_id')
    def _get_currency_id(self):
        self.currency_id = self.company_id.currency_id

    currency_id = fields.Many2one('res.currency', compute='_get_currency_id', required=True,
                                  string='Default company currency')

    @api.multi
    def post_customer_deposit(self):
        sale_order = self.env['service.order'].browse(self._context.get('active_ids', []))
        payment = self.env['account.payment'].search([])
        if sale_order:
            payment_ = payment.create({
                'paymentType': 'manual',
                'or_reference': self.or_ref,
                'journal_id': self.journal_id.id,
                'amount': self.amount,
                'payment_difference_handling': 'open',
                'payment_date': self.payment_date,
                'partner_type': 'customer',
                'payment_type': 'inbound',
                'communication': sale_order.name,
                'partner_id': sale_order.partner_id.id,
                'user_id': self.env.user.id,
                'payment_method_id': 1,
                'has_invoices': False,
            })
            payment_.post()

        # return {
        #     'type': "ir.actions.act_close_wizard_and_reload_view",
        # }, self.env['report'].get_action(self, 'brdc_account.official_receipt_depo_view')

    @api.multi
    def get_pa(self):
        sale_order = self.env['service.order'].browse(self._context.get('active_ids', []))
        return sale_order.name

    def get_name(self):
        sale_order = self.env['service.order'].browse(self._context.get('active_ids', []))
        return sale_order.partner_id.name

    def num2word(self, num):
        value = num2words.num2words(num) + "  only"
        return value.title()


class CustomerDeposit(models.Model):
    _name = 'customer.deposit'
    _order = 'date_paid'

    payment_id = fields.Many2one('account.payment')
    # name = fields.Char('Label', related='payment_id.name')
    amount = fields.Float('Amount Paid',)
    date_paid = fields.Date('Date Paid', )
    service_order_id = fields.Many2one('service.order')


class InstallmentLine(models.Model):
    _inherit = 'invoice.installment.line'

    service_order_id = fields.Many2one('service.order')


class ServiceOrder(models.Model):
    _name = 'service.order'
    _inherit = ['mail.thread']

    get_payments = fields.Boolean()

    payments_widget = fields.Text(compute='_get_payment_info_json')

    @api.one
    # @api.depends('payment_line1_ids')
    def _get_payment_info_json(self):
        # mali lol(MUST BE MOVE LINE)
        self.payments_widget = json.dumps(False)

        info = {'title': _('Less Payment'), 'outstanding': False, 'content': []}
        if self.state in ['ready', 'sale']:
            journal = self.env['account.journal'].search(
                [('is_customers_deposit', '=', True), ('id', '=', self.product_type.journal_id.id)])
            domain = [
                ('partner_id', '=', self.partner_id.id),
                ('journal_id', '=', journal.id),
                ('communication', '=', self.name),
                ('state', '=', 'posted')
            ]
            payments = self.env['account.payment'].search(domain)
            amount = 0.0
            for payment in payments:
                amount = payment.amount

                info['content'].append({
                    'name': payment.name,
                    'journal': payment.journal_id.name,
                    'amount': amount,
                    'currency': self.currency_id.symbol,
                    'digits': [69, self.currency_id.decimal_places],
                    'position': self.currency_id.position,
                    'date': payment.payment_date,
                    'payment_id': payment.id,
                    # 'move_id': payment.move_id.id,
                    # 'ref': ' (' + payment.move_id.ref + ')',
                })

            if info['content']:
                self.payments_widget = json.dumps(info)

                info['content'].pop(-1)
                for infos in info['content']:
                    amount += infos['amount']

                self.update({
                    'total_paid': amount
                })
                self.total_paid = amount
                print self.total_paid, '_get_payment_info_json'
                # self.compute_state()

    @api.model
    def _get_payments(self):
        for s in self:
            ids = None
            deposit = self.env['customer.deposit']
            deposit.search([('service_order_id', '=', s.id)]).unlink()
            total_paid = 0.0
            ids = None
            if s.state in ['ready', 'sale']:
                journal = self.env['account.journal'].search(
                    [('is_customers_deposit', '=', True), ('id', '=', s.product_type.journal_id.id)])
                payments = self.env['account.payment'].search(
                    [('partner_id', '=', s.partner_id.id), ('journal_id', '=', journal.id),
                     ('communication', '=', s.name)]).filtered(lambda rec: rec.state == 'posted')

                for payment in payments:
                    deposit.create({
                        'payment_id': payment.id,
                        'amount': payment.amount,
                        'date_paid': payment.payment_date,
                        'service_order_id': s.id
                    })

                ids = deposit.search([('service_order_id', '=', s.id)])
                print ids

            else:
                pass
            s.payment_line1_ids = ids
            s.update({
                'payment_line1_ids': ids,
                # 'payment_line_ids': ids
            })

    payment_line1_ids = fields.One2many(comodel_name="customer.deposit",
                                        inverse_name="service_order_id",
                                        string="Customer Deposit",
                                        required=False,
                                        compute=_get_payments,
                                        track_visibility="always")

    # payment_line_ids = fields.Many2many(comodel_name="customer.deposit",
    #                                     track_visibility="always",
    #                                     compute=_get_payments,
    #                                     store=True
    #                                     )

    # @api.depends('payment_line1_ids.amount')
    def _get_total_paid(self):
        for rec in self:
            print '_get_total_paid'

    @api.depends('amount_total', 'total_paid')
    def _get_estimated_balance(self):
        for rec in self:
            rec.update({
                'estimated_balance': rec.amount_total - rec.total_paid,
            })

    name = fields.Char(string='Name', default='New')
    state = fields.Selection([('draft', 'Quotation'),
                              ('ready', 'Ready for Collection'),
                              ('sale', 'Sale Order'),
                              ('lock', 'Locked'),
                              ('cancel', 'Cancelled')], default='draft', track_visibility='always')

    @api.onchange('total_paid')
    @api.depends('total_paid')
    def compute_state(self):
        res = None
        for rec in self:
            if rec.state not in ['ready', 'sale']:
                pass
            else:
                print 'compute_state'
                if rec.state == 'ready':

                    if rec.total_paid == rec.amount_total:
                        rec.sales_ready = True
                        rec.write({
                            'state': 'sale',
                        })
                        rec.update({
                            'to_invoice': True
                        })
                    elif rec.total_paid != rec.amount_total:
                        rec.sales_ready = False
                        rec.write({
                            'state': 'ready',
                        })
                        rec.update({
                            'to_invoice': False
                        })
                    print 'compute_', self.state
                else:
                    print '_state'
                    if rec.total_paid != rec.amount_total:
                        rec.sales_ready = False
                        rec.write({
                            'state': 'ready',
                        })
                        rec.update({
                            'to_invoice': False
                        })
                    elif rec.total_paid == rec.amount_total:
                        rec.sales_ready = True
                        rec.write({
                            'state': 'sale',
                        })
                        rec.update({
                            'to_invoice': True
                        })
                    print '_state', self.state
                invoices = self.filtered(lambda r: r.state != "cancel").mapped('invoice_ids')
                if invoices:
                    rec.update({
                        'to_invoice': False
                    })
                # print self.env['service.order'].search([('id', '=', rec.id)]).state

    to_invoice = fields.Boolean(default=False, compute=compute_state)

    partner_id = fields.Many2one('res.partner', 'Customer')
    discounted = fields.Boolean(string="SC/PWD Customer")

    # @api.onchange('discounted')
    # def _onchange_discounted(self):
    #     if self.discounted:
    #         discounted_rate = 0 
            
    #         if self.discounted == True:
    #             discounted_rate = 20

    #         else:
    #             discounted_rate = 0
            
    #         self.discount = discounted_rate


    order_date = fields.Date(default=fields.Date.today())
    confirmed_date = fields.Datetime()
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', required=True, readonly=True, states={'draft': [('readonly', False)]})
    currency_id = fields.Many2one("res.currency", related='pricelist_id.currency_id', string="Currency", readonly=True, required=True)

    @api.onchange('partner_id', 'prod_id')
    def product_domain(self):
        # for rec in self:
        if self.partner_id:
            stock = self.env['stock.production.lot'].search([('loanee_name', '=', self.partner_id.id)]).filtered(
                lambda rec: rec.status in ['fp', 'amo', 'wit'])
            ids = []
            for res in stock:
                ids.append(res.product_id.id)
            product = self.env['product.product'].search([('id', 'in', ids)])
            domain = {
                'prod_id': [('id', 'in', product.ids)],
                'lot_id': [('id', 'in', stock.filtered(
                    lambda rec: rec.product_id.id == self.prod_id.id).ids)]
            }

            return {'domain': domain}

    product_id = fields.Many2one('product.product', required=True, domain="[('type', '=', 'service')]")

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            # if self.discounted == True:
            #     self.discount = 20
            # else:
            #     self.discount = 0

            self.discount = 20 if self.discounted else 0
            
            price_list = {}

            self.price_unit = 0

            for item in self.pricelist_id.item_ids:
                price_list[str(item.name).replace(' ','')+"-"+(str(item.pay_conf_id.id) if item.attach_to_pay_conf == True else 'cash')] = [item.id, item.product_tmpl_id.name, item.fixed_price, item.selling_price, item.pay_conf_id]


            print("******************************************")
            print(price_list)

            search_ref_string = str(self.product_id.name).replace(' ','') +"-"+ (str(self.new_payment_term_id.id) if self.purchase_term == 'install' else 'cash')
            print(search_ref_string)
            
            if search_ref_string in price_list:
                price_to_use = price_list[search_ref_string]

                self.price_unit = price_to_use[2]
            else:
                self.product_id = False
                raise UserError("Product price hasn't been set")


    # picking_ids = fields.Many2many('stock.picking', compute='_compute_picking_ids',
    #                                string='Picking associated to this sale')
    # delivery_count = fields.Integer(string='Delivery Orders', compute='_compute_picking_ids')
    #
    # @api.multi
    # # @api.depends('procurement_group_id')
    # def _compute_picking_ids(self):
    #     for order in self:
    #         order.picking_ids = self.env['stock.picking'].search(
    #             [('group_id', '=', order.procurement_group_id.id)]) if order.procurement_group_id else []
    #         order.delivery_count = len(order.picking_ids)

    price_unit = fields.Float(string='Unit Price', track_visibility='always')
    company_id = fields.Many2one('res.company', 'Company',
                                 default=lambda self: self.env['res.users']._get_company())
    price_subtotal = fields.Float(string='Subtotal', track_visibility='always', compute="_price_discount")

    discount = fields.Float(compute="_get_discount_rate", store=True)

    @api.depends('discounted')
    def _get_discount_rate(self):
        for service in self:
            discount_rate = 0.00

            if service.discounted == True:
                discount_rate = 20.00
            else:
                discount_rate = 0.00

            service.discount = discount_rate

            service.update({'discount': discount_rate})
            print(" P Service =========================================================")

            print(service.discount)


    discount_value = fields.Float(string="Discount Amount",compute="_price_discount", store=True)
    
    user_id = fields.Many2one('res.users', 'Salesperson', default=lambda self: self.env.user)

    product_type = fields.Many2one('payment.config', string='Product Type', domain="[('is_parent', '=', 1), ('category', '=', 'service')]",
                                   default=lambda self: self.env['payment.config'].search([('name', '=', 'MM bundle')])[
                                       0].id)
    purchase_term = fields.Selection([('cash', 'Cash'), ('install', 'Installment')], string='Payment Type',
                                     default='install')

    @api.onchange('purchase_term')
    def purchase_term_change(self):
        if self.purchase_term:
            if self.purchase_term == 'cash':
                payment_term = self.env['payment.config'].search([('parent_id','=', self.product_type.id),('no_months','=',1)])
                self.new_payment_term_id = payment_term.id
            else:
                self.new_payment_term_id = False

    new_payment_term_id = fields.Many2one('payment.config', string='Payment Terms',
                                          domain="[('parent_id', '=', product_type),('payment_type','=',purchase_term),('bpt','=',True)]",
                                          # domain=new_payment_term_id_domain,
                                          required=1
                                          )
    tax_id = fields.Many2many('account.tax', string='Taxes',
                              domain=['|', ('active', '=', False), ('active', '=', True)])

    invoice_count = fields.Integer(string='# of Invoices', compute='_get_invoiced', readonly=True)
    # invoice_ids = fields.Many2many("account.invoice", string='Invoices', compute="_get_invoiced", readonly=True,
    #                                copy=False)
    invoice_status = fields.Selection([
        ('upselling', 'Upselling Opportunity'),
        ('invoiced', 'Fully Invoiced'),
        ('to invoice', 'To Invoice'),
        ('no', 'Nothing to Invoice'),
        ('paid', 'Fully Paid')
    ], string='Invoice Status', compute='_get_invoiced', store=True, readonly=True)
    # compute = '_get_invoiced'

    @api.onchange('product_type')
    def _product_type_onchange(self):
        self.prod_id = False
        self.lot_id = False

    prod_id = fields.Many2one('product.product', string='Product Class', required=False)

    lot_id = fields.Many2one('stock.production.lot', string='Lot / Vault', required=False, )
    is_used = fields.Boolean(default=False, string="Used")

    is_interment = fields.Boolean(default=False, store=True, onchange='show_fields')
    is_mm = fields.Boolean(default=False, store=True, onchange='show_fields')
    is_crematory = fields.Boolean(default=False, store=True, onchange='show_fields')
    inter_button = fields.Integer(compute='_count_interments')

    total_paid = fields.Float('Paid Amount', compute=_get_payment_info_json, track_visibility="always")

    installment_line_ids = fields.One2many(comodel_name='invoice.installment.line', inverse_name='service_order_id', string='Payment Schedule')
    service_avail_date = fields.Date(string="Avail Service Date")

    @api.depends('total_paid', 'installment_line_ids')
    def get_due(self):
        for res in self:
            if res.id:
                deposit = self.env['customer.deposit']
                deposit_ids = deposit.search([('service_order_id', '=', res.id)])
                installment_line = self.env['invoice.installment.line'].search([('service_order_id', '=', res.id)])
                due = 0.0
                total_paid = res.total_paid
                # if deposit_ids:
                #     for id_ in deposit_ids:
                #         total_paid += id_.amount
                dates = []
                amounts = []
                ids = []
                amount = []
                for line in installment_line:
                    amounts.append(line.amount_to_pay)
                    if sum(amounts) <= total_paid:
                        ids.append(line.id)
                        amount.append(line.amount_to_pay)
                due_list = installment_line.filtered(lambda rec: (rec.id not in ids) and (rec.date_for_payment < fields.Date.today()))
                sched_ = installment_line.filtered(lambda rec: rec.date_for_payment < fields.Date.today())
                sched_count = len(sched_) - 1
                for _list in due_list:
                    due += _list.amount_to_pay

                res.update({
                    'total_due': due,
                    'due_count': len(due_list),
                    'month_to_pay': datetime.strptime(res.order_date, '%Y-%m-%d') + relativedelta(months=sched_count)
                })

    total_due = fields.Float('Due', compute=get_due, store=True)
    due_count = fields.Float('Due Count', compute=get_due, store=True)
    month_to_pay = fields.Date('Payment Schedule', compute=get_due, store=True)

    @api.depends('total_due')
    def _has_due(self):
        for rec in self:
            order = self.env['service.order'].search([('id', '=', rec.id)])
            installment_line = self.env['invoice.installment.line'].search([('service_order_id', '=', rec.id)])
            due = 0.0
            total_paid = order.total_paid
            dates = []
            amounts = []
            ids = []
            amount = []
            for line in installment_line:
                amounts.append(line.amount_to_pay)
                if sum(amounts) <= total_paid:
                    ids.append(line.id)
                    amount.append(line.amount_to_pay)
            due_list = installment_line.filtered(
                lambda rec: (rec.id not in ids) and (rec.date_for_payment < fields.Date.today()))
            sched_ = installment_line.filtered(lambda rec: rec.date_for_payment < fields.Date.today())
            sched_count = len(sched_) - 1
            for _list in due_list:
                due += _list.amount_to_pay

            if due:
                rec.has_due = True
            else:
                rec.has_due = False

    has_due = fields.Boolean(default=False, compute=_has_due)

    @api.one
    def _count_interments(self):
        if self.env['interment.order2'].search([('or_id', '=', self.id)]):
            ic = self.env['interment.order2'].search_count([('or_id', '=', self.id)])
            self.inter_button = ic
        else:
            self.inter_button = 0

    @api.onchange('product_type')
    def show_fields(self):
        if self.product_type:
            if self.product_type.name == 'Interment Service / EIPP':
                self.is_interment = True
            else:
                self.is_interment = False

            if self.product_type.name == 'MM bundle':
                self.is_mm = True
                self.is_bundle = True
            else:
                self.is_mm = False
                self.is_bundle = False
            if self.product_type.name == 'Crematory Service':
                self.is_crematory = True
            else:
                self.is_crematory = False
        else:
            pass

    @api.depends('state', 'invoice_ids')
    def _get_invoiced(self):
        state = None
        invoice = self.filtered(lambda r: r.state != "cancel").mapped('invoice_ids')
        if len(invoice) >= 1:
            if invoice.filtered(lambda r: r.state == "cancel"):
                state = 'no'
            elif invoice.filtered(lambda r: r.state == "paid"):
                state = 'paid'
            else:
                state = 'invoiced'
        elif self.state != 'sale':
            state = 'no'
        else:
            state = 'to invoice'

        self.update({
            'invoice_count': len(invoice),
            'invoice_status': state
        })

    @api.onchange('product_id')
    def _get_taxes(self):
        for order in self:
            order.tax_id = [(6, 0, order.product_id.taxes_id.ids)]
            order.price_unit = order.product_id.list_price

    is_installable = fields.Boolean(default=False, compute="_installable")

    gross_amount = fields.Float(string="Gross Amount",compute="_compute_amount")
    adv_payment = fields.Float(string='Adv.', track_visibility='always', compute="_compute_amount")
    monthly_amort = fields.Float(string='Monthly Amortization', track_visibility='always', compute="_compute_amount")
    amount_tax = fields.Float(string='Taxes', track_visibility='always', compute="_compute_amount")
    discount_total = fields.Float(string="Total Discount", compute="_compute_amount", store=True)
    held_tax = fields.Float(string='Taxes', track_visibility='always', compute="_compute_amount")
    amount_untaxed = fields.Float(string='Untaxed Amount', track_visibility='always', compute="_compute_amount")
    amount_total = fields.Float(string='Total Amount', track_visibility='always', compute="_compute_amount")
    estimated_balance = fields.Float(string='Estimated Balance', track_visibility='always', compute="_get_estimated_balance")
    pcf = fields.Float(string='PCF', track_visibility='always', compute="_compute_amount")
    invoice_ids = fields.One2many(comodel_name="account.invoice", inverse_name="service_order_id", string="", required=False, )
    sales_ids = fields.One2many(comodel_name="sale.order", inverse_name="service_order_id", string="", required=False, limit=1)
    sales_ready = fields.Boolean(default=False, compute='_sales_ready')
    hide_payment = fields.Boolean(default=False, compute='_hide')

    ref_journal_entry = fields.Many2one(comodel_name="account.move", string="Journal Entry",  store=True) #compute="_get_journal_entry",
    ref_journal_entry_line = fields.One2many(related="ref_journal_entry.line_ids")

    @api.depends('invoice_ids')
    def _get_journal_entry(self):
        for service in self:
            print('___________ Check ___________________________')
            print(service.invoice_ids)

            invoice_result = self.env['account.invoice'].search([('service_order_id','=', service.id)], )
            print(invoice_result)
            if len(service.invoice_ids) != 0:
                print("May sulod Bai")

    


    @api.depends('sales_ids')
    def _has_sales(self):
        # todo add the sale order product and lot id in the filter.
        for rec in self:
            if len(rec.sales_ids) >= 1:
                rec.update({
                    'has_sales': True
                })
            else:
                rec.update({
                    'has_sales': False
                })
    has_sales = fields.Boolean(default=False, compute=_has_sales, store=True)

    # @api.multi
    # def _write(self, vals):
    #     res = super(ServiceOrder, self)._write(vals)
    #     self.filtered(lambda order: order.state == 'ready').state_onchange()
    #     return res

    @api.onchange('total_paid')
    @api.depends('amount_total', 'total_paid')
    def _sales_ready(self):
        for rec in self:
            if rec.amount_total != 0.0 and rec.total_paid == rec.amount_total:
                rec.sales_ready = True
                # if rec.state == 'ready':
                #     order = rec.filtered(lambda o: o.state != 'sale')
                #     print 'bong go 1'
                # rec.write({'state': 'sale'})
            else:
                rec.sales_ready = False

    @api.depends('sales_ready')
    def _hide(self):
        if not self.sales_ready and self.state == 'ready':
            self.hide_payment = False
        else:
            self.hide_payment = True

    # @api.multi
    # @api.onchange('total_paid', 'amount_total')
    # def state_onchange(self):
    #     if self.amount_total != 0.0 and self.total_paid == self.amount_total:
    #         self.sales_ready = True
    #         if self.state == 'ready':
    #             order = self.filtered(lambda o: o.state != 'sale')
    #             print 'state_onchange'
    #             return order.write({'state': 'sale'})
    #     else:
    #         print 'bogo'
    #         if self.amount_total != 0.0 and self.total_paid == self.amount_total:
    #             self.sales_ready = True
    #             if self.state == 'ready':
    #                 order = self.filtered(lambda o: o.state != 'sale')
    #                 return order.write({'state': 'sale'})

    @api.onchange('product_id')
    def _installable(self):
        for order in self:
            order.discount = 0.00
            order.is_installable = order.product_id.installable_product

    @api.onchange('partner_id')
    def _get_default_pricelist(self):
        for order in self:
            order.pricelist_id = order.partner_id.property_product_pricelist.id

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('service.order') or _('New')
            # vals['discount_total'] = vals['discount_value'] * vals['new_payment_term_id']['no_months']
            #vals['amount_total'] = vals['amount_untaxed'] - vals['discount_total'] - vals['amount_tax'] 

        result = super(ServiceOrder, self).create(vals)

        # if result.discounted:

        #     discount_ =(result.price_unit/1.12) * (result.discount/100.0 if result.discount > 0 else 0.00)
        #     result.discount_value = dis
            
        #     result.update({
        #                     'discount_value':amount_total,
        #         })

        return result

    @api.onchange('pricelist_id', 'product_id')
    def _from_pricelist(self):
        unit_price = None
        for order in self:
            pricelist_item = self.env['product.pricelist.item']
            product_price = pricelist_item.search(
                [('pricelist_id', '=', self.pricelist_id.id), ('applied_on', '=', '0_product_variant'),
                 ('product_id', '=', self.product_id.id)])
            if product_price:
                if product_price[-1].compute_price == 'fixed':
                    unit_price = product_price[-1].fixed_price
                elif product_price[-1].compute_price == 'percentage':
                    discount = order.product_id.lst_price * (product_price[-1].percent_price / 100)
                    unit_price = order.product_id.lst_price - discount
                else:
                    unit_price = 0.00
            else:
                unit_price = order.product_id.lst_price
            order.price_unit = unit_price

    @api.depends('price_unit', 'discount')
    def _price_discount(self):
        discount = unit_price = subtotal = 0.0
        for order in self:
            unit_price = order.price_unit
            # discount_rate =
            if order.discount:
                # discount = unit_price * discount
                discount = (unit_price/1.12) * (order.discount/100.0 if order.discount > 0 else 0.00)
                subtotal = unit_price  - discount
            else:
                subtotal = unit_price

            order.update({
                'price_subtotal': subtotal,
                'discount_value':discount,
            })

    @api.depends('tax_id')
    def compute_taxes(self):
        _vat = []
        _held = []
        _other = []
        vat = None
        held = None
        other = None
        if self.tax_id:
            for tax in self.tax_id:
                if tax.amount_type == 'vat':
                    _vat.append(tax.amount)
                elif tax.amount_type == 'held':
                    _held.append(tax.amount)
                else:
                    _other.append(tax.amount)

            vat = sum(_vat)
            held = sum(_held)
            other = sum(_other)

            print vat
            print held
            print other

        return{
            "vat": vat,
            "held": held,
            "other": other
        }

    @api.depends('price_subtotal', 'new_payment_term_id', 'discount', 'discount_value')
    def _compute_amount(self):

        _adv = 0.00
        _bal = 0.00
        _bal_wi = 0.00
        _total = 0.00
        _untaxed = 0.00
        _pcf = 0.00
        _taxed = 0.00
        _held = 0.00
        _total_discount = 0.00 # Total discount
        _gross = 0.00

        term = self.env['payment.config']
        for order in self:
            if not order.new_payment_term_id:
                pass
            else:
                if order.new_payment_term_id.bpt_wod:
                    _adv = 0.00
                    _bal = order.price_subtotal
                    _bal_wi = _bal * order.new_payment_term_id.less_perc
                else:
                    down = term.search([('parent_id', '=', order.product_type.id),
                                        ('name', '=', 'downpayment')
                                        ])
                    _adv = order.price_subtotal * down.less_perc if down else 0.00
                    _bal = order.price_subtotal * (1 - (down.less_perc or 0.0))
                    _bal_wi = 0 #(_bal if not order.product_id.installable_product else (_bal / order.new_payment_term_id.no_months)) * order.new_payment_term_id.less_perc

                # print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
                # print(_adv)
                _total = _adv + (_bal_wi * order.new_payment_term_id.no_months)
                # print(_total)

                taxes = order.compute_taxes()
                
                if order.product_id.has_pcf:
                    _pcf = _total * 0.10
                else:
                    _pcf = 0.00

                order.monthly_amort = _bal_wi
                # / (order.new_payment_term_id.no_months if order.product_id.installable_product else 1)
                order.adv_payment = _adv if _adv else order.monthly_amort

                _gross = order.price_unit * order.new_payment_term_id.no_months #(_total - _pcf) / (1 + (taxes['vat'] or 0.0) / 100.0)
                _untaxed = _gross - _pcf
                # _taxed = _untaxed * (taxes['vat'] or 0.0) / 100.0
                _held = _untaxed * (taxes['held'] or 0.0) / 100.0


                # print("*******************************************")
                # print(_total)
                # print(_total_discount)
                # print( _total - order.held_tax - _total_discount)
                
                tax_base = _untaxed - _total_discount
                tax_value = (tax_base / 1.12) * 0.12


                print(order.discount)
                print(order.discounted)
                discount = 0
                discount_value = 0

                if order.discounted:
                    discount = 20
                    discount_value = (order.price_unit/1.12) * (discount/100.0)


                print("++++++++++++++++++")
                print(discount_value)

                total_discount = discount_value * order.new_payment_term_id.no_months

                order.gross_amount = _gross
                order.amount_untaxed = _untaxed #- _pcf - _taxed
                order.pcf = _pcf
                order.amount_tax = tax_value
                order.held_tax = _held * - 1
                order.discount_total = total_discount
                order.amount_total = _untaxed - total_discount - tax_value
                # order.estimated_balance = order.amount_total - order.total_paid

                order.update({
                    'gross_amount':_gross,
                    'amount_untaxed': _untaxed,
                    'pcf': _pcf,
                    #'amount_tax': _taxed,
                    'amount_tax': tax_value,
                    'held_tax': _held * -1,
                    #'amount_total': _total - order.held_tax,
                    'discount_total':total_discount,
                    'amount_total': _untaxed - total_discount - tax_value,
                    # 'estimated_balance': order.amount_total - order.total_paid,
                })

                print("____-----------______________-----------")
                print({
                    'gross_amount':_gross,
                    'amount_untaxed': _untaxed,
                    'pcf': _pcf,
                    #'amount_tax': _taxed,
                    'amount_tax': tax_value,
                    'held_tax': _held * -1,
                    #'amount_total': _total - order.held_tax,
                    'discount_total':total_discount,
                    'amount_total': _untaxed - total_discount - tax_value,
                    # 'estimated_balance': order.amount_total - order.total_paid,
                })
                # pass

    @api.multi
    def confirm_(self):
        self.state = 'ready'
        self.invoice_status = 'no'

        installment_line = self.env['invoice.installment.line']
        installment_line.search([('service_order_id', '=', self.id)]).unlink()
        range_ = self.new_payment_term_id.no_months
        date_start_str = datetime.strptime(self.order_date, '%Y-%m-%d')
        for i in range(1, range_ + 1):
            installment_line.create({
                'name': "(%s/%s)" % (str(i), range_),
                'service_order_id': self.id,
                'date_for_payment': date_start_str,
                'customer_id': self.partner_id.id,
                'amount_to_pay': self.monthly_amort,
                'type': 'install',
                'payable_balance': self.monthly_amort,
                'series_no': i,
            })
            
            date_start_str = date_start_str + relativedelta(months=1)


        # acct_conf = self.env['brdc.transaction.acct.conf'].search([('model_reference','=','service.order')])

        # new_journal_entry = self.env['account.move'].create({
        #                                                         'name':acct_conf.account_journal.name,
        #                                                         'journal_id':acct_conf.account_journal.id,
        #                                                         'date': datetime.now(),
        #                                                         'company_id':self.env.user.company_id.id,
        #                                                         'state':'draft',
        #                                                     })
        # itemList = []

        # for line in acct_conf.reference_fields:
        #     field_value = self[line.field_reference]

        #     debit_value = 0
        #     credit_value = 0

        #     if line.account_type == 'debit':
        #         debit_value = field_value
        #         credit_value = 0
        #     else:
        #         credit_value = field_value
        #         debit_value = 0

        #     itemList.append({
        #                             'move_id':new_journal_entry.id,
        #                             'account_id':line.account.id,
        #                             'partner_id':self.partner_id.id,
        #                             'name': line.label,
        #                             'debit':debit_value,
        #                             'credit':credit_value,
        #                             'date_maturity':self.order_date,
        #                             'reconciled':False,
        #                             'company_id':self.env.user.company_id.id,
        #                     })

        # new_journal_entry.update({'line_ids':itemList})
        # self.ref_journal_entry = new_journal_entry.id

        # self.env['brdc.transactions'].create({
        #                                         'name': self.name + "/A_T",
        #                                         'ser_number': self.id,
        #                                         'journal_entry':new_journal_entry.id,
        #                                         'ref_type': 'service',
        # })

        #self.create_invoice(acct_conf.account_journal)

        # invoice_result = self.env['account.invoice'].search([('service_order_id','=',self.id)])
        # print("asasasasasasasasasasasasasasasasasasasasasasasasas")
        # print(invoice_result)

    @api.multi
    def create_invoice(self, journal_id):
        # print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
        # print("Creating Invoice")
        # self.ensure_one()
        # invoice = self.env['account.invoice'].search([])
        # service_order = self.env['service.order'].browse(self._context.get('active_ids', [])) or self.service_order_id
        # account_id = False

        payment_term_id = self.env['account.payment.term'].search([('name', '=', 'Immediate Payment')])
        # journal_id = self.env['account.invoice'].default_get(['journal_id'])['journal_id']
        # if not journal_id:
        #     raise UserError(_('Please define an accounting sale journal for this company.'))
        
        for order in self:
            payment_term = False if not order.new_payment_term_id.id else order.new_payment_term_id.id
            account_id = order.product_type.account_id
            if not account_id:
                raise UserError(
                    _('Please define income account for this product: "%s" (id:%d) - or for its category: "%s".') %
                    (order.product_id.name, order.product_id.id, order.product_id.categ_id.name))
            fpos = order.partner_id.property_account_position_id
            if fpos:
                account_id = fpos.map_account(account_id)

            invoice_vals = {
                'name': '',
                'origin': order.name,
                'type': 'in_invoice',
                'account_id': account_id.id,
                'partner_id': order.partner_id.id,
                'partner_shipping_id': order.partner_id.id,
                'journal_id': journal_id.id,
                'currency_id': order.pricelist_id.currency_id.id,
                # 'payment_term_id': order.new_payment_term_id.id, #order.payment_term_id.id,
                'fiscal_position_id': order.partner_id.property_account_position_id.id,
                'company_id': order.product_id.company_id.id,
                'user_id': order.user_id and order.user_id.id,
                'purchase_term': order.purchase_term,
                'product_type': order.product_type.id,
                'new_payment_term_id': False if order.purchase_term == 'cash' else order.new_payment_term_id.id,
                'spot_cash': order.amount_total,
                'service_order_id': order.id,
                'contract_price': order.amount_total,
                'date_invoice':date.today(),
                'invoice_line_ids': [(0, 0, {
                    'name': order.product_id.name,
                    'origin': order.name,
                    'account_id': order.product_id.property_account_income_id.id,
                    'price_unit': order.amount_total,
                    'quantity': 1,
                    'discount': order.discount,
                    # 'uom_id': self.product_uom.id,
                    'product_id': self.product_id.id or False,
                    'lot_id': self.lot_id.id or False,
                    'invoice_line_tax_ids': [(6, 0, order.tax_id.ids)],
                })],
                'unit_price': order.amount_untaxed,
                'pcf': order.pcf,
                'vat': order.amount_tax,
                'amount_tax': order.held_tax,

            }

            invoice = order.mapped('invoice_ids')
            invoice_created = self.env['account.invoice'].search([('id', 'in', invoice.ids), ('state', 'in', ['draft', 'open', 'paid'])])
            if len(invoice_created) >= 1:
                pass
            else:
                invoice.create(invoice_vals)
                order.invoice_status = 'invoiced'

        return True


    def cancel_(self):
        self.state = 'cancel'
        self.invoice_status = 'no'

    def draft_(self):
        self.state = 'draft'
        self.invoice_status = 'no'

    def confirm_sale(self):
        self.state = 'sale'

    fiscal_position_id = fields.Many2one('account.fiscal.position', oldname='fiscal_position', string='Fiscal Position')
    # product_uom = fields.Many2one('product.uom', string='Unit of Measure', required=True)

    # @api.multi
    # def action_view_invoice(self):
    # 	invoices = self.mapped('invoice_ids')
    # 	action = self.env.ref('account.action_invoice_tree1').read()[0]
    # 	for i in self.invoice_ids:
    # 		if len(i) > 1:
    # 			action['domain'] = [('id', 'in', i.ids)]
    # 		elif len(i) == 1:
    # 			action['views'] = [(self.env.ref('account.invoice_form').id, 'form')]
    # 			action['res_id'] = i[0].id
    # 			action['flags'] = {'initial_mode': 'edit'}
    # 		else:
    # 			action = {'type': 'ir.actions.act_window_close'}
    # 	return action
    @api.multi
    def button_dummy(self):
        pass

    @api.multi
    def action_view_invoice(self):
        invoices = self.filtered(lambda r: r.state != "cancel").mapped('invoice_ids')
        action = self.env.ref('account.action_invoice_tree1').read()[0]
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            action['views'] = [(self.env.ref('account.invoice_form').id, 'form')]
            action['res_id'] = invoices.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def view_sale_order(self):
        for so in self.sales_ids.filtered(lambda r: r.state != 'cancel'):
            return {
                'name': 'Sale Order',
                'res_model': 'sale.order',
                "res_id": so[0].id,
                'type': 'ir.actions.act_window',
                'target': 'self',
                'view_mode': 'form',
                'view_id': False,
                'view_type': 'form',
                'flags': {'initial_mode': 'edit'},
            }

    @api.multi
    def restructure_order(self):
        pass


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    service_order_id = fields.Many2one('service.order')
# class Stockpicking(models.Model):
# 	_inherit = 'stock.picking'
#
# 	# service_origin = fields.Charm


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    service_order_id = fields.Many2one('service.order')


class ServiceOrderInv(models.TransientModel):
    _name = 'service.order.invoice'

    state = fields.Selection(string="",
                             selection=[('with_product', 'Do not assign product'), ('no_product', 'Assign product'), ('from_other', "Assign from other's...")],
                             required=False, default='with_product')
    service_order_id = fields.Many2one('service.order', default=lambda rec: rec.env['service.order'].browse(
        rec._context.get('active_ids', [])).id, readonly=1)
    product_id = fields.Many2one('product.product', 'Product')
    lot_id = fields.Many2one('stock.production.lot', 'Lot / Vault')
    assign = fields.Boolean(default=False, compute='_compute_state')
    partner_id = fields.Many2one('res.partner', 'Lot Owner')

    @api.onchange('state')
    def onchange_state(self):
        self.partner_id = False

    @api.onchange('partner_id')
    def prod_domain(self):
        self.product_id = False
        self.lot_id = False

        product_ids = []
        if self.partner_id:
            stock_product_lot = self.env['stock.production.lot'].search([('loanee_name', '=', self.partner_id.id)])
            for stock in stock_product_lot:
                product_ids.append(stock.product_id.id)

            domain = {
                'product_id': [('id', 'in', product_ids)],
            }
        else:
            domain = {
                'product_id': [('type', '=', 'product')],
            }
        return {'domain': domain}

    @api.onchange('product_id')
    @api.depends('product_id')
    def lot_domain(self):
        self.lot_id = False
        lot_ids = []

        if self.partner_id:
            stock_product_lot = self.env['stock.production.lot'].search([('loanee_name', '=', self.partner_id.id)])
            for stock in stock_product_lot:
                lot_ids.append(stock.id)

            if self.product_id:
                domain = {
                    'lot_id': [('id', 'in', lot_ids), ('product_id', '=', self.product_id.id), ('status', 'not in', ('ter', 'fi', 'av'))]
                }
            else:
                domain = {
                    'lot_id': [('product_id', '=', self.product_id.id), ('status', '=', 'av')]
                }
            return {'domain': domain}


    @api.multi
    def _get_service_order(self):
        active_id = self.env['service.order'].browse(self._context.get('active_ids', []))
        print active_id
        self.service_order_id = active_id.id
        # s.update({
        #     'service_order_id': active_id.id
        # })

    @api.depends('service_order_id.prod_id')
    def _compute_state(self):
        if self.service_order_id.prod_id.id:
            self.assign = False
            self.state = 'with_product'
            print 'with_product'
        elif not self.service_order_id.prod_id.id:
            self.assign = True
            self.state = 'no_product'
            print 'no_product'
        else:
            pass

    @api.multi
    def create_sale_order(self):
        self.ensure_one()
        service_order = self.env['service.order'].browse(self._context.get('active_ids', [])) or self.service_order_id
        payment_term_id = self.env['account.payment.term'].search([('name', '=', 'Immediate Payment')])
        rec = None
        for order in service_order:
            sale_values = {
                'service_order_id': order.id,
                'product_type': order.product_type.id,
                'partner_id': order.partner_id.id,
                'purchase_term': 'cash',
                'new_payment_term_id': order.new_payment_term_id.id,
                'payment_term_id': payment_term_id.id,
                'name': 'New',
                'pricelist_id': order.pricelist_id.id,
                'order_line': [(0, 0, {
                    'name': order.product_id.name,
                    'product_id': order.product_id.id,
                    'product_uom_quantity': 1,
                    'price_unit': order.amount_total,
                })] if self.state in ('with_product', 'from_other') else [(0, 0, {
                    'name': self.product_id.name,
                    'product_id': self.product_id.id,
                    'lot_id': self.lot_id.id,
                    'product_uom_quantity': 1,
                    'price_unit': order.amount_total,
                    'tax_id': [(6, 0, order.tax_id.ids)],
                })],
                'spot_cash': order.amount_total,
                'amount_untaxed': order.amount_untaxed,
                'pcf': order.pcf,
                'amount_tax': order.amount_tax,
                'other_taxes': order.held_tax,
                'prod_id': self.product_id.id if self.state in ('no_product', 'from_other') else order.prod_id.id,
                'lot_id': order.lot_id.id if self.state == 'with_product' else self.lot_id.id,
                'is_interment': True
            }

            sales = order.mapped('sales_ids')
            sales_created = self.env['sale.order'].search([('id', '=', sales.ids), ('state', '!=', 'cancel')])
            if len(sales_created) >= 1:
                pass
            else:
                order.state = 'sale'
                sales.create(sale_values)
        pass

    @api.multi
    def create_invoice(self):
        # print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
        # print("Creating Invoice")
        self.ensure_one()
        invoice = self.env['account.invoice'].search([])
        service_order = self.env['service.order'].browse(self._context.get('active_ids', [])) or self.service_order_id
        account_id = False

        payment_term_id = self.env['account.payment.term'].search([('name', '=', 'Immediate Payment')])
        journal_id = self.env['account.invoice'].default_get(['journal_id'])['journal_id']
        if not journal_id:
            raise UserError(_('Please define an accounting sale journal for this company.'))
        for order in service_order:
            payment_term = False if not order.new_payment_term_id.id else order.new_payment_term_id.id
            account_id = order.product_type.account_id
            if not account_id:
                raise UserError(
                    _('Please define income account for this product: "%s" (id:%d) - or for its category: "%s".') %
                    (order.product_id.name, order.product_id.id, order.product_id.categ_id.name))
            fpos = order.partner_id.property_account_position_id
            if fpos:
                account_id = fpos.map_account(account_id)

            invoice_vals = {
                'name': '',
                'origin': order.name,
                'type': 'out_invoice',
                'account_id': account_id.id,
                'partner_id': order.partner_id.id,
                'partner_shipping_id': order.partner_id.id,
                'journal_id': journal_id,
                'currency_id': order.pricelist_id.currency_id.id,
                'payment_term_id': payment_term_id.id,
                'fiscal_position_id': order.partner_id.property_account_position_id.id,
                'company_id': order.product_id.company_id.id,
                'user_id': order.user_id and order.user_id.id,
                'purchase_term': 'cash',
                'product_type': order.product_type.id,
                'new_payment_term_id': False,
                'spot_cash': order.amount_total,
                'service_order_id': order.id,
                'contract_price': order.amount_total,
                'invoice_line_ids': [(0, 0, {
                    'name': self.product_id.name,
                    'origin': order.name,
                    'account_id': self.product_id.account_id.id,
                    'price_unit': order.amount_total,
                    'quantity': 1,
                    'discount': order.discount,
                    # 'uom_id': self.product_uom.id,
                    'product_id': self.product_id.id or False,
                    'lot_id': self.lot_id.id or False,
                    'invoice_line_tax_ids': [(6, 0, order.tax_id.ids)],
                })],
                'unit_price': order.amount_untaxed,
                'pcf': order.pcf,
                'vat': order.amount_tax,
                'amount_tax': order.held_tax,

            }

            invoice = order.mapped('invoice_ids')
            invoice_created = self.env['account.invoice'].search([('id', 'in', invoice.ids), ('state', 'in', ['draft', 'open', 'paid'])])
            if len(invoice_created) >= 1:
                pass
            else:
                invoice.create(invoice_vals)
                order.invoice_status = 'invoiced'

        return True


class ServiceOrderDraft(models.TransientModel):
    _name = 'service.order.draft'

    @api.multi
    def action_draft(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []

        for record in self.env['service.order'].browse(active_ids):
            if record.state != 'cancel':
                raise UserError(
                    _("Selected order(s) cannot be set to Draft."))
            record.draft_()
        return {'type': 'ir.actions.act_window_close'}


class ServiceOrderCancel(models.TransientModel):
    _name = 'service.order.cancel'

    @api.multi
    def action_cancel(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []

        for record in self.env['service.order'].browse(active_ids):
            if record.state == 'cancel':
                raise UserError(
                    _("Selected order(s) cannot be Cancel."))
            record.cancel_()
        return {'type': 'ir.actions.act_window_close'}

