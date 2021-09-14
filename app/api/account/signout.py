import datetime
import flask
import flask.views
import typing

import app.api.helper_class as api_class
import app.database as db_module
import app.database.jwt as jwt_module

from app.api.account.response_case import AccountResponseCase

db = db_module.db
redis_db = db_module.redis_db
RedisKeyType = db_module.RedisKeyType


class SignOutRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(auth={api_class.AuthType.RefreshToken: False, })
    @api_class.RequestBody(required_fields={'signout': {'type': 'string', }, })
    def post(self, req_body: dict, refresh_token: typing.Optional[jwt_module.RefreshToken] = None):
        '''
        description: Sign-Out and expire user token
        responses:
            - user_signed_out
        '''
        if refresh_token:
            revoke_target_jti = refresh_token.jti
            try:
                redis_key = RedisKeyType.TOKEN_REVOKE.as_redis_key(revoke_target_jti)
                redis_db.set(redis_key, 'revoked', datetime.timedelta(weeks=2))
                print(f'Refresh token {revoke_target_jti} registered on REDIS!')
            except Exception:
                print('Raised error while registering token from REDIS')

            try:
                db.session.delete(refresh_token)
                db.session.commit()
                print(f'Refresh token {revoke_target_jti} removed!')
            except Exception:
                db.session.rollback()
                print('Raised error while removing token from DB')
            return AccountResponseCase.user_signed_out.create_response(message='Goodbye!')
        return AccountResponseCase.user_signed_out.create_response(message='User already signed-out')
