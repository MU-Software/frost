import base64
import datetime
import flask
import flask.views
import imghdr
import json
import magic
import pathlib as pt
import PIL.Image
import secrets
import typing
import werkzeug.utils

import app.common.utils as utils
import app.api.helper_class as api_class
import app.database as db_module
import app.database.uploaded_file as filedb_module
import app.database.jwt as jwt_module

from app.api.response_case import CommonResponseCase, ResourceResponseCase

db = db_module.db
current_utctime = lambda: datetime.datetime.now().replace(tzinfo=datetime.timezone.utc)  # noqa
current_utctimestamp = lambda: int(current_utctime().timestamp())  # noqa

USER_CONTENT_UPLOAD_DIR = pt.Path.cwd() / 'user_content' / 'uploads'
WEB_IMAGE_EXT: dict[str, str] = {
    # suffix : imghdr_result
    'png': 'png', 'apng': 'png',
    'jpg': 'jpeg', 'jpeg': 'jpeg', 'jfif': 'jpeg', 'pjpeg': 'jpeg', 'pjp': 'jpeg',
    'gif': 'gif', 'webp': 'webp',
}
RESPONSABLE_MIME_TYPE = [
    'image/*',
    'audio/*',
    'video/*',
    'model/stl',
    'model/obj',
    'model/mtl',
    'model/gltf-binary',
    'model/gltf+json',
]


class FileManagementRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @staticmethod
    def is_web_friendly_image(file: typing.Union[str, pt.Path]) -> typing.Optional[bool]:
        file = pt.Path(file) if isinstance(file, str) else file

        # Check if the file exists and the file extension is web-friendly.
        # If not, then we don't need to test this file.
        if not file.exists() or file.suffix.lower() not in WEB_IMAGE_EXT:
            return None

        # Check if the file magic is web-friendly
        imghdr_result = imghdr.what(file)
        if imghdr_result.lower() not in WEB_IMAGE_EXT.values():
            return False

        try:
            # Check if the file is valid
            PIL.Image.open(file).verify()
            return True
        except Exception:
            return False

    @staticmethod
    def is_allowed_file(filename: str) -> bool:
        allowed_extensions: list[str] = flask.current_app.config.get('FILE_UPLOAD_ALLOW_EXTENSION', [])
        try:
            if '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions:
                return True
        except Exception:
            pass
        return False

    @api_class.RequestHeader(auth={api_class.AuthType.Bearer: False, })
    def get(self,
            filename: typing.Optional[str] = None,
            req_header: typing.Optional[dict] = None,
            access_token: typing.Optional[jwt_module.AccessToken] = None):
        '''
        description: Returns target file.
            This returns binary file if request requested Content-Type as `not application/json`
        responses:
            - resource_found
            - http_forbidden
            - resource_not_found
            - resource_forbidden
            - server_error
        '''
        file_upload_enabled: bool = flask.current_app.config.get('FILE_MANAGEMENT_ROUTE_ENABLE', False)
        if not file_upload_enabled:
            return CommonResponseCase.http_forbidden.create_response(
                message='File upload is not enabled',
                data={'reason': 'File upload is not enabled'}, )

        if not filename:
            return CommonResponseCase.http_forbidden.create_response()

        file_db_result = db.session.query(filedb_module.UploadedFile)\
            .filter(filedb_module.UploadedFile.deleted_at.is_(None))\
            .filter(filedb_module.UploadedFile.locked_at.is_(None))\
            .filter(filedb_module.UploadedFile.filename == werkzeug.utils.secure_filename(filename))\
            .first()
        if not file_db_result:
            return ResourceResponseCase.resource_not_found.create_response()
        if (file_db_result.private
            and (not access_token
                 or not (access_token.is_admin() or file_db_result.uploaded_by_id == access_token.user))):
            return ResourceResponseCase.resource_forbidden.create_response()

        filepath = USER_CONTENT_UPLOAD_DIR / str(file_db_result.uploaded_by_id) / file_db_result.filename
        if not filepath.exists():
            file_db_result.deleted_at = utils.as_utctime(datetime.datetime.now())
            db.session.commit()
            return ResourceResponseCase.resource_not_found.create_response()

        request_content_type = flask.request.accept_mimetypes
        request_content_type_list = [ct[0] for ct in list(request_content_type)[:-1]]
        if not request_content_type_list or 'application/json' in request_content_type_list:
            response_body = file_db_result.to_dict()
            response_body.update({
                'size': filepath.stat().st_size,
                'data': base64.urlsafe_b64encode(filepath.read_bytes()).decode(),
            })
            return ResourceResponseCase.resource_found.create_response(data={'file': response_body, }, )
        else:
            return flask.send_file(
                        filepath,
                        mimetype=file_db_result.mimetype)

    @api_class.RequestHeader(auth={api_class.AuthType.Bearer: True, })
    @api_class.RequestBody(
        optional_fields={
            'private': {'type': 'boolean', },
            'alt_data': {'type': 'string', }, }, )
    def post(self,
             req_header: dict,
             req_body: dict,
             access_token: jwt_module.AccessToken,
             filename: typing.Optional[str] = None):
        '''
        description: Upload new file.
        responses:
            - resource_created
            - http_forbidden
            - body_empty
            - resource_forbidden
            - body_bad_semantics
        '''
        file_upload_enabled: bool = flask.current_app.config.get('FILE_MANAGEMENT_ROUTE_ENABLE', False)
        if not file_upload_enabled:
            return CommonResponseCase.http_forbidden.create_response(
                message='File upload is not enabled',
                data={'reason': 'File upload is not enabled'}, )

        if filename:
            return CommonResponseCase.http_forbidden.create_response()

        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        file = flask.request.files.get('file', None)
        if not file or file.filename == '':
            return CommonResponseCase.body_empty.create_response(
                message='File is not included on the request', )

        filename = utils.normalize(file.filename).encode('ascii', 'backslashreplace').decode()
        filename = werkzeug.utils.secure_filename(filename)
        fileext = filename.split('.')[-1].lower()
        if not FileManagementRoute.is_allowed_file(filename):
            return ResourceResponseCase.resource_forbidden.create_response()

        is_new_filename_duplicate: bool = True
        while is_new_filename_duplicate:
            # Check for files with names of the same random string.
            # The reason why we query DB is that it is difficult to inspect in the file system
            # because of the extension.
            filename = secrets.token_urlsafe(24)
            is_new_filename_duplicate = db.session.query(filedb_module.UploadedFile)\
                .filter(filedb_module.UploadedFile.filename.startswith(filename))\
                .first()
        filename += f'.{fileext}'

        filepath = USER_CONTENT_UPLOAD_DIR / str(access_token.user) / filename
        if not filepath.parent.exists():
            filepath.parent.mkdir(parents=True)

        file.save(filepath)

        check_web_friendly_img = flask.current_app.config.get('FILE_UPLOAD_IMAGE_WEB_FRIENDLY_CHECK', False)
        detected_file_magic = magic.from_file(filepath, mime=True)
        # Examine mimetype and check web-friendly if needed
        file_err_reason: str = ''
        if file.mimetype != detected_file_magic:
            file_err_reason = ('The MIME type we guessed from the file you sent '
                               'does not match the MIME type you reported.')
        elif detected_file_magic.startswith('image/') and check_web_friendly_img:
            web_img_check_result = FileManagementRoute.is_web_friendly_image(filepath)
            if web_img_check_result is not None and not web_img_check_result:
                # Image is not web-friendly or broken.
                file_err_reason = 'Image you uploaded is broken, or Image is not web-friendly.'
        if file_err_reason:
            filepath.unlink(missing_ok=True)
            return CommonResponseCase.body_bad_semantics.create_response(
                data={'bad_semantics': [{'field': 'file', 'reason': file_err_reason, }, ], }, )

        alt_data: typing.Optional[str] = None
        if 'alt_data' in req_body:
            try:
                alt_data = json.loads(req_body['alt_data'])
            except Exception:
                alt_data = {'alt_text': req_body['alt_data']}

            alt_data = json.dumps(
                            alt_data,
                            skipkeys=True,
                            separators=(',', ':'),
                            indent=None)

        new_file_db = filedb_module.UploadedFile()
        new_file_db.uploaded_by_id = access_token.user
        new_file_db.mimetype = detected_file_magic
        new_file_db.size = filepath.stat().st_size
        new_file_db.filename = filename
        new_file_db.original_filename = file.filename

        new_file_db.alternative_data = alt_data
        new_file_db.private = req_body.get('private', False)

        db.session.add(new_file_db)
        db.session.commit()

        # Return created file data
        return ResourceResponseCase.resource_created.create_response(
            data={'file': new_file_db.to_dict(), }, )

    @api_class.RequestHeader(auth={api_class.AuthType.Bearer: True, })
    def delete(self, req_header: dict, access_token: jwt_module.AccessToken, filename: typing.Optional[str] = None):
        '''
        description: Delete file.
        responses:
            - resource_deleted
            - resource_not_found
            - resource_forbidden
            - http_not_found
        '''
        file_upload_enabled: bool = flask.current_app.config.get('FILE_MANAGEMENT_ROUTE_ENABLE', False)
        if not file_upload_enabled:
            return CommonResponseCase.http_forbidden.create_response(
                message='File upload is not enabled',
                data={'reason': 'File upload is not enabled'}, )

        if not filename:
            return CommonResponseCase.http_not_found.create_response()

        file_db_result = db.session.query(filedb_module.UploadedFile)\
            .filter(filedb_module.UploadedFile.deleted_at.is_(None))\
            .filter(filedb_module.UploadedFile.locked_at.is_(None))\
            .filter(filedb_module.UploadedFile.filename == werkzeug.utils.secure_filename(filename))\
            .first()
        if not file_db_result:
            return ResourceResponseCase.resource_not_found.create_response()
        if not access_token.is_admin() and file_db_result.uploaded_by_id != access_token.user:
            return ResourceResponseCase.resource_forbidden.create_response()

        file_db_result.deleted_at = utils.as_utctime(datetime.datetime.now())
        file_db_result.deleted_by_id = access_token.user
        db.session.commit()

        filepath = USER_CONTENT_UPLOAD_DIR / str(file_db_result.uploaded_by_id) / file_db_result.filename
        filepath.unlink(missing_ok=True)
        return ResourceResponseCase.resource_deleted.create_response()


resource_route = {
    '/uploads/<string:filename>': {
        'view_func': FileManagementRoute,
        'base_path': '/uploads',
        'defaults': {'filename': None},
    },
}
