from odoo import api, fields, models
import json
from datetime import datetime, timedelta
import time
import os
import pytz
os.environ['TZ'] = 'Asia/Manila'
time.timezone = 'Asia/Manila'


class IntermentNotification(models.TransientModel):
    _name = 'interment.notification'

    def action_send_notification(self):
        channel_id = self.env['ir.model.data'].xmlid_to_object('brdc_account.channel_interment_host')
        for partners in channel_id.channel_partner_ids:
            print partners.name
        # channel_id.message_post(
        #     subject='Interment Notification',
        #     body='Sample Message',
        #     subtype='mail.mt_comment'
        # )


class IntermentHostSchedule(models.TransientModel):
    _name = 'interment.host.schedule'

    host_id = fields.Many2one('res.users', default=lambda self: self.env.user)
    dashboard1 = fields.Text(compute="_get_interment_JSON")
    dashboard2 = fields.Text(compute="_get_tomorrow_JSON")

    @api.model
    @api.depends('host_id')
    def _get_interment_JSON(self):
        self.dashboard1 = json.dumps(False)
        os.environ['TZ'] = 'Asia/Manila'
        time.timezone = 'Asia/Manila'

        interment = self.env['interment.order2']
        deceased = self.env['deceased.list']
        info = {'has_schedule': False, 'content': [], 'deceased': []}
        tz = pytz.timezone('Asia/Manila')
        today = '%s' % datetime.strftime(datetime.now(tz), '%Y-%m-%d')
        later = '%s' % (datetime.strftime(datetime.now(tz) + timedelta(days=1), '%Y-%m-%d'))
        # today = '%s' % (datetime.strptime(today, '%Y-%m-%d %H:%M:%S') + timedelta(hours=8))
        # later = '%s' % (datetime.strptime(later, '%Y-%m-%d %H:%M:%S') + timedelta(hours=8))
        print today, 'today', later
        personal_schedule = interment.search([('host_id', '=', self.host_id.id)]).filtered(
            lambda res: (res.interment_td >= today) and (res.interment_td <= later)
        )
        print personal_schedule
        if personal_schedule:
            info['deceased'] = []
            info['has_schedule'] = True
            for rec in personal_schedule:
                interment_td = datetime.strptime(rec.interment_td, '%Y-%m-%d %H:%M:%S') + timedelta(hours=8)
                mass_td = datetime.strptime(rec.mass_td, '%Y-%m-%d %H:%M:%S') + timedelta(hours=8)
                info['content'].append({
                    'id': rec.id,
                    'informant': rec.informant_id.name,
                    'interment_sched': datetime.strftime(interment_td, '%Y-%m-%d %I:%M%p'),
                    'mass_sched': datetime.strftime(mass_td, '%Y-%m-%d %I:%M%p'),
                    'area': rec.product_id.name,
                    'block': rec.lot_id.block_number,
                    'lot': rec.lot_id.lot_number,
                    'state': rec.state,
                })

        self.dashboard1 = json.dumps(info)

    @api.model
    @api.depends('host_id')
    def _get_tomorrow_JSON(self):
        self.dashboard2 = json.dumps(False)
        os.environ['TZ'] = 'Asia/Manila'
        time.timezone = 'Asia/Manila'

        interment = self.env['interment.order2']
        deceased = self.env['deceased.list']
        info = {'has_schedule': False, 'content': [], 'deceased': []}
        tz = pytz.timezone('Asia/Manila')
        later = '%s' % (datetime.strftime(datetime.now(tz) + timedelta(days=1), '%Y-%m-%d'))
        print later
        personal_schedule = interment.search([('host_id', '=', self.host_id.id)]).filtered(
            lambda res: res.interment_td >= later
        )
        print personal_schedule
        if personal_schedule:
            info['deceased'] = []
            info['has_schedule'] = True
            for rec in personal_schedule:
                interment_td = datetime.strptime(rec.interment_td, '%Y-%m-%d %H:%M:%S') + timedelta(hours=8)
                mass_td = datetime.strptime(rec.mass_td, '%Y-%m-%d %H:%M:%S') + timedelta(hours=8)
                info['content'].append({
                    'id': rec.id,
                    'informant': rec.informant_id.name,
                    'interment_sched': datetime.strftime(interment_td, '%Y-%m-%d %I:%M%p'),
                    'mass_sched': datetime.strftime(mass_td, '%Y-%m-%d %I:%M%p'),
                    'area': rec.product_id.name,
                    'block': rec.lot_id.block_number,
                    'lot': rec.lot_id.lot_number,
                    'state': rec.state,
                })

        self.dashboard2 = json.dumps(info)

    def action_send_notification(self):
        channel_id = self.env['ir.model.data'].xmlid_to_object('brdc_account.channel_interment_host')
        interment = self.env['interment.order2']
        info = {'content': []}
        for partners in channel_id.channel_partner_ids:
            user = self.env['res.users'].search([('partner_id', '=', partners.id)])
            later = '%s' % (datetime.strptime(fields.Date.today(), '%Y-%m-%d') + timedelta(days=1))
            personal_schedule = interment.search([('host_id', '=', user.id)]).filtered(
                lambda res: res.interment_td >= later
            )
            if personal_schedule:

                channel_id.message_post(
                    subject='Interment Notification',
                    body='<a href="http://localhost:8069/web#model=res.partner&id=%s">@%s</a> You have (%s) interments to attend. please check <a href="http://localhost:8069/web#view_type=form&model=interment.host.schedule&menu_id=680&action=824" target="_blank">HERE</a>' % (partners.id, partners.name, len(personal_schedule)),
                    subtype='mail.mt_comment',
                    message_type='comment',
                    author_id=self.env.ref('base.user_root').id,
                    partner_ids=[(4, partners.id)]
                    # email_from='"%s"<%s>' % (self.env.ref('base.user_root').partner_id.name,
                    #                          self.env.ref('base.user_root').partner_id.email)
                )
            print partners.name

        # self.env['mail.message'].create({
        #     'email_from': self.env.user.partner_id.email,
        #     'author_id': self.env.user.partner_id.id,
        #     'model': 'mail.channel',
        #     'type': 'comment',
        #     'subtype_id': self.env.ref('mail.mt_comment').id,
        #     'body': 'sample message',
        #     # 'channel_ids': [(4, self.env.ref('brdc_account.channel_interment_host'))].id,
        #     'res_id': self.env.ref('brdc_account.channel_interment_host').id,
        # })
