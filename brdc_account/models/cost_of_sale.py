from odoo import api, fields, models, _


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    cost_of_sale_id = fields.Many2one('account.move', 'Cost of Sale', readonly=1)

    @api.multi
    def get_credit_account(self, move):
        account = None
        for line in move.line_ids:
            if line.is_credit and not line.is_tax:
                account = line.account_id
        return account

    @api.model
    @api.depends('cost_of_sale_id')
    def create_CostOfSale(self):
        invoice = self.env['account.invoice'].search([
            ('state', 'in', ['open', 'paid']),
            # ('purchase_term', '=', 'cash'),
            ('cost_of_sale_id', '=', False),
            ('amount_total', '!=', 0.0)
        ]) or \
                  self.filtered(
                      lambda res:
                      res.state in ['open', 'paid'] and
                      # res.purchase_term == 'cash' and
                      not res.cost_of_sale_id and
                      res.amount_total
                  )
        print len(invoice), 'create_CostOfSale', 'length'
        for rec in invoice:
        # for rec in self.filtered(
        #               lambda res:
        #               res.state in ['open', 'paid'] and
        #               not res.cost_of_sale_id and
        #               res.amount_total
        #           ):
            rec.ensure_one()
            # if not rec.cost_of_sale_id:
            print 'create_CostOfSale'
            print rec.pa_ref

            account = rec.get_credit_account(rec.move_id)
            inventory_account = self.env['account.account'].search([('code', '=', '15971000607100')])

            def get_product(origin):
                sale_order = self.env['sale.order'].search([('name', '=', origin)])
                stock_picking = sale_order.mapped('picking_ids')
                # if sales_invoice.delivery_count == 1:
                stock_pack_operation = self.env['stock.pack.operation'].search([('picking_id', '=', stock_picking.id)])
                product = None
                if len(stock_pack_operation) > 1:
                    pack_lots = self.env['stock.pack.operation.lot'].search(
                        [('operation_id', 'in', stock_pack_operation.ids)])
                    for pack_lot in pack_lots:
                        if pack_lot.lot_id.is_free:
                            product = pack_lot.lot_id.product_id
                        else:
                            pass
                else:
                    product = stock_pack_operation.product_id

                    # qty_done = stock_pack_operation.product_qty or stock_pack_operation.qty_done

                if product.standard_price:
                    return {
                        'cost': product.standard_price,
                        'qty_done': 1,
                        'property_account_cost_id': product.property_account_cost_id
                    }
                else:
                    return False
            if not get_product(rec.origin):
                print "not get_product"
            else:
                print "get_product"
                # print get_product(rec.origin)['cost'], "get_product(rec.origin)['cost']"
                # print get_product(rec.origin)['qty_done'], "get_product(rec.origin)['qty_done']"
                amount = get_product(rec.origin)['cost'] * get_product(rec.origin)['qty_done']

                cos_move = self.env['account.move'].search([])
                self.env['account.move'].search([('id', '=', rec.cost_of_sale_id.id)]).button_cancel()
                self.env['account.move'].search([('id', '=', rec.cost_of_sale_id.id)]).unlink()
                cost_account = account if rec.purchase_term == 'install' else get_product(rec.origin)['property_account_cost_id']

                cos = cos_move.create({
                    'name': rec.number.replace('INV', 'COS'),
                    'company_id': rec.company_id.id,
                    'currency_id': rec.currency_id.id,
                    'partner_id': rec.partner_id.id,
                    'journal_id': rec.journal_id.id,
                    'ref': rec.number,
                    'date': rec.date_invoice,
                    'line_ids': [(0, 0, { # debit
                        'partner_id': rec.partner_id.id, 'journal_id': rec.journal_id.id, 'date': rec.date_invoice,
                        'name': cost_account.name, 'company_id': rec.company_id.id, 'account_id': cost_account.id, 'debit': amount, 'credit': 0.0,
                        'balance': amount, 'quantity': 1, 'move_id': False, 'date_maturity': rec.date_invoice,
                        'blocked': False, 'amount_residual': 0.0, 'credit_cash_basis': 0.0, 'amount_residual_currency': 0.0,
                        'debit_cash_basis': 0.0, 'reconciled': False, 'tax_exigible': True, 'balance_cash_basis': 0.0, 'amount_currency': 0.0,
                        'company_currency_id': rec.company_id.currency_id.id, 'invoice_id': rec.id, 'is_debit': True, 'sequence': '1',
                    }), (0, 0, { # credit
                        'partner_id': rec.partner_id.id, 'journal_id': rec.journal_id.id, 'date': rec.date_invoice,
                        'name': 'Inventory', 'company_id': rec.company_id.id, 'account_id': inventory_account.id, 'debit': 0.0, 'credit': amount,
                        'balance': 0.0 - amount, 'quantity': 1, 'move_id': False, 'date_maturity': rec.date_invoice,
                        'blocked': False, 'amount_residual': 0.0, 'credit_cash_basis': 0.0, 'amount_residual_currency': 0.0,
                        'debit_cash_basis': 0.0, 'reconciled': False, 'tax_exigible': True, 'balance_cash_basis': 0.0, 'amount_currency': 0.0,
                        'company_currency_id': rec.company_id.currency_id.id, 'invoice_id': rec.id, 'is_credit': True, 'sequence': '2',
                    })]
                })

                cos.post()
                self._cr.execute("""update account_invoice set cost_of_sale_id = %s where id = %s""" % (cos.id, rec.id))
                self._cr.commit()
            # else:
            #     pass

    def get_open_costmove(self):
        invoice = self.env['account.invoice'].search([
            ('state', 'in', ['open', 'paid']),
            ('cost_of_sale_id', '=', False),
        ]) or \
                  self.filtered(
                      lambda res:
                      res.state in ['open', 'paid'] and
                      not res.cost_of_sale_id
                  )

        unpost = []
        
        for res in invoice:
            # if res.cost_of_sale_id:
            cost_id = res.cost_of_sale_id
            # if cost_id.state == 'draft':
            print cost_id.state
            unpost.append(res.id)

        print len(unpost), 'get_open_costmove', 'length'

    def get_move_line(self):
        invoice = self.env['account.invoice'].search([
            ('state', 'in', ['open', 'paid']),
            ('move_id', '!=', False)
            ])

        for rec in invoice:
            moves = rec.move_id
            debit = 0.0
            credit = 0.0
            tax_id = None
            credit_id = None
            for line in moves.line_ids:
                debit += line.balance if line.balance > 0 else 0
                credit += line.balance if line.balance < 0 else 0
                tax_id = line if line.is_tax else tax_id
                credit_id = line if not line.is_tax and line.balance < 0 else credit_id

            credit = credit * -1
            if round(debit, 2) != round(credit, 2):
                moves.button_cancel()
                tax_amount = tax_id.credit
                credit_amount = credit_id.credit
                print credit_amount, rec.pa_ref
                amount = credit_amount - tax_amount
                print credit_amount, '-', tax_amount, '=', amount
                self._cr.execute(
                    """update account_move_line
                    set credit = %s, balance = %s
                    where id = '%s'""" % (amount,
                                          0 - amount,
                                          credit_id.id
                                          )
                )
                self._cr.commit()
                moves.post()

