from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date


class RequestExpense(models.TransientModel):
    _name = 'request.expense'

    @api.multi
    def _fund_left(self):
        active_id = self.env['agent.commission.fund.monitor'].browse(self._context.get('active_ids', []))
        # print(config_settings.agent_commission_fund)
        for s in self:
            s.fund_left = active_id.remaining_fund
            s.fund_replenish = s.agent_commission_fund - s.fund_left

    name = fields.Char(string='Expense Description')
    fund_left = fields.Float(default=0.00, compute=_fund_left)
    agent_commission_fund = fields.Float(default=0.00)
    fund_replenish = fields.Float(default=0.00, string='Fund to Replenish', compute=_fund_left)
    product_id = fields.Many2one('product.product','Product', domain=[('can_be_expensed','=',True)])
    state = fields.Selection([('draft','Draft'),('confirm','Confirmed'),('sent','Sent')], default='draft')
    acfm_id = fields.Many2one('agent.commission.fund.monitor')

    @api.multi
    def action_draft(self):
        self.state = 'draft'

    @api.multi
    def action_confirm(self):
        self.state = 'confirm'

    @api.multi
    def action_submit(self):
        for s in self:
            expense = s.env['hr.expense']
            expense.create(s._prepare_expense())
            s.state = 'sent'
        return{
            'warning':{
                'title': 'Attention!',
                'message': 'Expense is forwarded!'
            }
        }

    @api.multi
    def _prepare_expense(self):
        for s in self:
            employee = self.env['hr.employee'].search([('user_id','=',self.env.user.id)])
            config_settings = s.env['brdc.config.settings'].search([])[0]
            account = s.product_id.product_tmpl_id._get_product_accounts()['expense']
            return {
                'name': s.name,
                'product_id': s.product_id.id,
                'unit_amount': s.fund_replenish,
                'product_uom_id': s.product_id.uom_id.id,
                'tax_ids': s.product_id.supplier_taxes_id.id,
                'account_id': account.id,
                'company_id': config_settings.company_id.id,
                'employee_id': employee.id,
                'payment_mode': 'company_account',
                'date': date.today(),
                'reference': s.acfm_id.name,
                'total_amount': s.fund_replenish,
                'acfm_id': s.acfm_id.id
            }

class HrExpense(models.Model):
    _inherit = 'hr.expense'

    acfm_id = fields.Many2one('agent.commission.fund.monitor')

    @api.multi
    def action_move_create(self):
        '''
        main function that is called when trying to create the accounting entries related to an expense
        '''
        for expense in self:
            journal = expense.sheet_id.bank_journal_id if expense.payment_mode == 'company_account' else expense.sheet_id.journal_id
            # create the move that will contain the accounting entries
            acc_date = expense.sheet_id.accounting_date or expense.date
            move = self.env['account.move'].create({
                'journal_id': journal.id,
                'company_id': self.env.user.company_id.id,
                'date': acc_date,
                'ref': expense.sheet_id.name,
                # force the name to the default value, to avoid an eventual 'default_name' in the context
                # to set it to '' which cause no number to be given to the account.move when posted.
                'name': '/',
            })
            company_currency = expense.company_id.currency_id
            diff_currency_p = expense.currency_id != company_currency
            # one account.move.line per expense (+taxes..)
            move_lines = expense._move_line_get()

            # create one more move line, a counterline for the total on payable account
            payment_id = False
            total, total_currency, move_lines = expense._compute_expense_totals(company_currency, move_lines, acc_date)
            if expense.payment_mode == 'company_account':
                if not expense.sheet_id.bank_journal_id.default_credit_account_id:
                    raise UserError(_("No credit account found for the %s journal, please configure one.") % (
                        expense.sheet_id.bank_journal_id.name))
                emp_account = expense.sheet_id.bank_journal_id.default_credit_account_id.id
                journal = expense.sheet_id.bank_journal_id
                # create payment
                payment_methods = (
                                              total < 0) and journal.outbound_payment_method_ids or journal.inbound_payment_method_ids
                journal_currency = journal.currency_id or journal.company_id.currency_id
                payment = self.env['account.payment'].create({
                    'payment_method_id': payment_methods and payment_methods[0].id or False,
                    'payment_type': total < 0 and 'outbound' or 'inbound',
                    'partner_id': expense.employee_id.address_home_id.commercial_partner_id.id,
                    'partner_type': 'supplier',
                    'journal_id': journal.id,
                    'payment_date': expense.date,
                    'state': 'reconciled',
                    'currency_id': diff_currency_p and expense.currency_id.id or journal_currency.id,
                    'amount': diff_currency_p and abs(total_currency) or abs(total),
                    'name': expense.name,
                    'or_series': False
                })
                payment_id = payment.id
            else:
                if not expense.employee_id.address_home_id:
                    raise UserError(_("No Home Address found for the employee %s, please configure one.") % (
                        expense.employee_id.name))
                emp_account = expense.employee_id.address_home_id.property_account_payable_id.id

            aml_name = expense.employee_id.name + ': ' + expense.name.split('\n')[0][:64]
            move_lines.append({
                'type': 'dest',
                'name': aml_name,
                'price': total,
                'account_id': emp_account,
                'date_maturity': acc_date,
                'amount_currency': diff_currency_p and total_currency or False,
                'currency_id': diff_currency_p and expense.currency_id.id or False,
                'payment_id': payment_id,
            })

            # convert eml into an osv-valid format
            lines = map(lambda x: (0, 0, expense._prepare_move_line(x)), move_lines)
            move.with_context(dont_create_taxes=True).write({'line_ids': lines})
            expense.sheet_id.write({'account_move_id': move.id})
            move.post()
            if expense.payment_mode == 'company_account':
                expense.sheet_id.paid_expense_sheets()
        return True