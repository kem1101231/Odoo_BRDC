from odoo import api, fields, models, _
from odoo.exceptions import UserError

class AccountTransfer(models.Model):
    _name = 'account.transfer'
    _order = 'create_date desc'

    partner_id = fields.Many2one('res.partner')
    invoice_id = fields.Many2one('account.invoice')

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    partner_id = fields.Many2one('res.partner', string='Partner', change_default=True,
                                 required=True,
                                 track_visibility='always')
    change_state = fields.Selection(string="Change", selection=[('draft', 'Draft'),
                                                                ('request', 'Requesting'),
                                                                ('progress','On Progress'),
                                                                ('sent','Sent'),
                                                                ('created', 'Created'),
                                                                ('approved', 'Approved'),
                                                                ('cancelled', 'Cancelled'), ], required=False, default='draft')
    has_request = fields.Boolean(default=False)

    transfer_ids = fields.One2many(comodel_name="account.transfer",
                                          inverse_name="invoice_id",
                                          string="Account Transfer",
                                          required=False,
                                          )
    sales_ids = fields.One2many(comodel_name="sale.order", inverse_name="invoice_id", string="History of Order", required=False, domain=[('invoice_status','=','invoiced')])

    transaction_inv_id = fields.Many2one('account.transfer.inv')

    @api.multi
    def action_request(self):
        self.change_state = 'request'
        for s in self:
            s.name = '(%s [%s])' % (s.number,'Requesting')
            s.has_request = True


    # @api.multi
    # def action_view_requests(self):
    #     action_id = self.env.ref('account.action_invoice_tree1')
    #     return {
    #         'name': action_id.name,
    #         'type': action_id.type,
    #         'res_model': action_id.res_model,
    #         'view_type': action_id.view_type,
    #         'view_mode': action_id.view_mode,
    #         'search_view_id': action_id.search_view_id,
    #         'domain': [('type','in',('out_invoice', 'out_refund')),('has_request', '=', True)],
    #         'context': action_id.context
    #     }

    @api.multi
    def action_create(self):
        move = self.move_id
        moves = self.env['account.move.line']
        lines_credit = moves.search([('move_id', '!=', move.id), ('id', 'in', move.line_ids.get_reconcile())])
        transfer_account = self.env['account.transfer.inv']
        payment = self.env['account.payment'].search(
            [('account_invoice_id', '=', self.id)])
        r_installment = self.env['invoice.installment.line'].search([('account_invoice_id', '=', self.id),
                                                                   ('is_paid', '=', False)])
        p_installment = self.env['invoice.installment.line'].search([('account_invoice_id', '=', self.id),
                                                                   ('is_paid', '=', True)])
        so_ = self.env['sale.order'].search([('name','=',self.origin)])

        if transfer_account.search(
                [('invoice_id', '=', self.id), ('state', 'not in', ('created', 'approved', 'cancelled'))]):
            transfer_account.search(
                [('invoice_id', '=', self.id), ('state', 'not in', ('created','approved','cancelled'))]).unlink()
        else:
            # print self.company_id.name
            transfer_account.create({
                'type': 'account',
                'partner_id': self.partner_id.id,
                'invoice_id': self.id,
                'product_type': self.product_type.id,
                'new_payment_term_id': self.new_payment_term_id.id,
                'amount_paid': sum(acc.credit for acc in lines_credit),
                'remaining_month': len(r_installment),
                'residual': self.residual,
                'paid_months': len(p_installment),
                'purchase_term': self.purchase_term,
                'pricelist_id': so_.pricelist_id.id,
                'currency_id': self.currency_id.id,
                'company_id': self.company_id.id,
                'partner_shipping_id': self.partner_shipping_id.id,
                'fiscal_position_id': self.fiscal_position_id.id,
            })
        for s in self:
            s.change_state = 'progress'
            s.name = '(%s [%s])' % (s.number, 'On Progress')

        return True


    @api.multi
    def action_pop(self, type=None):
        transfer_account = self.env['account.transfer.inv'].search([('invoice_id', '=', self.id), ('state', 'not in', ('approved', 'cancelled'))])
        # transfer_account.get_values()
        if transfer_account:
            return {
                'name': 'Change Request',
                'res_model': 'account.transfer.inv',
                "res_id": transfer_account.id,
                'type': 'ir.actions.act_window',
                'target': 'new',
                'views': [(self.env.ref('brdc_account.account_transfer_form_view').id, 'form')],
                'view_mode': 'form',
                'view_id': False,
                'view_type': 'form',
                # 'flags': {'initial_mode': 'edit'},
                # 'domain': [('invoice_id','=',self.id),('active','=',True)]
            }
        else:
            return {
                'name': 'Change Request',
                'res_model': 'account.transfer.inv',
                # "res_id": transfer_account.id,
                'type': 'ir.actions.act_window',
                'target': 'new',
                'views': [(self.env.ref('brdc_account.account_transfer_form_view').id, 'form')],
                'view_mode': 'form',
                'view_id': False,
                'view_type': 'form',
                # 'flags': {'initial_mode': 'edit'},
                # 'domain': [('invoice_id', '=', self.id), ('active', '=', True)]
            }

    @api.multi
    def action_approved(self):
        self.change_state = 'approved'
        # self.has_request = True
        for s in self:
            s.name = '(%s [%s])' % (s.number,'Approved')
    @api.multi
    def action_draft(self):
        self.change_state = 'draft'
        transfer_account = self.env['account.transfer.inv'].search(
            [('invoice_id', '=', self.id), ('state', 'not in', ('created', 'approved', 'cancelled'))])
        # transfer_account.write({
        #     'active': False
        # })
        # ids = []
        # for inv in transfer_account.invoice_ids:
        #     ids.append(inv.id)
        # invoice = self.env['account.invoice'].search([('id','in',ids)])
        # for inv_ in invoice:
        #     if inv_.state != 'draft':
        #         pass
        #     else:
                # invoice.unlink()
        transfer_account.unlink()
        for s in self:
            s.name = '%s' % ''
            s.has_request = False

    @api.multi
    def action_validate(self):
        for s in self:
            s.name = '(%s [%s])' % (s.number,'Transferred')
            installment_line_dp = s.env['invoice.installment.line.dp']
            for ildp in installment_line_dp.search([('account_invoice_id', '=', self.id), ('is_paid', '=', False)]):
                ildp.write({
                    'customer_id': s.partner_id.id
                })
            installment_line = s.env['invoice.installment.line']
            for il in installment_line.search([('account_invoice_id', '=', self.id), ('is_paid', '=', False)]):
                il.write({
                    'customer_id': s.partner_id.id
                })
                s.change_state = 'draft'
                # s.has_request = False
        #             il.unlink()

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    transaction_inv_id = fields.Many2one('account.transfer.inv')
    invoice_id = fields.Many2one('account.invoice')
    note = fields.Text(string='Notes')

class ProductTransferLine(models.Model):
    _name = 'product.transfer.line'

class AccountTransferInv(models.Model):
    _name = 'account.transfer.inv'

    @api.multi
    def get_name(self):
        self.name = '%s - %s' % (self.transfer_to_id.name if self.transfer_to_id.name else self.invoice_id.name, self.type)

    name = fields.Char(compute=get_name)
    state = fields.Selection(selection=[('draft', 'Draft'),
                                        ('sent', 'Sent'),
                                        ('created', 'Created'),
                                        ('approved', 'Approved'),
                                        ('cancelled', 'Cancelled')],
                             required=False, default='draft')

    type = fields.Selection(string="",
                            selection=[('account','Account Transfer'),
                                       ('product', 'Product Change'),
                                       ('term','Term Change'), ],
                            required=False,
                            default='account' )
    # @api.onchange('type')
    @api.multi
    def partner_domain(self):
        invoice = self.invoice_id if self.invoice_id else self.env['account.invoice'].browse(
                                     self._context.get('active_ids', []))
        invoice_partner = self.invoice_id.partner_id.id if self.invoice_id else self.env['account.invoice'].browse(
                                     self._context.get('active_ids', [])).partner_id.id
        account_transfer_list = []
        for trans in invoice.transfer_ids:
            for partner_id in trans.partner_id:
                account_transfer_list.append(partner_id.id)


        # print account_transfer_list
        account_transfer_list.append(invoice_partner)
        # return [('customer','=',True),('state','=','note'),('id','!=',invoice_partner),('id','not in',account_transfer_list)]
        return [('customer','=',True),('state','=','note'),('id','not in',account_transfer_list)]

    partner_id = fields.Many2one('res.partner',
                                 # default=lambda self: self.env['account.invoice'].browse(
                                 #     self._context.get('active_ids', [])).partner_id.id,
                                 # domain=partner_domain
                                 )
    transfer_to_id = fields.Many2one('res.partner',
                                 domain=partner_domain
                                 )
    product_type = fields.Many2one('payment.config', string='Product Type', domain="[('is_parent', '=', 1)]",
                                   default=lambda self: self.invoice_id.product_type.id if self.invoice_id else self.env['account.invoice'].browse(
                                       self._context.get('active_ids', [])).product_type.id)
    new_payment_term_id = fields.Many2one('payment.config', string='Payment Terms',
                                          domain="[('parent_id', '=', product_type),('payment_type','=','install'),('bpt','=',True)]",
                                          default=lambda self: self.invoice_id.new_payment_term_id.id if self.invoice_id else self.env['account.invoice'].browse(
                                              self._context.get('active_ids', [])).new_payment_term_id.id)

    product_line = fields.One2many('product.transfer.line', 'trans_order_id',limit=1)

    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', required=True, readonly=True,
                                   states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
                                   help="Pricelist for current sales order.")
    currency_id = fields.Many2one("res.currency", related='pricelist_id.currency_id', string="Currency", readonly=True,
                                  required=True)

    company_id = fields.Many2one('res.company', 'Company', )

    amount_untaxed = fields.Float(string='Untaxed Amount', store=True, readonly=True, compute='_amount_all',
                                  track_visibility='always')
    amount_tax = fields.Float(string='Taxes', store=True, readonly=True, compute='_amount_all',
                              track_visibility='always')
    amount_total = fields.Float(string='Total', store=True, readonly=True, compute='_amount_all',
                                track_visibility='always')
    date_order = fields.Datetime(string='Request Date', required=True, readonly=True, index=True,
                                 states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, copy=False,
                                 default=fields.Datetime.now)
    partner_shipping_id = fields.Many2one('res.partner', string='Delivery Address', readonly=True, required=True,
                                          states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
                                          help="Delivery address for current sales order.")
    fiscal_position_id = fields.Many2one('account.fiscal.position', oldname='fiscal_position', string='Fiscal Position')

    monthly_payment = fields.Float(string='Monthly Payment', default=0.00, store=0, compute='_amount_all')
    pa_ref = fields.Char(string='Purchase Agreement', )



    @api.multi
    def get_invoice(self):
        account_invoice = self.invoice_id if self.invoice_id else self.env['account.invoice'].browse(self._context.get('active_ids', []))
        for s in self:
            s.invoice_id = account_invoice.id

    @api.multi
    def create_requests(self):
        #### note: add service invoice in parent invoice as history of service payments, add note <3 <3 <3 work for tomorrow.
        for sid in self.sales_ids:
            get_invoice = self.env['account.invoice'].search([('sale_order_id','=',sid[0].id)])
            get_so = self.env['sale.order'].search([('transaction_inv_id','=',self.id)])
            invoice_service = self.env['account.invoice'].search([('transaction_inv_id','=',self.id),('state','!=','cancel')])
            # print invoice_service.state
            if get_invoice:
                if get_invoice[0].state == 'paid':
                    account_invoice = self.env[
                    'account.invoice'].browse(self._context.get('active_ids', [])) if not self.invoice_id else self.invoice_id
                    account_transfer = self.env['account.transfer']
                    payment_term_id = self.env['account.payment.term'].search([('name', '=', 'Immediate Payment')])
                    payment_term = False if not self.new_payment_term_id.id else self.new_payment_term_id.id
                    journal_id = self.env['account.invoice'].default_get(['journal_id'])['journal_id']
                    if not journal_id:
                        raise UserError(_('Please define an accounting sale journal for this company.'))
                    move = account_invoice.move_id
                    moves = self.env['account.move.line']
                    lines_credit = moves.search(
                        [('move_id', '!=', move.id), ('id', 'in', move.line_ids.get_reconcile())])
                    for s in self:
                        s.invoice_id = account_invoice.id
                        origin_sale = self.env['sale.order'].search([('name', '=', account_invoice.origin)])
                        s.state = 'approved'
                        account_move = self.env['account.move'].search([('id', '=', account_invoice.move_id.id)])
                        account_move_line = self.env['account.move.line'].search(
                            [('invoice_id', '=', account_invoice.id), ('partner_id', '=', s.partner_id.id)])
                        if s.type == 'account':
                            array = []
                            for pid in s.transfer_to_id:
                                array.append(pid.id)
                                account_transfer.create({
                                    'partner_id': account_invoice.partner_id.id,
                                    'invoice_id': account_invoice.id,
                                })
                                account_invoice.write({
                                    'partner_id': array[-1],
                                    'name': '%s' % '',
                                    'change_state': 'draft',
                                    'has_request': False
                                })
                                account_move.write({
                                    'partner_id': array[-1]
                                })
                                origin_sale.write({
                                    'partner_id': array[-1]
                                })
                                # account_move_line.write({
                                #     'partner_id': array[-1]
                                # })

                        elif s.type == 'product':
                            installment_line = self.env['invoice.installment.line'].search([('account_invoice_id','=',account_invoice.id),('is_paid','=',False)])
                            for il in installment_line:
                                il.write({
                                    'amount_to_pay': 0.00
                                })
                            prepare_invoice = {
                                'name': '',
                                'origin': self.name,
                                'type': 'out_invoice',
                                'account_id': self.partner_id.property_account_receivable_id.id,
                                'partner_id': self.partner_id.id,
                                'partner_shipping_id': self.partner_shipping_id.id,
                                'journal_id': journal_id,
                                'currency_id': self.pricelist_id.currency_id.id,
                                'comment': 'product change from invoice [%s]' % account_invoice.name,
                                'payment_term_id': payment_term_id.id,
                                'fiscal_position_id': self.fiscal_position_id.id or self.partner_id.property_account_position_id.id,
                                'company_id': self.company_id.id,
                                'transaction_inv_id': self.id,
                                # 'user_id': self.env['res.users'].browse(self._context.get('active_ids', [])).id,
                                # 'team_id': self.team_id.id,
                                'purchase_term': self.purchase_term,
                                'product_type': self.product_type.id,
                                'new_payment_term_id': payment_term,
                                'monthly_payment': self.monthly_payment,
                                'is_plan_mod': True,
                                'no_months_mode': self.remaining_month,
                                'unit_price': self.amount_untaxed,
                                'pcf': self.pcf,
                                'amount_tax': self.amount_tax,
                                'pa_ref': self.pa_ref,
                                'invoice_line_ids': [(0,0,{
                                    'origin': self.name,
                                    'name': self.product_line.product_id.name,
                                    'account_id': account_invoice.invoice_line_ids[0].account_id.id,
                                    'price_unit': self.amount_total,
                                    'quantity': self.product_line.product_uom_qty,
                                    'discount': self.product_line.discount,
                                    'uom_id': self.product_line.product_uom.id,
                                    'product_id': self.product_line.product_id.id or False,
                                    'invoice_line_tax_ids': [(6, 0, self.product_line.tax_id.ids)],
                                })],

                            }
                            round_curr = self.pricelist_id.currency_id.round
                            amount_total_company_signed = account_invoice.amount_total
                            amount_untaxed_signed = account_invoice.amount_untaxed
                            if account_invoice.currency_id and account_invoice.company_id and account_invoice.currency_id != account_invoice.company_id.currency_id:
                                currency_id = account_invoice.currency_id.with_context(date=account_invoice.date_invoice)
                                amount_total_company_signed = currency_id.compute(account_invoice.amount_total,
                                                                                  account_invoice.company_id.currency_id)
                                amount_untaxed_signed = currency_id.compute(account_invoice.amount_untaxed,
                                                                            account_invoice.company_id.currency_id)
                            sign = account_invoice.type in ['in_refund', 'out_refund'] and -1 or 1
                            account_invoice.write({
                                'name': '%s' % '',
                                'change_state': 'draft',
                                # 'amount_untaxed': sum(acc.credit for acc in lines_credit),
                                # 'amount_tax': sum(round_curr(line.amount) for line in account_invoice.tax_line_ids),
                                'amount_total': self.amount_paid,
                                'amount_total_company_signed': amount_total_company_signed * sign,
                                'amount_total_signed': account_invoice.amount_total * sign,
                                'amount_untaxed_signed': amount_untaxed_signed * sign,
                                'has_request': False,
                                # 'state': 'paid',
                            })
                            account_invoice.write_move(self.amount_paid)

                            account_move.write({
                                'amount': self.amount_paid
                            })
                            account_invoice.update_vat_pfc(True, account_invoice.id, 'is_tax')
                            account_invoice.update_vat_pfc(True, account_invoice.id, 'is_pcf')
                            account_invoice.refresh()
                            account_invoice.write({
                                'state': 'paid',
                            })
                            self.env['account.invoice'].create(prepare_invoice)
                            pass
                        elif s.type == 'term':
                            pass
                    else:
                        pass
            else:
                pass

        return True

    @api.multi
    def disapp_requests(self):
        for sid in self.sales_ids:
            get_invoice = self.env['account.invoice'].search([('sale_order_id','=',sid[0].id)])
            get_so = self.env['sale.order'].search([('transaction_inv_id','=',self.id)])
            account_invoice = self.invoice_id if self.invoice_id else self.env['account.invoice'].browse(self._context.get('active_ids', []))
            if get_invoice:
                if get_invoice[0].state != 'cancel':
                    raise UserError(_('You need to UNRECONCILE PAYMENT in the Special Service invoice and CANCEL INVOICE to cancel request.'))
                else:
                    get_so.write({
                        'state': 'cancel'
                    })
                    account_invoice.write({
                        'name': '%s' % '',
                        'change_state': 'draft',
                        'has_request': False
                    })
                    # print account_invoice.change_state
            else:
                # print 'yow bok 123 456'
                account_invoice.write({
                    'name': '%s' % '',
                    'change_state': 'draft',
                    'has_request': False
                })

        for s in self:
            s.state = 'cancelled'
            # s.unlink()
        return True






    @api.model
    def _default_amount(self):
        invoice = self.invoice_id if self.invoice_id else self.env['account.invoice'].browse(self._context.get('active_ids', []))
        move = invoice.move_id
        moves = self.env['account.move.line']
        lines_credit = moves.search([('move_id', '!=', move.id), ('id', 'in', move.line_ids.get_reconcile())])
        # payment = self.env['account.payment'].search(
        #     [('account_invoice_id', '=', invoice.id)])
        return sum(acc.credit for acc in lines_credit)
    @api.model
    def _default_month(self):
        invoice = self.invoice_id if self.invoice_id else self.env['account.invoice'].browse(self._context.get('active_ids', []))
        installment = self.env['invoice.installment.line'].search([('account_invoice_id', '=', invoice.id),
                                                                   ('is_paid', '=', False)])
        return len(installment)

    amount_paid = fields.Float(string='Amount Paid',
                               default=_default_amount)
    remaining_month = fields.Integer(string='Number of Unpaid Month(s)',
                                     default=_default_month,
                                     )
    invoice_id = fields.Many2one('account.invoice',
                                 # compute=get_invoice,
                                 default=lambda self: self.env['account.invoice'].browse(self._context.get('active_ids', [])).id)

    # invoice_ids = fields.One2many(comodel_name="account.invoice",
    #                             inverse_name="transaction_inv_id",
    #                             string="Account Transfer",
    #                             required=False,
    #                             domain=[('state','!=','cancel')]
    #                                )
    sales_ids = fields.One2many(comodel_name="sale.order",
                                inverse_name="transaction_inv_id",
                                string="Account Transfer",
                                required=False,
                                # domain=[('invoice_status','=','invoiced')]
                                   )

    @api.model
    def _default_residual(self):
        invoice = self.invoice_id if self.invoice_id else self.env['account.invoice'].browse(self._context.get('active_ids', []))
        return invoice.residual

    @api.model
    def _default_pmonth(self):
        invoice = self.invoice_id if self.invoice_id else self.env['account.invoice'].browse(self._context.get('active_ids', []))
        installment = self.env['invoice.installment.line'].search([('account_invoice_id', '=', invoice.id),
                                                                   ('is_paid', '=', True)])
        return len(installment)

    residual = fields.Float('Amount Due', default=_default_residual)
    paid_months = fields.Integer('Number of Paid Month(s)',default=_default_pmonth)
    @api.onchange('product_type')
    def new_payment_term_id_value(self):
        for s in self:
            payment_config = s.env['payment.config'].search(
                [('parent_id', '=', s.product_type.id), ('payment_type', '=', 'install'), ('bpt', '=', True)])
            for pc in payment_config:
                s.new_payment_term_id = pc[0].id if pc[0].id else False

    purchase_term = fields.Selection([('cash', 'Cash'), ('install', 'Installment')], string='Payment Type',
                                     default='install')

    active = fields.Boolean(default=True)



    @api.multi
    def action_draft(self):
        for s in self:
            s.state = 'draft'
            invoice = s.invoice_id if s.invoice_id else s.env['account.invoice'].browse(s._context.get('active_ids', []))
            invoice_ = s.env['account.invoice']
            obj_inv = invoice.search([('transaction_inv_id', '=', s.id), ('state', 'not in', ('cancel','paid'))])
            for inv in invoice:
                inv.write({
                    'name': '(%s [%s])' % (inv.number, 'On Progress'),
                    # 'change_state': 'draft'
                })
            # obj_inv.write({'state':'cancel'})
        return True, {
            "type": "ir.actions.do_nothing",
        }

    @api.multi
    def action_save(self):
        for s in self:
            s.state = 'sent'
        invoice = self.invoice_id if self.invoice_id else self.env['account.invoice'].browse(self._context.get('active_ids', []))

        for inv in invoice:
            inv.write({
                'name': '(%s [%s])' % (inv.number, 'Sent'),
                'change_state': 'sent'
            })
        return {
            "type": "ir.actions.do_nothing",
        }
        # invoice.action_pop()

    @api.multi
    def action_create(self):
        sale_order = self.env['sale.order']
        invoice_active = self.invoice_id if self.invoice_id else self.env['account.invoice'].browse(self._context.get('active_ids', []))
        obj_sale = sale_order.search([('transaction_inv_id','=',self.id), ('state', 'not in', ('cancel','sale','done'))])
        sales_ = ''
        if obj_sale:
            pass
        else:
            for s in self:
                note = ''
                if s.type == 'account':
                    note = 'Account Transfer to %s [Reference No. %s]' % (s.transfer_to_id.name, invoice_active.number)
                elif s.type == 'product':
                    note = 'Change of Product'
                elif s.type == 'term':
                    note = 'Change of Payment Term'
                product_type = s.env['payment.config'].search(
                    [('name', '=', 'Special Service'), ('category', '=', 'service'), ('is_parent', '=', True)])
                payment_term = s.env['payment.config'].search(
                    [('name', '=', 'cash'), ('payment_type', '=', 'cash'), ('parent_id', '=', product_type.id)])
                sales_ = sale_order.create({
                    'partner_id': invoice_active.partner_id.id,
                    'partner_shipping_id': invoice_active.partner_shipping_id.id,
                    'currency_id': invoice_active.currency_id.id,
                    'payment_term_id': invoice_active.payment_term_id.id,
                    'fiscal_position_id': invoice_active.fiscal_position_id.id or invoice_active.partner_id.property_account_position_id.id,
                    'team_id': invoice_active.team_id.id,
                    'user_id': invoice_active.user_id.id,
                    'product_type': product_type.id,
                    'purchase_term': 'cash',
                    'new_payment_term_id': payment_term.id,
                    'transaction_inv_id': s.id,
                    'invoice_id': invoice_active.id,
                    'note': note,
                })
                s.state = 'created'
                for inv in invoice_active:
                    inv.write({
                        'name': '(%s [%s])' % (inv.number, 'Created'),
                        'change_state': 'created'
                    })

        return sales_, {
            "type": "ir.actions.do_nothing",
        }

        # for s in self:
        #     s.state = 'create'
        # invoice = self.env['account.invoice'].browse(self._context.get('active_ids', []))
        # for inv in invoice:
        #     inv.write({'name': '(%s [%s])' % (inv.number, 'Create')})

    @api.multi
    def action_view_sale(self):
        for s in self:
            for so in s.sales_ids:
                return {
                    'res_model': 'sale.order',
                    "res_id": so[0].id,
                    'type': 'ir.actions.act_window',
                    'target': 'self',
                    'view_mode': 'form',
                    'view_id': False,
                    'view_type': 'form',
                    'flags': {'initial_mode': 'edit'},
                    # 'domain': [('invoice_id','=',self.id),('active','=',True)]
                }
        # action = self.env.ref('sale.view_order_tree').read()[0]
        # for s in self.sales_ids:
        #     if len(s) > 1:
        #         action['domain'] = [('id', '=', s[0].id)]
        #     elif len(s) == 1:
        #         action['views'] = [(self.env.ref('sale.view_order_form').id, 'form')]
        #         action['res_id'] = s[0].id
        #         action['flags'] = {'initial_mode': 'edit'}
        #     else:
        #         action = {'type': 'ir.actions.act_window_close'}
        # return action

    @api.multi
    def action_view_invoice(self):
        invoices = self.mapped('invoice_ids')
        action = self.env.ref('account.action_invoice_tree1').read()[0]
        for i in self.invoice_ids:
            if len(i) > 1:
                action['domain'] = [('id', 'in', i.ids)]
            elif len(i) == 1:
                action['views'] = [(self.env.ref('account.invoice_form').id, 'form')]
                action['res_id'] = i[0].id
                action['flags'] = {'initial_mode': 'edit'}
            else:
                action = {'type': 'ir.actions.act_window_close'}
        return action
