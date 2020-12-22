from odoo import api, fields, models, _
from odoo.exceptions import UserError

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    _order = 'sequence'

    # @api.multi
    # def has_tax(self):
    #     for s in self:
    #         if s.tax_line_id:
    #             s.is_tax = True

    is_debit = fields.Boolean(default=False)
    is_credit = fields.Boolean(default=False)
    is_tax = fields.Boolean(default=False,)
    is_pcf = fields.Boolean(default=False,)
    is_surcharge = fields.Boolean(default=False)
    sequence = fields.Integer(default=1)
    account_invoice_id = fields.Many2one('account.invoice')

    @api.multi
    def get_reconcile(self):
        ids = []
        for aml in self:
            if aml.account_id.reconcile:
                ids.extend(
                    [r.debit_move_id.id for r in aml.matched_debit_ids] if aml.credit > 0 else [r.credit_move_id.id for
                                                                                                r in
                                                                                                aml.matched_credit_ids])
                ids.append(aml.id)
        return ids


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def update_move_line(self, tax_id):
        move = self.move_id
        moves = self.env['account.move.line']
        tax_ids = moves.search([('move_id', '=', move.id), ('tax_line_id', 'in', tax_id)])
        for tbo in tax_ids:
            tbo.write({
                'is_tax': 1
            })
        lines_debit = moves.search([('move_id','=',move.id), ('balance', '>', 0), ('is_tax', '=', False)])
        print lines_debit
        lines_credit = moves.search([('move_id','=',move.id), ('balance', '<', 0), ('is_tax', '=', False)])
        print lines_credit

        for line in lines_debit:
            line.write({
                'is_debit': 1,
                'is_credit': 0
            })
        for line in lines_credit:
            line.write({
                'is_debit': 0,
                'is_credit': 1
            })
        return True

    @api.multi
    def write_move(self, amount):
        move = self.move_id
        moves = self.env['account.move.line']
        lines_debit = moves.search([('move_id', '=', move.id), ('id', 'in', move.line_ids.get_reconcile()), ('is_debit','=', True)])
        lines_credit = moves.search([('move_id', '=', move.id), ('id', 'not in', move.line_ids.get_reconcile()), ('is_credit','=', True)])
        # self._cr.execute("""insert into res_groups_users_rel(gid,uid)values(%s,%s)""" % (gid, uid))
        # self._cr.commit()

        self._cr.execute("""select * from account_move_line where move_id = '%s'""" % move.id)
        res = self._cr.fetchall()

        for line in lines_debit:
            self._cr.execute("""update account_move_line set amount_residual = %s, amount_residual_currency = %s, debit = %s, balance = %s, sequence = 0, name = 'Cash' where id = '%s'""" % (0.00, 0.00, amount, amount,line.id))
            self._cr.commit()

        for line in lines_credit:
            self._cr.execute("""update account_move_line set credit = %s, balance = %s where id = '%s'""" % (amount, 0 - amount,line.id))
            self._cr.commit()

        return True, self._compute_residual()

    @api.multi
    def update_tax_0(self, move_id, tax_id, insline, tax, pcf, account_id_, has_pcf, held):
        move = self.move_id
        move_line_ids = self.env['account.move.line']
        tax_ids = move_line_ids.search([('move_id','=',move_id),('tax_line_id', 'in', tax_id),('is_tax', '=', True)])
        lines_debit = move_line_ids.search([('move_id', '=', move_id), ('is_debit', '=', True), ('is_tax', '=', False), ('is_pcf', '=', False)])
        lines_credit = move_line_ids.search([('move_id', '=', move_id), ('is_credit', '=', True), ('is_tax', '=', False), ('is_pcf', '=', False)])
        # account = self.env['account.account'].search([('code','=','15971002424400')])
        total = insline + held
        print total

        move.write({
            'amount': total
        })

        debit_val = 0
        sales_val = 0
        if self.purchase_term == 'install':
            if self.is_paidup:
                debit_val = self.s_dp
            elif self.is_split:
                debit_val = self.st4_dp * 4
            else:
                debit_val = self.o_dp
                pass
        elif self.purchase_term == 'cash':
            debit_val = total
            pass

        for line in lines_debit:
            icr = total + held
            account_id = None
            name = None

            if self.account_id:
                name = self.account_id.name
                self._cr.execute("""update account_move_line set amount_residual = %s, debit = %s, balance = %s, name = '%s', account_id = %s, sequence = 0 where id = '%s'""" % (icr, icr, icr, name.replace("'", "`"), self.account_id.id, line.id))
                self._cr.commit()

        adv = 0
        if self.new_payment_term_id.bpt_wod:
            adv = total / self.new_payment_term_id.no_months
            pass

        if self.purchase_term == 'install':
            total = total - tax
            ugptotal = total
            sales_val = ugptotal + held
            print sales_val, tax, 'install'
        elif self.purchase_term == 'cash':
            total = total - tax
            ugptotal = total
            sales_val = ugptotal + held
            print sales_val, tax, 'cash'

        self.update_line_credit(sales_val, lines_credit)

        self.update_tax_1(tax_ids, tax)
        
        self._compute_residual()
        
    @api.multi
    def update_line_credit(self, sales_val, lines_credit):
        account_id = None
        name = None
        if self.purchase_term == 'install':
            account_id = self.env['account.account'].search([('code', '=', '15971000202800')])
            name = 'Unrealized Gross Profit'
        else:
            pass

        for line in lines_credit:
            print line.id, 'lines_credit'
            if account_id:
                self._cr.execute("""
                update account_move_line set credit = %s, balance = %s, account_id = %s, name = '%s' where id = '%s'
                """ % (sales_val, 0 - sales_val, account_id.id, name, line.id))
            else:
                self._cr.execute("""
                                update account_move_line set credit = %s, balance = %s where id = '%s'
                                """ % (sales_val, 0 - sales_val, line.id))
            self._cr.commit()

    @api.multi
    def update_tax_1(self, tax_ids, tax):
        for t in tax_ids:
            if t.tax_line_id.amount_type == 'vat':
                self._cr.execute("""update account_move_line set name = 'Deferred Tax liability', credit = %s, balance = %s, is_tax = %s where id = '%s'""" % (tax, 0 - tax, True, t.id))
                self._cr.commit()
            elif t.tax_line_id.amount_type == 'held':
                self._cr.execute("""delete from account_move_line where id = '%s'""" % t.id)
                self._cr.commit()

    def update_vat_pfc(self, boolean_val, invoice_id=None, label=None):
        self._cr.execute("""
        update account_move_line set credit = %s, balance = %s where invoice_id = %s and %s = %s
        """ % (0, 0, invoice_id, label, boolean_val))



