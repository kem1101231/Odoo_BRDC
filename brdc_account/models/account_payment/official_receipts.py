from odoo import api, fields, models,_
from odoo.exceptions import UserError, ValidationError
import num2words
from dateutil.relativedelta import relativedelta
from datetime import datetime
import math
from re import sub
from decimal import Decimal
import locale

MAP_INVOICE_TYPE_PARTNER_TYPE = {
    'out_invoice': 'customer',
    'out_refund': 'customer',
    'in_invoice': 'supplier',
    'in_refund': 'supplier',
}

MAP_INVOICE_TYPE_PAYMENT_SIGN = {
    'out_invoice': 1,
    'in_refund': 1,
    'in_invoice': -1,
    'out_refund': -1,
}

class ORSeriesConfiguration(models.Model):
    _name = 'or.series.config'

    name = fields.Char(compute='name_')
    reference_id = fields.Char(string='Reference ID', required=True, readonly=True, copy=False, default=lambda self: _('New'))
    type = fields.Selection([('or', 'Official'), ('tp', 'Temporary')], string='Receipt Type')
    series_from = fields.Integer(string='Series From')
    series_to = fields.Integer(string='Series To')
    responsible = fields.Many2one('res.users', string='Assigned Personnel',required=True)
    or_series_line = fields.One2many(comodel_name="or.series.line", inverse_name="or_series_id", string="OR Series Line", required=True, index=True)
    state = fields.Selection([('draft', 'Draft'), ('valid', 'Validated'), ('confirm', 'Confirmed')], string='State', default='draft')

    @api.multi
    def action_draft(self):
        or_line = self.env['or.series.line']
        or_line.search([('or_series_id', '=', self.id)]).unlink()
        self.state = 'draft'
        self.refresh()


    @api.multi
    def action_valid(self):
        number = 1
        for series in self:
            from_series = series.series_from
            for i in range(from_series, series.series_from + 1):
                if series.type == 'or':
                    start_series = 'ORNo. ' + '%%0%sd' % 7 % from_series
                else:
                    start_series = 'TRNo. ' + '%%0%sd' % 7 % from_series
                search_start_line = series.env['or.series.line'].search([('name', '=', start_series)])
                if search_start_line:
                    raise UserError(_('Series is already existing'))
                else:
                    series.state = 'valid'
                number += 1
                from_series = from_series + 1


            return True

    @api.model
    def name_(self):
        for series in self:
            series_from = '%%0%sd' % 7 % series.series_from
            series_to = '%%0%sd' % 7 % series.series_to
            if series.type == 'or':
                series.name = 'OR/%s/%s - %s' % (datetime.now().year, series_from, series_to)
            else:
                series.name = 'TR/%s/%s - %s' % (datetime.now().year, series_from, series_to)

    @api.multi
    def action_confirm(self):
        self.state = 'confirm'

    @api.multi
    def create_or_line(self):
        or_line = self.env['or.series.line']
        or_line.search([('or_series_id','=',self.id)]).unlink()
        for series in self:
            series.refresh()
            from_series = series.series_from
            number = 1
            if series.type == 'or':
                for i in range(from_series, series.series_to + 1):
                    line_id = or_line.create({
                        'name': 'ORNo. ' + '%%0%sd' % 7 % from_series,
                        'or_series_id': series.id,
                        'responsible': series.responsible.id,
                        'state': 'unused'
                    })
                    number += 1
                    from_series = from_series + 1
            else:
                for i in range(from_series, series.series_to + 1):
                    line_id = or_line.create({
                        'name': 'TRNo. ' + '%%0%sd' % 7 % from_series,
                        'or_series_id': series.id,
                        'responsible': series.responsible.id,
                        'state': 'unused'
                    })
                    number += 1
                    from_series = from_series + 1
        return True

    @api.multi
    def unlink(self):
        #print("--------------------")
        #print("sdsdsdsdsdsd")
        for series in self:
            or_line = series.env['or.series.line']
            or_line.search([('or_series_id', '=', series.id)]).unlink()
        return super(ORSeriesConfiguration, self).unlink()

    @api.model
    def create(self,vals):
        if vals.get('reference_id',_('New')) == _('New'):
            vals['reference_id'] = self.env['ir.sequence'].next_by_code('or.series.config') or _('New')

        return super(ORSeriesConfiguration, self).create(vals)

    @api.multi
    def unlink_unused(self):
        for s in self:
            series_line = self.env['or.series.line'].search([('or_series_id', '=', s.id), ('state', '=', 'unused')])
            series_line.unlink()


class ORSeriesLine(models.Model):
    _name = 'or.series.line'
    _order = 'state, name, id'

    name = fields.Char(string='OR Series', required=True, readonly= True)
    or_series_id = fields.Many2one(comodel_name="or.series.config", string="", required=False,readonly= True )
    responsible = fields.Many2one('res.users', string='Assigned Personnel', related="or_series_id.responsible", required=True)
    state = fields.Selection([('used','USED'),('unused','UNUSED'),('reject','REJECTED')],readonly= True)

    # @api.model
    # def func_write(self,or_number):
    #     for i in self:
    #         if i.name == or_number:
    #             i.write({'state': 'used'})
    #

    @api.multi
    def or_series_write(self):
        for rec in self:
            or_number_line = self.env['or.series.line']
            or_number = or_number_line.search([('name', '=', rec.name)])
            if or_number:
                rec.write({'state': 'used'})

    @api.multi
    def action_reject(self):
        self.state = 'reject'
    @api.multi
    def action_reset(self):
        self.state = 'unused'
