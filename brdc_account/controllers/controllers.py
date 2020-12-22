# -*- coding: utf-8 -*-
from odoo import http

class BrdcAccount(http.Controller):
    @http.route('/brdc_account/brdc_account/', auth='public')
    def index(self, **kw):
        return '<div style="background:green">Hello world</div>'

#     @http.route('/brdc_account/brdc_account/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('brdc_account.listing', {
#             'root': '/brdc_account/brdc_account',
#             'objects': http.request.env['brdc_account.brdc_account'].search([]),
#         })

#     @http.route('/brdc_account/brdc_account/objects/<model("brdc_account.brdc_account"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('brdc_account.object', {
#             'object': obj
#         })