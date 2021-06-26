import flask
import flask.views
import jwt
import jwt.exceptions
import typing

import app.api.helper_class as api_class
import app.database.user as user_module
import app.database.jwt as jwt_module

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase


class PasswordChangeRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestQuery(
        required_fields={},
        optional_fields={'email_token': {'type': 'string', }, })
    @api_class.RequestHeader(
        required_fields={},
        optional_fields={},
        auth={api_class.AuthType.RefreshToken: False, })
    @api_class.RequestBody(
        required_fields={
            'new_password': {'type': 'string', },
            'new_password_check': {'type': 'string', }, },
        optional_fields={
            'original_password': {'type': 'string', }, })
    def post(self,
             req_query: dict[str, typing.Any],
             req_header: dict[str, typing.Any],
             req_body: dict[str, typing.Any],
             refresh_token:  jwt_module.RefreshToken):
        '''
        description: Change account password. Either email token or refresh token must be given.
        responses:
            - email_expired
            - email_invalid
            - email_not_found
            - email_token_not_given
            - password_changed
            - user_wrong_password
            - password_change_failed
        '''
        try:
            secret_key: str = flask.current_app.config.get('SECRET_KEY')

            # Find target user
            target_user: user_module.User = None
            original_password: typing.Optional[str] = req_body.get('original_password', None)
            new_password = req_body['new_password']
            new_password_check = req_body['new_password_check']
            is_forced_password_change = False

            if new_password != new_password_check:
                return AccountResponseCase.password_change_failed.create_response(
                    message='Re-typed new password is not match with previously typed new password.',
                    data={'reason': 'RETYPE_MISMATCH'})

            if refresh_token:
                if not original_password:
                    return CommonResponseCase.body_required_omitted.create_response(
                        data={'lacks': ['original_password']})
                target_user = refresh_token.usertable

            elif 'email_token' in req_query:
                email_jwt_token: str = req_query['email_token']
                try:
                    # Validate jwt token before querying on DB
                    jwt.decode(email_jwt_token, key=secret_key, algorithms='HS256')
                except jwt.exceptions.ExpiredSignatureError:
                    return AccountResponseCase.email_expired.create_response()
                except Exception:
                    return AccountResponseCase.email_invalid.create_response()

                target_email_token: user_module.EmailToken = user_module.EmailToken.query\
                    .filter(user_module.EmailToken.token == email_jwt_token).first()
                if target_email_token is None:
                    return AccountResponseCase.email_not_found.create_response()
                target_user = target_email_token.user

                # User forgot their password, so want to reset it.
                # This means that user cannot provide original password, and need to force-change password
                is_forced_password_change = True

            if not target_user:
                AccountResponseCase.email_token_not_given.create_response()

            pw_change_success, fail_reason = target_user.change_password(
                orig_pw=original_password, new_pw=new_password,
                force_change=is_forced_password_change)
            if pw_change_success:
                return AccountResponseCase.password_changed.create_response()
            else:
                if fail_reason == 'WRONG_PASSWORD':
                    return AccountResponseCase.user_wrong_password.create_response()
                return AccountResponseCase.password_change_failed.create_response(
                    data={'reason': fail_reason})
        except Exception:
            return CommonResponseCase.server_error.create_response()
