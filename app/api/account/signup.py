import datetime
import flask
import flask.views
import jwt
from passlib.hash import argon2
import secrets
import sqlalchemy as sql

import app.api.helper_class as api_class
import app.common.utils as utils
import app.common.mailgun.aws_ses as mailgun_aws
import app.common.mailgun.gmail as mailgun_gmail
import app.database as db_module
import app.database.user as user
import app.database.jwt as jwt_module

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase

db = db_module.db

# SignUp confirmation email will expire after 48 hours
signup_verify_mail_valid_duration: datetime.timedelta = datetime.timedelta(hours=48)


class SignUpRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={
            'User-Agent': {'type': 'string', },
            'X-Csrf-Token': {'type': 'string', },
        },
        optional_fields={'X-Client-Token': {'type': 'string', }, })
    @api_class.RequestBody(
        required_fields={
            'id': {'type': 'string', },
            'pw': {'type': 'string', },
            'nick': {'type': 'string', },
            'email': {'type': 'string', },
        })
    def post(self, req_header, req_body):
        '''
        description: Sign-up with Email
        responses:
            - user_signed_up
            - user_signed_up_but_mail_error
            - user_already_used
            - body_bad_semantics
            - server_error
        '''
        # Normalize all user inputs, including password
        for k, v in req_body.items():
            req_body[k] = utils.normalize(v)

        if not utils.is_email(req_body['email']):
            return CommonResponseCase.body_bad_semantics.create_response(
                data={'bad_semantics': ({'email': 'NOT_A_VALID_EMAIL_ADDRESS'},)})
        if reason := utils.is_useridsafe(req_body['id']):
            return CommonResponseCase.body_bad_semantics.create_response(
                data={'bad_semantics': ({'id': reason},)})
        if reason := utils.is_passwordsafe(req_body['pw']):
            return CommonResponseCase.body_bad_semantics.create_response(
                data={'bad_semantics': ({'pw': reason},)})

        new_user = user.User()
        new_user.email = req_body['email']
        new_user.id = req_body['id']
        new_user.nickname = req_body['nick']
        new_user.password = argon2.hash(req_body['pw'])
        new_user.pw_changed_at = sql.func.now()
        new_user.last_login_date = sql.func.now()
        db.session.add(new_user)

        try:
            db.session.commit()

            email_token_exp = datetime.datetime.utcnow().replace(tzinfo=utils.UTC) + signup_verify_mail_valid_duration
            # Send account verification & confirmation mail
            email_token = jwt.encode({
                'api_ver': flask.current_app.config.get('RESTAPI_VERSION'),
                'iss': flask.current_app.config.get('SERVER_NAME'),
                'exp': email_token_exp,
                'sub': 'Email Auth',
                'jti':  secrets.randbits(64),
                'user': new_user.uuid,
                'data': {'action': user.EmailTokenAction.EMAIL_VERIFICATION.value, },
            }, key=flask.current_app.config.get('SECRET_KEY'), algorithm='HS256')

            new_email_token: user.EmailToken = user.EmailToken()
            new_email_token.user = new_user
            new_email_token.action = user.EmailTokenAction.EMAIL_VERIFICATION
            new_email_token.token = email_token
            new_email_token.expired_at = email_token_exp

            db.session.add(new_email_token)
        except Exception as err:
            try:
                err_diag = db_module.IntegrityCaser(err)
                if err_diag[0] == 'FAILED_UNIQUE':
                    return AccountResponseCase.user_already_used.create_response(data={'duplicate': dict(err_diag[1])})
                else:
                    raise err
            except Exception:
                return CommonResponseCase.server_error.create_response()

        mail_sent: bool = True
        if flask.current_app.config.get('MAIL_ENABLE'):
            try:
                http_or_https = 'https://' if flask.current_app.config.get('HTTPS_ENABLE', True) else 'http://'
                email_result = flask.render_template(
                    'email/email_verify.html',
                    domain_url=http_or_https + flask.current_app.config.get('SERVER_NAME'),
                    api_base_url=(http_or_https + flask.current_app.config.get('SERVER_NAME')
                                  + '/api/' + flask.current_app.config.get('RESTAPI_VERSION')),
                    project_name=flask.current_app.config.get('PROJECT_NAME'),
                    user_nick=new_user.nickname,
                    email_key=email_token,
                    language='kor'
                )

                mail_provider = flask.current_app.config.get('MAIL_PROVIDER', 'AMAZON')
                if mail_provider == 'AMAZON':
                    mailgun_aws.send_mail(
                        fromaddr='do-not-reply@' + flask.current_app.config.get('MAIL_DOMAIN'),
                        toaddr=new_user.email,
                        subject=f'{flask.current_app.config.get("PROJECT_NAME")}에 오신 것을 환영합니다!',
                        message=email_result)
                elif mail_provider == 'GOOGLE':
                    mailgun_gmail.send_mail(
                        google_client_id=flask.current_app.config.get('GOOGLE_CLIENT_ID'),
                        google_client_secret=flask.current_app.config.get('GOOGLE_CLIENT_SECRET'),
                        google_refresh_token=flask.current_app.config.get('GOOGLE_REFRESH_TOKEN'),
                        fromaddr='do-not-reply@' + flask.current_app.config.get('MAIL_DOMAIN'),
                        toaddr=new_user.email,
                        subject=f'{flask.current_app.config.get("PROJECT_NAME")}에 오신 것을 환영합니다!',
                        message=email_result)
                else:
                    raise NotImplementedError(f'Mail provider "{mail_provider}" is not supported')
                mail_sent = True
            except Exception:
                mail_sent = False

        jwt_data_header, jwt_data_body = jwt_module.create_login_data(
                                            new_user,
                                            req_header.get('User-Agent'),
                                            req_header.get('X-Csrf-Token'),
                                            req_header.get('X-Client-Token', None),
                                            flask.request.remote_addr,
                                            flask.current_app.config.get('SECRET_KEY'))

        response_body = {'user': new_user.to_dict()}
        response_body['user'].update(jwt_data_body)

        response_type: api_class.Response = AccountResponseCase.user_signed_up
        if not mail_sent:
            response_type = AccountResponseCase.user_signed_up_but_mail_error

        return response_type.create_response(header=jwt_data_header, data=response_body)
