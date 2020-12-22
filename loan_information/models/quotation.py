from odoo import api, fields, models, _
from datetime import date, datetime,timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError

class IntermentQuotation(models.Model):
    _name = 'interment.quotation.request'

    name = fields.Char(required=True, copy=False, readonly=True, default=lambda self: _('New'), string='Reference Number')
    customer_id = fields.Many2one('res.partner',string='Customer Name',domain=[('customer','=',True)], required=True)
    date_requested = fields.Date(string='Date of Request', default=fields.Date.today())
    loan_type = fields.Selection([('package','Purchase Package'),
                                  ('eipp','EIPP')], string='Loan Type')
    # order_id = fields.Many2one('sale.order', string='Order Reference', required=True, ondelete='cascade', index=True,
    #                            copy=False)


    product_pricelist_id = fields.Many2one('product.pricelist', string='Price List')
    product_id = fields.Many2one('product.product',string='Product',
                                 # default=_get_pricelist_item,
                                 domain=[('type', 'in', ['consu','product']), ('sale_ok', '=', 'True')]
                                 )
    product_lot_id = fields.Many2one('stock.production.lot', string='Lawn Lot',)

    selling_price = fields.Float(string='Selling Price')
    spot_cash = fields.Float(string='Spot Cash', store=False, compute='_get_spotcash',)
    split_cash = fields.Float(string='3-Months Deferred Cash', store=False, compute='_get_splitcash')
    is_split_cash = fields.Boolean(default=False)
    down_payment = fields.Float(string='Down Payment', store=False, compute='_get_dp')
    o_down_payment = fields.Float(string='Down Payment', store=False, compute='_get_dp')
    dp_split = fields.Float(string='4 Months Split', store=False, compute='_get_split_dp')
    purchase_term = fields.Selection([('cash','Cash'),('install','Installment')],string='Payment Type',default='install')

    @api.onchange('purchase_term')
    def onchange_purchase_term(self):
        self.is_split_cash = (self.purchase_term == 'cash')
    bal_payment_term = fields.Float(string='Balance Payment', store=False, compute='_get_bpt')

    payment_term_id = fields.Many2one('payment.config', string='Payment Terms', domain=['&',('bpt','=',True),
                                                                                            ('name','not like','%EIPP ')],
                                      default=lambda self: self.env['payment.config'].search([])[0].id
                                      )
    bal_payment_wInterest = fields.Float(string='Balance Payment with interest', store=False,
                                         compute='_get_bp_wi'
                                         )
    monthly_payment = fields.Float(string='Monthly Payment', store=False,
                                   compute='_get_bp_wi'
                                   )
    is_60m = fields.Boolean(default=False,)
    interment_loan_line = fields.One2many(comodel_name="interment.loan.line", 
                                          inverse_name="loan_id",
                                          string="Loan Line", 
                                                  required=False, index=True )
    start_payment_date = fields.Date(string='Starting Date of Payment')
    total_amount = fields.Float(string="Total Amount", readonly=True, compute='_get_amount')
    total_paid_amount = fields.Float(string='Total Paid Amount', compute='_get_amount')
    balance_amount = fields.Float(string='Balance Amount', compute='_get_amount')
    
    # remaining_balance = fields.Float(related='balance_amount')

    @api.multi
    def _get_amount(self):
        total_paid_amount = 0.00
        compute_total_amount = 0.00
        for loan in self:
            for line in loan.interment_loan_line:
                if line.is_paid == True:
                    total_paid_amount += line.paid_amount
                compute_total_amount += line.amount_to_pay
            if self.purchase_term == 'cash':
                if self.is_split_cash == True:
                    compute_total_amount = 3 * loan.split_cash
                else:
                    compute_total_amount = self.spot_cash
                bal_amount = (compute_total_amount) - (total_paid_amount)
            else:
                # compute_total_amount = loan.payment_term_id.no_months * loan.monthly_payment
                bal_amount = (compute_total_amount) - (total_paid_amount)
            
            self.total_amount = round(compute_total_amount,2)
            self.balance_amount = round(bal_amount,2)
            self.total_paid_amount = round(total_paid_amount,2)

    @api.onchange('product_id','selling_price','product_pricelist_id','purchase_term')
    def get_selling_price(self):
        # name = self.env['payment.config'].search([('name', 'like', '%60 ')]).name
        # self.is_60m = (self.payment_term_id.name == name)

        # Modified
        self.selling_price = self.product_id.list_price

        if self.env['product.pricelist.item'].search([('pricelist_id','=',self.product_pricelist_id.id),
                                                                    ('product_tmpl_id', '=', self.product_id.id),]):
            pricelist_item = self.env['product.pricelist.item'].search([('pricelist_id','=',self.product_pricelist_id.id),
                                                                    ('product_tmpl_id', '=', self.product_id.id),])
            self.selling_price = pricelist_item.fixed_price
        # Modified

        # self._get_bp_wi()
        # print pricelist_item

        spotcash = self.env['payment.config'].search([('name', '=', 'spotcash')])
        self.spot_cash = self.selling_price * spotcash.less_perc
        deferred3 = self.env['payment.config'].search([('name', '=', '3-months deferred')])
        deferred = self.selling_price * deferred3.less_perc
        self.split_cash = deferred / 3
        if self.purchase_term == 'install':
            dpcon = self.env['payment.config'].search([('name', '=', 'downpayment')])
            dp = self.selling_price * dpcon.less_perc
            paid_up_dp = self.env['payment.config'].search([('name', '=', 'paid up DP')])
            self.down_payment = dp * paid_up_dp.less_perc
            self.o_down_payment = dp
            split_dp = self.env['payment.config'].search([('name', '=', '4 mos split dp')])
            split = dp * split_dp.less_perc
            self.dp_split = split / 4
        elif self.purchase_term == 'cash':
            self.down_payment = 0.00
            self.dp_split = 0.00

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('interment.quotation.request') or _('New')

        res = super(IntermentQuotation, self).create(vals)
        return res
    @api.model
    def _get_spotcash(self):
        spotcash = self.env['payment.config'].search([('name', '=', 'spotcash')])
        for s in self:
            s.spot_cash = s.selling_price * spotcash.less_perc
    @api.model
    def _get_splitcash(self):
        deferred3 = self.env['payment.config'].search([('name', '=', '3-months deferred')])
        deferred = self.selling_price * deferred3.less_perc
        self.split_cash = deferred / 3
    @api.model
    def _get_dp(self):
        dpcon = self.env['payment.config'].search([('name', '=', 'downpayment')])
        paid_up_dp = self.env['payment.config'].search([('name', '=', 'paid up DP')])
        dp = self.selling_price * dpcon.less_perc
        self.down_payment = dp * paid_up_dp.less_perc
        self.o_down_payment = dp
    @api.model
    def _get_split_dp(self):
        dpcon = self.env['payment.config'].search([('name', '=', 'downpayment')])
        split_dp = self.env['payment.config'].search([('name', '=', '4 mos split dp')])
        dp = self.selling_price * dpcon.less_perc
        split = dp * split_dp.less_perc
        self.dp_split = split / 4
    @api.model
    @api.onchange('selling_price','payment_term_id','is_60m')
    def _get_bpt(self):
        if self.is_60m == True:
            bpt = self.selling_price
        else:
            dpcon = self.env['payment.config'].search([('name', '=', 'downpayment')])
            bpt = self.selling_price * (1 - dpcon.less_perc)

        self.bal_payment_term = bpt
        # print bpt
    @api.onchange('payment_term_id','selling_price','bal_payment_term','is_60m','purchase_term')
    def _get_bp_wi(self):
        name = self.env['payment.config'].search([('name', 'like', '%60 ')]).name
        self.is_60m = (self.payment_term_id.name == name)
        # if self.purchase_term == 'install':
        if self.is_60m == 'True':
            self.bal_payment_wInterest = self.selling_price * self.payment_term_id.less_perc
            self.monthly_payment = abs(self.bal_payment_wInterest / self.payment_term_id.no_months)
        else:
            self.bal_payment_wInterest = self.bal_payment_term * self.payment_term_id.less_perc
            self.monthly_payment = abs(self.bal_payment_wInterest / self.payment_term_id.no_months)
        # elif self.purchase_term == 'cash':
        #     self.bal_payment_wInterest = 0
        #     self.monthly_payment = abs(self.bal_payment_wInterest)


    active = fields.Boolean(default=True)

    user_evaluate = fields.Many2one(comodel_name="res.users",
                                    string="Evaluated by",
                                    readonly=1,
                                    )
    user_approve = fields.Many2one(comodel_name="res.users",
                                   string="Approved by",
                                   readonly=1,
                                   )
    user_note = fields.Many2one(comodel_name="res.users",
                                string="Noted by",
                                readonly=1,
                                )

    state = fields.Selection([
        ('draft', "Draft"),
        ('eval', "Evaluated"),
        ('apro', "Approved"),
        ('note', 'Noted'),
    ], default='draft')

    @api.multi
    def action_draft(self):
        self.state = 'draft'

    @api.multi
    def action_eval(self):
        self.state = 'eval'
        self.user_evaluate = self.env.user

    @api.multi
    def action_apro(self):
        self.state = 'apro'
        self.user_approve = self.env.user
        # self.product_lot_id.loanee_id = self.customer_id.id
        # self.product_lot_id.loanee_name = self.customer_id.name
        # self.product_lot_id.loanee_payment_term = self.purchase_term
        # self.product_lot_id.loanee_contract_price = self.balance_amount
        # self.product_lot_id.status = 'amo'

    @api.multi
    def action_note(self):
        self.state = 'note'
        self.user_note = self.env.user

    @api.multi
    def unlink(self):
        for quo in self:
            if quo.state != 'draft':
                raise UserError(_("Cannot delete evaluated application"))
            return super(IntermentQuotation, self).unlink()

    @api.multi
    def compute_loan_line(self):
        loan_line = self.env['interment.loan.line']
        loan_line.search([('loan_id','=',self.id)]).unlink()
        loan_line_dp = self.env['interment.loan.line.dp']
        loan_line_dp.search([('loan_id', '=', self.id)]).unlink()

        payment_config = self.env['payment.config']

        for loan in self:
            loan.refresh()
            date_start_str = datetime.strptime(loan.start_payment_date,'%Y-%m-%d')
            counter = 1
            if self.purchase_term == 'cash':
                if self.is_split_cash == True:
                    payment_term_id = payment_config.search([('name','=','3-months deferred')]).id
                    amount_per_time = loan.split_cash
                    for i in range(1, 3 + 1):
                        line_id = loan_line.create({
                            'date_for_payment': date_start_str,
                            'amount_to_pay': round(amount_per_time,2),
                            'customer_id': loan.customer_id.id,
                            'loan_id': loan.id,
                            'payment_term': payment_term_id})
                        counter += 1
                        date_start_str = date_start_str + relativedelta(months=1)
                else:
                    amount_per_time = loan.spot_cash
                    payment_term_id = payment_config.search([('name', '=', 'spotcash')]).id
                    for i in range(1, 1 + 1):
                        line_id = loan_line.create({
                            'date_for_payment': date_start_str,
                            'amount_to_pay': round(amount_per_time,2),
                            'customer_id': loan.customer_id.id,
                            'loan_id': loan.id,
                            'payment_term': payment_term_id})
                        counter += 1
                        date_start_str = date_start_str + relativedelta(months=1)
        return True
    
    split_4 = fields.Boolean(default=False)

    interment_loan_line_dp = fields.One2many(comodel_name="interment.loan.line.dp",
                                             inverse_name="loan_id",
                                             string="Loan Line",
                                             required=False, index=True)

    @api.multi
    def compute_loan_line_dp(self):
        loan_line = self.env['interment.loan.line']
        loan_line.search([('loan_id', '=', self.id)]).unlink()

        for loan in self:
            loan.refresh()
            date_start_str = datetime.strptime(loan.start_payment_date, '%Y-%m-%d')
            date_start_str = date_start_str + relativedelta(months=1)
            counter = 1
            amount_per_time = loan.monthly_payment
            for i in range(1, loan.payment_term_id.no_months + 1):
                line_id = loan_line.create({
                    'date_for_payment': date_start_str,
                    'amount_to_pay': amount_per_time,
                    'customer_id': loan.customer_id.id,
                    'loan_id': loan.id,
                    'payment_term': loan.payment_term_id.id})
                counter += 1
                date_start_str = date_start_str + relativedelta(months=1)

        loan_line_dp = self.env['interment.loan.line.dp']
        loan_line_dp.search([('loan_id', '=', self.id)]).unlink()

        for loan in self:
            loan.refresh()
            date_start_str = datetime.strptime(loan.start_payment_date, '%Y-%m-%d')
            counter = 1
            if loan.split_4 == True:
                
                amount_per_time = loan.dp_split
                for i in range(1, 4 + 1):
                    line_id = loan_line_dp.create({
                        'date_for_payment': date_start_str,
                        'amount_to_pay': round(amount_per_time,2),
                        'customer_id': loan.customer_id.id,
                        'loan_id': loan.id,
                        'payment_term': loan.payment_term_id.id})
                    counter += 1
                    date_start_str = date_start_str + relativedelta(months=1)
                    self._loan_down()
            else:
                amount_per_time = loan.down_payment
                for i in range(1, 1 + 1):
                    line_id = loan_line_dp.create({
                        'date_for_payment': date_start_str,
                        'amount_to_pay': round(amount_per_time,2),
                        'customer_id': loan.customer_id.id,
                        'loan_id': loan.id,
                        'payment_term': loan.payment_term_id.id})
                    counter += 1
                    date_start_str = date_start_str + relativedelta(months=1)
        self._get_amount()
        self._get_amount_dp()
        return True


    @api.multi
    def _loan_down(self):
        loan_line_dp = self.env['interment.loan.line.dp']
        loan_line = self.env['interment.loan.line']
        # dp_amount = 0.00
        # ll_amount = 0.00
        number = 1
        dp_ = loan_line_dp.search([('loan_id','=',self.id)])
        for dp in dp_:
            ip_ = loan_line.search([('loan_id','=',self.id),('date_for_payment','=',dp.date_for_payment)])
        for ip in ip_:
            lldp_ = loan_line_dp.search([('loan_id', '=', self.id), ('date_for_payment', '=', ip.date_for_payment)])
            amount_to_pay = round((ip.amount_to_pay + lldp_.amount_to_pay), 2)
            res = ip.update({'amount_to_pay':amount_to_pay,
                          'notes':'Splitted Downpayment + Monthly Payment'
                          })
            number += 1
            lldp_.unlink()
            return res

    total_amount_dp = fields.Float(string="Total Amount", readonly=True, compute='_get_amount_dp')
    total_paid_amount_dp = fields.Float(string='Total Paid Amount', compute='_get_amount_dp')
    balance_amount_dp = fields.Float(string='Balance Amount', compute='_get_amount_dp')
    
    @api.multi
    def _get_amount_dp(self):
        total_amount_dp = 0.00
        compute_total_amount_dp = 0.00
        for loan in self:
            for line in loan.interment_loan_line_dp:
                if line.is_paid == True:
                    total_amount_dp += line.paid_amount
                compute_total_amount_dp += line.amount_to_pay

            bal_amount_dp = (compute_total_amount_dp) - (total_amount_dp)
            self.total_amount_dp = round(compute_total_amount_dp,2)
            self.balance_amount_dp = round(bal_amount_dp,2)
            self.total_paid_amount_dp = round(total_amount_dp,2)

