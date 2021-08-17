import os
import app.api.helper_class as api_class
import app.common.utils as utils

server_name = os.environ.get('SERVER_NAME')
restapi_version = os.environ.get('RESTAPI_VERSION')
https_enable = os.environ.get('HTTPS_ENABLE', True)
cookie_samesite = ('None' if https_enable else 'Lax') if restapi_version == 'dev' else 'strict'

admin_token_remover_cookie = utils.delete_cookie(
                                    name='admin_token',
                                    path=f'/api/{restapi_version}/admin',
                                    domain=server_name if restapi_version != 'dev' else None,
                                    samesite=cookie_samesite,
                                    secure=https_enable)
delete_admin_token: tuple[str, str] = ('Set-Cookie', admin_token_remover_cookie)


class AdminResponseCase(api_class.ResponseCaseCollector):
    # Admin Token related
    admin_token_invalid = api_class.Response(
        description='Admin token cookie is invalid.',
        code=401, success=False,
        public_sub_code='admin_token.invalid',
        header=[delete_admin_token, ])
    admin_token_expired = api_class.Response(
        description='Admin token cookie is expired. Please refresh it.',
        code=401, success=False,
        public_sub_code='admin_token.expired',
        header=[delete_admin_token, ])
    admin_forbidden = api_class.Response(
        description='We assumes that you are not a admin, so this action could not be executed.',
        code=403, success=False,
        public_sub_code='admin.forbidden')

    # Admin Token related (HTML)
    admin_token_invalid_html = api_class.Response(
        description='Admin token cookie is invalid.',
        code=401, success=False,
        content_type='text/html', template_path='admin/error/admin_token_invalid.html',
        header=[delete_admin_token, ])
    admin_token_expired_html = api_class.Response(
        description='Admin token cookie is expired. Please refresh it.',
        code=401, success=False,
        content_type='text/html', template_path='admin/error/admin_token_expired.html',
        header=[delete_admin_token, ])
    admin_forbidden_html = api_class.Response(
        description='We assumes that you are not a admin, so this action could not be executed.',
        code=403, success=False,
        content_type='text/html', template_path='admin/error/admin_forbidden.html')
