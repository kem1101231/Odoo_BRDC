# -*- coding: utf-8 -*-
from odoo import http

# class BrdcAcf(http.Controller):
#     @http.route('/brdc_acf/brdc_acf/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/brdc_acf/brdc_acf/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('brdc_acf.listing', {
#             'root': '/brdc_acf/brdc_acf',
#             'objects': http.request.env['brdc_acf.brdc_acf'].search([]),
#         })

#     @http.route('/brdc_acf/brdc_acf/objects/<model("brdc_acf.brdc_acf"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('brdc_acf.object', {
#             'object': obj
#         })