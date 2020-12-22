import odoo.addons.decimal_precision as dp
from itertools import groupby
from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.misc import formatLang

# class SaleOrderLine(models.Model):
#     _name = 'product.transfer.line'
#     _inherit = 'sale.order.line'
#
#     trans_order_id = fields.Many2one('account.transfer.inv')



class AccountTransferInv(models.Model):
    _inherit = 'account.transfer.inv'

    # order_line = fields.One2many('sale.order.line', 'trans_order_id', string='Order Lines',
    #                              states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=True)
    # contract = fields.Float(string='Contract', store=True, readonly=True, compute='_amount_all',
    #                               track_visibility='always')
    pcf = fields.Float(string='PCF', store=True, readonly=True, compute='_amount_all',
                                  track_visibility='always')
    contract = fields.Float(string='Contract Price', store=True, readonly=True, compute='_amount_all',
                                  track_visibility='always')

    @api.depends('product_line')
    def _amount_all(self):
        for order in self:
            amount_untaxed = amount_tax = 0
            unit_price = 0
            pcf = 0
            advance = order.amount_paid
            contract = 0
            down = 0
            balance = 0
            wi_balance = 0
            term = self.env['payment.config']
            for line in order.product_line:
                unit_price += line.price_subtotal
                if not order.new_payment_term_id.bpt_wod:
                    down_perc = term.search([('name', '=', 'downpayment'), ('parent_id', '=', order.product_type.id)])
                    down = unit_price * down_perc.less_perc
                    balance = unit_price * (1 - down_perc.less_perc)
                    wi_balance = balance * order.new_payment_term_id.less_perc
                elif order.new_payment_term_id.bpt_wod:
                    down = 0
                    wi_balance = unit_price * order.new_payment_term_id.less_perc
                if line.product_id.has_pcf:
                    contract = down + wi_balance
                    # contract = (unit_price - advance) * order.new_payment_term_id.less_perc
                    pcf = contract * 0.10
                    amount_untaxed = (contract * 0.90) - advance
                else:
                    contract = down + wi_balance
                    amount_untaxed = contract - advance

                price = amount_untaxed * (1 - (line.discount or 0.0) / 100.0)
                taxes = line.tax_id.compute_all(price, line.trans_order_id.currency_id, line.product_uom_qty,
                                                product=line.product_id,
                                                partner=line.trans_order_id.partner_shipping_id)

                order.update({
                    'contract': contract,
                    'amount_untaxed': amount_untaxed / (1 + (taxes['total_included'] - taxes['total_excluded'])),
                    'pcf': pcf,
                    'amount_tax': (amount_untaxed / (1 + (taxes['total_included'] - taxes['total_excluded']))) * (
                                taxes['total_included'] - taxes['total_excluded']),
                    'amount_total': (amount_untaxed / (1 + (taxes['total_included'] - taxes['total_excluded']))) + (
                                amount_untaxed / (1 + (taxes['total_included'] - taxes['total_excluded']))) * (
                                                taxes['total_included'] - taxes['total_excluded']) + pcf,
                    'monthly_payment': ((amount_untaxed / (1 + (taxes['total_included'] - taxes['total_excluded']))) + (
                                amount_untaxed / (1 + (taxes['total_included'] - taxes['total_excluded']))) * (
                                                    taxes['total_included'] - taxes[
                                                'total_excluded']) + pcf) / self.remaining_month,
                })


class ProductTransferLine(models.Model):
    _name = 'product.transfer.line'
    _order = 'trans_order_id, layout_category_id, sequence, id'

    trans_order_id = fields.Many2one('account.transfer.inv')

    # @api.depends('state', 'product_uom_qty', 'qty_delivered', 'qty_to_invoice', 'qty_invoiced')
    # def _compute_invoice_status(self):
    #     precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
    #     for line in self:
    #         if line.state not in ('sale', 'done'):
    #             line.invoice_status = 'no'
    #         elif not float_is_zero(line.qty_to_invoice, precision_digits=precision):
    #             line.invoice_status = 'to invoice'
    #         elif line.state == 'sale' and line.product_id.invoice_policy == 'order' and \
    #                 float_compare(line.qty_delivered, line.product_uom_qty, precision_digits=precision) == 1:
    #             line.invoice_status = 'upselling'
    #         elif float_compare(line.qty_invoiced, line.product_uom_qty, precision_digits=precision) >= 0:
    #             line.invoice_status = 'invoiced'
    #         else:
    #             line.invoice_status = 'no'

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(price, line.trans_order_id.currency_id, line.product_uom_qty,
                                            product=line.product_id, partner=line.trans_order_id.partner_shipping_id)
            line.update({
                'price_tax': taxes['total_included'] - taxes['total_excluded'],
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    @api.depends('price_unit', 'discount')
    def _get_price_reduce(self):
        for line in self:
            line.price_reduce = line.price_unit * (1.0 - line.discount / 100.0)

    @api.depends('price_total', 'product_uom_qty')
    def _get_price_reduce_tax(self):
        for line in self:
            line.price_reduce_taxinc = line.price_total / line.product_uom_qty if line.product_uom_qty else 0.0

    @api.depends('price_subtotal', 'product_uom_qty')
    def _get_price_reduce_notax(self):
        for line in self:
            line.price_reduce_taxexcl = line.price_subtotal / line.product_uom_qty if line.product_uom_qty else 0.0

    @api.multi
    def _compute_tax_id(self):
        for line in self:
            fpos = line.trans_order_id.fiscal_position_id or line.trans_order_id.partner_id.property_account_position_id
            taxes = line.product_id.taxes_id.filtered(lambda r: not line.company_id or r.company_id == line.company_id)
            line.tax_id = fpos.map_tax(taxes, line.product_id, line.trans_order_id.partner_shipping_id) if fpos else taxes

    @api.model
    def _get_purchase_price(self, pricelist, product, product_uom, date):
        return {}

    # @api.model
    # def _prepare_add_missing_fields(self, values):
    #     res = {}
    #     onchange_fields = ['name', 'price_unit', 'product_uom', 'tax_id']
    #     if values.get('order_id') and values.get('product_id') and any(f not in values for f in onchange_fields):
    #         line = self.new(values)
    #         line.product_id_change()
    #         for field in onchange_fields:
    #             if field not in values:
    #                 res[field] = line._fields[field].convert_to_write(line[field], line)
    #     return res

    name = fields.Text(string='Description', required=True)
    sequence = fields.Integer(string='Sequence', default=10)

    invoice_lines = fields.Many2many('account.invoice.line', 'sale_order_line_invoice_rel', 'order_line_id',
                                     'invoice_line_id', string='Invoice Lines', copy=False)
    # invoice_status = fields.Selection([
    #     ('upselling', 'Upselling Opportunity'),
    #     ('invoiced', 'Fully Invoiced'),
    #     ('to invoice', 'To Invoice'),
    #     ('no', 'Nothing to Invoice')
    # ], string='Invoice Status', compute='_compute_invoice_status', store=True, readonly=True, default='no')
    price_unit = fields.Float('Unit Price', required=True, digits=dp.get_precision('Product Price'), default=0.0)

    price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', readonly=True, store=True)
    price_tax = fields.Monetary(compute='_compute_amount', string='Taxes', readonly=True, store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='Total', readonly=True, store=True)

    price_reduce = fields.Monetary(compute='_get_price_reduce', string='Price Reduce', readonly=True, store=True)
    tax_id = fields.Many2many('account.tax', string='Taxes',
                              domain=['|', ('active', '=', False), ('active', '=', True)])
    price_reduce_taxinc = fields.Monetary(compute='_get_price_reduce_tax', string='Price Reduce Tax inc', readonly=True,
                                          store=True)
    price_reduce_taxexcl = fields.Monetary(compute='_get_price_reduce_notax', string='Price Reduce Tax excl',
                                           readonly=True, store=True)

    discount = fields.Float(string='Discount (%)', digits=dp.get_precision('Discount'), default=0.0)

    product_id = fields.Many2one('product.product', string='Product', domain=[('sale_ok', '=', True)],
                                 change_default=True, ondelete='restrict', required=True)
    product_uom_qty = fields.Float(string='Quantity', digits=dp.get_precision('Product Unit of Measure'), required=True,
                                   default=1.0)
    product_uom = fields.Many2one('product.uom', string='Unit of Measure', required=True)

    qty_delivered_updateable = fields.Boolean(compute='_compute_qty_delivered_updateable', string='Can Edit Delivered',
                                              readonly=True, default=True)
    qty_delivered = fields.Float(string='Delivered', copy=False, digits=dp.get_precision('Product Unit of Measure'),
                                 default=0.0)
    # qty_to_invoice = fields.Float(
    #     compute='_get_to_invoice_qty', string='To Invoice', store=True, readonly=True,
    #     digits=dp.get_precision('Product Unit of Measure'))
    # qty_invoiced = fields.Float(
    #     compute='_get_invoice_qty', string='Invoiced', store=True, readonly=True,
    #     digits=dp.get_precision('Product Unit of Measure'))

    # salesman_id = fields.Many2one(related='order_id.user_id', store=True, string='Salesperson', readonly=True)
    @api.depends('product_id.invoice_policy','trans_order_id.state')
    def _compute_qty_delivered_updateable(self):
        for line in self:
            line.qty_delivered_updateable = (line.trans_order_id.state == 'sent') and (
                        line.product_id.track_service == 'manual') and (line.product_id.expense_policy == 'no')

    currency_id = fields.Many2one(related='trans_order_id.currency_id', store=True, string='Currency', readonly=True)
    company_id = fields.Many2one(related='trans_order_id.company_id', string='Company', store=True, readonly=True)
    order_partner_id = fields.Many2one(related='trans_order_id.partner_id', store=True, string='Customer')

    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags')

    # ranzu
    lot_id = fields.Many2one('stock.production.lot', string='Lot / Vault', required=False, )
    # ranzu
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sale Order'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Order Status', readonly=True, copy=False, store=True, default='draft')

    customer_lead = fields.Float(
        'Delivery Lead Time', required=True, default=0.0,
        help="Number of days between the order confirmation and the shipping of the products to the customer",
        oldname="delay")
    procurement_ids = fields.One2many('procurement.order', 'sale_line_id', string='Procurements')

    layout_category_id = fields.Many2one('sale.layout_category', string='Section')
    layout_category_sequence = fields.Integer(string='Layout Sequence')


    @api.multi
    def _get_display_price(self, product):
        if self.trans_order_id.pricelist_id.discount_policy == 'with_discount':
            return product.with_context(pricelist=self.trans_order_id.pricelist_id.id).price
        final_price, rule_id = self.trans_order_id.pricelist_id.get_product_price_rule(self.product_id,
                                                                                 self.product_uom_qty or 1.0,
                                                                                 self.trans_order_id.partner_id)
        context_partner = dict(self.env.context, partner_id=self.trans_order_id.partner_id.id, date=self.trans_order_id.date_order)
        base_price, currency_id = self.with_context(context_partner)._get_real_price_currency(self.product_id, rule_id,
                                                                                              self.product_uom_qty,
                                                                                              self.product_uom,
                                                                                              self.trans_order_id.pricelist_id.id)
        if currency_id != self.trans_order_id.pricelist_id.currency_id.id:
            base_price = self.env['res.currency'].browse(currency_id).with_context(context_partner).compute(base_price,
                                                                                                            self.trans_order_id.pricelist_id.currency_id)
        return max(base_price, final_price)

    @api.multi
    @api.onchange('product_id')
    def product_id_change(self):
        if not self.product_id:
            return {'domain': {'product_uom': []}}

        vals = {}
        domain = {'product_uom': [('category_id', '=', self.product_id.uom_id.category_id.id)]}
        if not self.product_uom or (self.product_id.uom_id.id != self.product_uom.id):
            vals['product_uom'] = self.product_id.uom_id
            vals['product_uom_qty'] = 1.0

        product = self.product_id.with_context(
            lang=self.trans_order_id.partner_id.lang,
            partner=self.trans_order_id.partner_id.id,
            quantity=vals.get('product_uom_qty') or self.product_uom_qty,
            date=self.trans_order_id.date_order,
            pricelist=self.trans_order_id.pricelist_id.id,
            uom=self.product_uom.id
        )

        result = {'domain': domain}

        title = False
        message = False
        warning = {}
        if product.sale_line_warn != 'no-message':
            title = _("Warning for %s") % product.name
            message = product.sale_line_warn_msg
            warning['title'] = title
            warning['message'] = message
            result = {'warning': warning}
            if product.sale_line_warn == 'block':
                self.product_id = False
                return result

        name = product.name_get()[0][1]
        if product.description_sale:
            name += '\n' + product.description_sale
        vals['name'] = name

        self._compute_tax_id()

        if self.trans_order_id.pricelist_id and self.trans_order_id.partner_id:
            vals['price_unit'] = self.env['account.tax']._fix_tax_included_price_company(
                self._get_display_price(product), product.taxes_id, self.tax_id, self.company_id)
        self.update(vals)

        return result

    @api.onchange('product_uom', 'product_uom_qty')
    def product_uom_change(self):
        if not self.product_uom or not self.product_id:
            self.price_unit = 0.0
            return
        if self.trans_order_id.pricelist_id and self.trans_order_id.partner_id:
            product = self.product_id.with_context(
                lang=self.trans_order_id.partner_id.lang,
                partner=self.trans_order_id.partner_id.id,
                quantity=self.product_uom_qty,
                date=self.trans_order_id.date_order,
                pricelist=self.trans_order_id.pricelist_id.id,
                uom=self.product_uom.id,
                fiscal_position=self.env.context.get('fiscal_position')
            )
            self.price_unit = self.env['account.tax']._fix_tax_included_price_company(self._get_display_price(product),
                                                                                      product.taxes_id, self.tax_id,
                                                                                      self.company_id)

    def _get_real_price_currency(self, product, rule_id, qty, uom, pricelist_id):
        PricelistItem = self.env['product.pricelist.item']
        field_name = 'lst_price'
        currency_id = None
        product_currency = None
        if rule_id:
            pricelist_item = PricelistItem.browse(rule_id)
            if pricelist_item.pricelist_id.discount_policy == 'without_discount':
                while pricelist_item.base == 'pricelist' and pricelist_item.base_pricelist_id and pricelist_item.base_pricelist_id.discount_policy == 'without_discount':
                    price, rule_id = pricelist_item.base_pricelist_id.with_context(uom=uom.id).get_product_price_rule(
                        product, qty, self.trans_order_id.partner_id)
                    pricelist_item = PricelistItem.browse(rule_id)

            if pricelist_item.base == 'standard_price':
                field_name = 'standard_price'
            if pricelist_item.base == 'pricelist' and pricelist_item.base_pricelist_id:
                field_name = 'price'
                product = product.with_context(pricelist=pricelist_item.base_pricelist_id.id)
                product_currency = pricelist_item.base_pricelist_id.currency_id
            currency_id = pricelist_item.pricelist_id.currency_id

        product_currency = product_currency or (
                    product.company_id and product.company_id.currency_id) or self.env.user.company_id.currency_id
        if not currency_id:
            currency_id = product_currency
            cur_factor = 1.0
        else:
            if currency_id.id == product_currency.id:
                cur_factor = 1.0
            else:
                cur_factor = currency_id._get_conversion_rate(product_currency, currency_id)

        product_uom = self.env.context.get('uom') or product.uom_id.id
        if uom and uom.id != product_uom:
            # the unit price is in a different uom
            uom_factor = uom._compute_price(1.0, product.uom_id)
        else:
            uom_factor = 1.0

        return product[field_name] * uom_factor * cur_factor, currency_id.id

    @api.onchange('product_id', 'price_unit', 'product_uom', 'product_uom_qty', 'tax_id')
    def _onchange_discount(self):
        self.discount = 0.0
        if not (self.product_id and self.product_uom and
                self.trans_order_id.partner_id and self.trans_order_id.pricelist_id and
                self.trans_order_id.pricelist_id.discount_policy == 'without_discount' and
                self.env.user.has_group('sale.group_discount_per_so_line')):
            return

        context_partner = dict(self.env.context, partner_id=self.trans_order_id.partner_id.id, date=self.trans_order_id.date_order)
        pricelist_context = dict(context_partner, uom=self.product_uom.id)

        price, rule_id = self.trans_order_id.pricelist_id.with_context(pricelist_context).get_product_price_rule(
            self.product_id, self.product_uom_qty or 1.0, self.trans_order_id.partner_id)
        new_list_price, currency_id = self.with_context(context_partner)._get_real_price_currency(self.product_id,
                                                                                                  rule_id,
                                                                                                  self.product_uom_qty,
                                                                                                  self.product_uom,
                                                                                                  self.trans_order_id.pricelist_id.id)

        if new_list_price != 0:
            if self.trans_order_id.pricelist_id.currency_id.id != currency_id:
                # we need new_list_price in the same currency as price, which is in the SO's pricelist's currency
                new_list_price = self.env['res.currency'].browse(currency_id).with_context(context_partner).compute(
                    new_list_price, self.trans_order_id.pricelist_id.currency_id)
            discount = (new_list_price - price) / new_list_price * 100
            if discount > 0:
                self.discount = discount
