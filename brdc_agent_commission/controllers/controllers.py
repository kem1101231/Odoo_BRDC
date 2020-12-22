# -*- coding: utf-8 -*-
from odoo import http

# class BrdcAgentCommission(http.Controller):
#     @http.route('/brdc_agent_commission/brdc_agent_commission/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/brdc_agent_commission/brdc_agent_commission/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('brdc_agent_commission.listing', {
#             'root': '/brdc_agent_commission/brdc_agent_commission',
#             'objects': http.request.env['brdc_agent_commission.brdc_agent_commission'].search([]),
#         })

#     @http.route('/brdc_agent_commission/brdc_agent_commission/objects/<model("brdc_agent_commission.brdc_agent_commission"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('brdc_agent_commission.object', {
#             'object': obj
#         })