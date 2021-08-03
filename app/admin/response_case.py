import app.api.helper_class as api_class


class AdminResponseCase(api_class.ResponseCaseCollector):
    # Admin Token related
    admin_token_invalid = api_class.Response(
        description='Admin token cookie is invalid.',
        code=401, success=False,
        public_sub_code='admin_token.invalid')
    admin_token_expired = api_class.Response(
        description='Admin token cookie is expired. Please refresh it.',
        code=401, success=False,
        public_sub_code='admin_token.expired')
    admin_forbidden = api_class.Response(
        description='We assumes that you are not a admin, so this action could not be executed.',
        code=401, success=False,
        public_sub_code='admin.forbidden')

    # Admin Token related (HTML)
    admin_token_invalid_html = api_class.Response(
        description='Admin token cookie is invalid.',
        code=401, success=False,
        content_type='text/html', template_path='admin/error/admin_token_invalid.html')
    admin_token_expired_html = api_class.Response(
        description='Admin token cookie is expired. Please refresh it.',
        code=401, success=False,
        content_type='text/html', template_path='admin/error/admin_token_expired.html')
    admin_forbidden_html = api_class.Response(
        description='We assumes that you are not a admin, so this action could not be executed.',
        code=401, success=False,
        content_type='text/html', template_path='admin/error/admin_forbidden.html')
