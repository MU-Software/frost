import flask
import flask.views
import typing

import app.api.helper_class as api_class
import app.database as db_module
import app.database.user as user_module

from app.api.account.response_case import AccountResponseCase

db = db_module.db


class AccountDuplicateCheckRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestBody(
        optional_fields={
            'email': {'type': 'string'},
            'id': {'type': 'string'},
            'nickname': {'type': 'string'}, })
    def post(self, req_body: dict[str, typing.Any]):
        '''
        description: Check if Email/ID/Nickname is in use
        responses:
            - user_already_used
            - user_safe_to_use
            - server_error
        '''
        field_column_map = {
            'email': user_module.User.email,
            'id': user_module.User.id,
            'nickname': user_module.User.nickname,
        }
        check_result = list()

        for field_name, field_value in req_body.items():
            if db.session.query(user_module.User).filter(field_column_map[field_name] == field_value).first():
                check_result.append(field_name)

        if check_result:
            return AccountResponseCase.user_already_used.create_response(data={
                'duplicate': check_result
            })
        return AccountResponseCase.user_safe_to_use.create_response()
