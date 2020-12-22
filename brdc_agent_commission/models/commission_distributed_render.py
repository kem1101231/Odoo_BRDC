from odoo.exceptions import ValidationError

from odoo import api, fields, models

class commission_distributed_render(models.AbstractModel):
    _name = 'report.brdc_agent_commission.commission_distributed_view'
    # _rec_name = 'name'
    _description = 'Commission distributed Render'

    @api.multi
    def render_html(self, docids, data):
        print "pumasok ako"

        self.model = self.env.context.get('active_model')
        docs = self.env[self.model].browse(self.env.context.get('active_ids', []))

        # print data
        # fp = data['form']['filter_per']
        # ps = data['form']['prod_sel'][0]
        # print fp, ps
        #
        # if fp == 'prod' and ps:
        #     recs = self.env['general.aging'].search([('prod_id','=',ps)])
        # else:
        # if data['form']['filter_per'] == 'prod':
        #     ps = data['form']['prod_sel'][0]
        #     recs = self.env['general.aging'].search([('prod_id','like',ps), ('balance','!=',0), ('total_due_payment','!=',0)])
        # elif data['form']['filter_per'] == 'gen':
        #     recs = self.env['general.aging'].search([('balance','!=',0), ('total_due_payment','!=',0)])
        # elif data['form']['filter_per'] == 'area':
        #     # print data['form']['area_list']
        #     # for c in range(0,len(data['form']['area_list'])):
        #     recs = self.env['general.aging'].search([('balance', '!=', 0), ('total_due_payment', '!=', 0),
        #                                              ('invoice_id.partner_id.barangay_id.id', 'in', data['form']['area_list'])])

        agent_id = data['form']['agent_id']
        print agent_id
        # for x in agent_id:
        #     if self.env['res.partner'].search([('id', '=', x)]).agency_id.name == "Sales Agent":
        #         print "uno"
        #         recs = self.env['sa.commission.line'].search([('is_distributed', '=', True), ('is_paid', '=', True)])
        #         print recs
        #     if self.env['res.partner'].search([('id', '=', x)]).agency_id.name == "Unit Manager":
        #         print "dos"
        #         recs = self.env['um.commission.line'].search([('is_distributed', '=', True), ('is_paid', '=', True)])
        #         print recs
        #     if self.env['res.partner'].search([('id', '=', x)]).agency_id.name == "Agency Manager":
        #         print "tres"
        #         recs = self.env['am.commission.line'].search([('is_distributed', '=', True), ('is_paid', '=', True)])
        #         print recs
        #     else:
        #         pass
        #     x += 1

        recs = self.env['commission.distributed_transient'].search([])
        # fp = data['form']['filter_per']
        # print fp
        if len(recs) >= 0:
            recs
        else:
            raise ValidationError("No Record Found!")


        docargs = {
            'doc_ids': self.ids,
            'doc_model': self.model,
            'docs': docs,
            'recs': recs,
            # 'notiftypecount': notiftypecount,

        }

        return self.env['report'].render('brdc_agent_commission.commission_distributed_view', docargs)