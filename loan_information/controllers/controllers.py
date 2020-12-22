# -*- coding: utf-8 -*-
from odoo import http

# class LoanInformation(http.Controller):
#     @http.route('/loan_information/loan_information/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/loan_information/loan_information/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('loan_information.listing', {
#             'root': '/loan_information/loan_information',
#             'objects': http.request.env['loan_information.loan_information'].search([]),
#         })

#     @http.route('/loan_information/loan_information/objects/<model("loan_information.loan_information"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('loan_information.object', {
#             'object': obj
#         })