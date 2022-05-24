import flask
import flask_admin as fadmin
import jwt

import app.api.helper_class as api_class
import app.database.jwt as jwt_module
import app.admin.project_modelview as project_modelview

from app.admin.response_case import AdminResponseCase


def fadmin_is_accessible_mod(self: fadmin.base.BaseView) -> tuple[bool, api_class.Response]:
    '''
    This returns (True, None) if authenticaion succeed,
    else (False, <One of AccountResponseCase>) if it fails to authenticate.
    '''
    secret_key = flask.current_app.config.get('SECRET_KEY')
    request_content_type: str = flask.request.accept_mimetypes
    admin_token: jwt_module.AdminToken = None
    try:
        admin_token_cookie = flask.request.cookies.get('admin_token', type=str, default='')
        if not admin_token_cookie:
            if 'text/html' in request_content_type:
                return (False, AdminResponseCase.admin_forbidden_html.create_response())
            return (False, AdminResponseCase.admin_forbidden.create_response())
        admin_token = jwt_module.AdminToken.from_token(admin_token_cookie, secret_key)

    except jwt.exceptions.ExpiredSignatureError:
        if 'text/html' in request_content_type:
            return (False, AdminResponseCase.admin_token_expired_html.create_response())
        return (False, AdminResponseCase.admin_token_expired.create_response())
    except Exception:
        if 'text/html' in request_content_type:
            return (False, AdminResponseCase.admin_token_invalid_html.create_response())
        return (False, AdminResponseCase.admin_token_invalid.create_response())
    if not admin_token:
        if 'text/html' in request_content_type:
            return (False, AdminResponseCase.admin_forbidden_html.create_response())
        return (False, AdminResponseCase.admin_forbidden.create_response())

    return (True, None)


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
        for target_modelview in project_modelview.target_flask_admin_modelview:
            admin.add_view(target_modelview)

    import app.admin.token_revoke as token_revoke
    admin.add_view(token_revoke.Admin_TokenRevoke_View(name='Token Revoke', endpoint='token-revoke'))
    import app.admin.mail_test as mail_test
    admin.add_view(mail_test.Admin_MailTest_View(name='Mail test', endpoint='mail-test'))

    # init_app must return app
    return app
