from odoo import api, fields, models
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT


class inherited_sale_order2(models.Model):

    _inherit = 'sale.order'

    agent_id = fields.Many2one('res.partner', string="Sales Agent", domain=[('agency_id','=','Sales Agent')], required=True, track_visibility='onchange')
    um_id = fields.Many2one('res.partner', string="Unit Manager", domain=[('agency_id', '=', 'Unit Manager')], track_visibility='onchange')
    am_id = fields.Many2one('res.partner', string="Agency Manager", domain=[('agency_id', '=', 'Agency Manager')], track_visibility='onchange')

    @api.onchange('agent_id')
    def onchange_agent_id(self):
        self.um_id = self.agent_id.unit_manager_id
        self.am_id = self.agent_id.agent_manager_id

    @api.onchange('um_id')
    def onchange_um_id(self):
        self.am_id = self.um_id.agent_manager_id

    @api.onchange('product_type')
    # @api.depends('product_type')
    def show_fields(self):
        if self.product_type:
            if self.product_type.name == 'Lot':
                self.is_lot = True
            else:
                self.is_lot = False

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

            if self.product_type.name == 'Columbary Vault':
                self.is_columbary = True
            else:
                self.is_columbary = False

            if self.product_type.name == 'Community Vault':
                self.is_cv = True
            else:
                self.is_cv = False
        else:
            pass


        # if self.product_type.name == 'Interment Services' or self.product_type.name == 'Crematory Services' or self.product_type.name == 'MM bundles':
        #     self.show_fields_bool = False
        # else:
        #     self.show_fields_bool = True

    @api.one
    def _count_interments(self):
        if self.env['interment.order2'].search([('or_id', '=', self.id)]):
            ic = self.env['interment.order2'].search_count([('or_id', '=', self.id)])
            self.inter_button = ic
        else:
            self.inter_button = 0

    @api.multi
    def action_invoice_create(self, grouped=False, final=False):

        # if self.product_type == 'service':
        #     if self.is_bundle == True:
        #         # self.lot_id.status = 'amo'
        #         pass
        if self.product_type.name == 'Lot':
            block_serial = self.env['stock.production.lot'].search([('id', '=', self.env['sale.order.line'].
                                                                     search([('order_id', '=', self.id),
                                                                             ('is_free', '=', False)]).lot_id.id)])
            for c in range(0, len(block_serial)):
                block_serial[c].status = 'amo'

        """
                Create the invoice associated to the SO.
                :param grouped: if True, invoices are grouped by SO id. If False, invoices are grouped by
                                (partner_invoice_id, currency)
                :param final: if True, refunds will be generated if necessary
                :returns: list of created invoices
                """
        inv_obj = self.env['account.invoice']
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        invoices = {}
        references = {}
        for order in self:
            group_key = order.id if grouped else (order.partner_invoice_id.id, order.currency_id.id)
            for line in order.order_line.sorted(key=lambda l: l.qty_to_invoice < 0):
                if float_is_zero(line.qty_to_invoice, precision_digits=precision):
                    continue
                if group_key not in invoices:
                    inv_data = order._prepare_invoice()
                    invoice = inv_obj.create(inv_data)
                    references[invoice] = order
                    invoices[group_key] = invoice
                elif group_key in invoices:
                    vals = {}
                    if order.name not in invoices[group_key].origin.split(', '):
                        vals['origin'] = invoices[group_key].origin + ', ' + order.name
                    if order.client_order_ref and order.client_order_ref not in invoices[group_key].name.split(
                            ', ') and order.client_order_ref != invoices[group_key].name:
                        vals['name'] = invoices[group_key].name + ', ' + order.client_order_ref
                    invoices[group_key].write(vals)
                if line.qty_to_invoice > 0:
                    line.invoice_line_create(invoices[group_key].id, line.qty_to_invoice)
                elif line.qty_to_invoice < 0 and final:
                    line.invoice_line_create(invoices[group_key].id, line.qty_to_invoice)

            if references.get(invoices.get(group_key)):
                if order not in references[invoices[group_key]]:
                    references[invoice] = references[invoice] | order

        if not invoices:
            raise UserError(_('There is no invoicable line.'))

        for invoice in invoices.values():
            if not invoice.invoice_line_ids:
                raise UserError(_('There is no invoicable line.'))
            # If invoice is negative, do a refund invoice instead
            if invoice.amount_untaxed < 0:
                invoice.type = 'out_refund'
                for line in invoice.invoice_line_ids:
                    line.quantity = -line.quantity
            # Use additional field helper function (for account extensions)
            for line in invoice.invoice_line_ids:
                line._set_additional_fields(invoice)
            # Necessary to force computation of taxes. In account_invoice, they are triggered
            # by onchanges, which are not triggered when doing a create.
            invoice.compute_taxes()
            invoice.message_post_with_view('mail.message_origin_link',
                                           values={'self': invoice, 'origin': references[invoice]},
                                           subtype_id=self.env.ref('mail.mt_note').id)
        return [inv.id for inv in invoices.values()]

    @api.multi
    def action_confirm(self):
        if self.product_type.category == 'service':
            if self.is_bundle == False and self.product_type.name == 'Interment':
                self.lot_id.allowable_interment = self.lot_id.allowable_interment - 1
            elif self.is_bundle == True:
                print "testy"
                #automatic create delivery here!
                # create_delivery = self.env['stock.picking']
                #
                # line_id = create_delivery.create({
                #     'partner_id': self.partner_id.id,
                #     'origin': self.name,
                #     'location_id': self.company_id.id,
                #     'picking_type_id': 4,
                #     'location_id': 15,
                #     'location_dest_id': 9,
                # })
                #
                # self.prod_id = self.prod_id2
                # self.lot_id = self.lot_id2
                #
                # set_lot_del = self.env['stock.move']
                #
                # line_id2 = set_lot_del.create({
                #     'picking_id': self.env['stock.picking'].search([])[-1].id,
                #     'location_dest_id': 9,
                #     'product_id': self.prod_id.id,
                #     'warehouse_id': 1,
                #     'product_uom': 1,
                #     'location_id': 15,
                #     'name': self.prod_id.name,
                # })

                # self.lot_id.status = 'reserved'
                # usab temporarily
                if len(self.agent_id) == 1 or len(self.um_id) == 1 or len(self.am_id) == 1:
                    generate_commission = self.env['agent.commission']

                    line_id3 = generate_commission.create({
                        'so_id': self.id,
                        'sales_agent_id': self.agent_id.id,
                    })

                    line_id3.compute_commission()
                else:
                    pass

                pass

        if self.product_type.category == 'product':
            # block_serial = self.env['stock.production.lot'].search([('id', '=', self.env['sale.order.line'].
            #                                                          search([('order_id', '=', self.id)]).lot_id.id)])
            # for c in range(0, len(block_serial)):
            #     block_serial[c].status = 'reserved'

            self.prod_id = self.env['sale.order.line'].search([('order_id', '=', self.id), ('is_free', '=', False)]).product_id.id
            self.lot_id = self.env['sale.order.line'].search([('order_id', '=', self.id), ('is_free', '=', False)]).lot_id.id
            # print self.prod_id, self.lot_id

            # usab temporarily
            if len(self.agent_id) == 1 or len(self.um_id) == 1 or len(self.am_id) == 1:
                generate_commission = self.env['agent.commission']

                line_id3 = generate_commission.create({
                    'so_id': self.id,
                    'sales_agent_id': self.agent_id.id,
                })

                line_id3.compute_commission()
            else:
                pass

        for order in self:
            order.state = 'sale'
            order.confirmation_date = fields.Datetime.now()
            if self.env.context.get('send_email'):
                self.force_quotation_send()
            order.order_line._action_procurement_create()
        if self.env['ir.values'].get_default('sale.config.settings', 'auto_done_setting'):
            self.action_done()
        return True

    @api.multi
    def action_cancel(self):
        if self.product_type.name == 'MM Bundle':
            if self.is_bundle == True:
                self.lot_id.status = 'av'
                self.lot_id.sale_order_id = ''
        if self.product_type.name == 'Lot' or self.product_type.name == 'Columbary Vault' or self.product_type.name == 'Community Vault':
            for line in self.env['sale.order.line'].search([('order_id', '=', self.id)]):
                block_serial = self.env['stock.production.lot'].search([('id', '=', line.lot_id.id)])
                if len(block_serial) > 0:
                    block_serial.status = 'av'
                    block_serial.sale_order_id = False

            # for c in range(0, len(block_serial)):
            #     block_serial[c].status = 'av'
            #     self.lot_id.sale_order_id = ''
        # usab temporarily
        self.env['agent.commission'].search([('so_id', '=', self.id)]).unlink()

        return self.write({'state': 'cancel'})