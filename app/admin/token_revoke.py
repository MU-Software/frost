import datetime
import flask
import flask_admin as fadmin

import app.api.helper_class as api_class
import app.database as db_module
import app.database.user as user
import app.database.jwt as jwt_module

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase

db = db_module.db
redis_db = db_module.redis_db
RedisKeyType = db_module.RedisKeyType


class Admin_TokenRevoke_View(fadmin.BaseView):
    @fadmin.expose('/', methods=('GET', ))
    def index(self):
        user_result = db.session.query(user.User).all()
        token_result = db.session.query(jwt_module.RefreshToken).all()
        revoked_dict = dict()
        redis_key = RedisKeyType.TOKEN_REVOKE.as_redis_key('*')
        for k in redis_db.scan_iter(match=redis_key):
            revoked_dict[k.decode()] = redis_db.get(k.decode()).decode()

        return self.render(
                    'admin/token_revoke.html',
                    user_result=user_result,
                    token_result=token_result,
                    revoked_result=revoked_dict)

    @fadmin.expose('/', methods=('POST', ))
    @api_class.RequestBody(
        optional_fields={
            'user_uuid': {'type': 'integer', },
            'target_jti': {'type': 'integer', },
            'do_delete': {'type': 'boolean', }, })
    def post(self, req_body: dict):
        restapi_version = flask.current_app.config.get('RESTAPI_VERSION')

        if not any((('user_uuid' in req_body), ('target_jti' in req_body))):
            CommonResponseCase.body_required_omitted.create_response(
                message='Need user_uuid or target_jti',
                data={'lacks': ['user_uuid', 'target_jti']})

        if 'user_uuid' in req_body:
            # How this goddamn query works?!
            query_result = db.session.query(jwt_module.RefreshToken)\
                                .join(jwt_module.RefreshToken.usertable, aliased=True)\
                                .filter_by(uuid=int(req_body['user_uuid'])).all()
            if not query_result:
                return AccountResponseCase.user_not_found.create_response(
                    message='User or JWT that mapped to that user not found')

            for target in query_result:
                # TODO: set can set multiple at once, so use that method instead
                redis_key = RedisKeyType.TOKEN_REVOKE.as_redis_key(target.jti)
                redis_db.set(redis_key, 'revoked', datetime.timedelta(weeks=2))

                if 'do_delete' in req_body:
                    db.session.delete(target)
        else:
            query_result = db.session.query(jwt_module.RefreshToken)\
                                .filter(jwt_module.RefreshToken.jti == int(req_body['target_jti']))\
                                .first()
            if not query_result:
                return AccountResponseCase.refresh_token_invalid(
                    message='RefreshToken that has such JTI not found')

            redis_key = RedisKeyType.TOKEN_REVOKE.as_redis_key(req_body["target_jti"])
            redis_db.set(redis_key, 'revoked', datetime.timedelta(weeks=2))

            if 'do_delete' in req_body:
                db.session.delete(query_result)

        if 'do_delete' in req_body:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                return CommonResponseCase.db_error.create_response()

        return CommonResponseCase.http_ok.create_response(
            code=301,
            header=(('Location', f'/api/{restapi_version}/admin/token-revoke'), ))
