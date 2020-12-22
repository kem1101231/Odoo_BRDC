odoo.define('interment.host.schedule', function(require){
'use strict';

var core = require('web.core');
var form_common = require('web.form_common');
var formats = require('web.formats');
var Model = require('web.Model');

var QWeb = core.qweb;
var _t = core._t;

var ShowIntermentSchedule = form_common.AbstractField.extend({
    render_value: function() {
        var self = this;
        var info = JSON.parse(this.get('value'));
        if (info !== false){
            _.each(info.context, function(k,v){
             k.index = v;
            });
            this.$el.html(QWeb.render('ShowIntermentSchedule', {
                'content': info.content,
                'deceased': info.deceased,
                'title': 'Interment',
                'has_schedule': info.has_schedule
            }));
            this.$('.js_pop_information').click(function(){
                var interment_id = parseInt($(this).attr('interment-id'))
                if (interment_id !== undefined && interment_id !== NaN){
                    self.do_action({
                        type: 'ir.actions.act_window',
                        res_model: 'interment.order2',
                        res_id: interment_id,
                        views: [[false, 'form']],
                        target: 'current',
                        flags: {'initial_mode': 'view'},
                    });
                }
            });

            _.each(this.$('.pop_information'), function(k, v){
                var options = {
                    'content': QWeb.render('IntermentPopOver',{
                        'name': 'INTERMENT SCHEDULED BY %s' % info.content[v].informant,
                        'schedule': info.content[v].interment_sched,
                        'mass': info.content[v].mass_sched,
                        'interment_id': info.content[v].id
                    }),
                    'html': true,
                    'placement': 'right',
                    'title': _t(''),
                    'trigger': 'focus',
                    'delay': {"show": 0, "hide": 100},
                };
                $(k).popover(options);
                $(k).on('shown.bs.popover', function(event){
                    $(this).parent().find('.open_information').click(function(){
                        var interment_id = parseInt($(this).attr('interment-id'))
                        if (interment_id !== undefined && interment_id !== NaN){
                            self.do_action({
                                type: 'ir.actions.act_window',
                                res_model: 'interment.order2',
                                res_id: interment_id,
                                views: [[false, 'form']],
                                target: 'new'
                            });
                        }
                    });
                });
            });

        }
        else{
            this.$el.html('');
        }
    }
});

core.form_widget_registry.add('interment_schedule', ShowIntermentSchedule);

});