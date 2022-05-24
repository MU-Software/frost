import flask
import werkzeug.exceptions

import app.common.utils as utils
from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase


# Request handler
def before_first_request():
    pass


def before_request():
    if flask.current_app.config.get('RESTAPI_VERSION') == 'dev':
        config_dev_key = flask.current_app.config.get('DEVELOPMENT_KEY', None)
        req_dev_key = flask.request.headers.get('X-Development-Key', None)

        if req_dev_key != config_dev_key:
            return AccountResponseCase.user_signed_out.create_response()

    # if flask.current_app.config.get('REFERER_CHECK'):
    #     server_name: str = flask.current_app.config.get('SERVER_NAME')
    #     referer_url: str = flask.request.headers.get('referer', '')
    #     if urllib.parse.urlparse(referer_url).netloc != server_name:
    #         return CommonResponseCase.http_forbidden.create_response()


def after_request(response):
    return response


def teardown_request(exception):
    pass


def teardown_appcontext(exception):
    pass


# Register all request handler
def register_request_handler(app: flask.Flask):
    app.before_first_request(before_first_request)
    app.before_request(before_request)
    app.after_request(after_request)
    app.teardown_request(teardown_request)
    app.teardown_appcontext(teardown_appcontext)

    @app.errorhandler(404)
    def handle_404(exception: werkzeug.exceptions.HTTPException):
        return CommonResponseCase.http_not_found.create_response()

    @app.errorhandler(405)
    def handle_405(exception: werkzeug.exceptions.HTTPException):
        return CommonResponseCase.http_mtd_forbidden.create_response()

    @app.errorhandler(429)
    def handle_429(exception: werkzeug.exceptions.HTTPException):
        return CommonResponseCase.rate_limit.create_response()

    @app.errorhandler(Exception)
    def handle_exception(exception: werkzeug.exceptions.HTTPException):
        # response = exception.get_response()  # TODO: Log this
        if flask.current_app.config.get('RESTAPI_VERSION', None) == 'dev':
            print(utils.get_traceback_msg(exception), flush=True)
        return CommonResponseCase.server_error.create_response()
