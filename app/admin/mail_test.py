import flask
import flask_admin as fadmin

import app.common.mailgun as mailgun
import app.api.helper_class as api_class
import app.database as db_module

from app.api.response_case import CommonResponseCase, ResourceResponseCase

db = db_module.db
redis_db = db_module.redis_db
RedisKeyType = db_module.RedisKeyType


class Admin_MailTest_View(fadmin.BaseView):
    @fadmin.expose('/', methods=('POST', ))
    @api_class.RequestBody(
        required_fields={
            'from_address': {'type': 'string', },
            'to_address': {'type': 'string', },
            'title': {'type': 'string', },
            'body': {'type': 'string', }, })
    def post(self, req_body: dict):
        MAIL_ENABLE = flask.current_app.config.get('MAIL_ENABLE')
        if not MAIL_ENABLE:
            return ResourceResponseCase.resource_forbidden.create_response(
                message='Mail service disabled', data={'resource_name': ['mail', ]})

        did_sent = mailgun.send_mail(
            fromaddr=req_body['from_address'],
            toaddr=req_body['to_address'],
            subject=req_body['title'],
            message=req_body['body'],
            raise_on_fail=True)

        if did_sent:
            return ResourceResponseCase.resource_created.create_response()
        else:
            return CommonResponseCase.server_error.create_response()
