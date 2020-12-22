from odoo import api, fields, models
from datetime import datetime, timedelta
import time

class commission_distributed_handler(models.TransientModel):
    _name = 'commission.distributed_handler'
    # _rec_name = 'name'
    _description = 'Commission Distributed handler'

    distributed_date_from = fields.Date(string="From", default=lambda *a: time.strftime('%Y-%m-%d'))
    distributed_date_to = fields.Date(string="To", default=lambda *a: time.strftime('%Y-%m-%d'))
    # aging_date_from = fields.Date(string="As of", default=lambda *a:(datetime.now() + timedelta(days=(6))).strftime('%Y-%m-%d'))

    agent_id = fields.Many2many('res.partner', string="Agent", domain="[('is_agent', '=', True)]")


    @api.multi
    def print_distributed_commission_report(self):
        self.ensure_one()
        data = {}
        data['ids'] = self.env.context.get('active_ids', [])
        data['model'] = self.env.context.get('active_model', 'ir.ui.menu')
        data['form'] = self.read(['distributed_date_from', 'distributed_date_to','agent_id'])[0]
        # print data
        # aging_date_from =generate_general_aging data['form']['aging_date_from']
        # period_length = data['form']['period_length']
        # print aging_date_from, period_length
        # list_of_distributed_commission = self.env['.aging'].search([])
        agent_id = data['form']['agent_id']
        ddf = data['form']['distributed_date_from']
        ddt = data['form']['distributed_date_to']
        print agent_id
        self.env['commission.distributed_transient'].search([]).unlink()
        for x in agent_id:
            if self.env['res.partner'].search([('id', '=', x)]).agency_id.name == "Sales Agent":
                print "uno"
                recs = self.env['sa.commission.line'].search([('is_distributed', '=', True), ('is_paid', '=', True)
                                                              ,('date_distributed','<=',ddt),('date_distributed','>=',ddf)])
                for i in recs:
                    self.env['commission.distributed_transient'].create({
                        'agent_commission_id': i.agent_commission_id.id,
                        'so_id': i.so_id,
                        'distribute_commission_line_id': i.distribute_commission_line_id.id,
                        'invoice_id': i.invoice_id.id,
                        'name': i.name,
                        'agent_percentage': i.sa_percentage,
                        'agent_id': x,
                    })
                # print recs
            elif self.env['res.partner'].search([('id', '=', x)]).agency_id.name == "Unit Manager":
                print "dos"
                recs = self.env['um.commission.line'].search([('is_distributed', '=', True), ('is_paid', '=', True)
                                                              ,('date_distributed','<=',ddt),('date_distributed','>=',ddf)])
                for i in recs:
                    self.env['commission.distributed_transient'].create({
                        'agent_commission_id': i.agent_commission_id.id,
                        'so_id': i.so_id,
                        'distribute_commission_line_id': i.distribute_commission_line_id.id,
                        'invoice_id': i.invoice_id.id,
                        'name': i.name,
                        'agent_percentage': i.um_percentage,
                        'agent_id': x,
                    })
                # print recs
            elif self.env['res.partner'].search([('id', '=', x)]).agency_id.name == "Agency Manager":
                print "tres"
                recs = self.env['am.commission.line'].search([('is_distributed', '=', True), ('is_paid', '=', True)
                                                              ,('date_distributed','<=',ddt),('date_distributed','>',ddf)])
                for i in recs:
                    self.env['commission.distributed_transient'].create({
                        'agent_commission_id': i.agent_commission_id.id,
                        'so_id': i.so_id,
                        'distribute_commission_line_id': i.distribute_commission_line_id.id,
                        'invoice_id': i.invoice_id.id,
                        'name': i.name,
                        'agent_percentage': i.am_percentage,
                        'agent_id': x,
                    })
                    # print recs
            else:
                pass
            x += 1

        # pl = data['form']['period_length']
        # for c in range(0, len(generate_general_aging)):
        #     generate_general_aging[c].get_days_passed(dt,pl)
        # if self.env['res.partner'].search([('id','=',agent_id[0])]).agency_id.name == "Sales Agent":
        #     print "uno"
        #     data = self.env['sa.commission.line'].search([('is_distributed','=',True),('is_paid','=',True)])
        #     print data
        # elif self.env['res.partner'].search([('id','=',agent_id[0])]).agency_id.name == "Unit Manager":
        #     print "dos"
        #     data = self.env['um.commission.line'].search([('is_distributed','=',True),('is_paid','=',True)])
        #     print data
        # elif self.env['res.partner'].search([('id','=',agent_id[0])]).agency_id.name == "Agency Manager":
        #     print "tres"
        #     data = self.env['am.commission.line'].search([('is_distributed', '=', True), ('is_paid', '=', True)])
        #     print data
        # else:
        #     pass


        return self._print_report(data)

        # @api.multi
    # def print_general_aging_report(self):
    #     # self.ensure_one()
    #     data = {}
    #     data['ids'] = self.env.context.get('active_ids', [])
    #     data['model'] = self.env.context.get('active_model', 'ir.ui.menu')
    #     data['form'] = self.read(['aging_date_from','period_length'])[0]
    #     print data
    #     return self._print_report(data)
    #

    def _print_report(self, data):
        # print 'test handler'
        # data['form'].update(self.read(['aging_date_from', 'period_length'])[0])
        # data = {}
        # data['form'] = self.read(['course_id', 'batch_id'])[0]
        return self.env['report'].get_action(self, 'brdc_agent_commission.commission_distributed_view', data=data)
