import json
import flask
import flask.views

import app.api.helper_class as api_class
import app.api.common.file_manage as route_filemgr
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.user as user_module

from app.api.response_case import CommonResponseCase, ResourceResponseCase
from app.api.account.response_case import AccountResponseCase

db = db_module.db


class ProfileImageRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(auth={api_class.AuthType.Bearer: True, })
    def post(self, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Profile image set route
        responses:
            - http_forbidden
            - resource_modified
            - user_not_found
            - body_empty
            - resource_forbidden
            - body_bad_semantics
            - server_error
        '''
        file_upload_enabled: bool = flask.current_app.config.get('FILE_MANAGEMENT_ROUTE_ENABLE', False)
        if not file_upload_enabled:
            return CommonResponseCase.http_forbidden.create_response(
                message='File upload is not enabled',
                data={'reason': 'File upload is not enabled'}, )

        target_user = db.session.query(user_module.User)\
            .filter(user_module.User.locked_at.is_(None))\
            .filter(user_module.User.deactivated_at.is_(None))\
            .filter(user_module.User.uuid == access_token.user)\
            .first()
        if not target_user:
            return AccountResponseCase.user_not_found.create_response()

        # We'll handle upload first to make sure whether upload process success.
        # We can't revert this when error raised if we delete files first.
        # This calls internal REST API
        up_result: api_class.ResponseType = route_filemgr.FileManagementRoute().post()
        up_res_body, up_res_code, up_res_header = up_result
        if up_res_code != 201:  # Upload failed
            return up_result
        up_res_body = json.loads(up_res_body.data)  # I hate this

        if target_user.profile_image:
            target_file: str = target_user.profile_image.replace('/uploads/', '').replace('/', '').strip()
            # This calls internal REST API
            del_result: api_class.ResponseType = route_filemgr.FileManagementRoute().delete(filename=target_file)
            del_res_body, del_res_code, del_res_header = del_result
            if del_res_code != 204:  # Deletion didn't done completely.
                return CommonResponseCase.server_error.create_response()

        target_user.profile_image = up_res_body['data']['file']['url']
        db.session.commit()
        return ResourceResponseCase.resource_modified.create_response()

    @api_class.RequestHeader(auth={api_class.AuthType.Bearer: True, })
    def delete(self, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Profile image \"unset\" route
        responses:
            - http_forbidden
            - resource_deleted
            - user_not_found
            - resource_not_found
            - server_error
        '''
        file_upload_enabled: bool = flask.current_app.config.get('FILE_MANAGEMENT_ROUTE_ENABLE', False)
        if not file_upload_enabled:
            return CommonResponseCase.http_forbidden.create_response(
                message='File upload is not enabled',
                data={'reason': 'File upload is not enabled'}, )

        target_user = db.session.query(user_module.User)\
            .filter(user_module.User.locked_at.is_(None))\
            .filter(user_module.User.deactivated_at.is_(None))\
            .filter(user_module.User.uuid == access_token.user)\
            .first()
        if not target_user:
            return AccountResponseCase.user_not_found.create_response()
        if not target_user.profile_image:
            return ResourceResponseCase.resource_not_found.create_response()

        target_file: str = target_user.profile_image.replace('/uploads/', '').replace('/', '').strip()
        # Internal REST API call
        del_result: api_class.ResponseType = route_filemgr.FileManagementRoute().delete(filename=target_file)
        del_res_body, del_res_code, del_res_header = del_result
        if del_res_code != 204:
            # Deletion didn't done completely.
            return CommonResponseCase.server_error.create_response()

        target_user.profile_image = None
        db.session.commit()
        return ResourceResponseCase.resource_deleted.create_response()
