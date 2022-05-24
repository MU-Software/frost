import flask
import flask.views

import app.api.helper_class as api_class
import app.database as db_module
import app.database.user as user
import app.database.jwt as jwt_module

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase

db = db_module.db


class SignInRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={
            'User-Agent': {'type': 'string', },
            'X-Csrf-Token': {'type': 'string', },
        },
        optional_fields={'X-Client-Token': {'type': 'string', }, })
    @api_class.RequestBody(
        required_fields={
            'id': {'type': 'string', },
            'pw': {'type': 'string', },
        })
    def post(self, req_header: dict, req_body: dict):
        '''
        description: Sign-in by email or id
        responses:
            - user_signed_in
            - user_not_found
            - user_wrong_password
            - user_locked
            - user_deactivated
        '''
        account_result, reason = user.User.try_login(req_body['id'], req_body['pw'])

        if account_result is False:
            if reason == 'ACCOUNT_NOT_FOUND':
                return AccountResponseCase.user_not_found.create_response()
            elif reason.startswith('WRONG_PASSWORD'):
                return AccountResponseCase.user_wrong_password.create_response(
                    data={'left_chance': int(reason.replace('WRONG_PASSWORD::', ''))}
                )
            elif 'TOO_MUCH_LOGIN_FAIL' in reason:
                return AccountResponseCase.user_locked.create_response(
                            data={'reason': 'TOO_MUCH_LOGIN_FAIL'})
            elif reason.startswith('ACCOUNT_LOCKED'):
                return AccountResponseCase.user_locked.create_response(
                            data={'reason': reason.replace('ACCOUNT_LOCKED::', '')})
            elif reason.startswith('ACCOUNT_DEACTIVATED'):
                return AccountResponseCase.user_deactivated.create_response(
                            data={'reason': reason.replace('ACCOUNT_DEACTIVATED::', '')})
            elif reason == 'EMAIL_NOT_VERIFIED':
                return AccountResponseCase.user_email_not_verified.create_response()
            elif reason == 'DB_ERROR':
                return CommonResponseCase.db_error.create_response()
            return CommonResponseCase.server_error.create_response()

        jwt_data_header, jwt_data_body = jwt_module.create_login_data(
                                            account_result,
                                            req_header.get('User-Agent'),
                                            req_header.get('X-Csrf-Token'),
                                            req_header.get('X-Client-Token', None),
                                            flask.request.remote_addr,
                                            flask.current_app.config.get('SECRET_KEY'))

        response_body = {'user': account_result.to_dict()}
        response_body['user'].update(jwt_data_body)

        return AccountResponseCase.user_signed_in.create_response(
                    header=jwt_data_header, data=response_body)
