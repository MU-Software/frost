import datetime
import flask
import flask.views
import jwt
import jwt.exceptions
import typing

import app.api.helper_class as api_class
import app.database.user as user_module
import app.database as db_module
import app.database.jwt as jwt_module

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase

db = db_module.db
redis_db = db_module.redis_db
RedisKeyType = db_module.RedisKeyType

password_reset_mail_valid_duration: datetime.timedelta = datetime.timedelta(hours=48)


class PasswordChangeRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(auth={api_class.AuthType.RefreshToken: False, })
    @api_class.RequestBody(
        required_fields={
            'new_password': {'type': 'string', },
            'new_password_check': {'type': 'string', }, },
        optional_fields={
            'original_password': {'type': 'string', }, })
    def post(self,
             req_body: dict[str, typing.Any],
             refresh_token:  jwt_module.RefreshToken,
             email_token: typing.Optional[str] = None):
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
            # Change password using Refresh Token Auth. Normal situation.
            if not original_password:
                return CommonResponseCase.body_required_omitted.create_response(
                    data={'lacks': ['original_password']})
            target_user = refresh_token.usertable

        elif email_token:
            # Change password using EmailToken Auth. Maybe user forgot their password?
            try:
                # Validate jwt token while querying on DB
                target_email_token = user_module.EmailToken.query_using_token(email_token)
            except jwt.exceptions.ExpiredSignatureError:
                return AccountResponseCase.email_expired.create_response()
            except Exception:
                return AccountResponseCase.email_invalid.create_response()
            if target_email_token is None:
                return AccountResponseCase.email_not_found.create_response()

            target_user = target_email_token.user

            # Maybe user forgot their password, so want to reset it.
            # This means that user cannot provide original password, and need to force-change password
            is_forced_password_change = True

            # Clear spam-block record
            redis_key = RedisKeyType[target_email_token.action.name].as_redis_key(target_email_token.user_id)
            redis_result = redis_db.get(redis_key)
            if redis_result:
                redis_db.delete(redis_key)

            # Remove this email token
            db.session.delete(target_email_token)
            db.session.commit()
        else:
            return AccountResponseCase.user_not_signed_in.create_response()

        if not target_user:
            return AccountResponseCase.user_not_found.create_response()

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
