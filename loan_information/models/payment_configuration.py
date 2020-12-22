from odoo import api, fields, models

class PaymentConfig(models.Model):
    _name = 'payment.config'
    _order = 'sequence'

    display_name = fields.Char(compute='_get_display_name')
    name = fields.Char()

    less_perc = fields.Float(string='Percentage')

    bpt = fields.Boolean(string='Is Term',default=False)
    bpt_wod = fields.Boolean(string='Term w/o downpayment',default=False)
    category = fields.Selection([('product','Product'),('service','Service')],'Category')
    is_parent = fields.Boolean(default=0)
    parent_id = fields.Many2one('payment.config', 'Parent',domain="[('is_parent','=',1)]")
    payment_type = fields.Selection([('install','For Installment'),('cash','For Cash')],'Type', default='install')
    no_months = fields.Integer()
    sequence = fields.Integer()
    journal_id = fields.Many2one('account.journal', 'Default Journal')
    account_id = fields.Many2one('account.account', 'Invoice Account', related='journal_id.default_debit_account_id')

    #==================
    # Default Journals use for a transaction that uses the payment configuration\
    # This will be only set on parent type configs

    full_cash = fields.Many2one(comodel_name="account.journal", string="Spot Cash")
    split_cash = fields.Many2one(comodel_name="account.journal", string="Deffered Cash")
    split_downpayment = fields.Many2one(comodel_name="account.journal", string="Split Downpayment")
    downpayment = fields.Many2one(comodel_name="account.journal", string="Paid Up Downpayment")
    amortization = fields.Many2one(comodel_name="account.journal", string="Monthly Amortization")

    #====================
    # Default pricelist for a specific payment configuration
    # Can only be set on parent type configs

    def_pricelist = fields.Many2one(comodel_name="product.pricelist", string="Default Pricelist")

    #=====================

    def term_default(self):
        print("_____________________________ *********************")
        print("sdsdsdsdsdsd")
        return 'short'

    @api.depends('no_months')
    def get_category_value(self):
        for payment in self:
            months = payment.no_months

            category_value = ''
            if months <= 48:
                category_value = 'short'
            else:
                category_value = 'long'

            payment.term_cat = category_value
            payment.update({'term_cat':category_value,})


    term_cat = fields.Selection(selection=[('short','Short Term'),('long','Long Term')], string="Term Category", compute="get_category_value")# default=_term_default


    @api.model
    @api.onchange('no_months')
    def get_year(self):
        for s in self:
            s.years = 1.0 * s.no_months / 12
            print(s.years)

    years = fields.Float(string='number of Year/s', compute=get_year)

    @api.model
    @api.onchange('name','parent_id')
    def _get_display_name(self):
        for config in self:
            parent = ('%s')% (config.parent_id.name if not config.is_parent else "")
            name = config.name if config.name else ""
            config.display_name = ('%s %s') % (parent, name)

    @api.model
    def create(self, vals):

        res = super(PaymentConfig, self).create(vals)
        vals['sequence'] = res.id

        return res

