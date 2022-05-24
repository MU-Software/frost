import flask
import flask.views
import typing

import app.api.helper_class as api_class
import app.database as db_module
import app.database.jwt as jwt_module

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase

db = db_module.db


class AccountInformationChangeRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(auth={api_class.AuthType.RefreshToken: True, })
    @api_class.RequestBody(
        optional_fields={
            # profile_image must be handled separately.
            'id': {'type': 'string', },
            'nickname': {'type': 'string', },
            'private': {'type': 'boolean', },
            'description': {'type': 'string', }, })
    def post(self, req_body: dict[str, typing.Any], refresh_token: jwt_module.RefreshToken):
        '''
        description: Change account information.
        responses:
            - body_empty
            - user_not_found
            - body_bad_semantics
            - user_safe_to_use
        '''
        target_user = refresh_token.usertable
        if not target_user:
            # How could this happened?
            return AccountResponseCase.user_not_found.create_response()

        # Filter-out body just in case.
        req_body = {k: v for k, v in req_body.items()
                    if k in ('id', 'nickname', 'private', 'description')
                    and bool(v if not isinstance(v, (bool, int)) else True)}
        if not req_body:
            return CommonResponseCase.body_empty.create_response()

        did_succeed: bool = True
        failed_reason: list[typing.TypedDict('FailedReasonType', {'field': str, 'reason': str, })] = list()
        for field, value in req_body.items():
            if field == 'id':
                result = target_user.change_id('', str(value), True, False)

                if did_succeed:
                    # Only update if did_succeed is true,
                    # so that true to false can happen,
                    # and opposite(false to true) cannot happen.
                    did_succeed = result[0]
                if not result[0]:
                    failed_reason.append({'field': field, 'reason': result[1], })

                continue
            elif field == 'private':
                if not isinstance(value, bool):
                    failed_reason.append({'field': field, 'reason': 'TYPE_MISMATCH', })
                    continue

            setattr(target_user, field, value)

        if not did_succeed:
            return CommonResponseCase.body_bad_semantics.create_response(data=failed_reason)

        # Check UNIQUE constraints
        try:
            db.session.commit()
        except Exception as err:
            db.session.rollback()
            err_reason, err_column_name = db_module.IntegrityCaser(err)
            if err_reason == 'FAILED_UNIQUE':
                return AccountResponseCase.user_already_used.create_response(
                    data={'duplicate': [err_column_name, ]})
            else:
                raise err

        return AccountResponseCase.user_safe_to_use.create_response(
            data={'user': target_user.to_dict(), }, )
