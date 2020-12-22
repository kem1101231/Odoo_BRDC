odoo.define('collection.efficiency.report', function (require){
"use strict";

var core = require('web.core');
var form_common = require('web.form_common');
var formats = require('web.formats');
var Model = require('web.Model');

var QWeb = core.qweb;
var _t = core._t;


var ShowCollectionGraphWidget = form_common.AbstractField.extend({
    render_value: function() {
        var self = this;
        var info = JSON.parse(this.get('value'));
        if (info !== false) {
            _.each(info.content, function(k,v){
                k.index = v;
                k.past_due = formats.format_value(k.past_due, {type: "float", digits: k.digits});
                k.current_due = formats.format_value(k.current_due, {type: "float", digits: k.digits});
                k.collection_past = formats.format_value(k.collection_past, {type: "float", digits: k.digits});
                k.collection_current = formats.format_value(k.collection_current, {type: "float", digits: k.digits});
                k.percentage_past = formats.format_value(k.percentage_past, {type: "float", digits: k.digits});
                k.percentage_current = formats.format_value(k.percentage_current, {type: "float", digits: k.digits});
                if (k.date) {
                    k.date = formats.format_value(k.date, {type: "date"});
                }
            });
            this.$el.html(QWeb.render('ShowCollectionInfo', {
            'content': info.content,
            'title': info.title,
            }));
        }
        else{
            this.$el.html('');
        }
    },
});
core.form_widget_registry.add('collection_widget', ShowCollectionGraphWidget)
});