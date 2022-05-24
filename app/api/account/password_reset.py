import datetime
import enum
import flask
import flask.views
import typing

import app.api.helper_class as api_class
import app.database as db_module
import app.database.user as user_module
import app.common.mailgun as mailgun

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase

password_reset_mail_valid_duration: datetime.timedelta = datetime.timedelta(hours=48)

db = db_module.db


class PasswordResetMailSendFailCase(enum.Enum):
    MAIL_SENT_IN_48HOURS = enum.auto()
    MAIL_SEND_FAILURE = enum.auto()


class PasswordResetRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestBody(
        required_fields={'email': {'type': 'string', }, },
        optional_fields={})
    def post(self, req_body: dict[str, typing.Any], ):
        '''
        description: Send email that can force-reset account password.
        responses:
            - password_reset_mail_sent
            - password_reset_mail_send_failed
        '''
        # Find target user
        target_user: user_module.User = None
        try:
            target_user = db.session.query(user_module.User)\
                .filter(user_module.User.email == req_body['email']).first()
        except Exception:
            return CommonResponseCase.db_error.create_response()
        if not target_user:
            # Just send a response that says
            # 'OK, mail will be sent if there's a matching user
            return AccountResponseCase.password_reset_mail_sent.create_response()

        # Create email token. This also checks redis to block spamming.
        try:
            new_email_token = user_module.EmailToken.create(
                target_user,
                user_module.EmailTokenAction.EMAIL_PASSWORD_RESET,
                password_reset_mail_valid_duration)
        except user_module.EmailAlreadySentOnSpecificHoursException:
            return AccountResponseCase.password_reset_mail_send_failed.create_response(
                data={'reason': PasswordResetMailSendFailCase.MAIL_SENT_IN_48HOURS.name, })

        # Send mail
        http_or_https = 'https://' if flask.current_app.config.get('HTTPS_ENABLE', True) else 'http://'
        email_result = flask.render_template(
            'email/password_reset.html',
            domain_url=http_or_https + flask.current_app.config.get('SERVER_NAME'),
            api_base_url=(http_or_https + flask.current_app.config.get('SERVER_NAME')
                          + '/api/' + flask.current_app.config.get('RESTAPI_VERSION')),
            project_name=flask.current_app.config.get('PROJECT_NAME'),
            user_nick=target_user.nickname,
            email_key=new_email_token.token,
            language='kor')

        mail_sent = mailgun.send_mail(
            fromaddr='do-not-reply@' + flask.current_app.config.get('MAIL_DOMAIN'),
            toaddr=target_user.email,
            subject='비밀번호 초기화 안내 메일입니다.',
            message=email_result)
        if not mail_sent:
            return AccountResponseCase.password_reset_mail_send_failed.create_response(
                data={'reason': PasswordResetMailSendFailCase.MAIL_SEND_FAILURE.name, })

        return AccountResponseCase.password_reset_mail_sent.create_response()
