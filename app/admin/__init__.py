import flask
import flask_admin as fadmin
import flask_admin.contrib.sqla as fadmin_sqla
import jwt

import app.api.helper_class as api_class
import app.database.jwt as jwt_module

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase


def check_admin_authenticate(in_jwt: str, csrf_token: str) -> tuple[bool, api_class.Response]:
    '''
    This returns (True, None) if authenticaion succeed,
    else (False, <One of AccountResponseCase>) if it fails to authenticate.
    '''
    access_token: jwt_module.AccessToken = None
    try:
        access_token = jwt_module.AccessToken.from_token(in_jwt, flask.current_app.config.get('SECRET_KEY')+csrf_token)
    except jwt.exceptions.ExpiredSignatureError:
        # AccessToken Expired error must be raised when bearer auth is softly required,
        # so that client can re-request after refreshing AccessToken
        return (False, AccountResponseCase.access_token_expired.create_response())
    except Exception:
        return (False, AccountResponseCase.access_token_invalid.create_response())
    if not access_token:
        return (False, AccountResponseCase.user_not_signed_in.create_response())

    if 'admin' in access_token.role:
        return (True, None)
    else:
        return (False, CommonResponseCase.http_forbidden.create_response())


def fadmin_is_accessible_mod(self: fadmin.base.BaseView):
    csrf_token = flask.request.headers.get('X-Csrf-Token', '')
    access_token_bearer = flask.request.headers.get('Authorization', '').replace('Bearer ', '')
    return check_admin_authenticate(access_token_bearer, csrf_token)[0]


def fadmin__handle_view(self: fadmin.base.BaseView, name: str, **kwargs):
    is_accessible_result = self.is_accessible()
    if not is_accessible_result[0]:
        kwargs['expected_response'] = is_accessible_result[1]
        return self.inaccessible_callback(name, **kwargs)


def fadmin_inaccessible_callback(self: fadmin.base.BaseView, name: str, **kwargs):
    if 'expected_response' in kwargs:
        return kwargs['expected_response']
    return flask.abort(403)


def init_app(app: flask.Flask, add_model_to_view: bool = True):
    app_name = app.config.get('BACKEND_NAME', 'Backend Core')
    restapi_version = app.config.get('RESTAPI_VERSION')

    # Register flask-admin authenticate
    fadmin.base.BaseView.is_accessible = fadmin_is_accessible_mod
    fadmin.base.BaseView._handle_view = fadmin__handle_view
    fadmin.base.BaseView.inaccessible_callback = fadmin_inaccessible_callback
    admin = fadmin.Admin(
                app,
                name=app_name,
                url=f'/api/{restapi_version}/admin',
                template_mode='bootstrap4')

    if add_model_to_view:
        import app.database as db_module
        import app.database.user as user
        import app.database.jwt as jwt_module

        admin.add_view(fadmin_sqla.ModelView(user.User, db_module.db.session))
        admin.add_view(fadmin_sqla.ModelView(user.EmailToken, db_module.db.session))
        admin.add_view(fadmin_sqla.ModelView(jwt_module.RefreshToken, db_module.db.session))

    import app.admin.token_revoke as token_revoke
    admin.add_view(token_revoke.Admin_TokenRevoke_View(name='Token Revoke', endpoint='token-revoke'))
