from app.api.account.response_case import AccountResponseCase
import flask
import flask.views
import jwt
import jwt.exceptions

import app.api.helper_class as api_class
import app.database as db_module
import app.database.user as user

db = db_module.db


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
        '''
        if not email_token:
            return AccountResponseCase.email_token_not_given.create_response()

        try:
            jwt_token = jwt.decode(email_token, key=flask.current_app.config.get('SECRET_KEY'), algorithms='HS256')
        except jwt.exceptions.ExpiredSignatureError:
            # TODO: We need to delete this from DB, or at least, garbage collect this.
            return AccountResponseCase.email_expired.create_response()
        except jwt.exceptions.DecodeError:
            return AccountResponseCase.email_invalid.create_response()

        target_token: user.EmailToken = user.EmailToken.query.filter(user.EmailToken.token == jwt_token).first()
        if not target_token:
            return AccountResponseCase.email_not_found.create_response()
        if target_token.action != jwt_token['data']['action'] or target_token.user_id != jwt_token['user']:
            return AccountResponseCase.email_invalid.create_response()

        # OK, now we can assumes that email is verified,
        # Do what token says.
        if target_token.action == 'EMAIL_VERIFY':
            target_token.user.email_verified = True
            db.session.delete(target_token)
            db.session.commit()
            return AccountResponseCase.email_success.create_response()

        return AccountResponseCase.email_invalid.create_response(
                    message='Email has no action')
