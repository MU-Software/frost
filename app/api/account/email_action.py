import flask
import flask.views
import jwt
import jwt.exceptions

import app.api.helper_class as api_class
import app.database as db_module
import app.database.user as user

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase

db = db_module.db
redis_db = db_module.redis_db
RedisKeyType = db_module.RedisKeyType


class EmailActionRoute(flask.views.MethodView, api_class.MethodViewMixin):
    def get(self, email_token: str):
        '''
        description: Do Email action, such as email address verification or finding password, etc.
        responses:
            - email_success
            - email_token_not_given
            - email_expired
            - email_invalid
            - email_not_found
            - email_success_html
            - email_token_not_given_html
            - email_expired_html
            - email_invalid_html
            - email_not_found_html
        '''
        request_content_type: str = flask.request.accept_mimetypes

        if not email_token:
            if 'text/html' in request_content_type:
                return AccountResponseCase.email_token_not_given_html.create_response()
            return AccountResponseCase.email_token_not_given.create_response()

        try:
            target_token = user.EmailToken.query_using_token(email_token)
        except jwt.exceptions.ExpiredSignatureError:
            # TODO: We need to delete this from DB, or at least, garbage collect this.
            if 'text/html' in request_content_type:
                return AccountResponseCase.email_expired_html.create_response()
            return AccountResponseCase.email_expired.create_response()
        except Exception:
            if 'text/html' in request_content_type:
                return AccountResponseCase.email_invalid_html.create_response()
            return AccountResponseCase.email_invalid.create_response()

        if not target_token:
            if 'text/html' in request_content_type:
                return AccountResponseCase.email_not_found_html.create_response()
            return AccountResponseCase.email_not_found.create_response()

        # OK, now we can assumes that email is verified,
        # Do what token says.
        # But first, clear spam-block record
        redis_key = RedisKeyType[target_token.action.name].as_redis_key(target_token.user_id)
        redis_result = redis_db.get(redis_key)
        if redis_result:
            redis_db.delete(redis_key)

        if target_token.action == user.EmailTokenAction.EMAIL_VERIFICATION:
            target_token.user.email_verified = True
            db.session.delete(target_token)
            try:
                db.session.commit()
                if 'text/html' in request_content_type:
                    return AccountResponseCase.email_success_html.create_response()
                return AccountResponseCase.email_success.create_response()
            except Exception:
                db.session.rollback()
                return CommonResponseCase.db_error.create_response()
        elif target_token.action == user.EmailTokenAction.EMAIL_PASSWORD_RESET:
            if 'text/html' in request_content_type:
                return AccountResponseCase.email_success_html.create_response(
                    template_path='email_action/password_reset.html')
            return CommonResponseCase.http_unsupported_content_type.create_response()

        if 'text/html' in request_content_type:
            return AccountResponseCase.email_invalid_html.create_response()
        return AccountResponseCase.email_invalid.create_response()
