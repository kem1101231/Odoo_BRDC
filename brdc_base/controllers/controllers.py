# -*- coding: utf-8 -*-
from odoo import http

# class BrdcBase(http.Controller):
#     @http.route('/brdc_base/brdc_base/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/brdc_base/brdc_base/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('brdc_base.listing', {
#             'root': '/brdc_base/brdc_base',
#             'objects': http.request.env['brdc_base.brdc_base'].search([]),
#         })

#     @http.route('/brdc_base/brdc_base/objects/<model("brdc_base.brdc_base"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('brdc_base.object', {
#             'object': obj
#         })