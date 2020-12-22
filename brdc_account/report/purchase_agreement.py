from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrders(models.Model):
    _inherit = 'sale.order'

    @api.multi
    def print_purchase_order(self):
        for loan in self:
            if loan.product_type.category == 'product' and loan.purchase_term == 'install':
                return loan.env['report'].get_action(loan, 'brdc_account.purchase_agreement_template')
            elif loan.product_type.category == 'product' and loan.purchase_term == 'cash':
                return loan.env['report'].get_action(loan, 'brdc_account.cash_agreement_report_template')
            elif loan.is_bundle:
                pass
            else:
                return loan.env['report'].get_action(loan, 'brdc_account.eipp_agreement_report_template')

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    # @api.multi
    # def write(self, vals, context = None):
    #     pa_ref = ''
    #     if 'pa_ref' in vals and vals['pa_ref']:
    #         pa_ref = vals['pa_ref']
    #     elif 'pa_ref' in vals and vals['pa_ref']:
    #         pa_ref = self.pa_ref
    #     else:
    #         pa_ref = 1
    #
    #     vals['pa_ref'] = "%s" % (pa_ref)
    #
    #     pa_ref_id = self.env['account.invoice'].search([('id', '!=', self.id), ('pa_ref', '=', vals['pa_ref'])])
    #     if pa_ref_id:
    #         raise UserError(_('PA Reference Redundancy.'))
    #
    #     res = super(AccountInvoice, self).write(vals)
    #
    #     return res

    # @api.multi
    # def create(self,vals):
    #
    #     res = super(AccountInvoice, self).create(vals)
    #     pa_ref_id = self.env['account.invoice'].search([('id', '!=', res.id), ('pa_ref', '=', vals['pa_ref'])])
    #     if pa_ref_id:
    #         pass
    #
    #     return res

    @api.multi
    def print_purchase_order(self):
        for loan in self:
            stock_lot = self.env['stock.production.lot'].search([('sale_order_id', '=', self.sale_order_id.id)])
            if not stock_lot:
                raise UserError(_('Lot not assigned!'))
            if not loan.pa_ref:
                raise UserError(_('PA Reference is empty!'))

            pa_ref = self.env['account.invoice'].search([('id','!=',self.id),('pa_ref','=',self.pa_ref)])
            if pa_ref:
                raise UserError(_('PA Reference Redundancy.'))
            if loan.purchase_term == 'cash' and not loan.is_split:
                if loan.state != 'paid':
                    raise UserError(_('Not yet Paid'))

            return loan.env['report'].get_action(loan, 'brdc_account.purchase_agreement_template')

    @api.multi
    def get_lots(self):
        stock_lot = self.env['stock.production.lot'].search([('sale_order_id','=',self.sale_order_id.id)])
        lots = []
        if stock_lot:
            for so in stock_lot:
                lots.append("Block %s Lot %s" % (so.block_number, so.lot_number))
        # else:
            # for line in self.invoice_line_ids:
            #     if line[0].quantity == 1:
            #         print(1)
                    # lots.append("Block %s Lot %s" % (line[0].block_number, line[0].lot_number))

        return ", ".join(lots)

    @api.multi
    def get_lot_price(self):
        sale_order = self.env['sale.order'].search([('id','=',self.sale_order_id.id)])
        lot_price = 0.00
        for so in sale_order:
            if self.purchase_term == 'cash' or self.new_payment_term_id.no_months >= 60:
                product = self.env['product.product'].search([('id','=',so.product_id.id)])
                for pro in product:
                    lot_price = pro.list_price
            else:
                for sol in so.order_line:
                    lot_price = sol.price_unit

        return '{:0,.2f}'.format(lot_price)

    @api.multi
    def get_downpayment(self):
        downpayment = 0.00
        installment_line = self.env['invoice.installment.line'].search([('account_invoice_id','=',self.id)])
        for s in self:
            if s.purchase_term == 'cash' and not s.is_split:
                downpayment = 0.00
            elif s.purchase_term == 'cash' and s.is_split:
                downpayment = s.amount_total / 3
            else:
                if s.is_split and s.st4_dp != 0:
                    downpayment = s.st4_dp
                elif s.is_paidup and s.s_dp != 0:
                    downpayment = s.s_dp
                else:
                    if s.o_dp != 0:
                        downpayment = s.o_dp
                    else:
                        downpayment = installment_line[0].paid_amount
        return '{:0,.2f}'.format(downpayment)

    @api.multi
    def get_balance_due(self):
        due = 0.00
        downpayment = 0.00
        installment_line = self.env['invoice.installment.line'].search([('account_invoice_id', '=', self.id)])
        for s in self:
            if s.purchase_term == 'cash' and not s.is_split:
                downpayment = s.amount_total
            elif s.purchase_term == 'cash' and s.is_split:
                downpayment = s.amount_total / 3
            else:
                if s.is_split and s.st4_dp != 0:
                    downpayment = s.st4_dp
                elif s.is_paidup and s.s_dp != 0:
                    downpayment = s.s_dp
                else:
                    if s.o_dp != 0:
                        downpayment = s.o_dp
                    else:
                        downpayment = installment_line[0].paid_amount
            due = s.amount_untaxed - downpayment

        return '{:0,.2f}'.format(due)

    @api.multi
    def get_monthly(self):
        monthly = 0.00
        for s in self:
            if s.purchase_term == 'cash' and s.is_split:
                monthly = s.amount_total / 3
            elif s.purchase_term == 'cash' and not s.is_split:
                monthly = 0.00
            else:
                # if s.is_split:
                #     monthly = s.monthly_payment / 4
                # else:
                monthly = s.monthly_payment
        return '{:0,.2f}'.format(monthly)

    @api.multi
    def get_term(self):
        term = ''
        for s in self:
            if s.purchase_term == 'cash' and s.is_split:
                term = 'Deferred Cash'
            elif s.purchase_term == 'cash' and not s.is_split:
                term = 'Spot Cash'
            else:
                if s.is_split:
                    term = '%s MONS' % (s.new_payment_term_id.no_months + 3)
                else:
                    if s.o_dp == 0:
                        term = '%s MONS' % (s.new_payment_term_id.no_months - 1)
                    else:
                        term = '%s MONS' % s.new_payment_term_id.no_months
        return term.upper()

    @api.multi
    def get_pcf(self):
        return '{:0,.2f}'.format(self.pcf)

    @api.multi
    def get_vat(self):
        return '{:0,.2f}'.format(self.amount_tax)
