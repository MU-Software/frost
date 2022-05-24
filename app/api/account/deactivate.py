import datetime
import flask
import flask.views

import app.api.helper_class as api_class
import app.common.utils as utils
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.user as user_module

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase

db = db_module.db
redis_db = db_module.redis_db
RedisKeyType = db_module.RedisKeyType


class AccountDeactivationRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(auth={api_class.AuthType.RefreshToken: True, })
    @api_class.RequestBody(
        required_fields={
            'email': {'type': 'string', },
            'password': {'type': 'string', },
        },)
    def post(self, req_body: dict, refresh_token: jwt_module.RefreshToken):
        '''
        description: Self-deactivate account route
        responses:
            - user_deactivate_success
            - user_not_signed_in
            - user_info_mismatch
            - user_locked
            - user_deactivated
            - user_wrong_password
            - refresh_token_expired
            - refresh_token_invalid
            - server_error
        '''
        target_user: user_module.User = refresh_token.usertable
        if target_user.email != req_body['email']:
            return AccountResponseCase.user_info_mismatch.create_response(
                data={'fields': ['email']})
        if not target_user.check_password(req_body['password']):
            return AccountResponseCase.user_wrong_password.create_response()

        if target_user.locked_at:
            why_locked: str = target_user.why_locked.replace('ACCOUNT_LOCKED::', '')
            return AccountResponseCase.user_locked.create_response(data={'reason': why_locked})
        elif target_user.deactivated_at:
            why_deactivated: str = target_user.why_deactivated.replace('ACCOUNT_DEACTIVATED::', '')
            return AccountResponseCase.user_deactivated.create_response(data={'reason': why_deactivated})

        # Revoke all user tokens
        target_tokens = db.session.query(jwt_module.RefreshToken)\
            .filter(jwt_module.RefreshToken.user == target_user.uuid)\
            .all()
        if not target_tokens:
            # No refresh token of target user don't make any sense,
            # how could user get here although user don't have any valid refresh token?
            return CommonResponseCase.server_error.create_response()
        for token in target_tokens:
            # TODO: set can set multiple at once, so use that method instead
            redis_key = RedisKeyType.TOKEN_REVOKE.as_redis_key(token.jti)
            redis_db.set(redis_key, 'revoked', datetime.timedelta(weeks=2))
            db.session.delete(token)

        target_user.deactivated_at = datetime.datetime.utcnow().replace(tzinfo=utils.UTC)
        target_user.why_deactivated = 'ACCOUNT_LOCKED::USER_SELF_LOCKED'
        target_user.deactivated_by_orm = target_user
        db.session.commit()

        return AccountResponseCase.user_deactivate_success.create_response()
