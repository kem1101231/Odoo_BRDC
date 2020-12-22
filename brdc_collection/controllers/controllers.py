# -*- coding: utf-8 -*-
from odoo import http

# class BrdcCollection(http.Controller):
#     @http.route('/brdc_collection/brdc_collection/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/brdc_collection/brdc_collection/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('brdc_collection.listing', {
#             'root': '/brdc_collection/brdc_collection',
#             'objects': http.request.env['brdc_collection.brdc_collection'].search([]),
#         })

#     @http.route('/brdc_collection/brdc_collection/objects/<model("brdc_collection.brdc_collection"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('brdc_collection.object', {
#             'object': obj
#         })