odoo.define('service.order', function (require) {
"use strict";

var core = require('web.core');
var form_common = require('web.form_common');
var formats = require('web.formats');
var Model = require('web.Model');

var QWeb = core.qweb;
var _t = core._t;

var ShowPaymentLineWidget = form_common.AbstractField.extend({
    render_value: function() {
        var self = this;
        var info = JSON.parse(this.get('value'));
        if (info !== false) {
            _.each(info.content, function(k,v){
                k.index = v;
                k.amount = formats.format_value(k.amount, {type: "float", digits: k.digits});
                if (k.date) {
                    k.date = formats.format_value(k.date, {type: "date"});
                }
            });
            this.$el.html(QWeb.render('ShowPaymentInfo_', {
                'lines': info.content,
                'outstanding': info.outstanding,
                'title': info.title
            }));
        }
        else {
            this.$el.html('');
        }
    },

});

core.form_widget_registry.add('payment_', ShowPaymentLineWidget)

});